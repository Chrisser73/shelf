"""The reviewed video-game metadata sync must never touch a cover."""

import asyncio

from tests.conftest import _insert_item


def test_reviewed_game_metadata_sync_updates_only_metadata(admin_client, db):
    item_id = _insert_item(
        db, title="Metroid Prime 4", isbn=None, media_type="video_game",
        cover_path="covers/keep.jpg",
    )
    db.commit()

    response = admin_client.post("/api/game-metadata/apply", json={"items": [{
        "id": item_id, "include": True, "title": "Metroid Prime 4: Beyond",
        "alternate_title": None, "authors": "Retro Studios", "publisher": "Nintendo",
        "platform": "switch2", "region": "PAL", "language": "en", "publish_year": 2025,
    }]})

    assert response.json() == {"ok": True, "updated": [{"id": item_id, "title": "Metroid Prime 4: Beyond"}]}
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    assert row["cover_path"] == "covers/keep.jpg"
    assert row["title"] == "Metroid Prime 4: Beyond"
    assert row["authors"] == "Retro Studios"
    assert row["publisher"] == "Nintendo"
    assert row["platform"] == "switch2"
    assert row["region"] == "PAL"
    assert row["language"] == "en"
    assert row["publish_year"] == 2025


def test_metadata_plan_rejects_a_mod_or_fan_project_ranked_first(monkeypatch):
    from app.services import game_metadata, igdb, provider_result

    async def fake_identity(item, settings, client):
        return {}

    async def fake_search(*args, **kwargs):
        return provider_result.found("igdb", [
            {"title": "Super Smash Bros. Sonic", "developer": "Fan Team", "publisher": "Fan Team"},
            {"title": "Super Smash Bros.", "developer": "Nintendo", "publisher": "Nintendo", "publish_year": 1999},
        ])

    monkeypatch.setattr(game_metadata, "identify_edition", fake_identity)
    monkeypatch.setattr(igdb, "search_games", fake_search)
    proposed = asyncio.run(game_metadata.propose(
        {"id": 1, "title": "Super Smash Bros.", "alternate_title": None,
         "authors": None, "publisher": None, "platform": "n64", "region": None,
         "language": None, "publish_year": None, "location_id": None},
        {"igdb_client_id": "id", "igdb_client_secret": "secret"},
        {"n64": "Nintendo 64"}, None,
    ))

    assert proposed["title"] == "Super Smash Bros."
    assert proposed["authors"] == "Nintendo"
    assert proposed["publisher"] == "Nintendo"
    assert proposed["publish_year"] == 1999


def test_metadata_plan_does_not_save_an_ai_platform_guess(monkeypatch):
    from app.services import game_metadata, igdb, provider_result

    async def fake_identity(item, settings, client):
        return {"platform": "Wii"}

    async def fake_search(*args, **kwargs):
        assert kwargs["platform"] is None
        return provider_result.found("igdb", [{
            "title": "Star Fox 64", "platform_names": ["Wii", "Nintendo 64"],
        }])

    monkeypatch.setattr(game_metadata, "identify_edition", fake_identity)
    monkeypatch.setattr(igdb, "search_games", fake_search)
    proposed = asyncio.run(game_metadata.propose(
        {"id": 1, "title": "Star Fox 64", "alternate_title": None,
         "authors": None, "publisher": None, "platform": None, "region": None,
         "language": None, "publish_year": None, "location_id": None},
        {"igdb_client_id": "id", "igdb_client_secret": "secret"},
        {"n64": "Nintendo 64", "wii": "Wii"}, None,
    ))

    assert proposed["platform"] == "n64"


def test_metadata_plan_rejects_platforms_newer_than_the_game(monkeypatch):
    from app.services import game_metadata, igdb, provider_result

    async def fake_identity(item, settings, client):
        return {}

    async def fake_search(*args, **kwargs):
        return provider_result.found("igdb", [{
            "title": "The Legend of Zelda", "publish_year": 1986,
            "platform_names": ["Nintendo 3DS", "Nintendo Entertainment System (NES)"],
        }])

    monkeypatch.setattr(game_metadata, "identify_edition", fake_identity)
    monkeypatch.setattr(igdb, "search_games", fake_search)
    proposed = asyncio.run(game_metadata.propose(
        {"id": 1, "title": "The Legend of Zelda", "alternate_title": None,
         "authors": None, "publisher": None, "platform": None, "region": None,
         "language": None, "publish_year": 1986, "location_id": None},
        {"igdb_client_id": "id", "igdb_client_secret": "secret"},
        {"nes": "Nintendo Entertainment System", "3ds": "Nintendo 3DS"}, None,
    ))

    assert proposed["platform"] == "nes"


def test_metadata_plan_leaves_platform_empty_when_only_a_later_port_is_returned(monkeypatch):
    from app.services import game_metadata, igdb, provider_result

    async def fake_identity(item, settings, client):
        return {}

    async def fake_search(*args, **kwargs):
        return provider_result.found("igdb", [{
            "title": "The Legend of Zelda", "publish_year": 1986,
            "platform_names": ["Nintendo 3DS"],
        }])

    monkeypatch.setattr(game_metadata, "identify_edition", fake_identity)
    monkeypatch.setattr(igdb, "search_games", fake_search)
    proposed = asyncio.run(game_metadata.propose(
        {"id": 1, "title": "The Legend of Zelda", "alternate_title": None,
         "authors": None, "publisher": None, "platform": None, "region": None,
         "language": None, "publish_year": 1986, "location_id": None},
        {"igdb_client_id": "id", "igdb_client_secret": "secret"},
        {"nes": "Nintendo Entertainment System", "3ds": "Nintendo 3DS"}, None,
    ))

    assert proposed["platform"] is None
