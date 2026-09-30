"""Small, shared helpers for forgiving human-entered catalogue searches."""

from __future__ import annotations

import unicodedata


def fold(value: object) -> str:
    """Return a case- and accent-insensitive representation of ``value``.

    NFKD keeps non-Latin scripts intact while splitting characters such as
    ``é`` into ``e`` plus its combining accent.  Stripping only combining
    marks means Japanese, Korean, Cyrillic, and similar titles remain fully
    searchable instead of being reduced to an ASCII-only approximation.
    """
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return "".join(char for char in text if not unicodedata.combining(char))


def folded_match_ranges(text: str, query: str) -> list[tuple[int, int]]:
    """Find accent-insensitive query matches as ranges in the original text.

    The range points into ``text`` rather than its folded variant, letting the
    UI highlight ``Poké`` while the user typed ``Poke``.  Combining accents
    following a matched character are included too, which keeps decomposed
    Unicode visually intact.
    """
    needle = fold(query.strip())
    if not needle:
        return []

    folded_parts: list[str] = []
    original_positions: list[int] = []
    for index, char in enumerate(text):
        for folded_char in fold(char):
            folded_parts.append(folded_char)
            original_positions.append(index)
    haystack = "".join(folded_parts)

    ranges: list[tuple[int, int]] = []
    offset = 0
    while True:
        start = haystack.find(needle, offset)
        if start < 0:
            break
        end = start + len(needle)
        original_start = original_positions[start]
        original_end = original_positions[end - 1] + 1
        while original_end < len(text) and unicodedata.combining(text[original_end]):
            original_end += 1
        ranges.append((original_start, original_end))
        offset = end
    return ranges
