"""Normalizers for CSV exports from reading-tracker and catalogue apps
(Goodreads, StoryGraph, LibraryThing, Libib).

The import endpoint lowercases headers and replaces spaces with underscores
before these functions see a row, so keys here match that convention
(e.g. "Exclusive Shelf" -> "exclusive_shelf", "ISBN/UID" -> "isbn/uid").

Each normalizer returns the shelf-native shape consumed by the CSV import:

    {
        "title": str,
        "authors": str | None,
        "isbn": str | None,          # validated 10/13-digit
        "media_type": str,           # book / ebook / audiobook / dvd / cd / vinyl / video_game
        "publisher": str | None,
        "publish_year": str | None,  # numeric string, endpoint coerces
        "page_count": str | None,
        "series_name": str | None,
        "series_position": float | None,
        "reading_status": str | None,   # read / reading / want_to_read
        "date_finished": str | None,    # ISO date
        "owned": bool | None,        # generic: None when absent/blank
        "wishlisted": bool | None,   # generic only; None when absent/blank
        "deleted": bool | None,      # generic only; None when absent/blank —
                                      # Goodreads/StoryGraph emit None, since
                                      # neither tracker has a Trash concept.
        "upc": str | None,            # Libib only — normalized EAN-13 storage form
        "copy": dict | None,          # LibraryThing only — acquisition fields for
                                       # the new item's primary copy (see add_copy)
        "dropped": list[tuple[str, str]],  # Libib only — per-row (column, reason)
                                            # drops the route folds into the response
        "tags": list[str],           # generic, LibraryThing and Libib emit it;
                                      # [] when absent/blank. Goodreads/StoryGraph
                                      # emit no "tags" key at all, so callers must
                                      # read norm.get("tags") or [].
    }
"""

import math
import re
import unicodedata

from app import config
from app.services import tags as tags_svc
from app.services import upc as upc_svc

GOODREADS = "goodreads"
STORYGRAPH = "storygraph"
LIBRARYTHING = "librarything"
LIBIB = "libib"
GENERIC = "generic"


def choose_delimiter(first_line: str) -> str:
    """Pick the CSV/TSV delimiter from the file's first (header) line.

    Tab when the line holds more tabs than commas, counting only those
    outside a double-quoted field; comma otherwise, including an empty line
    or a tie. LibraryThing's classic export is tab-separated, and one of
    its column names, "Author (First, Last)", carries an unquoted comma —
    so a mere "no comma outside quotes" test would read that file as CSV.
    No `csv.Sniffer` (it is known to guess wrong on single-column and
    quoted files).
    """
    tabs = commas = 0
    in_quotes = False
    for ch in first_line or "":
        if ch == '"':
            in_quotes = not in_quotes
        elif in_quotes:
            continue
        elif ch == "\t":
            tabs += 1
        elif ch == ",":
            commas += 1
    return "\t" if tabs > commas else ","


# Goodreads embeds series in the title: "The Gray Man (Gray Man, #1)".
# Multi-series titles look like "(Series A, #1; Series B, #4)" — we take the
# first pairing and discard the rest.
_SERIES_TITLE_RE = re.compile(
    r"^(?P<title>.+?)\s*"
    r"\((?P<series>[^()#;]+?),?\s+#(?P<pos>\d+(?:\.\d+)?)(?:;[^)]*)?\)\s*$"
)


def split_series_title(raw: str | None) -> tuple[str, str | None, float | None]:
    """Split a Goodreads-style title into (title, series_name, position)."""
    raw = (raw or "").strip()
    m = _SERIES_TITLE_RE.match(raw)
    if not m:
        return raw, None, None
    pos = float(m.group("pos"))
    return m.group("title").strip(), m.group("series").strip(), pos


def detect_format(fieldnames) -> str:
    """Identify the CSV source from its (normalized) header columns."""
    fields = set(fieldnames or [])
    if "exclusive_shelf" in fields:
        return GOODREADS
    if "read_status" in fields:
        return STORYGRAPH
    if "book_id" in fields:
        return LIBRARYTHING
    if "item_type" in fields and "ean_isbn13" in fields:
        return LIBIB
    return GENERIC


