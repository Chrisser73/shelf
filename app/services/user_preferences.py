"""Per-user Shelf appearance and platform-logo preferences."""

import re

from app.services.platform_logos import logo_path


_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
_THEMES = {"light", "navi", "ocean", "sakura", "coffee", "retro", "matrix"}


def normalise_hex_color(value: str) -> str | None:
    """Return a safe CSS hex colour, an empty default, or ``None`` if invalid."""
    value = value.strip()
    if not value:
        return ""
    return value.upper() if _HEX_COLOR.fullmatch(value) else None


def user_symbol_preferences(db, user_id: int) -> dict[str, str | bool]:
    """Read the small, per-account avatar configuration for template rendering."""
    background = normalise_hex_color(get_preference(db, user_id, "user_symbol_background"))
    text = normalise_hex_color(get_preference(db, user_id, "user_symbol_text"))
    return {
        "background": background or "",
        "text": text or "",
        "show_initial": get_preference(db, user_id, "user_symbol_show_initial") == "1",
    }


def set_user_symbol_preferences(
    db, user_id: int, background: str, text: str, show_initial: bool,
) -> tuple[bool, str]:
    """Validate and store one user's header-symbol configuration."""
    background = normalise_hex_color(background)
    text = normalise_hex_color(text)
    if background is None or text is None:
        return False, "Colours must use a six-digit hex value, for example #5B5BF7."
    set_preference(db, user_id, "user_symbol_background", background)
    set_preference(db, user_id, "user_symbol_text", text)
    set_preference(db, user_id, "user_symbol_show_initial", "1" if show_initial else "0")
    return True, "User symbol updated"


def user_theme(db, user_id: int) -> str:
    """Return a supported theme name, or the unstyled default theme."""
    theme = get_preference(db, user_id, "theme")
    return theme if theme in _THEMES else ""


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
