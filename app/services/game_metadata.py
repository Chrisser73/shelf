"""Preview-only enrichment for existing video-game catalogue entries.

The service deliberately never touches cover fields.  It first asks the
configured AI for an exact-edition identity, then uses that identity to query
IGDB.  Callers receive a proposal and remain responsible for the explicit
write step after the user has reviewed it.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.services import igdb
from app.services.search_text import fold
from app.services.title_match import titles_match_exactly

logger = logging.getLogger(__name__)

EDITABLE_FIELDS = (
    "title", "alternate_title", "authors", "publisher", "platform",
    "region", "language", "publish_year", "location_id",
)

# Storage names behind the labels used in the admin settings UI.
MISSING_FIELD_LABELS = {
    "title": "Name", "authors": "Developer", "publisher": "Publisher",
    "platform": "Platform", "region": "Region", "language": "Language",
    "publish_year": "Year",
}
DEFAULT_MISSING_FIELDS = tuple(MISSING_FIELD_LABELS)

# A missing platform should describe the original physical release, not a
# later eShop/Virtual-Console port that happened to rank first in IGDB. These
# are the launch years for Shelf's built-in platform slugs; unknown/custom
# platforms remain eligible rather than being guessed away.
PLATFORM_LAUNCH_YEARS = {
    "nes": 1983, "snes": 1990, "n64": 1996, "gamecube": 2001,
    "wii": 2006, "wiiu": 2012, "switch": 2017, "switch2": 2025,
    "gameboy": 1989, "gba": 2001, "nds": 2004, "3ds": 2011,
    "genesis": 1988, "saturn": 1994, "dreamcast": 1998,
    "ps1": 1994, "ps2": 2000, "ps3": 2006, "ps4": 2013, "ps5": 2020,
    "xbox": 2001, "xbox360": 2005, "xboxone": 2013, "xboxsx": 2020,
}
def missing_sql(prefix: str = "", fields=None) -> str:
    """SQL predicate for games with at least one maintenance field missing."""
    fields = tuple(field for field in (fields if fields is not None else DEFAULT_MISSING_FIELDS)
                   if field in MISSING_FIELD_LABELS)
    if not fields:
        return "0 = 1"
    clauses = [f"{prefix}{field} IS NULL" if field == "publish_year"
               else f"({prefix}{field} IS NULL OR TRIM({prefix}{field}) = '')"
               for field in fields]
    return f"{prefix}media_type = 'video_game' AND (" + " OR ".join(clauses) + ")"


def configured_missing_fields(db) -> tuple[str, ...]:
    from app.database import get_setting
    raw = get_setting(db, "missing_game_metadata_fields")
    if raw is None or raw == "":
        return DEFAULT_MISSING_FIELDS
    if raw == "none":
        return ()
    # V1.2.3 originally bound the user-facing "Name" checkbox to the
    # optional alternate title.  Preserve administrators' saved choice, but
    # interpret it as the actual catalogue title from now on.
    return tuple(
        "title" if field == "alternate_title" else field
        for field in raw.split(",")
        if field in MISSING_FIELD_LABELS or field == "alternate_title"
    )


def missing_metadata_count(db) -> int:
    return db.execute(f"SELECT COUNT(*) AS c FROM items_live WHERE {missing_sql(fields=configured_missing_fields(db))}").fetchone()["c"]


def cost_hint(settings: dict[str, Any], item_count: int) -> str:
    """Honest, bounded cost preview without guessing a provider's live price."""
    provider = settings.get("vision_provider") or ""
    if provider == "ollama":
        return f"{item_count} local AI request{'s' if item_count != 1 else ''} (no API charge)"
    if provider == "anthropic":
        # Metadata identity is text-only: approximately one compact prompt
        # plus a small JSON response per selected game. Reuse the configured
        # Anthropic model's published per-token rate used by Photo Intake.
        from app.config import VISION_PRICING, VISION_PRICING_DEFAULT
        model = settings.get("anthropic_vision_model") or "claude-haiku-4-5"
        in_price, out_price = VISION_PRICING_DEFAULT
        for prefix, prices in VISION_PRICING.items():
            if prefix in model:
                in_price, out_price = prices
                break
        estimated = item_count * (350 * in_price + 150 * out_price) / 1_000_000
        return f"Estimated AI cost for {model}: ~${estimated:.2f} ({item_count} short request{'s' if item_count != 1 else ''})"
    if provider == "openai":
        return (
            f"Up to {item_count} short OpenAI-compatible request"
            f"{'s' if item_count != 1 else ''}; your provider bills these at its current model price."
        )
    return "No AI provider is configured."


def _json_object(value: object) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _identity_prompt(item: dict[str, Any]) -> str:
    return (
        "Identify the exact video-game edition from this existing catalogue record. "
        "There is no cover image. Do not guess. Return JSON only with these optional "
        "keys: title, alternate_title, developer, publisher, platform, region, language, publish_year. "
        "Preserve an original-script title; alternate_title must be the official international "
        "title of this one edition, never a paired-release name. platform is the console name; "
        "region is PAL, NTSC, NTSC-J, PAL-M, or unknown; language is an ISO 639-1 code.\n\n"
        + json.dumps({key: item.get(key) for key in EDITABLE_FIELDS}, ensure_ascii=False)
    )


