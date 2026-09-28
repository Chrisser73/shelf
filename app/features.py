"""Feature registry and per-feature on/off flags.

A feature is an optional part of Shelf an admin can turn off: its nav tab, its
routes, its scan modes and its background job. Core surfaces (scan, Browse,
items, locations, tags, Trash, settings, auth, backup, logs) are never
registered and cannot be turned off.

**Flags gate surfaces and schedulers, never schema and never data.** Every
table exists whatever the flags say; disabling hides and refuses, enabling
re-reveals everything, including rows written while the feature was off.

Each flag is one `settings` row, `feature.<key>`. Only the exact value "0"
disables a feature: an absent row (every upgraded install) or any other value
means enabled, so an upgrade changes nothing until an admin turns something
off. Flags are rows only; no env var overrides them.

`nav.py` imports this module, never the reverse at module level.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


# A route is (METHOD, path) exactly as `app.routes` spells the path.
Route = tuple[str, str]


@dataclass(frozen=True)
class Feature:
    label: str
    description: str
    # NAV_TABS keys this feature owns; a disabled feature hides them.
    nav_tabs: tuple[str, ...] = ()
    # Scan modes (dispatched inside core /api/scan) that refuse while off.
    scan_modes: tuple[str, ...] = ()
    # The background job that skips its pass while off.
    job: str | None = None
    # Impact probes run before turning the feature off: each returns
    # (count, phrase) and a nonzero count asks the admin to confirm.
    probes: tuple[Callable, ...] = ()
    # Where the disabled page's Enable button lands. From the registry, never
    # from the request (an open redirect on an admin POST otherwise).
    entry_path: str = "/settings"
    # Dotted router modules the feature owns. Every route in them is gated by
    # this feature unless listed in `ungated` or `inline` (the registry lint
    # in tests/test_features.py holds this). Dotted, never basenames (G88).
    modules: tuple[str, ...] = ()
    # Gated routes that live in core modules (pages.py).
    routes: tuple[Route, ...] = ()
    # Routes in `modules` that stay reachable while off, and why.
    ungated: dict[Route, str] = field(default_factory=dict)
    # Routes in `modules` gated in their body rather than by a dependency.
    inline: dict[Route, str] = field(default_factory=dict)
    # Whether an integration feature has what it needs to do anything.
    # None for features that need no setup.
    configured: Callable[[], bool] | None = None


_CONFIG = "configuration: an admin can set an integration up before turning it on"


# --- Impact probes: what stops happening, for people other than the admin ---
#
# Each opens its own connection, so call them outside any open write
# transaction (G112). They read the live views only (G105).


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _probe_share_links() -> tuple[int, str]:
    from app.database import get_db
    with get_db() as db:
        # No revoked or expiry column exists: every row is an active link.
        n = db.execute("SELECT COUNT(*) FROM share_links").fetchone()[0]
    verb = "stops" if n == 1 else "stop"
    return n, f"{_plural(n, 'active share link')} {verb} working for the people you sent them to."


def _probe_open_loans() -> tuple[int, str]:
    from app.database import get_db
    with get_db() as db:
        loans, borrowers = db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT c.borrower_id) FROM checkouts c "
            "JOIN items_live i ON c.item_id = i.id WHERE c.checked_in IS NULL"
        ).fetchone()
    verb = "stays" if loans == 1 else "stay"
    return loans, (f"{_plural(loans, 'open loan')} to {_plural(borrowers, 'borrower')} "
                   f"{verb} recorded, but overdue reminders pause.")


# --- Whether an integration feature has what it needs ------------------------
#
# Read through get_setting (env overrides count, secrets decrypted — G15).


def _settings_present(*keys: str) -> bool:
    from app.database import get_db, get_setting
    with get_db() as db:
        return all((get_setting(db, k) or "").strip() for k in keys)


def _hardcover_configured() -> bool:
    return _settings_present("hardcover_token")


def _abs_configured() -> bool:
    return _settings_present("abs_url", "abs_token")


def _komga_configured() -> bool:
    from app.services import komga_sync
    config = komga_sync.configuration()
    return bool(config["url"]) and config["api_key_saved"]


def _romm_configured() -> bool:
    from app.services import romm_sync
    config = romm_sync.configuration()
    return bool(config["url"]) and config["token_saved"]


def _intake_configured() -> bool:
    from app import nav
    return nav._is_configured("vision", nav._nav_settings())


FEATURES: dict[str, Feature] = {
    "lending": Feature(
        label="Lending",
        description="Lend items to borrowers, track loans and send overdue reminders.",
        scan_modes=("lend", "return"),
        job="loan_reminders",
        probes=(_probe_open_loans,),
        modules=("app.routers.checkouts",),
    ),
    "series": Feature(
        label="Series",
        description="Track series, find gaps and mark series complete.",
        nav_tabs=("series",),
        entry_path="/series",
        modules=("app.routers.series",),
    ),
    "stats": Feature(
        label="Statistics",
        description="Charts and counts about your collection.",
        nav_tabs=("stats",),
        entry_path="/stats",
        routes=(("GET", "/stats"),),
    ),
    "store": Feature(
        label="Store Mode",
        description="An offline page for checking what you own while out shopping.",
        nav_tabs=("store",),
        entry_path="/store",
        modules=("app.routers.store",),
        ungated={
            ("GET", "/sw.js"): "an installed worker must fetch its own script",
        },
    ),
    "share": Feature(
        label="Sharing",
        description="Public read-only links to your collection.",
        probes=(_probe_share_links,),
        modules=("app.routers.share",),
        inline={
            ("GET", "/share/{token}"): "anonymous: answers exactly like an unknown token",
        },
    ),
    "valuation": Feature(
        label="Valuation",
        description="Price lookups and the insurance valuation report.",
        modules=("app.routers.valuation",),
        ungated={
            ("POST", "/api/valuate/test-key"): _CONFIG,
            ("POST", "/api/tmdb/test-key"): "TMDb is core DVD scanning",
        },
    ),
    "music": Feature(
        label="Music",
        description="Music releases with Discogs details.",
        nav_tabs=("music",),
        entry_path="/music",
        modules=("app.routers.music",),
    ),
    "periodicals": Feature(
        label="Periodicals",
        description="Magazines and other periodicals, grouped by publication.",
        nav_tabs=("periodicals",),
        entry_path="/periodicals",
        modules=("app.routers.periodicals",),
        ungated={
            ("GET", "/api/periodicals/assist/search"): "core Scan's 977 flow",
            ("GET", "/api/periodicals/assist/select"): "core Scan's 977 flow",
            ("POST", "/api/periodicals/confirm"): "core Scan's 977 flow",
        },
    ),
    "shelf_fill": Feature(
        label="Shelf Fill",
        description="Place items on shelves and see how full each location is.",
        nav_tabs=("shelf-fill",),
        entry_path="/shelf-fill",
        modules=("app.routers.shelf_fill",),
    ),
    "intake": Feature(
        label="Photo Intake",
        description="Add many books at once from a photo of a shelf.",
        nav_tabs=("intake",),
        entry_path="/intake",
        modules=("app.routers.intake",),
        routes=(("GET", "/intake"),),
        configured=_intake_configured,
    ),
    "hardcover": Feature(
        label="Hardcover",
        description="Discover, reading-status sync and transfers with Hardcover.",
        nav_tabs=("discover",),
        job="hardcover_sync",
        entry_path="/discover",
        modules=("app.routers.hardcover",),
        routes=(("GET", "/discover"),),
        configured=_hardcover_configured,
        ungated={
            ("POST", "/api/hardcover/test"): _CONFIG,
            ("POST", "/api/hardcover/schedule"): _CONFIG,
        },
    ),
    "abs_sync": Feature(
        label="Audiobookshelf sync",
        description="Import and link items from Audiobookshelf libraries.",
        job="abs_sync",
        modules=("app.routers.sync",),
        configured=_abs_configured,
        ungated={
            ("POST", "/api/sync/audiobookshelf/test"): _CONFIG,
            ("GET", "/api/sync/audiobookshelf/libraries"): _CONFIG,
            ("POST", "/api/sync/audiobookshelf/libraries"): _CONFIG,
            ("POST", "/api/sync/audiobookshelf/schedule"): _CONFIG,
        },
    ),
    "komga": Feature(
        label="Komga",
        description="Link comics and manga to a Komga server.",
        modules=("app.routers.komga",),
        configured=_komga_configured,
        ungated={
            ("GET", "/api/komga/status"): _CONFIG,
            ("POST", "/api/komga/settings"): _CONFIG,
            ("POST", "/api/komga/test"): _CONFIG,
            ("GET", "/api/komga/libraries"): _CONFIG,
            ("POST", "/api/komga/libraries"): _CONFIG,
        },
    ),
    "romm": Feature(
        label="RomM",
        description="Link video games to a RomM server.",
        modules=("app.routers.romm",),
        configured=_romm_configured,
        ungated={
            ("GET", "/api/romm/status"): _CONFIG,
            ("POST", "/api/romm/settings"): _CONFIG,
            ("POST", "/api/romm/test"): _CONFIG,
            ("GET", "/api/romm/platforms"): _CONFIG,
            ("POST", "/api/romm/platforms"): _CONFIG,
        },
    ),
}

# NAV_TABS keys that belong to no feature and are always available.
CORE_NAV_TABS = frozenset({"browse", "scan", "trash", "settings", "logs"})


def setting_key(key: str) -> str:
    return f"feature.{key}"


_cached_flags: dict[str, bool] | None = None

#: Bumped by every invalidation. A refill stores its snapshot only if no
#: invalidation happened while it was reading (the trash.py pattern).
_generation = 0


def invalidate_cache() -> None:
    """Drop the cached flags so the next read re-reads them."""
    global _cached_flags, _generation
    _cached_flags = None
    _generation += 1


def _flags() -> dict[str, bool]:
    global _cached_flags
    if _cached_flags is not None:
        return _cached_flags
    from app.database import get_db, get_setting
    generation = _generation
    try:
        with get_db() as db:
            flags = {k: get_setting(db, setting_key(k)) != "0" for k in FEATURES}
    except Exception:
        # Mirrors nav._nav_settings: an unreadable DB must not take the page
        # down. Everything reads as enabled for this call, and nothing is
        # cached, so the next call tries again.
        logger.warning("Could not read feature flags; treating all as enabled", exc_info=True)
        return {k: True for k in FEATURES}
    if generation == _generation:
        _cached_flags = flags
    return flags


def feature_enabled(key: str) -> bool:
    """Whether a registered feature is on. An unknown key raises KeyError."""
    if key not in FEATURES:
        raise KeyError(key)
    return _flags()[key]


def _invalidate_all() -> None:
    from app import nav
    invalidate_cache()
    nav.invalidate_cache()


def set_feature_enabled(db, key: str, enabled: bool) -> None:
    """Turn a feature on or off. The one write path for flags.

    Drops the flag and nav caches now, and again once `db`'s transaction
    commits: another connection may refill them from the pre-commit state in
    between (the race `database._Connection` documents).
    """
    from app.database import after_commit, set_setting
    if key not in FEATURES:
        raise KeyError(key)
    set_setting(db, setting_key(key), "1" if enabled else "0")
    _invalidate_all()
    after_commit(db, _invalidate_all)


def confirm_message(key: str) -> str:
    """The warning shown before turning `key` off, or "" when nothing is lost
    for anyone but the admin (every probe reads zero)."""
    phrases = [phrase for count, phrase in (probe() for probe in FEATURES[key].probes) if count]
    return " ".join(phrases + ["Turn it off anyway?"]) if phrases else ""


def feature_rows() -> list[dict]:
    """One row per feature for Settings → Features. Runs every probe, so
    call it outside any open write transaction (G112)."""
    flags = _flags()
    return [{
        "key": key,
        "label": f.label,
        "description": f.description,
        "enabled": flags[key],
        "configured": f.configured() if f.configured else None,
        "confirm": confirm_message(key) if flags[key] else "",
    } for key, f in FEATURES.items()]


def disabled_message(key: str) -> str:
    return f"{FEATURES[key].label} is turned off on this Shelf."


def disabled_page(request, key: str):
    """The full page a disabled feature's HTML route answers with (200)."""
    f = FEATURES[key]
    user = getattr(request.state, "user", None) or {}
    return request.app.state.templates.TemplateResponse(request, "feature_disabled.html", {
        "feature": {"key": key, "label": f.label, "description": f.description},
        "is_admin": user.get("role") == "admin",
    })


