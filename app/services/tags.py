"""Custom item tags — free-form labels (signed, first-edition, book-club…)
edited as chips on the item detail page and filterable on Browse.

`tags.media_type` (nullable) is an *advisory* scope: NULL means the tag is
global, and nothing here strips or refuses an out-of-scope association —
that is a settled design decision, not an omission.

Every function here takes the caller's own `db` connection and never opens
one of its own — callers already hold one, often inside a write
transaction, so nothing in this module logs (a second connection opened to
write a log record would block on the caller's in-flight write until
SQLite's busy timeout).

Add-time default tags ride the item's own transaction: an add route wraps
its body in `default_tags(raw)`, and `item_write.insert_item` calls
`attach_pending` on the connection that inserted or restored the row. The
item and its tags commit together or not at all (G118).
"""

import re
from contextlib import contextmanager
from contextvars import ContextVar

from app import config

MAX_TAG_LENGTH = 40


def normalize_tag(name: str) -> str:
    """Trim, collapse inner whitespace, cap length. Case is preserved as
    typed; uniqueness is case-insensitive (NOCASE column)."""
    return re.sub(r"\s+", " ", name or "").strip()[:MAX_TAG_LENGTH]


def get_item_tags(db, item_id: int) -> list:
    return db.execute(
        "SELECT t.id, t.name FROM item_tags it JOIN tags t ON it.tag_id = t.id "
        "WHERE it.item_id = ? ORDER BY t.name COLLATE NOCASE",
        (item_id,),
    ).fetchall()


def get_all_tags(db, media_type=None) -> list:
    """All tags with usage counts, for the Browse filter and suggestions.

    Both statements join `items_live`, so a trashed item's tag association
    counts toward neither statement's `count` — a tag whose only item is
    trashed still lists, with `count` 0. `media_type=None` emits the
    unscoped statement; passing a `media_type` narrows to tags that are
    global or scoped to it, same join.
    """
    if media_type is None:
        return db.execute(
            "SELECT t.id, t.name, COUNT(il.id) AS count FROM tags t "
            "LEFT JOIN item_tags it ON it.tag_id = t.id "
            "LEFT JOIN items_live il ON il.id = it.item_id "
            "GROUP BY t.id ORDER BY t.name COLLATE NOCASE"
        ).fetchall()
    return db.execute(
        "SELECT t.id, t.name, t.media_type, COUNT(il.id) AS count FROM tags t "
        "LEFT JOIN item_tags it ON it.tag_id = t.id "
        "LEFT JOIN items_live il ON il.id = it.item_id "
        "WHERE t.media_type IS NULL OR t.media_type = ? "
        "GROUP BY t.id ORDER BY t.name COLLATE NOCASE",
        (media_type,),
    ).fetchall()


def parse_tag_list(raw) -> list:
    """Split `raw` on ';', normalise each piece, drop blanks, and dedupe
    NOCASE with first spelling wins. Order is preserved. `None`/`""` -> []."""
    if not raw:
        return []
    seen = set()
    out = []
    for piece in raw.split(";"):
        name = normalize_tag(piece)
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def get_or_create_tag(db, name: str, media_type=None) -> int:
    """Return the id of the tag named `name`, creating it (scoped to
    `media_type`) if it does not exist. An existing row wins outright —
    its scope is never updated, even if this call asked for a different
    one."""
    db.execute(
        "INSERT OR IGNORE INTO tags (name, media_type) VALUES (?, ?)",
        (name, media_type),
    )
    row = db.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    return row["id"]


def attach_tags(db, item_id: int, names) -> None:
    """Additively associate each name in `names` with `item_id`, creating
    any tag that does not exist yet (global scope)."""
    for name in names:
        tag_id = get_or_create_tag(db, name)
        db.execute(
            "INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)",
            (item_id, tag_id),
        )


def detach_tags(db, item_id: int, tag_ids) -> int:
    """Remove the association between `item_id` and each id in `tag_ids`.
    Returns how many associations were actually removed."""
    removed = 0
    for tag_id in tag_ids:
        cursor = db.execute(
            "DELETE FROM item_tags WHERE item_id = ? AND tag_id = ?",
            (item_id, tag_id),
        )
        removed += cursor.rowcount
    return removed


def gc_orphans(db, tag_ids) -> None:
    """Delete each tag in `tag_ids` that no longer has any association,
    so the Browse dropdown and suggestion lists stay clean."""
    for tag_id in tag_ids:
        db.execute(
            "DELETE FROM tags WHERE id = ? "
            "AND NOT EXISTS (SELECT 1 FROM item_tags WHERE tag_id = ?)",
            (tag_id, tag_id),
        )


