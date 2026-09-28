"""E2E: Settings → Features round trips — the disabled page, a probe-gated
confirm, and turning a feature back on from its own disabled page.

**Scope note (T11, 2026-09-27).** The plan's third scenario — "scan a 977
barcode from /scan with periodicals off, and assert the periodical scan
result renders and its confirm form saves an item" — could not be written.
Confirmed by reading the scan dispatch top to bottom (`app/routers/items.py`,
`app/routers/items_common.py::_scan_upc`, `app/services/detect.py`): a 977
EAN-13 is not an ISBN prefix (978/979), so `upc_svc.detect_barcode_type`
files it as `"upc"`, and `_scan_upc` never reads `PERIODICAL_MEDIA_TYPES` or
calls `app.routers.periodicals.render_scan_candidate` — that function, and
the whole assist/confirm flow it feeds, is unreachable from any live route
today (`grep -rn 977 app/routers/items.py app/routers/items_common.py
app/services/detect.py` finds nothing). A 977 scan through `/scan` today
lands on the generic "not found — add manually" card, media_type=magazine,
via the ordinary UPC Item DB path. Writing a test against the plan's
described behaviour would either fabricate a route that does not exist or
silently assert the (different) real behaviour in its place, so this was
reported to the orchestrator instead of guessed at. Tests 1, 2 and the
`tests/e2e/test_responsive.py` addition (T11's other work items) are here.
"""
import sqlite3
from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _insert_share_link(data_dir: Path, token: str) -> None:
    """Insert one share-link row directly into the E2E SQLite DB.

    Mirrors conftest.insert_item / test_scan.py's _insert_borrower — there is
    no shared share-links helper.
    """
    db_path = data_dir / "shelf.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO share_links (token, scope) VALUES (?, 'collection')",
            (token,),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_share_link(data_dir: Path, token: str) -> None:
    conn = sqlite3.connect(str(data_dir / "shelf.db"))
    try:
        conn.execute("DELETE FROM share_links WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def one_share_link(live_server):
    """One share link for the length of a test, then gone again.

    The live_server DB is session-scoped. A leftover link renders the Sharing
    card's "Copied!" span on /settings, a second `span.text-shelf-success`
    that later tests' strict locators trip over (G126).
    """
    token = "e2e-share-token"
    _insert_share_link(live_server["data_dir"], token)
    yield token
    _delete_share_link(live_server["data_dir"], token)


def _open_features_tab(page, base_url: str) -> None:
    page.goto(f"{base_url}/settings")
    page.click('[data-testid="tab-features"]')
    expect(page.locator('[data-testid="feature-row-series"]')).to_be_visible()


def _feature_state(page, key: str) -> str:
    """"on" or "off", read from the row's state badge without a reload."""
    row = page.locator(f'[data-testid="feature-row-{key}"]')
    if row.locator('[data-feature-state="on"]').count():
        return "on"
    assert row.locator('[data-feature-state="off"]').count()
    return "off"


def test_disabled_series_page_round_trips_through_enable(live_server, authed_page):
    """Turn Series off with no dialog, see it gone from the nav and gated at
    /series, then turn it back on from the disabled page itself."""
    base_url = live_server["url"]

    dialogs: list[str] = []

    def _fail_on_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    authed_page.on("dialog", _fail_on_dialog)

    _open_features_tab(authed_page, base_url)
    assert _feature_state(authed_page, "series") == "on"

    with authed_page.expect_navigation():
        authed_page.click('[data-testid="feature-toggle-series"]')
    assert authed_page.url == f"{base_url}/settings"
    assert dialogs == []  # series has no probes — turning it off never asks

    # The nav no longer offers Series, on the desktop bar or the mobile menu.
    expect(
        authed_page.locator('[data-nav-tab="series"], [data-nav-menu-tab="series"]')
    ).to_have_count(0)

    authed_page.goto(f"{base_url}/series")
    expect(authed_page.locator('[data-testid="feature-disabled"]')).to_be_visible()
    expect(authed_page.locator('[data-testid="feature-enable-form"]')).to_be_visible()

    with authed_page.expect_navigation():
        authed_page.click('[data-testid="feature-enable-form"] button[type=submit]')
    assert authed_page.url == f"{base_url}/series"
    expect(authed_page.locator('[data-testid="feature-disabled"]')).to_have_count(0)
    expect(authed_page.locator("h1")).to_contain_text("Series")

    assert dialogs == []


def test_turning_off_share_with_a_link_confirms_first(live_server, authed_page, one_share_link):
    """A nonzero probe raises a confirm; dismissing it changes nothing, and
    accepting it turns the flag off. Restores the flag afterwards."""
    base_url = live_server["url"]

    _open_features_tab(authed_page, base_url)
    assert _feature_state(authed_page, "share") == "on"

    dismissed: list[str] = []

    def _dismiss(dialog):
        dismissed.append(dialog.message)
        dialog.dismiss()

    authed_page.once("dialog", _dismiss)
    authed_page.click('[data-testid="feature-toggle-share"]')
    assert len(dismissed) == 1
    assert "1 active share link" in dismissed[0]
    # Dismissed: the form never submitted, so nothing navigated and the flag
    # is unchanged.
    assert _feature_state(authed_page, "share") == "on"

    accepted: list[str] = []

    def _accept(dialog):
        accepted.append(dialog.message)
        dialog.accept()

    authed_page.once("dialog", _accept)
    with authed_page.expect_navigation():
        authed_page.click('[data-testid="feature-toggle-share"]')
    assert len(accepted) == 1
    assert "1 active share link" in accepted[0]
    assert _feature_state(authed_page, "share") == "off"

    # Restore: the live_server DB is session-scoped and shared with every
    # other E2E test.
    with authed_page.expect_navigation():
        authed_page.click('[data-testid="feature-toggle-share"]')
    assert _feature_state(authed_page, "share") == "on"
