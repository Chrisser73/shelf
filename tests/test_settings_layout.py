"""Regression coverage for the sectioned Settings workspace and user menu."""

from pathlib import Path


def test_settings_page_has_five_section_controls(admin_client):
    html = admin_client.get("/settings").text
    assert "Administration" in html
    assert 'data-testid="settings-section-nav"' in html
    assert 'aria-label="Settings sections"' in html
    assert 'data-testid="settings-section-content"' in html
    for key in ("library", "integrations", "data", "users", "features"):
        assert html.count(f'data-testid="tab-{key}"') == 1


def test_settings_page_keeps_existing_setting_surfaces(admin_client, db):
    """The layout is a shell change: representative existing forms survive."""
    # The tag manager's forms are per-row, so a tag must exist to render one.
    db.execute("INSERT INTO tags (name) VALUES ('layout-check')")
    db.execute("COMMIT")
    html = admin_client.get("/settings").text
    assert 'action="/api/settings/display"' in html
    assert 'action="/api/settings/nav"' in html
    assert 'data-testid="settings-appearance"' in html
    assert 'name="always_show_game_title"' in html
    assert 'name="show_platform_logo_in_collection"' in html
    assert 'action="/api/settings"' in html
    assert 'action="/api/tags/' in html
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


def test_light_theme_is_a_per_user_appearance_preference(admin_client):
    admin_client.post(
        "/api/settings/appearance",
        data={"theme": "light"},
        follow_redirects=False,
    )
    html = admin_client.get("/settings").text
    assert '<html lang="en" class="dark" data-theme="light">' in html
    theme_input = html[html.index('name="theme" value="light"'):]
    assert "checked" in theme_input[:200]

    admin_client.post("/api/settings/appearance", data={}, follow_redirects=False)
    html = admin_client.get("/settings").text
    assert 'data-theme="light"' not in html


def test_ocean_theme_is_a_per_user_appearance_preference(admin_client):
    admin_client.post(
        "/api/settings/appearance",
        data={"theme": "ocean"},
        follow_redirects=False,
    )
    html = admin_client.get("/settings").text
    assert '<html lang="en" class="dark" data-theme="ocean">' in html
    theme_input = html[html.index('name="theme" value="ocean"'):]
    assert "checked" in theme_input[:200]


def test_additional_dark_themes_are_available_per_user(admin_client):
    for theme in ("navi", "sakura", "coffee", "retro", "matrix"):
        admin_client.post(
            "/api/settings/appearance",
            data={"theme": theme},
            follow_redirects=False,
        )
        html = admin_client.get("/settings").text
        assert f'<html lang="en" class="dark" data-theme="{theme}">' in html
        theme_input = html[html.index(f'name="theme" value="{theme}"'):]
        assert "checked" in theme_input[:200]


def test_admin_settings_entry_lives_in_account_menu(admin_client):
    html = admin_client.get("/browse").text
    assert 'data-testid="account-menu-button"' in html
    assert 'data-testid="account-menu-panel"' in html
    assert 'data-testid="account-menu-settings"' in html
    assert 'data-nav-tab="settings"' in html


def test_editor_sees_only_the_curated_library_settings(editor_client):
    html = editor_client.get("/browse").text
    assert 'data-testid="account-menu-button"' in html
    assert 'data-testid="account-menu-settings"' in html

    response = editor_client.get("/settings", follow_redirects=False)
    assert response.status_code == 200
    assert 'data-testid="tab-library"' in response.text
    for key in ("integrations", "data", "users", "features"):
        assert f'data-testid="tab-{key}"' not in response.text
    for label in ("Appearance", "Missing game data", "Navigation", "Locations"):
        assert label in response.text
    assert "Audiobookshelf" not in response.text


def test_viewer_cannot_open_settings_or_see_the_menu_entry(viewer_client):
    html = viewer_client.get("/browse").text
    assert 'data-testid="account-menu-button"' in html
    assert 'data-testid="account-menu-settings"' not in html
    response = viewer_client.get("/settings", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/browse"


def test_settings_is_not_rendered_in_primary_nav(admin_client):
    html = admin_client.get("/browse").text
    desktop_start = html.index('<div class="hidden min-w-0 overflow-hidden lg:flex items-center gap-1">')
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
