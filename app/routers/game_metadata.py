"""Admin-only review and write endpoints for existing video-game metadata."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth import require_role
from app.database import get_all_settings, get_db, get_game_platforms
from app.services import game_metadata
from app.services.national import SEARCH_LANGS

router = APIRouter(prefix="/api/game-metadata", dependencies=[Depends(require_role("admin"))])


class MetadataUpdate(BaseModel):
    id: int
    include: bool = True
    title: str
    alternate_title: str | None = None
    authors: str | None = None
    publisher: str | None = None
    platform: str | None = None
    region: str | None = None
    language: str | None = None
    publish_year: int | None = None
    location_id: int | None = None


class ApplyRequest(BaseModel):
    items: list[MetadataUpdate]


@router.get("/estimate")
async def estimate():
    with get_db() as db:
        settings = get_all_settings(db)
        count = game_metadata.missing_metadata_count(db)
    return {"ok": True, "count": count, "cost_hint": game_metadata.cost_hint(settings, count)}


@router.post("/plan")
async def plan(request: Request):
    with get_db() as db:
        settings = get_all_settings(db)
        platforms = get_game_platforms(db)
        from app.services.user_preferences import get_preference
        default_location_id = get_preference(db, request.state.user["id"], "default_location_id")
        rows = db.execute(
            f"SELECT id, {', '.join(game_metadata.EDITABLE_FIELDS)} FROM items_live "
            f"WHERE {game_metadata.missing_sql()} ORDER BY title COLLATE NOCASE"
        ).fetchall()
    if not rows:
        return {"ok": True, "items": [], "cost_hint": game_metadata.cost_hint(settings, 0)}
    if not settings.get("vision_provider"):
        return {"ok": False, "message": "Configure a vision/AI provider before planning metadata."}
    if not settings.get("igdb_client_id") or not settings.get("igdb_client_secret"):
        return {"ok": False, "message": "Configure IGDB before planning video-game metadata."}

    planned = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for row in rows:
            current = dict(row)
            proposed = await game_metadata.propose(current, settings, platforms, client)
            if not current.get("location_id") and default_location_id:
                proposed["location_id"] = int(default_location_id)
            if proposed != {key: current.get(key) for key in game_metadata.EDITABLE_FIELDS}:
                planned.append({"id": current["id"], "current": current, "proposed": proposed})
    return {"ok": True, "items": planned, "cost_hint": game_metadata.cost_hint(settings, len(rows))}


@router.post("/apply")
async def apply(payload: ApplyRequest):
    chosen = [row for row in payload.items if row.include]
    if not chosen:
        return {"ok": False, "message": "Select at least one item to sync."}
    updated = []
    with get_db() as db:
        platforms = get_game_platforms(db)
        for row in chosen:
            if row.platform and row.platform not in platforms:
                return {"ok": False, "message": "One selected platform is no longer available."}
            if row.language and row.language not in SEARCH_LANGS:
                return {"ok": False, "message": "One selected language is not supported."}
            if row.region and row.region not in {"unknown", "PAL", "NTSC", "NTSC-J", "PAL-M"}:
                return {"ok": False, "message": "One selected region is not supported."}
            if row.location_id:
                location = db.execute("SELECT id FROM locations WHERE id = ?", (row.location_id,)).fetchone()
                if not location:
                    return {"ok": False, "message": "One selected location is no longer available."}
            found = db.execute("SELECT id FROM items_live WHERE id = ? AND media_type = 'video_game'", (row.id,)).fetchone()
            if not found:
                continue
            values = {field: getattr(row, field) for field in game_metadata.EDITABLE_FIELDS}
            db.execute(
                "UPDATE items SET title = :title, alternate_title = :alternate_title, authors = :authors, "
                "publisher = :publisher, platform = :platform, region = :region, language = :language, "
                "publish_year = :publish_year, location_id = :location_id, updated_at = datetime('now') WHERE id = :id",
                {**values, "id": row.id},
            )
            updated.append({"id": row.id, "title": row.title})
    return {"ok": True, "updated": updated}
