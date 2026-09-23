"""Read-only catalogue summary for Shelf's future Home page.

The dashboard deliberately knows nothing about which media types are physical
or digital. It reports facts already present in upstream Shelf — catalogue
size, ownership, lending, cover completeness, media-type counts and recent
additions — so future media families can appear automatically without this
service needing edits.
"""

from __future__ import annotations

from app.services import lists
from app.services.platform_logos import logo_path


def dashboard_summary(db, *, recent_limit: int = 8, user_id: int | None = None) -> dict:
    """Return stable, presentation-neutral metrics for the Home page."""
    total = db.execute("SELECT COUNT(*) AS c FROM items_live").fetchone()["c"]
    owned = db.execute(
        "SELECT COUNT(*) AS c FROM items_live WHERE owned = 1"
    ).fetchone()["c"]
    wishlist = db.execute(
        f"SELECT COUNT(*) AS c FROM items_live i WHERE {lists.WISHLISTED_SQL}"
    ).fetchone()["c"]
    lent_out = db.execute(
        "SELECT COUNT(DISTINCT item_id) AS c FROM checkouts WHERE checked_in IS NULL"
    ).fetchone()["c"]
    # Excludes items dismissed in the cover review queue, so this tile and
    # Settings' "N items without a cover" are the same number. Before the queue
    # existed they always agreed; letting them diverge would put two different
    # counts of the same apparent thing on two screens, with this tile not even
    # clickable to reconcile them (Dan's call, 2026-09-09).
    missing_cover = db.execute(
        "SELECT COUNT(*) AS c FROM items_live "
        "WHERE (cover_path IS NULL OR TRIM(cover_path) = '') "
        "AND cover_review_dismissed = 0"
    ).fetchone()["c"]

    type_rows = db.execute(
        "SELECT i.media_type, COUNT(*) AS item_count, "
        "SUM(CASE WHEN i.owned = 1 THEN 1 ELSE 0 END) AS owned_count, "
        f"SUM(CASE WHEN {lists.WISHLISTED_SQL} THEN 1 ELSE 0 END) AS wishlist_count "
        "FROM items_live i GROUP BY i.media_type "
        "ORDER BY item_count DESC, i.media_type COLLATE NOCASE"
    ).fetchall()
    media_types = [dict(row) for row in type_rows]

    platform_rows = db.execute(
        "SELECT p.slug, p.name, l.svg_path, COUNT(*) AS item_count "
        "FROM items_live i JOIN game_platforms p ON p.slug = i.platform "
        "LEFT JOIN user_platform_logos l ON l.platform_slug = p.slug AND l.user_id = ? "
        "WHERE i.media_type = 'video_game' "
        "GROUP BY p.slug, p.name, l.svg_path, p.sort_order "
        "ORDER BY p.sort_order, p.name COLLATE NOCASE",
        (user_id,),
    ).fetchall()
    platforms = [
        {**dict(row), "logo_path": logo_path(row["slug"], row["svg_path"])}
        for row in platform_rows
    ]

    limit = max(0, min(int(recent_limit), 50))
    recent = []
    if limit:
        recent = [
            dict(row)
            for row in db.execute(
                "SELECT i.id, i.title, i.authors, i.media_type, i.cover_path, i.owned, "
                f"i.created_at, {lists.WISHLISTED_SQL} AS wishlisted "
                "FROM items_live i ORDER BY i.created_at DESC, i.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        ]

    return {
        "total_count": total,
        "owned_count": owned,
        "wishlist_count": wishlist,
        "lent_out_count": lent_out,
        "missing_cover_count": missing_cover,
        "media_types": media_types,
        "platforms": platforms,
        "recent_items": recent,
    }
