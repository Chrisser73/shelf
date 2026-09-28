"""T8: each of the three background jobs skips its pass while its feature is
off — no service call, no last-sync/last-sent stamp written — and resumes on
the very next pass once the feature is turned back on (no restart needed).

See tests/test_loan_reminders.py for the pre-existing digest-task tests,
which this file leaves unchanged; it only adds feature-gate coverage on top.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.features import set_feature_enabled
from tests.conftest import _insert_borrower, _insert_item


def _set_setting(db, key, value):
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )


def _stamp(db, key):
    return db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()


def _toggle(key, enabled):
    """Flip a feature flag on its own committed connection.

    `set_feature_enabled` drops the flag/nav caches itself, but only once its
    write actually commits — a fresh `get_db()` connection (rather than the
    test's own `db` fixture connection, which stays open/uncommitted until
    teardown) is what makes the flip visible to the pass under test.
    """
    from app.database import get_db
    with get_db() as conn:
        set_feature_enabled(conn, key, enabled)


class TestAbsSyncPassFeatureGate:
    def _seed(self, db):
        _set_setting(db, "abs_sync_interval", "daily")
        _set_setting(db, "abs_url", "https://abs.example")
        _set_setting(db, "abs_token", "tok")
        db.execute("COMMIT")

    @pytest.mark.asyncio
    async def test_off_skips_sync_and_writes_no_stamp(self, db):
        from app.main import _abs_sync_pass
        self._seed(db)
        _toggle("abs_sync", False)

        with patch("app.services.audiobookshelf.sync", new=AsyncMock()) as sync:
            assert await _abs_sync_pass() is False
        sync.assert_not_awaited()
        assert _stamp(db, "abs_last_sync") is None

    @pytest.mark.asyncio
    async def test_on_after_off_syncs_and_writes_stamp(self, db):
        from app.main import _abs_sync_pass
        self._seed(db)
        _toggle("abs_sync", False)
        with patch("app.services.audiobookshelf.sync", new=AsyncMock()) as sync:
            assert await _abs_sync_pass() is False
        sync.assert_not_awaited()
        assert _stamp(db, "abs_last_sync") is None

        _toggle("abs_sync", True)
        with patch("app.services.audiobookshelf.sync", new=AsyncMock()) as sync:
            assert await _abs_sync_pass() is True
        sync.assert_awaited_once()
        assert _stamp(db, "abs_last_sync") is not None


class TestHardcoverSyncPassFeatureGate:
    def _seed(self, db):
        _set_setting(db, "hc_sync_interval", "daily")
        _set_setting(db, "hardcover_token", "tok")
        db.execute("COMMIT")

    @pytest.mark.asyncio
    async def test_off_skips_sync_and_writes_no_stamp(self, db):
        from app.main import _hardcover_sync_pass
        self._seed(db)
        _toggle("hardcover", False)

        with patch("app.services.hardcover.sync_reading_statuses", new=AsyncMock()) as sync:
            assert await _hardcover_sync_pass() is False
        sync.assert_not_awaited()
        assert _stamp(db, "hc_last_sync") is None

    @pytest.mark.asyncio
    async def test_on_after_off_syncs_and_writes_stamp(self, db):
        from app.main import _hardcover_sync_pass
        self._seed(db)
        _toggle("hardcover", False)
        with patch("app.services.hardcover.sync_reading_statuses", new=AsyncMock()) as sync:
            assert await _hardcover_sync_pass() is False
        sync.assert_not_awaited()
        assert _stamp(db, "hc_last_sync") is None

        _toggle("hardcover", True)
        with patch("app.services.hardcover.sync_reading_statuses", new=AsyncMock()) as sync:
            assert await _hardcover_sync_pass() is True
        sync.assert_awaited_once()
        assert _stamp(db, "hc_last_sync") is not None


class TestLoanRemindersFeatureGate:
    def _seed_overdue(self, db):
        item_id = _insert_item(db, title="Very Late Book", isbn="9789000002019")
        borrower_id = _insert_borrower(db, name="Slow Reader")
        db.execute(
            "INSERT INTO checkouts (item_id, borrower_id, checked_out, due_date, checked_in) "
            "VALUES (?, ?, datetime('now', '-60 days'), NULL, NULL)",
            (item_id, borrower_id),
        )
        _set_setting(db, "notify_url", "https://ntfy.example/shelf")
        db.execute("COMMIT")

    @pytest.mark.asyncio
    async def test_off_skips_send_and_writes_no_stamp(self, db):
        from app.main import check_loan_reminders
        self._seed_overdue(db)
        _toggle("lending", False)

        with patch("app.services.notify.send_notification", new=AsyncMock()) as send:
            assert await check_loan_reminders() is False
        send.assert_not_awaited()
        assert _stamp(db, "loan_reminder_last_sent") is None

    @pytest.mark.asyncio
    async def test_on_after_off_sends_and_writes_stamp(self, db):
        from app.main import check_loan_reminders
        self._seed_overdue(db)
        _toggle("lending", False)
        with patch("app.services.notify.send_notification", new=AsyncMock()) as send:
            assert await check_loan_reminders() is False
        send.assert_not_awaited()
        assert _stamp(db, "loan_reminder_last_sent") is None

        _toggle("lending", True)
        with patch("app.services.notify.send_notification", new=AsyncMock(return_value=True)) as send:
            assert await check_loan_reminders() is True
        send.assert_awaited_once()
        assert _stamp(db, "loan_reminder_last_sent") is not None
