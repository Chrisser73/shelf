"""Per-user Shelf appearance and platform-logo preferences."""

from app.services.platform_logos import logo_path


def get_preference(db, user_id: int, key: str, default: str = "") -> str:
    row = db.execute(
        "SELECT value FROM user_preferences WHERE user_id = ? AND key = ?",
        (user_id, key),
    ).fetchone()
    return row["value"] if row else default


def set_preference(db, user_id: int, key: str, value: str) -> None:
    db.execute(
        "INSERT INTO user_preferences (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
        (user_id, key, value),
    )


def platform_logos(db, user_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT p.*, l.svg_path AS user_svg_path "
        "FROM game_platforms p LEFT JOIN user_platform_logos l "
        "ON l.platform_slug = p.slug AND l.user_id = ? "
        "ORDER BY p.sort_order, p.name",
        (user_id,),
    ).fetchall()
    return [
        {**dict(row), "effective_svg_path": logo_path(row["slug"], row["user_svg_path"]),
         "svg_path": row["user_svg_path"]}
        for row in rows
    ]


def platform_logo_map(db, user_id: int) -> dict[str, str]:
    """Return effective logo paths keyed by platform slug for collection cards."""
    return {
        row["slug"]: row["effective_svg_path"]
        for row in platform_logos(db, user_id)
        if row["effective_svg_path"]
    }
