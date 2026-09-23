"""Tests for app.routers.platforms — game platform CRUD and slugify."""

import pytest

from app.database import get_db
from app.routers.platforms import _platform_name_and_slug, _slugify
from app.services import platform_logos


class TestSlugify:
    def test_basic(self):
        assert _slugify("Nintendo 64") == "nintendo64"

    def test_special_chars(self):
        assert _slugify("Xbox Series X/S") == "xboxseriesxs"

    def test_already_slug(self):
        assert _slugify("nes") == "nes"

    def test_empty_after_strip(self):
        assert _slugify("---") == ""

    def test_explicit_slug_keeps_display_name_separate(self):
        assert _platform_name_and_slug("Testconsole (blubb)") == ("Testconsole", "blubb")

    def test_empty_parentheses_keep_the_existing_name_only_behavior(self):
        assert _platform_name_and_slug("Testconsole ()") == ("Testconsole ()", "testconsole")


class TestCreatePlatform:
    def test_create(self, admin_client):
        resp = admin_client.post("/api/platforms", data={"name": "Atari Jaguar"}, follow_redirects=False)
        assert resp.status_code == 303
        with get_db() as db:
            row = db.execute("SELECT slug, name FROM game_platforms WHERE slug = 'atarijaguar'").fetchone()
        assert row is not None
        assert row["name"] == "Atari Jaguar"

    def test_create_duplicate_ignored(self, admin_client):
        admin_client.post("/api/platforms", data={"name": "Neo Geo"}, follow_redirects=False)
        admin_client.post("/api/platforms", data={"name": "Neo Geo"}, follow_redirects=False)
        with get_db() as db:
            count = db.execute("SELECT COUNT(*) as c FROM game_platforms WHERE slug = 'neogeo'").fetchone()["c"]
        assert count == 1

    def test_create_uses_explicit_slug_in_parentheses(self, admin_client):
        admin_client.post("/api/platforms", data={"name": "Testconsole (blubb)"}, follow_redirects=False)
        with get_db() as db:
            row = db.execute(
                "SELECT slug, name FROM game_platforms WHERE slug = 'blubb'"
            ).fetchone()
        assert row is not None
        assert row["name"] == "Testconsole"

    def test_create_empty_name_rejected(self, admin_client):
        resp = admin_client.post("/api/platforms", data={"name": "---"}, follow_redirects=False)
        assert resp.status_code == 303  # redirects without creating

    def test_requires_admin(self, editor_client):
        resp = editor_client.post("/api/platforms", data={"name": "Test"}, follow_redirects=False)
        assert resp.status_code in (303, 401, 403)


class TestDeletePlatform:
    def test_delete(self, admin_client, db):
        db.execute("INSERT INTO game_platforms (slug, name) VALUES ('testplat', 'Test Platform')")
        db.commit()
        with get_db() as check_db:
            row = check_db.execute("SELECT id FROM game_platforms WHERE slug = 'testplat'").fetchone()
        plat_id = row["id"]

        resp = admin_client.post(f"/api/platforms/{plat_id}/delete", follow_redirects=False)
        assert resp.status_code == 303
        with get_db() as check_db:
            row = check_db.execute("SELECT id FROM game_platforms WHERE id = ?", (plat_id,)).fetchone()
        assert row is None

    def test_delete_nullifies_items(self, admin_client, db):
        """Deleting a platform should null out items using that platform."""
        db.execute("INSERT INTO game_platforms (slug, name) VALUES ('removeme', 'Remove Me')")
        db.execute(
            "INSERT INTO items (title, media_type, platform, source) VALUES ('Game', 'video_game', 'removeme', 'test')"
        )
        db.commit()
        with get_db() as check_db:
            plat_id = check_db.execute("SELECT id FROM game_platforms WHERE slug = 'removeme'").fetchone()["id"]
        admin_client.post(f"/api/platforms/{plat_id}/delete", follow_redirects=False)
        with get_db() as check_db:
            item = check_db.execute("SELECT platform FROM items WHERE title = 'Game'").fetchone()
        assert item["platform"] is None


class TestPlatformLogos:
    def test_save_custom_logo_mapping(self, admin_client, db, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_logos, "SVG_DIRECTORY", tmp_path)
        (tmp_path / "nintendo_switch_tall.svg").touch()
        resp = admin_client.post(
            "/api/platforms/logos",
            data={"platform": "switch", "svg_path": "icons/platforms/nintendo_switch_tall.svg"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        row = db.execute(
            "SELECT svg_path FROM game_platform_logos WHERE platform_slug = 'switch'"
        ).fetchone()
        assert row["svg_path"] == "icons/platforms/nintendo_switch_tall.svg"

    def test_rejects_paths_outside_the_bundled_svg_directory(self, admin_client, db, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_logos, "SVG_DIRECTORY", tmp_path)
        admin_client.post(
            "/api/platforms/logos",
            data={"platform": "switch", "svg_path": "https://example.com/logo.svg"},
        )
        assert db.execute(
            "SELECT 1 FROM game_platform_logos WHERE platform_slug = 'switch'"
        ).fetchone() is None

    def test_legacy_mapping_path_is_migrated_to_the_new_directory(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_logos, "SVG_DIRECTORY", tmp_path)
        (tmp_path / "nintendo_switch.svg").touch()
        assert platform_logos.normalise_svg_path("icons/svg/nintendo_switch.svg") == (
            "icons/platforms/nintendo_switch.svg"
        )