def _clean_isbn(value: str | None) -> str | None:
    """Strip Goodreads' Excel wrapper (="...") and validate length.

    Returns a bare 10- or 13-character ISBN, or None. StoryGraph's ISBN/UID
    column can hold non-ISBN UIDs for some editions — those are dropped too.
    """
    if not value:
        return None
    v = value.strip().lstrip("=").strip('"').strip()
    v = v.replace("-", "").replace(" ", "")
    if len(v) == 13 and v.isdigit():
        return v
    if len(v) == 10 and v[:9].isdigit() and (v[9].isdigit() or v[9] in "Xx"):
        return v.upper()
    return None


def _clean_date(value: str | None) -> str | None:
    """Normalize YYYY/MM/DD (both apps' export format) to ISO YYYY-MM-DD."""
    if not value:
        return None
    v = value.strip().replace("/", "-")
    parts = v.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts) and len(parts[0]) == 4:
        return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return None


_TRUTHY = {"1", "true", "yes"}
_FALSY = {"0", "false", "no"}


def _parse_flag(value: str | None) -> bool | None:
    """Parse a generic CSV's own `owned` or `wishlisted` column.

    Accepts 1/0, true/false, yes/no, case-insensitive. Blank or absent (the
    column itself may not exist in the row dict) yields None, and the
    importer treats None as "this file does not say" (G87) — see
    items_csv.py for how each flag is resolved.
    """
    v = (value or "").strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    return None


def _media_type_from(binding: str | None) -> str:
    b = (binding or "").strip().lower()
    if "audio" in b:
        return "audiobook"
    if "kindle" in b or "ebook" in b or b == "digital":
        return "ebook"
    return "book"


_GOODREADS_SHELF_STATUS = {
    "read": "read",
    "currently-reading": "reading",
    "to-read": "want_to_read",
}

_STORYGRAPH_STATUS = {
    "read": "read",
    "currently-reading": "reading",
    "to-read": "want_to_read",
    # did-not-finish intentionally maps to no status
}


def normalize_goodreads(row: dict) -> dict:
    authors = (row.get("author") or "").strip() or None
    additional = (row.get("additional_authors") or "").strip()
    if authors and additional:
        authors = f"{authors}, {additional}"

    shelf = (row.get("exclusive_shelf") or "").strip().lower()
    status = _GOODREADS_SHELF_STATUS.get(shelf)

    title, series_name, series_position = split_series_title(row.get("title"))

    return {
        "title": title,
        "authors": authors,
        "isbn": _clean_isbn(row.get("isbn13")) or _clean_isbn(row.get("isbn")),
        "media_type": _media_type_from(row.get("binding")),
        "publisher": (row.get("publisher") or "").strip() or None,
        "publish_year": (row.get("year_published") or "").strip() or None,
        "page_count": (row.get("number_of_pages") or "").strip() or None,
        "series_name": series_name,
        "series_position": series_position,
        "reading_status": status,
        "date_finished": _clean_date(row.get("date_read")),
        # Goodreads tracks reading, not possession — trust its Owned Copies
        # count instead of assuming everything on a shelf is on a shelf.
        "owned": (row.get("owned_copies") or "").strip().isdigit()
                 and int(row["owned_copies"]) > 0,
        "wishlisted": None,  # generic-only column; Goodreads has no equivalent
        "deleted": None,  # generic-only column; Goodreads has no Trash concept
    }


def normalize_storygraph(row: dict) -> dict:
    owned_raw = (row.get("owned?") or "").strip().lower()

    status = _STORYGRAPH_STATUS.get((row.get("read_status") or "").strip().lower())

    return {
        "title": (row.get("title") or "").strip(),
        "authors": (row.get("authors") or "").strip() or None,
        "isbn": _clean_isbn(row.get("isbn/uid")),
        "media_type": _media_type_from(row.get("format")),
        "publisher": None,
        "publish_year": None,
        "page_count": None,
        "series_name": None,
        "series_position": None,
        "reading_status": status,
        "date_finished": _clean_date(row.get("last_date_read")),
        # Only an explicit "No" marks the book as not owned (wishlist)
        "owned": owned_raw != "no",
        "wishlisted": None,  # generic-only column; StoryGraph has no equivalent
        "deleted": None,  # generic-only column; StoryGraph has no Trash concept
    }


