"""Settings → Features: the toggle list, its warnings and its write route."""

import html
import re

import pytest

from app.features import FEATURES, feature_enabled
from tests.conftest import _insert_item
from tests.test_features_gate import off


def _row(page, key):
    """The markup of one feature's card."""
    m = re.search(
        rf'<div data-testid="feature-row-{key}".*?</form>', page, re.S
    )
    assert m, f"no row for {key}"
    return m.group(0)


def _confirm(page, key):
    m = re.search(r'data-confirm="([^"]*)"', _row(page, key))
    return html.unescape(m.group(1)) if m else None


def _borrower(db, name):
    return db.execute("INSERT INTO borrowers (name) VALUES (?)", (name,)).lastrowid


def _loan(db, item_id, borrower_id, checked_in=None):
    db.execute(
        "INSERT INTO checkouts (item_id, borrower_id, checked_in) VALUES (?, ?, ?)",
        (item_id, borrower_id, checked_in),
    )


def _share(db, token):
    db.execute("INSERT INTO share_links (token, scope) VALUES (?, 'collection')", (token,))


def test_lists_every_feature_on_by_default(admin_client):
    page = admin_client.get("/settings").text
    assert 'data-testid="tab-features"' in page
    for key in FEATURES:
        row = _row(page, key)
        assert 'data-feature-state="on"' in row
        assert 'value="0"' in row and "Turn off" in row


def test_turn_off_and_back_on(admin_client):
    resp = admin_client.post("/api/settings/features/stats", data={"enabled": "0"},
                             follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/settings"
    assert feature_enabled("stats") is False
    row = _row(admin_client.get("/settings").text, "stats")
    assert 'data-feature-state="off"' in row and "Turn on" in row
    assert "data-confirm" not in row  # turning on never asks

    admin_client.post("/api/settings/features/stats", data={"enabled": "1"})
    assert feature_enabled("stats") is True


def test_editor_gets_role_refusal(editor_client):
    resp = editor_client.post("/api/settings/features/stats", data={"enabled": "0"},
                              follow_redirects=False)
    assert resp.status_code == 403
    assert feature_enabled("stats") is True


def test_unknown_key_is_404(admin_client):
    resp = admin_client.post("/api/settings/features/nope", data={"enabled": "0"})
    assert resp.status_code == 404


def test_bad_value_changes_nothing(admin_client):
    resp = admin_client.post("/api/settings/features/stats", data={"enabled": "off"})
    assert resp.status_code == 400
    assert feature_enabled("stats") is True


def test_share_warning_counts_links(admin_client, db):
    _share(db, "a")
    _share(db, "b")
    db.commit()
    msg = _confirm(admin_client.get("/settings").text, "share")
    assert "2 active share links stop working" in msg
    assert msg.endswith("Turn it off anyway?")


def test_single_share_link_is_singular(admin_client, db):
    _share(db, "a")
    db.commit()
    assert "1 active share link stops working" in _confirm(admin_client.get("/settings").text, "share")


def test_lending_warning_counts_live_open_loans(admin_client, db):
    a, b = _borrower(db, "Ann"), _borrower(db, "Bob")
    i1 = _insert_item(db, title="One", isbn="9780000000019")
    i2 = _insert_item(db, title="Two", isbn="9780000000026")
    i3 = _insert_item(db, title="Three", isbn="9780000000033",
                      deleted_at="2026-01-01 00:00:00")
    i4 = _insert_item(db, title="Four", isbn="9780000000040")
    _loan(db, i1, a)
    _loan(db, i2, b)
    _loan(db, i3, b)  # on a trashed item: does not count
    _loan(db, i4, a, checked_in="2026-01-02 00:00:00")  # returned: does not count
    db.commit()
    msg = _confirm(admin_client.get("/settings").text, "lending")
    assert "2 open loans to 2 borrowers stay recorded" in msg
    assert "overdue reminders pause" in msg


def test_zero_probes_mean_no_confirm(admin_client):
    page = admin_client.get("/settings").text
    for key in ("stats", "share", "lending"):
        assert _confirm(page, key) is None


def test_data_survives_disable_and_enable(admin_client, db):
    a = _borrower(db, "Ann")
    _loan(db, _insert_item(db), a)
    _share(db, "tok")
    db.commit()

    def counts():
        return [db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("checkouts", "borrowers", "share_links")]

    before = counts()
    for key in ("lending", "share"):
        admin_client.post(f"/api/settings/features/{key}", data={"enabled": "0"})
    assert counts() == before
    for key in ("lending", "share"):
        admin_client.post(f"/api/settings/features/{key}", data={"enabled": "1"})
    assert counts() == before


def _needs_setup(page, key):
    return "data-feature-needs-setup" in _row(page, key)


def test_hardcover_needs_setup_without_a_token(admin_client):
    assert _needs_setup(admin_client.get("/settings").text, "hardcover")


def test_hardcover_configured_by_env_only_token(admin_client, monkeypatch):
    monkeypatch.setenv("HARDCOVER_TOKEN", "env-only")
    assert not _needs_setup(admin_client.get("/settings").text, "hardcover")


def test_features_without_setup_never_say_needs_setup(admin_client):
    page = admin_client.get("/settings").text
    for key, f in FEATURES.items():
        if f.configured is None:
            assert not _needs_setup(page, key), key


def test_disabled_feature_can_be_turned_on_from_settings(admin_client):
    off("series")
    row = _row(admin_client.get("/settings").text, "series")
    assert 'value="1"' in row and "Turn on" in row
