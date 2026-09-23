import re

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse

from app.auth import require_role
from app.database import get_db
from app.services.platform_logos import normalise_svg_path

router = APIRouter(prefix="/api/platforms", dependencies=[Depends(require_role("admin"))])


def _slugify(name: str) -> str:
    """Generate a slug from a platform name: lowercase, keep alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _platform_name_and_slug(value: str) -> tuple[str, str]:
    """Split ``Display name (slug)`` while preserving the legacy name-only form."""
    value = value.strip()
    explicit = re.fullmatch(r"(.+?)\s*\(([^()]+)\)\s*", value)
    if explicit:
        name, requested_slug = (part.strip() for part in explicit.groups())
        slug = _slugify(requested_slug)
        if name and slug:
            return name, slug
    return value, _slugify(value)


@router.post("")
async def create_platform(name: str = Form(...)):
    name, slug = _platform_name_and_slug(name)
    if not slug:
        return RedirectResponse(url="/settings", status_code=303)
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO game_platforms (slug, name) VALUES (?, ?)",
            (slug, name),
        )
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/{platform_id}/delete")
async def delete_platform(platform_id: int):
    with get_db() as db:
        row = db.execute("SELECT slug FROM game_platforms WHERE id = ?", (platform_id,)).fetchone()
        if row:
            db.execute("UPDATE items SET platform = NULL WHERE platform = ?", (row["slug"],))
            db.execute("DELETE FROM game_platforms WHERE id = ?", (platform_id,))
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/logos")
async def save_platform_logo(platform: str = Form(...), svg_path: str = Form("")):
    """Create or replace a platform's mapping from the bundled SVG files."""
    platform = platform.strip()
    path = normalise_svg_path(svg_path)
    with get_db() as db:
        exists = db.execute(
            "SELECT 1 FROM game_platforms WHERE slug = ?", (platform,)
        ).fetchone()
        if not exists:
            return RedirectResponse(url="/settings", status_code=303)
        if path is None:
            db.execute("DELETE FROM game_platform_logos WHERE platform_slug = ?", (platform,))
        else:
            db.execute(
                "INSERT INTO game_platform_logos (platform_slug, svg_path) VALUES (?, ?) "
                "ON CONFLICT(platform_slug) DO UPDATE SET svg_path = excluded.svg_path",
                (platform, path),
            )
    return RedirectResponse(url="/settings", status_code=303)