def normalize_generic(row: dict) -> dict:
    """Shelf's own CSV format — mirrors the pre-existing import behavior."""
    raw_media = (row.get("media_type") or "book").strip()
    media_type = config.canonical_media_type(raw_media)
    tags = tags_svc.parse_tag_list(row.get("tags"))
    if media_type != raw_media:
        # The raw value named a retired alias (e.g. kids_book) — that is a
        # statement about the book itself, the same way a live kids_book row
        # earned the tag at boot (database.py's _retire_kids_book), so this
        # row earns it too. Contrast a stale media_type sitting in an
        # in-page form value, which is just a transient and gets no tag —
        # this only fires for a value the row itself actually carried.
        if not any(t.casefold() == "kids" for t in tags):
            tags.append("Kids")
    return {
        "title": (row.get("title") or "").strip(),
        "authors": (row.get("authors") or row.get("author") or "").strip() or None,
        "isbn": (row.get("isbn") or "").strip() or None,
        "media_type": media_type,
        "publisher": (row.get("publisher") or "").strip() or None,
        "publish_year": (row.get("publish_year") or row.get("year") or "").strip() or None,
        "page_count": (row.get("page_count") or row.get("pages") or "").strip() or None,
        "series_name": (row.get("series_name") or row.get("series") or "").strip() or None,
        "series_position": None,
        "reading_status": None,
        "date_finished": None,
        # Both state columns are Shelf's own export (#125). None means the
        # column is absent or blank; items_csv.py applies the defaults.
        "owned": _parse_flag(row.get("owned")),
        "wishlisted": _parse_flag(row.get("wishlisted")),
        # Absent, blank and "0" all mean live (G87 via _parse_flag), so every
        # export written before the `deleted` column still imports every row live
        # (G101's old-file rule).
        "deleted": _parse_flag(row.get("deleted")),
        "tags": tags,
    }


_LT_YEAR_RE = re.compile(r"\b\d{4}\b")

_LT_SERIES_RE = re.compile(r"^(?P<name>.*?)\s*\((?P<pos>\d+(?:\.\d+)?)\)\s*$")

# Built-in LibraryThing collections that decide reading/ownership state
# (decision 7). Every other collection name on a row is a custom category,
# which becomes a tag instead (the kids_book retirement settled tags as
# Shelf's user-category layer).
_LT_COLLECTION_STATUS = {
    "currently reading": "reading",
    "to read": "want_to_read",
    "read but unowned": "read",
}
_LT_RECOGNIZED_COLLECTIONS = {
    "your library", "wishlist", "currently reading", "to read", "read but unowned",
}

_CSV_MAX_TEXT = 1000


def _lt_first_year(*values: str | None) -> str | None:
    """The first four-digit year found across `values`, in order."""
    for value in values:
        if not value:
            continue
        m = _LT_YEAR_RE.search(value)
        if m:
            return m.group(0)
    return None


def _digits_only(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def _lt_strip_isbn_brackets(value: str | None) -> str:
    """LT brackets its ISBN cell (e.g. "[0441013597]") — strip both
    characters wherever they appear before validating."""
    return (value or "").replace("[", "").replace("]", "")


def _lt_isbn(row: dict) -> str | None:
    """`isbn`, then each comma- or space-separated entry of `isbns`; the
    first value `_clean_isbn` accepts wins."""
    isbn = _clean_isbn(_lt_strip_isbn_brackets(row.get("isbn")))
    if isbn:
        return isbn
    isbns_raw = _lt_strip_isbn_brackets(row.get("isbns"))
    for token in re.split(r"[,\s]+", isbns_raw):
        candidate = _clean_isbn(token)
        if candidate:
            return candidate
    return None


_NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


def _lt_display_name(value: str | None) -> str:
    """LibraryThing's sort form, "Last, First", turned round to "First
    Last" — `authors` is a comma-separated list (the item page links each
    piece), so a sort-form name kept as-is becomes two authors, "Herbert"
    and "Frank". "Last, First, Jr." keeps its suffix. Anything else — no
    comma, more commas, an empty side — is returned unchanged, because it is
    not a shape this rule can be sure of."""
    text = (value or "").strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) == 2 and all(parts):
        return f"{parts[1]} {parts[0]}"
    if len(parts) == 3 and all(parts) and parts[2].lower() in _NAME_SUFFIXES:
        return f"{parts[1]} {parts[0]} {parts[2]}"
    return text


