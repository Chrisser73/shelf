"""`locations.find_by_path` and `resolve_or_create` (CSV round-trip, #145)."""

import pytest

from app.services import locations
from app.services.locations import LocationError


def _count(db):
    return db.execute("SELECT COUNT(*) FROM locations").fetchone()[0]


def test_exact_and_case_insensitive_top_level_match(db):
    office = locations.create_location(db, "Office")
    db.commit()

    assert locations.resolve_or_create(db, "Office") == (office, False)
    assert locations.resolve_or_create(db, "oFFice") == (office, False)
    assert _count(db) == 1


def test_nested_path_matches_by_full_path(db):
    office = locations.create_location(db, "Office")
    shelf = locations.create_location(db, "Shelf 2", parent_id=office)
    db.commit()

    assert locations.resolve_or_create(db, "Office / Shelf 2") == (shelf, False)
    assert locations.resolve_or_create(db, "office / shelf 2") == (shelf, False)
    assert _count(db) == 2


def test_miss_creates_top_level_node_once(db):
    loc_id, created = locations.resolve_or_create(db, "  Garage  ")
    assert created is True
    row = db.execute(
        "SELECT name, label, parent_id FROM locations WHERE id = ?", (loc_id,)
    ).fetchone()
    assert (row["name"], row["label"], row["parent_id"]) == ("Garage", "Garage", None)

    assert locations.resolve_or_create(db, "Garage") == (loc_id, False)
    assert _count(db) == 1


def test_unmatched_path_raises_and_writes_nothing(db):
    locations.create_location(db, "Office")
    db.commit()
    before = _count(db)

    with pytest.raises(LocationError, match='location "A / B" not found'):
        locations.resolve_or_create(db, "A / B")

    assert _count(db) == before
    assert locations.find_by_path(db, "A") is None


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_raises(db, name):
    with pytest.raises(LocationError):
        locations.resolve_or_create(db, name)
    assert _count(db) == 0


def test_find_by_path_miss_returns_none(db):
    assert locations.find_by_path(db, "Nowhere") is None
