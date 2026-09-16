"""Issue #125 T5: after every writer, on the wishlist iff owned = 0.

The write funnel (`app/services/item_write.py`) accepts a virtual
`wishlisted: bool` field and writes `list_items` membership through
`app/services/lists.py`. T5 threads `wishlisted` through every scan,
manual-add, UPC, store, intake, periodicals and music call site that sets
`owned = 0`. Each test here drives one such writer end to end and then
calls `_assert_wishlist_invariant(db)` — the fixture-sanity check from
`tests/conftest.py` that fails loudly on any `owned = 0` row missing from
the wishlist, or any wishlisted row that is `owned = 1`.

These are the sites the plan's recon found with **no** wishlist-mode pin
at all before this task: the film UPC branch, the store's unreadable and
bare-fallback rows, periodicals confirm, and music add. Everywhere else
that already had a wishlist-mode test gained one line — see
test_scan_modes.py, test_upc_manual_add.py, test_scan_upc_enrichment.py,
test_store.py and test_intake.py.
"""

from unittest.mock import AsyncMock, patch

from app.routers import hardcover as hc_router
from app.services import (
    komga_records,
    lists,
    musicbrainz,
    periodicals,
    provider_result,
    romm_records,
    tmdb,
    upcitemdb,
)
from tests.conftest import _assert_wishlist_invariant, _insert_item
from tests.test_komga_records import _candidate as _komga_candidate
from tests.test_reading_imports import GOODREADS_HEADER, _gr_row, _post_csv
from tests.test_romm_records import _candidate as _romm_candidate

DVD_UPC = "085391163121"
GOODFELLAS = (
    "Goodfellas [DVD]  Feature Thriller Drama  Action  Suspense  Drama  "
    "Crime  Drama Drama"
)

# ISSN 0161-7370 (Popular Science) encoded as a 977 EAN — a valid periodical
# barcode, per tests/test_periodicals.py.
POPULAR_SCIENCE_EAN = "9770161737008"