def _lt_authors(row: dict) -> str | None:
    """`author_(first,_last)` as-is when present; otherwise `primary_author`
    or `author_(last,_first)`, turned round from LT's "Last, First" sort
    form. `secondary_author` (also sort form) and `other_authors` appended
    with ", " — the same join Goodreads uses."""
    authors = (row.get("author_(first,_last)") or "").strip() or _lt_display_name(
        row.get("primary_author") or row.get("author_(last,_first)")
    )
    authors = authors or None
    secondary = _lt_display_name(row.get("secondary_author"))
    if authors and secondary:
        authors = f"{authors}, {secondary}"
    other = (row.get("other_authors") or "").strip()
    if authors and other:
        authors = f"{authors}, {other}"
    return authors


def _lt_series(raw: str | None) -> tuple[str | None, float | None]:
    """Text before the first ';', then `Name (N)` -> (name, position);
    otherwise the whole value is the name."""
    text = (raw or "").split(";", 1)[0].strip()
    if not text:
        return None, None
    m = _LT_SERIES_RE.match(text)
    if m:
        return m.group("name").strip(), float(m.group("pos"))
    return text, None


def _lt_media_type(value: str | None) -> str:
    """`media`, lowercased. Disc/vinyl arms are checked before the shared
    `_media_type_from` fallback, which knows nothing about them."""
    v = (value or "").strip().lower()
    if "dvd" in v or "blu-ray" in v or "bluray" in v:
        return "dvd"
    if re.search(r"\bcd\b", v):
        return "cd"
    if "vinyl" in v or re.search(r"\blp\b", v):
        return "vinyl"
    return _media_type_from(value)


def _lt_price(value: str | None) -> float | None:
    """Currency symbols and spaces removed. One comma followed by exactly
    two trailing digits and no '.' is a decimal comma (E12,50 -> 12.5); any
    other comma is a thousands separator ($1,250.00 -> 1250.0). Kept only
    if it parses as a finite float >= 0 (matches
    CHECK(acquisition_price >= 0) on item_copies)."""
    if not value:
        return None
    # Strip currency symbols (Unicode category Sc), whitespace and a
    # three-letter currency code — nothing else. Any other character left
    # over (a letter, a bracket) means this is not a plain price, and
    # stripping it would turn "£5 (2 for 1)" into 521.
    v = "".join(ch for ch in value if unicodedata.category(ch) != "Sc" and not ch.isspace())
    v = re.sub(r"^[A-Za-z]{3}|[A-Za-z]{3}$", "", v)
    if not re.fullmatch(r"-?[0-9][0-9,]*(?:\.[0-9]+)?", v):
        return None
    if "." not in v and re.fullmatch(r"-?\d+,\d{2}", v):
        v = v.replace(",", ".")
    else:
        v = v.replace(",", "")
    try:
        f = float(v)
    except ValueError:
        return None
    if not math.isfinite(f) or f < 0:
        return None
    return f