async def identify_edition(item: dict[str, Any], settings: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """Ask the configured provider for a conservative title/edition identity."""
    prompt = _identity_prompt(item)
    provider = settings.get("vision_provider") or ""
    try:
        if provider == "anthropic" and settings.get("anthropic_api_key"):
            import anthropic

            response = await anthropic.AsyncAnthropic(
                api_key=settings["anthropic_api_key"]
            ).messages.create(
                model=settings.get("anthropic_vision_model") or "claude-haiku-4-5",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            return _json_object(response.content[0].text if response.content else "")
        if provider == "openai" and settings.get("openai_api_key"):
            base = (settings.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/")
            response = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {settings['openai_api_key']}"},
                json={"model": settings.get("openai_vision_model") or "gpt-6-luna",
                      "messages": [{"role": "user", "content": prompt}],
                      "response_format": {"type": "json_object"}},
            )
            if response.status_code == 200:
                data = response.json()
                return _json_object(((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
        if provider == "ollama":
            base = (settings.get("ollama_url") or "http://localhost:11434").rstrip("/")
            response = await client.post(
                f"{base}/api/chat",
                json={"model": settings.get("ollama_model") or "gemma3:12b",
                      "messages": [{"role": "user", "content": prompt}], "format": "json", "stream": False},
            )
            if response.status_code == 200:
                return _json_object((response.json().get("message") or {}).get("content"))
    except Exception:
        logger.warning("Game metadata identity request failed for %r", item.get("title"), exc_info=True)
    return {}


def platform_slug(value: object, platforms: dict[str, str]) -> str | None:
    """Map a provider platform label to Shelf's configured platform slug."""
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw in platforms:
        return raw
    # IGDB commonly writes "Nintendo Entertainment System (NES)" while a
    # Shelf platform is simply "Nintendo Entertainment System". Parenthetic
    # abbreviations are presentation, not a different platform. Famicom is
    # the Japanese NES hardware and maps to Shelf's shared NES entry.
    bare = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    needle = fold(bare)
    if needle in {"famicom", "family computer"} and "nes" in platforms:
        return "nes"
    for slug, label in platforms.items():
        if fold(label) == needle:
            return slug
    return None


def _first_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


async def propose(item: dict[str, Any], settings: dict[str, Any], platforms: dict[str, str], client: httpx.AsyncClient) -> dict[str, Any]:
    """Produce editable proposed fields for one game, without any write."""
    ai = await identify_edition(item, settings, client)
    alternate = _first_value(ai.get("alternate_title"))
    query = alternate or _first_value(ai.get("title")) or item["title"]
    # An AI's platform guess is useful context for a human reviewer, but it
    # must never restrict an IGDB lookup nor become a stored platform by
    # itself. A wrong guess (Star Fox 64 → Wii) otherwise prevents IGDB from
    # returning the actual edition at all.
    current_platform = item.get("platform")
    game = None
    if settings.get("igdb_client_id") and settings.get("igdb_client_secret"):
        result = await igdb.search_games(
            query, settings["igdb_client_id"], settings["igdb_client_secret"], client,
            platform=current_platform, limit=10,
        )
        if result.found and result.payload:
            # Never accept a merely similar search result: IGDB can rank a
            # mod, fan project, or a sequel ahead of the original.  A known
            # alternate title may bridge original-script editions, but the
            # selected IGDB result must still match one whole title exactly.
            game = next((candidate for candidate in result.payload if (
                titles_match_exactly(item["title"], candidate.get("title"))
                or (alternate and titles_match_exactly(alternate, candidate.get("title")))
            )), None)

    proposed = {key: item.get(key) for key in EDITABLE_FIELDS}
    # AI contributes the edition-specific attributes IGDB does not retain.
    for source, target in (("alternate_title", "alternate_title"),
                           ("region", "region"), ("language", "language")):
        if ai.get(source) not in (None, ""):
            proposed[target] = ai[source]
    if game:
        for source, target in (("developer", "authors"),
                               ("publisher", "publisher"), ("publish_year", "publish_year")):
            if game.get(source) not in (None, ""):
                proposed[target] = game[source]
        if not proposed.get("alternate_title") and game.get("title") and fold(game["title"]) != fold(item["title"]):
            proposed["alternate_title"] = game["title"]
        if not proposed.get("platform"):
            platform_names = game.get("platform_names") or []
            # A console generation in the title is stronger evidence than
            # IGDB's API ordering, which can place a later Virtual Console
            # port ahead of the original release.
            if "64" in item["title"]:
                platform_names = sorted(platform_names, key=lambda label: 0 if "nintendo 64" in fold(label) else 1)
            candidates = [platform_slug(label, platforms) for label in platform_names]
            candidates = [slug for slug in candidates if slug]
            release_year = item.get("publish_year") or game.get("publish_year")
            if release_year:
                try:
                    year = int(release_year)
                    original_candidates = [slug for slug in candidates if PLATFORM_LAUNCH_YEARS.get(slug, year) <= year]
                    # Do not fall back to a later port when no platform is
                    # compatible with the release year. Leaving the field
                    # empty is safer than filing Zelda (1986) as 3DS.
                    candidates = sorted(original_candidates, key=lambda slug: PLATFORM_LAUNCH_YEARS.get(slug, 0), reverse=True)
                except (TypeError, ValueError):
                    pass
            if candidates:
                proposed["platform"] = candidates[0]
    return proposed