def _refusal(request, key: str):
    """The response for a request that reached a disabled feature's route.

    Branch order matters. An EventSource hides a 403's body from the page, so
    a stream gets its refusal as an SSE error frame, which every stream
    consumer already renders. A native form post or link lands on the
    disabled page rather than on raw JSON. htmx and fetch() send
    Sec-Fetch-Mode `cors`, so they fall through to the toast or the JSON.
    """
    from fastapi.responses import JSONResponse, Response
    from app.routers import items_common

    message = disabled_message(key)
    headers = request.headers
    if "text/event-stream" in headers.get("accept", ""):
        import json
        frame = f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
        return Response(frame, status_code=200, media_type="text/event-stream")
    if headers.get("sec-fetch-mode") == "navigate":
        return disabled_page(request, key)
    if headers.get("HX-Request"):
        resp = Response(status_code=403)
        # HX-Trigger, not -After-Swap: htmx fires it before its no-swap-on-4xx rule.
        resp.headers["HX-Trigger"] = items_common._toast_header(message, "error")
        return resp
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {"error": "feature_disabled", "feature": key, "ok": False, "message": message},
            status_code=403,
        )
    return disabled_page(request, key)


def require_feature(key: str):
    """A route dependency refusing the request while `key` is turned off.

    Declare it after the route's `require_role`: the role answer comes first,
    so the disabled page never tells a user what a route they may not use is
    for. The registry lint checks the order and finds gates by `feature_key`.
    """
    if key not in FEATURES:
        raise KeyError(key)
    from fastapi import Request

    async def _dependency(request: Request):
        if feature_enabled(key):
            return
        from app.auth import _ResponseException
        raise _ResponseException(_refusal(request, key))

    _dependency.feature_key = key
    return _dependency