def _lt_copy(row: dict) -> dict | None:
    """The new item's primary copy (decision 10) — parsed here, before any
    write, so a bad price or date can never raise after the insert (G85).
    `None` when every source column was blank; `{}` when they held data but
    nothing parsed (so no copy is written, and nothing is reported, because
    the columns were read — G87)."""
    raw_acquired = row.get("acquired") or row.get("date_acquired") or ""
    raw_from_where = row.get("from_where") or ""
    raw_price = row.get("purchase_price") or ""
    raw_condition = row.get("condition") or ""
    if not (raw_acquired.strip() or raw_from_where.strip()
            or raw_price.strip() or raw_condition.strip()):
        return None

    copy: dict = {}
    acquired_date = _clean_date(raw_acquired)
    if acquired_date:
        copy["acquired_date"] = acquired_date
    from_where = raw_from_where.strip()
    if from_where and len(from_where) <= _CSV_MAX_TEXT:
        copy["acquisition_source"] = from_where
    price = _lt_price(raw_price)
    if price is not None:
        copy["acquisition_price"] = price
    condition = raw_condition.strip()
    if condition and len(condition) <= _CSV_MAX_TEXT:
        copy["condition"] = condition
    return copy


def _comma_tags(raw: str | None, extra: list[str] = ()) -> list[str]:
    """A comma-split tag cell (LibraryThing and Libib both separate tags
    with commas). Each piece through `tags_svc.normalize_tag`, blanks
    dropped, `extra` appended, deduplicated case-insensitively with the
    first spelling winning — as `parse_tag_list` does, without touching its
    ';' contract (Shelf's own export writes "; ")."""
    seen: set[str] = set()
    out: list[str] = []
    for piece in (raw or "").split(",") + list(extra):
        name = tags_svc.normalize_tag(piece)
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def normalize_librarything(row: dict) -> dict:
    """LibraryThing's TSV (classic) or CSV (spreadsheet) export."""
    collections_raw = [c.strip() for c in (row.get("collections") or "").split(",") if c.strip()]
    collections_lower = {c.lower() for c in collections_raw}
    custom_collections = [
        c for c in collections_raw if c.lower() not in _LT_RECOGNIZED_COLLECTIONS
    ]

    owned = not ("wishlist" in collections_lower or "read but unowned" in collections_lower)
    wishlisted = True if "wishlist" in collections_lower else None

    status = None
    for name, mapped in _LT_COLLECTION_STATUS.items():
        if name in collections_lower:
            status = mapped
            break
    date_finished = _clean_date(row.get("date_read") or row.get("date_ended"))
    if status is None and date_finished:
        status = "read"

    series_name, series_position = _lt_series(row.get("series"))

    return {
        "title": (row.get("title") or "").strip(),
        "authors": _lt_authors(row),
        "isbn": _lt_isbn(row),
        "media_type": _lt_media_type(row.get("media")),
        "publisher": None,  # LT's `publication` cell is a compound
                             # place/publisher/year string — reported as
                             # unmapped rather than guessed apart.
        "publish_year": _lt_first_year(row.get("publication_date"), row.get("date")),
        "page_count": _digits_only(row.get("page_count")),
        "series_name": series_name,
        "series_position": series_position,
        "reading_status": status,
        "date_finished": date_finished,
        "owned": owned,
        "wishlisted": wishlisted,
        "deleted": None,  # LT has no Trash concept
        "tags": _comma_tags(row.get("tags") or row.get("your_tags"), custom_collections),
        "copy": _lt_copy(row),
    }


# Libib's `item_type` values, lowercased with spaces/`_`/`-` removed, mapped
# onto Shelf's media types. Every other value is a row error (see
# _libib_media_type) — never defaulted to `book` (G57, the #90 lesson).
_LIBIB_MEDIA_TYPE_MAP = {
    "book": "book",
    "movie": "dvd",
    "movies": "dvd",
    "music": "cd",
    "videogame": "video_game",
    "videogames": "video_game",
    "game": "video_game",
    "games": "video_game",
}

# Completed -> read, In progress -> reading. Not begun and Abandoned (and
# anything else) map to no status, mirroring StoryGraph's did-not-finish
# rule (_STORYGRAPH_STATUS).
_LIBIB_STATUS = {
    "completed": "read",
    "in progress": "reading",
}