_MUSIC_RELEASE = {
    "title": "The Dark Side of the Moon",
    "artist_credit": "Pink Floyd",
    "musicbrainz_release_id": "11111111-1111-1111-1111-111111111111",
    "musicbrainz_release_group_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "release_type": "Album",
    "release_status": "Official",
    "release_date": "1973-03-23",
    "first_release_date": "1973-03-01",
    "country": "GB",
    "label": "Harvest",
    "catalog_number": "SHVL 804",
    "barcode": None,
    "packaging": "Gatefold Cover",
    "media_count": 1,
    "format_summary": "12\" Vinyl",
    "source": "musicbrainz",
    "media": [
        {
            "position": 1,
            "format": "12\" Vinyl",
            "title": None,
            "track_count": 1,
            "tracks": [
                {
                    "position": 1,
                    "number": "A1",
                    "title": "Speak to Me",
                    "artist_credit": "Pink Floyd",
                    "duration_ms": 65000,
                    "musicbrainz_recording_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                },
            ],
        }
    ],
}


def _set_tmdb_key(monkeypatch, key="0123456789abcdef0123456789abcdef"):
    monkeypatch.setenv("TMDB_API_KEY", key)


class TestFilmUpcWishlistMode:
    """`_scan_upc` (items_common.py) — the DVD/disc UPC branch, wishlist mode.

    Mocked the way TestGameScanHonoursWishlistMode mocks the game UPC branch
    in tests/test_scan_upc_enrichment.py:277 — here the film provider (TMDb)
    stands in for IGDB.
    """

    def test_wishlist_mode_stores_unowned_and_is_on_the_wishlist(
        self, editor_client, db, monkeypatch
    ):
        async def _lookup(upc, client):
            return provider_result.found(
                "upcitemdb", {"title": GOODFELLAS, "category": None, "brand": None, "images": []}
            )
        monkeypatch.setattr(upcitemdb, "lookup", _lookup)

        async def _lookup_by_title(query, key, client):
            return provider_result.no_match("tmdb")
        monkeypatch.setattr(tmdb, "lookup_by_title", _lookup_by_title)
        _set_tmdb_key(monkeypatch)

        resp = editor_client.post(
            "/api/scan",
            data={"isbn": DVD_UPC, "media_type": "dvd", "mode": "wishlist"},
        )

        assert resp.status_code == 200
        row = db.execute("SELECT * FROM items WHERE upc IS NOT NULL").fetchone()
        assert row["owned"] == 0
        _assert_wishlist_invariant(db)
        assert "wishlisted" in resp.text.lower()


class TestStoreQueueWishlistMembership:
    """store.py — the unreadable-barcode row and the bare-fallback row.

    Both are `insert_item(..., owned=0, ...)` sites that never went through
    a follow-up UPDATE, so a missing `wishlisted=True` here would silently
    create an owned=0 row with no wishlist membership — the exact bug the
    per-writer pins exist to catch.
    """

    def test_unreadable_barcode_row_is_on_the_wishlist(self, admin_client, db):
        resp = admin_client.post("/api/store/queue", json={"isbns": ["not-an-isbn"]})
        result = resp.json()["results"][0]
        assert result["status"] == "unreadable"

        row = db.execute("SELECT owned FROM items WHERE id = ?", (result["item_id"],)).fetchone()
        assert row["owned"] == 0
        _assert_wishlist_invariant(db)

    def test_bare_fallback_row_is_on_the_wishlist(self, admin_client, db):
        with patch("app.routers.items_common._lookup_metadata",
                   new=AsyncMock(return_value=(None, None, {}, False))):
            resp = admin_client.post("/api/store/queue", json={"isbns": ["9789000000111"]})
        result = resp.json()["results"][0]
        assert result["status"] == "added_bare"

        row = db.execute("SELECT owned FROM items WHERE id = ?", (result["item_id"],)).fetchone()
        assert row["owned"] == 0
        _assert_wishlist_invariant(db)


class TestPeriodicalsConfirmWishlistMode:
    """periodicals.py — /api/periodicals/confirm with mode=wishlist."""

    def test_wishlist_mode_stores_unowned_and_is_on_the_wishlist(self, editor_client, db):
        resp = editor_client.post(
            "/api/periodicals/confirm",
            data={
                "raw_barcode": POPULAR_SCIENCE_EAN,
                "publication_title": "Popular Science",
                "mode": "wishlist",
            },
        )
        assert resp.status_code in (200, 303)

        row = db.execute(
            "SELECT owned FROM items WHERE title LIKE 'Popular Science%'"
        ).fetchone()
        assert row is not None
        assert row["owned"] == 0
        _assert_wishlist_invariant(db)


class TestMusicAddWishlistMode:
    """music.py — /api/music/add with owned=0."""

    def test_owned_zero_stores_unowned_and_is_on_the_wishlist(
        self, editor_client, db, monkeypatch
    ):
        async def _lookup_release(release_id, client):
            return provider_result.found("musicbrainz", _MUSIC_RELEASE)
        monkeypatch.setattr(musicbrainz, "lookup_release", _lookup_release)

        resp = editor_client.post(
            "/api/music/add",
            data={
                "release_id": _MUSIC_RELEASE["musicbrainz_release_id"],
                "media_type": "vinyl",
                "owned": "0",
            },
        )
        assert resp.status_code in (200, 303)

        row = db.execute(
            "SELECT owned FROM items WHERE title = ?", (_MUSIC_RELEASE["title"],)
        ).fetchone()
        assert row is not None
        assert row["owned"] == 0
        _assert_wishlist_invariant(db)


class TestHardcoverWishlistMembership:
    """hardcover.py — add-to-shelf and library sync (T6)."""

    def test_add_to_shelf_is_a_member(self, editor_client, db):
        resp = editor_client.post(
            "/api/hardcover/add-to-shelf",
            json={"title": "Add To Shelf Wishlist"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

        row = db.execute("SELECT owned FROM items WHERE id = ?", (body["item_id"],)).fetchone()
        assert row["owned"] == 0
        assert lists.is_member(db, lists.WISHLIST, body["item_id"])
        _assert_wishlist_invariant(db)

    def test_sync_want_to_read_book_is_a_member(self, db):
        result, _cover_job = hc_router._import_single_book_metadata(
            {"title": "Sync Want To Read", "reading_status": "want_to_read"},
            overwrite=False, title_index={},
        )
        assert result == "added"

        item = db.execute(
            "SELECT id, owned FROM items WHERE title = ?", ("Sync Want To Read",)
        ).fetchone()
        assert item["owned"] == 0
        assert lists.is_member(db, lists.WISHLIST, item["id"])
        _assert_wishlist_invariant(db)

    def test_sync_read_book_is_not_a_member(self, db):
        result, _cover_job = hc_router._import_single_book_metadata(
            {"title": "Sync Already Read", "reading_status": "read"},
            overwrite=False, title_index={},
        )
        assert result == "added"

        item = db.execute(
            "SELECT id, owned FROM items WHERE title = ?", ("Sync Already Read",)
        ).fetchone()
        assert item["owned"] == 1
        assert not lists.is_member(db, lists.WISHLIST, item["id"])
        _assert_wishlist_invariant(db)


class TestCsvImportWishlistMembership:
    """items_csv.py — new-row insert and the tracker-update path (T6)."""

    def test_new_row_with_to_read_wishlist_is_a_member(self, admin_client, db):
        csv_content = GOODREADS_HEADER + "\n" + _gr_row(
            title="CSV Wishlist New", isbn13="9780553283686", isbn10="0553283685",
            shelf="to-read", date_read="")
        data = _post_csv(admin_client, csv_content, to_read_wishlist="1").json()
        assert data["imported"] == 1

        item = db.execute(
            "SELECT id, owned FROM items WHERE isbn = '9780553283686'"
        ).fetchone()
        assert item["owned"] == 0
        assert lists.is_member(db, lists.WISHLIST, item["id"])
        _assert_wishlist_invariant(db)

    def test_tracker_update_to_unowned_makes_it_a_member(self, admin_client, db):
        item_id = _insert_item(
            db, title="Tracker To Unowned", isbn="9780553283686", media_type="book", owned=1
        )
        db.execute("COMMIT")

        csv_content = GOODREADS_HEADER + "\n" + _gr_row(
            title="Tracker To Unowned", isbn13="9780553283686", isbn10="0553283685",
            owned_copies="0")
        data = _post_csv(admin_client, csv_content, mode="update").json()
        assert data["imported"] == 1

        row = db.execute("SELECT owned FROM items WHERE id = ?", (item_id,)).fetchone()
        assert row["owned"] == 0
        assert lists.is_member(db, lists.WISHLIST, item_id)
        _assert_wishlist_invariant(db)

    def test_tracker_update_to_owned_removes_membership(self, admin_client, db):
        item_id = _insert_item(
            db, title="Tracker To Owned", isbn="9780553283686", media_type="book", owned=0
        )
        db.execute("COMMIT")

        csv_content = GOODREADS_HEADER + "\n" + _gr_row(
            title="Tracker To Owned", isbn13="9780553283686", isbn10="0553283685",
            owned_copies="1")
        data = _post_csv(admin_client, csv_content, mode="update").json()
        assert data["imported"] == 1

        row = db.execute("SELECT owned FROM items WHERE id = ?", (item_id,)).fetchone()
        assert row["owned"] == 1
        assert not lists.is_member(db, lists.WISHLIST, item_id)
        _assert_wishlist_invariant(db)


class TestEditFormWishlistMembership:
    """items.py's edit form — the owned checkbox (T6)."""

    def test_owned_one_to_zero_is_a_member(self, editor_client, db):
        item_id = _insert_item(db, title="Edit To Unowned", isbn="9780000000026", owned=1)
        db.commit()

        resp = editor_client.post(f"/api/items/{item_id}", data={"owned": "0"},
                                  follow_redirects=False)
        assert resp.status_code == 303

        row = db.execute("SELECT owned FROM items WHERE id = ?", (item_id,)).fetchone()
        assert row["owned"] == 0
        assert lists.is_member(db, lists.WISHLIST, item_id)
        _assert_wishlist_invariant(db)

    def test_owned_zero_to_one_removes_membership(self, editor_client, db):
        item_id = _insert_item(db, title="Edit To Owned", isbn="9780000000026", owned=0)
        db.commit()

        resp = editor_client.post(f"/api/items/{item_id}", data={"owned": "1"},
                                  follow_redirects=False)
        assert resp.status_code == 303

        row = db.execute("SELECT owned FROM items WHERE id = ?", (item_id,)).fetchone()
        assert row["owned"] == 1
        assert not lists.is_member(db, lists.WISHLIST, item_id)
        _assert_wishlist_invariant(db)


class TestBulkEditWishlistMembership:
    """items.py's /api/items/bulk-update — the owned field (T6)."""

    def _three_owned_items(self, db):
        ids = [
            _insert_item(db, title=f"Bulk Owned {i}", isbn=f"978000000{i:04d}", owned=1)
            for i in range(3)
        ]
        db.commit()
        return ids

    def test_bulk_owned_zero_makes_all_members(self, admin_client, db):
        ids = self._three_owned_items(db)

        resp = admin_client.post(
            "/api/items/bulk-update",
            json={"item_ids": ids, "updates": {"owned": 0}},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        for item_id in ids:
            row = db.execute("SELECT owned FROM items WHERE id = ?", (item_id,)).fetchone()
            assert row["owned"] == 0
            assert lists.is_member(db, lists.WISHLIST, item_id)
        _assert_wishlist_invariant(db)

    def test_bulk_owned_one_removes_all_membership(self, admin_client, db):
        ids = [
            _insert_item(db, title=f"Bulk Unowned {i}", isbn=f"978000001{i:04d}", owned=0)
            for i in range(3)
        ]
        db.commit()

        resp = admin_client.post(
            "/api/items/bulk-update",
            json={"item_ids": ids, "updates": {"owned": 1}},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        for item_id in ids:
            row = db.execute("SELECT owned FROM items WHERE id = ?", (item_id,)).fetchone()
            assert row["owned"] == 1
            assert not lists.is_member(db, lists.WISHLIST, item_id)
        _assert_wishlist_invariant(db)

    def test_bulk_invalid_owned_is_still_refused(self, admin_client, db):
        ids = self._three_owned_items(db)

        resp = admin_client.post(
            "/api/items/bulk-update",
            json={"item_ids": ids, "updates": {"owned": "2"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["message"] == "Owned must be 0 or 1"

        for item_id in ids:
            row = db.execute("SELECT owned FROM items WHERE id = ?", (item_id,)).fetchone()
            assert row["owned"] == 1
        _assert_wishlist_invariant(db)


class TestServiceBackedInsertsAreNeverMembers:
    """RomM (`romm_records.py`) and Komga (`komga_records.py`) insert with
    `owned = 1` through `insert_item` and never touch ownership again — they
    never pass `wishlisted`, so `_apply_membership` must write nothing, and
    the row must never become a wishlist member (T7)."""

    def test_romm_insert_is_not_a_member(self, db):
        result = romm_records.persist_candidate(db, _romm_candidate())

        row = db.execute(
            "SELECT owned FROM items WHERE id = ?", (result["item_id"],)
        ).fetchone()
        assert row["owned"] == 1
        assert not lists.is_member(db, lists.WISHLIST, result["item_id"])
        _assert_wishlist_invariant(db)

    def test_komga_insert_is_not_a_member(self, db):
        result = komga_records.persist_candidate(db, _komga_candidate())

        row = db.execute(
            "SELECT owned FROM items WHERE id = ?", (result["item_id"],)
        ).fetchone()
        assert row["owned"] == 1
        assert not lists.is_member(db, lists.WISHLIST, result["item_id"])
        _assert_wishlist_invariant(db)
