"""Regression coverage for the sectioned Settings workspace and user menu."""

from pathlib import Path


def test_settings_page_has_four_section_controls(admin_client):
    html = admin_client.get("/settings").text
    assert "Administration" in html
    assert 'data-testid="settings-section-nav"' in html
    assert 'aria-label="Settings sections"' in html
    assert 'data-testid="settings-section-content"' in html
    for key in ("library", "integrations", "data", "users"):
        assert html.count(f'data-testid="tab-{key}"') == 1


def test_settings_page_keeps_existing_setting_surfaces(admin_client):
    """The layout is a shell change: representative existing forms survive."""
    html = admin_client.get("/settings").text
    assert 'action="/api/settings/display"' in html
    assert 'action="/api/settings/nav"' in html
    assert 'data-testid="settings-appearance"' in html
    assert 'name="always_show_game_title"' in html
    assert 'name="show_platform_logo_in_collection"' in html
    assert 'action="/api/settings"' in html
    assert "Audiobookshelf" in html
    assert "Portable archive" in html
    assert "Users" in html


def test_platform_logo_appearance_checkbox_reflects_the_saved_user_preference(admin_client):
    admin_client.post(
        "/api/settings/appearance",
        data={"show_platform_logo_in_collection": "1"},
        follow_redirects=False,
    )
    html = admin_client.get("/settings").text
    logo_input = html[html.index('name="show_platform_logo_in_collection"'):]
    assert "checked" in logo_input[:200]

    admin_client.post("/api/settings/appearance", data={}, follow_redirects=False)
    html = admin_client.get("/settings").text
    logo_input = html[html.index('name="show_platform_logo_in_collection"'):]
    assert "checked" not in logo_input[:200]


def test_admin_settings_entry_lives_in_account_menu(admin_client):
    html = admin_client.get("/browse").text
    assert 'data-testid="account-menu-button"' in html
    assert 'data-testid="account-menu-panel"' in html
    assert 'data-testid="account-menu-settings"' in html
    assert 'data-nav-tab="settings"' in html


def test_non_admin_users_can_open_personal_settings(editor_client, viewer_client):
    for client in (editor_client, viewer_client):
        html = client.get("/browse").text
        assert 'data-testid="account-menu-button"' in html
        assert 'data-testid="account-menu-settings"' in html
        response = client.get("/settings", follow_redirects=False)
        assert response.status_code == 200
        assert 'data-testid="settings-appearance"' in response.text
        assert 'action="/api/settings/platform-logo"' in response.text


def test_settings_is_not_rendered_in_primary_nav(admin_client):
    html = admin_client.get("/browse").text
    desktop_start = html.index('<div class="hidden lg:flex items-center gap-1">')
    desktop_end = html.index("</div>", desktop_start)
    desktop_nav = html[desktop_start:desktop_end]
    assert 'data-nav-tab="settings"' not in desktop_nav

    mobile_start = html.index('data-testid="nav-menu-panel"')
    mobile_end = html.index("</div>", mobile_start)
    mobile_nav = html[mobile_start:mobile_end]
    assert 'data-nav-menu-tab="settings"' not in mobile_nav


def test_account_menu_controller_is_registered():
    js = Path(__file__).resolve().parent.parent.joinpath("static/js/components.js").read_text()
    assert "Alpine.data('accountMenu'" in js
    assert "openAccount()" in js
    assert "closeAll()" in js