def tags_for_items(db, ids) -> dict:
    """Map real item id -> list of tag names, NOCASE-sorted, for the ids
    given. One grouped query per chunk of 500 ids (SQLite's parameter
    limit). `{}` for no ids."""
    ids = list(ids)
    if not ids:
        return {}
    out: dict = {}
    chunk_size = 500
    for start in range(0, len(ids), chunk_size):
        chunk = ids[start:start + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        rows = db.execute(
            "SELECT item_tags.item_id AS item_id, tags.name AS name "
            "FROM item_tags JOIN tags ON tags.id = item_tags.tag_id "
            f"WHERE item_tags.item_id IN ({placeholders}) "
            "ORDER BY item_tags.item_id, tags.name COLLATE NOCASE",
            chunk,
        ).fetchall()
        for r in rows:
            out.setdefault(r["item_id"], []).append(r["name"])
    return out


def list_tags_with_counts(db) -> list:
    """Every tag with its live association count and how many of those
    associated items carry a media type the tag is scoped away from.

    No caller today — the tag-manager plan wires this in. Counts only
    untrashed items (the items_live relation), so a trashed item's
    association counts toward neither `count` nor `out_of_scope_count`.
    """
    return db.execute(
        "SELECT t.id, t.name, t.media_type, "
        "COUNT(il.id) AS count, "
        "SUM(CASE WHEN t.media_type IS NOT NULL AND il.media_type IS NOT NULL "
        "AND il.media_type != t.media_type THEN 1 ELSE 0 END) AS out_of_scope_count "
        "FROM tags t "
        "LEFT JOIN item_tags it ON it.tag_id = t.id "
        "LEFT JOIN items_live il ON il.id = it.item_id "
        "GROUP BY t.id ORDER BY t.name COLLATE NOCASE"
    ).fetchall()


def suggestions_for(db, media_type: str) -> list:
    """Suggested tags for `media_type`: the user's own tags (global +
    scoped to this type) first, then any `config.TAG_SUGGESTIONS[media_type]`
    starter not already present (NOCASE). If any user tag is already scoped
    to this media type, no starters are offered at all — a deliberate
    scoped tag means the user has taken charge of that type's vocabulary.

    `suggestion_payload` calls this once per configured type for the
    starter half of `GET /api/tags`.
    """
    user_tags = get_all_tags(db, media_type=media_type)
    seen = {row["name"].casefold() for row in user_tags}
    has_scoped = any(row["media_type"] == media_type for row in user_tags)

    out = [{"name": row["name"], "starter": False} for row in user_tags]
    if not has_scoped:
        for starter in config.TAG_SUGGESTIONS.get(media_type, []):
            name = normalize_tag(starter)
            if name.casefold() not in seen:
                out.append({"name": name, "starter": True})
                seen.add(name.casefold())
    return out


def suggestion_payload(db) -> list:
    """The `GET /api/tags` rows every tag datalist is built from.

    The user's own tags come first, NOCASE-ordered, each with its own
    `media_type` (None for a global tag). The starters follow: for each type
    in `config.TAG_SUGGESTIONS`, in order, the `starter` rows of
    `suggestions_for`, stamped with that type — so a type's starters vanish
    once the user has a tag scoped to it. The client filters by type.
    """
    out = [
        {"name": row["name"], "media_type": row["media_type"], "starter": False}
        for row in db.execute(
            "SELECT name, media_type FROM tags ORDER BY name COLLATE NOCASE"
        ).fetchall()
    ]
    for media_type in config.TAG_SUGGESTIONS:
        out.extend(
            {"name": row["name"], "media_type": media_type, "starter": True}
            for row in suggestions_for(db, media_type) if row["starter"]
        )
    return out


_pending: ContextVar = ContextVar("pending_default_tags", default=None)


@contextmanager
def default_tags(raw):
    """Within this block, every item `insert_item` files takes the tags in
    `raw` (`;`-separated) in the same transaction.

    The holder is emptied on exit, not only unset: a task spawned inside the
    block copies the context, and must not tag what it inserts later.
    """
    holder = {"names": parse_tag_list(raw)}
    token = _pending.set(holder)
    try:
        yield
    finally:
        holder["names"] = []
        _pending.reset(token)


def attach_pending(db, item_id: int) -> None:
    """Attach the enclosing `default_tags` block's names to `item_id` on the
    caller's connection. A no-op outside a block."""
    holder = _pending.get()
    if holder and holder["names"]:
        attach_tags(db, int(item_id), holder["names"])
