#!/usr/bin/env python3
"""Tripwire lint: every read of `items` in app/ must go through the
`items_live` TEMP view (app/database.py::get_db()), not the physical table.

T1 added `deleted_at` to `items`/`item_copies`; T2 made get_db() create a
per-connection `CREATE TEMP VIEW IF NOT EXISTS items_live AS SELECT * FROM
items WHERE deleted_at IS NULL`. T4-T6 repointed the ~172 existing direct
reads in app/ onto that view, so the census is 0 and this script is the
guard that holds it there: a new direct read of `items` in app/ reds it.

Only app/**/*.py is scanned. Tests legitimately read the physical table (a
later plan needs them to) and are out of scope.

G53: prose in app/ that needs to talk about this should say "the items
table" or "items_live", never write the literal `FROM items` / `JOIN items`
construct in a comment or docstring — this guard strips `#`-comment *lines*
but not inline prose inside a docstring, and a comment quoting the construct
must not trip it.

Run directly (exit 1 on violations) or via tests/test_items_live_lint.py.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Strip a string literal's prefix together with its opening quote, before
# the bare-quote strip below. Skipping this turns `f"FROM items i "` into
# `fFROM items i ` and `\bFROM` no longer matches, because `f` and `F` are
# both word characters with no boundary between them. Three statements have
# exactly this shape today: app/routers/items.py:901, app/routers/pages.py:70,
# app/routers/series.py:83. (An equivalent fix is a prefix-aware matcher —
# `(?<!\w)(?:[rubf]{1,2})?(FROM|JOIN)\s+items\b` — this file picks the
# prefix-strip approach instead.)
_STRING_PREFIX_QUOTE = re.compile(r'\b[rRbBuUfF]{1,2}"')

# The forbidden construct. Excluded, each pinned in
# tests/test_items_live_lint.py even though only the first exists in app/
# today:
#   - preceded by "DELETE " (`DELETE FROM items ...`) — a write, stays on
#     the physical table.
#   - preceded by "yield " (`yield from items`).
#   - followed by " import" (`from items import x`).
# `\b` does not split on `_`, so items_live / item_copies / item_tags /
# item_links never match.
_ITEMS_READ = re.compile(
    r"(?<!DELETE )(?<!yield )\b(FROM|JOIN)\s+items\b(?! import)", re.I
)

VIOLATION_MSG = (
    "{path}:{line}: reads the items table directly — read through "
    "items_live (writes and the allowlisted lookups in "
    "scripts/check_items_live.py stay on items; prose quoting the "
    "FROM/JOIN construct inside a docstring trips this too, see G53)"
)

#: repo-relative path -> {statement substring: how many reads it may suppress}.
#: A substring identifies a legitimate direct read of the physical `items`
#: table, and is normalised the same way the scanner reads source (quotes
#: stripped, whitespace collapsed to single spaces). Mirrors
#: RAW_UPDATE_ALLOWLIST in tests/test_item_write.py — each entry was read at
#: its call site and carries a one-line reason. Allowlisted by
#: repository-relative path, never by basename (G88).
#:
#: An entry must SPAN the read it excuses (see `_spanning`), so it has to
#: quote enough of its statement to contain the FROM/JOIN clause outright.
#: Keep each one long enough that a *different* statement cannot reproduce
#: it and allowlist itself: the count beside it is the structural half of
#: that guard, and `allowlist_mismatches()` reds when a new read rides along
#: inside an existing entry's text.
ALLOWLIST: dict[str, dict[str, int]] = {
    "app/database.py": {
        # The items_live view CREATE in get_db() itself — the seam reads the
        # physical table by definition. Without this entry the lint reds on
        # the statement that defines it.
        "SELECT * FROM items WHERE deleted_at IS NULL": 1,
        # Migrations 20 and 21 (UPC re-filing) — the two statements share
        # this prefix and diverge after it, so one substring, two hits.
        "AND NOT EXISTS (SELECT 1 FROM items o WHERE o.upc =": 2,
        # Migration 26 — backfill primary copies from legacy locations.
        "SELECT i.id, 1, i.location_id, 1 FROM items i": 1,
        # Migration 36 — seed the wishlist from every unowned item.
        "SELECT (SELECT id FROM lists WHERE slug = 'wishlist'), id "
        "FROM items WHERE owned = 0": 1,
        # gc_orphaned_series_meta: a soft-deleted item keeps its series
        # alive so a restore finds it intact.
        "SELECT 1 FROM items WHERE series_name = ? COLLATE NOCASE": 1,
    },
    "app/routers/items.py": {
        # _find_item_by_barcode's existing-item scan modes must find a
        # soft-deleted row so the next plan can restore it.
        "SELECT i.*, l.name as location_name FROM items i "
        "LEFT JOIN locations l ON i.location_id = l.id WHERE i.isbn = ?": 1,
        "SELECT i.*, l.name as location_name FROM items i "
        "LEFT JOIN locations l ON i.location_id = l.id WHERE i.upc = ?": 1,
    },
    "app/routers/items_csv.py": {
        # CSV dedup — same reason as _find_item_by_barcode above.
        "SELECT id FROM items WHERE media_type = ? AND isbn IN (?, ?)": 1,
        "SELECT id FROM items WHERE TRIM(title) = TRIM(?)": 1,
    },
}


def _normalise_file(path: Path) -> tuple[str, list[tuple[int, int]]]:
    """Return (joined_buffer, offsets) for one file.

    Comment-only lines are dropped first (G53). Each string literal's
    prefix is stripped together with its opening quote (see
    `_STRING_PREFIX_QUOTE`), then any remaining `"` characters are stripped,
    whitespace is collapsed to single spaces, and the surviving lines are
    joined with a single separating space — so a statement split across
    adjacent string literals or an f-string fragment that opens on `FROM`
    reads as one piece of text. `offsets` maps each surviving line's start
    position in the joined buffer to its 1-based source line number.
    """
    lines = path.read_text().splitlines()
    buf_parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    pos = 0
    for i, raw_line in enumerate(lines, 1):
        if raw_line.lstrip().startswith("#"):
            continue
        unprefixed = _STRING_PREFIX_QUOTE.sub("", raw_line)
        collapsed = re.sub(r"\s+", " ", unprefixed.replace('"', "")).strip()
        if not collapsed:
            continue
        offsets.append((pos, i))
        buf_parts.append(collapsed)
        pos += len(collapsed) + 1  # +1 for the joining space
    return " ".join(buf_parts), offsets


def _line_for(offsets: list[tuple[int, int]], offset: int) -> int:
    line_no = offsets[0][1] if offsets else 1
    for start, ln in offsets:
        if start > offset:
            break
        line_no = ln
    return line_no


def _spanning(buf: str, sub: str, match: re.Match) -> bool:
    """True when some occurrence of `sub` in `buf` CONTAINS the whole match.

    This is the suppression rule, and it is deliberately not a proximity
    test. An earlier revision checked whether an allowlisted substring
    appeared anywhere in a ±200/300-character window around the match, which
    excused any new direct read that happened to land beside an allowlisted
    statement — two reads in the same short function, or a literal a few
    lines from the view's own CREATE, went unreported. Requiring the entry
    to span the match ties each exemption to the one statement it names.
    """
    idx = buf.find(sub)
    while idx != -1:
        if idx <= match.start() and match.end() <= idx + len(sub):
            return True
        idx = buf.find(sub, idx + 1)
    return False


def find_violations(root: Path = ROOT) -> list[str]:
    violations = []
    for path in sorted((root / "app").rglob("*.py")):
        rel = str(path.relative_to(root))
        buf, offsets = _normalise_file(path)
        allowed = ALLOWLIST.get(rel, {})
        for match in _ITEMS_READ.finditer(buf):
            if any(_spanning(buf, sub, match) for sub in allowed):
                continue
            line = _line_for(offsets, match.start())
            violations.append(VIOLATION_MSG.format(path=rel, line=line))
    return violations


def allowlist_mismatches(root: Path = ROOT) -> list[str]:
    """Every allowlist entry must span exactly the number of reads declared
    beside it in ALLOWLIST.

    A count of 0 is the stale case — an entry the code no longer produces,
    sitting there silently over-permissive (mirrors
    test_raw_update_allowlist_has_no_stale_entries in
    tests/test_item_write.py). A count ABOVE the declared one is the
    ride-along case: a new direct read written inside text an existing entry
    already covers, which would otherwise be exempted without anyone
    deciding it should be. Both are mismatches and both must fail.
    """
    buf_by_path: dict[str, str] = {}
    for path in sorted((root / "app").rglob("*.py")):
        rel = str(path.relative_to(root))
        buf_by_path[rel] = _normalise_file(path)[0]

    mismatches = []
    for rel, expected in ALLOWLIST.items():
        buf = buf_by_path.get(rel, "")
        matches = list(_ITEMS_READ.finditer(buf))
        for sub, want in expected.items():
            got = sum(1 for m in matches if _spanning(buf, sub, m))
            if got != want:
                mismatches.append(
                    f"{rel}: {sub!r} spans {got} read(s), expected {want}"
                )
    return mismatches


def main() -> int:
    violations = find_violations()
    mismatches = allowlist_mismatches()
    if violations:
        print(f"items_live lint: {len(violations)} violation(s)\n")
        for v in violations:
            print(f"  {v}")
    if mismatches:
        print(f"items_live lint: {len(mismatches)} allowlist mismatch(es)\n")
        for m in mismatches:
            print(f"  {m}")
    if violations or mismatches:
        return 1
    print("items_live lint: every read goes through the view.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