def _libib_media_type(raw: str | None) -> str:
    """`item_type`, lowercased with spaces/`_`/`-` removed, mapped onto
    Shelf's media types. An unrecognized value raises before any write —
    filing it as a book would be convincing and wrong (the #90 lesson)."""
    value = raw or ""
    normalized = re.sub(r"[\s_-]+", "", value.strip().lower())
    media_type = _LIBIB_MEDIA_TYPE_MAP.get(normalized)
    if media_type is None:
        raise ValueError(f"Unknown media type: {value!r}")
    return media_type


def normalize_libib(row: dict) -> dict:
    """Libib's CSV export. Every row is owned (decision 8) — Libib
    catalogues possessions, and its export has no ownership column."""
    media_type = _libib_media_type(row.get("item_type"))

    creators = (row.get("creators") or "").strip()
    dropped: list[tuple[str, str]] = []
    if media_type == "video_game":
        # Libib puts the platform here for a game, not an author — reported
        # as dropped rather than written to authors (design, Out of scope:
        # game platform matching is a lookup problem of its own).
        authors = None
        if creators:
            dropped.append(("creators", "game_platform"))
    else:
        authors = creators or None

    isbn = None
    upc = None
    if media_type == "book":
        isbn = _clean_isbn(row.get("ean_isbn13")) or _clean_isbn(row.get("upc_isbn10"))
    else:
        for candidate in (row.get("ean_isbn13"), row.get("upc_isbn10")):
            digits = _digits_only(candidate)
            if digits and len(digits) in (12, 13):
                upc = upc_svc.normalize_upc(digits)  # G130 — EAN-13 storage form
                break

    status = _LIBIB_STATUS.get((row.get("status") or "").strip().lower())

    return {
        "title": (row.get("title") or "").strip(),
        "authors": authors,
        "isbn": isbn,
        "upc": upc,
        "media_type": media_type,
        "publisher": (row.get("publisher") or "").strip() or None,
        "publish_year": _lt_first_year(row.get("publish_date")),
        "page_count": _digits_only(row.get("length")) if media_type == "book" else None,
        "series_name": (row.get("group") or "").strip() or None,
        "series_position": None,
        "reading_status": status,
        "date_finished": _clean_date(row.get("completed") or row.get("completed_date")),
        "owned": True,
        "wishlisted": None,
        "deleted": None,
        "tags": _comma_tags(row.get("tags")),
        "dropped": dropped,
    }


NORMALIZERS = {
    GOODREADS: normalize_goodreads,
    STORYGRAPH: normalize_storygraph,
    LIBRARYTHING: normalize_librarything,
    LIBIB: normalize_libib,
    GENERIC: normalize_generic,
}

# Every normalized header column each format's normalizer actually reads.
# The route diffs a row's non-blank columns against this set to report the
# rest as "unmapped" in the `dropped` response key (decision 4). T2 and T3
# add the LibraryThing and Libib entries.
CONSUMED_COLUMNS: dict[str, frozenset[str]] = {
    GENERIC: frozenset({
        "title", "authors", "author", "isbn", "media_type", "publisher",
        "publish_year", "year", "page_count", "pages", "series_name",
        "series", "owned", "wishlisted", "deleted", "tags",
    }),
    GOODREADS: frozenset({
        "title", "author", "additional_authors", "exclusive_shelf", "isbn13",
        "isbn", "binding", "publisher", "year_published", "number_of_pages",
        "date_read", "owned_copies",
    }),
    STORYGRAPH: frozenset({
        "title", "authors", "isbn/uid", "format", "read_status",
        "last_date_read", "owned?",
    }),
    LIBRARYTHING: frozenset({
        "title", "primary_author", "author_(first,_last)", "author_(last,_first)",
        "secondary_author", "other_authors", "isbn", "isbns", "publication_date", "date",
        "page_count", "series", "media", "collections", "date_read",
        "date_ended", "tags", "your_tags",
        # Detection-only (reporting it would be noise) and acquisition
        # columns, which are read but land on the copy, not the item.
        "book_id", "acquired", "date_acquired", "from_where",
        "purchase_price", "condition",
    }),
    LIBIB: frozenset({
        "item_type", "title", "creators", "ean_isbn13", "upc_isbn10",
        "publisher", "publish_date", "group", "tags", "status",
        "completed", "completed_date", "length",
    }),
}
