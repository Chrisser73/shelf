"""POST /api/items/bulk-tags — editor-role bulk add/remove of tags on a
Browse selection (routers/tags.py + services/tags.bulk_tag)."""
from tests.conftest import _insert_item

URL = "/api/items/bulk-tags"


def _seed(db, n=3):
    ids = [_insert_item(db, title=f"Bulk {i}", isbn=f"97890000{i:05d}") for i in range(n)]
    db.execute("COMMIT")
    return ids


def _tags_of(db, item_id):
    return [r["name"] for r in db.execute(
        "SELECT t.name FROM item_tags it JOIN tags t ON t.id = it.tag_id "
        "WHERE it.item_id = ? ORDER BY t.name", (item_id,),
    ).fetchall()]


def _tag_row(db, name):
    return db.execute("SELECT id, media_type FROM tags WHERE name = ?", (name,)).fetchone()


def _post(client, item_ids, add=(), remove=()):
    return client.post(URL, json={"item_ids": item_ids, "add": list(add), "remove": list(remove)})


class TestBulkAdd:
    def test_tags_exactly_the_selected_items(self, editor_client, db):
        a, b, c = _seed(db)
        resp = _post(editor_client, [a, b], add=["Simulation"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True and body["updated"] == 2
        assert body["message"] == "Added Simulation to 2 item(s)"
        assert _tags_of(db, a) == ["Simulation"]
        assert _tags_of(db, b) == ["Simulation"]
        assert _tags_of(db, c) == []
        assert _tag_row(db, "Simulation")["media_type"] is None

    def test_readding_a_carried_tag_changes_nothing(self, editor_client, db):
        a, b, _ = _seed(db)
        _post(editor_client, [a, b], add=["signed"])
        resp = _post(editor_client, [a, b], add=["Signed"])
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["updated"] == 0
        assert _tags_of(db, a) == ["signed"]

    def test_names_normalise_and_dedupe_nocase(self, editor_client, db):
        a, _, _ = _seed(db)
        resp = _post(editor_client, [a], add=["  book   club ", "Book Club", ""])
        assert resp.json()["updated"] == 1
        assert _tags_of(db, a) == ["book club"]


class TestBulkRemove:
    def test_removes_from_selected_only_and_keeps_other_uses(self, editor_client, db):
        a, b, c = _seed(db)
        _post(editor_client, [a, b, c], add=["kids"])
        resp = _post(editor_client, [a, b], remove=["kids"])
        assert resp.json() == {"ok": True, "updated": 2,
                               "message": "Removed kids from 2 item(s)"}
        assert _tags_of(db, a) == [] and _tags_of(db, b) == []
        assert _tags_of(db, c) == ["kids"]
        assert _tag_row(db, "kids") is not None

    def test_removing_the_last_use_garbage_collects_the_tag(self, editor_client, db):
        a, b, _ = _seed(db)
        _post(editor_client, [a, b], add=["temp"])
        _post(editor_client, [a, b], remove=["TEMP"])
        assert _tag_row(db, "temp") is None

    def test_removing_an_unknown_name_is_a_noop_and_creates_nothing(self, editor_client, db):
        a, _, _ = _seed(db)
        resp = _post(editor_client, [a], remove=["never-existed"])
        assert resp.status_code == 200
        assert resp.json()["ok"] is True and resp.json()["updated"] == 0
        assert _tag_row(db, "never-existed") is None

    def test_add_and_remove_in_one_request(self, editor_client, db):
        a, b, _ = _seed(db)
        _post(editor_client, [a, b], add=["old"])
        resp = _post(editor_client, [a, b], add=["new"], remove=["old"])
        assert resp.json()["updated"] == 2
        assert _tags_of(db, a) == ["new"] and _tags_of(db, b) == ["new"]
        assert _tag_row(db, "old") is None


class TestRefusals:
    def test_unknown_id_refuses_the_whole_request(self, editor_client, db):
        a, _, _ = _seed(db)
        resp = _post(editor_client, [a, 999999], add=["nope"])
        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "message": "1 selected item(s) no longer exist"}
        assert _tags_of(db, a) == []
        assert _tag_row(db, "nope") is None

    def test_trashed_id_refuses_the_whole_request(self, editor_client, db):
        from app.services.item_write import trash_item

        a, b, _ = _seed(db)
        trash_item(db, b)
        db.execute("COMMIT")
        resp = _post(editor_client, [a, b], add=["nope"])
        assert resp.status_code == 400
        assert resp.json()["ok"] is False
        assert _tags_of(db, a) == [] and _tags_of(db, b) == []

    def test_blank_names_refused(self, editor_client, db):
        a, _, _ = _seed(db)
        resp = _post(editor_client, [a], add=["   "], remove=[""])
        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "message": "No tag given"}

    def test_empty_selection_refused(self, editor_client):
        resp = _post(editor_client, [], add=["x"])
        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "message": "No items selected"}

    def test_string_id_refused(self, editor_client, db):
        a, _, _ = _seed(db)
        resp = _post(editor_client, [a, "2"], add=["x"])
        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "message": "Invalid item IDs"}

    def test_missing_item_ids_refused(self, editor_client):
        resp = editor_client.post(URL, json={"add": ["x"]})
        assert resp.status_code == 400
        assert resp.json()["message"] == "Invalid item IDs"


class TestRoles:
    def test_admin_allowed(self, admin_client, db):
        a, _, _ = _seed(db)
        assert _post(admin_client, [a], add=["x"]).status_code == 200

    def test_viewer_forbidden(self, viewer_client, db):
        a, _, _ = _seed(db)
        resp = _post(viewer_client, [a], add=["x"])
        assert resp.status_code == 403
        assert _tags_of(db, a) == []

    def test_anonymous_redirected_to_login(self, client, admin_user, db):
        a, _, _ = _seed(db)
        resp = client.post(URL, json={"item_ids": [a], "add": ["x"]}, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"


class TestBulkBarTemplate:
    """The Browse bulk bar's tag controls (browse.html + browse.js:bulkTags)."""

    def _seed_tag(self, db, name="vintage"):
        db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        db.execute("COMMIT")

    def test_editor_sees_bulk_tag_controls_and_datalist(self, editor_client, db):
        self._seed_tag(db)
        html = editor_client.get("/browse").text
        assert 'data-testid="bulk-tag-input"' in html
        assert 'data-testid="bulk-tag-add"' in html
        assert 'data-testid="bulk-tag-remove"' in html
        assert '<datalist id="bulk-tag-options">' in html
        assert '<option value="vintage">' in html

    def test_admin_sees_bulk_tag_controls(self, admin_client, db):
        self._seed_tag(db)
        html = admin_client.get("/browse").text
        assert 'data-testid="bulk-tag-input"' in html

    def test_viewer_does_not_see_bulk_tag_controls(self, viewer_client, db):
        self._seed_tag(db)
        html = viewer_client.get("/browse").text
        assert 'data-testid="bulk-tag-input"' not in html
        assert 'data-testid="bulk-tag-add"' not in html
        assert 'data-testid="bulk-tag-remove"' not in html

    def test_select_tooltip_mentions_tagging(self, editor_client, db):
        html = editor_client.get("/browse").text
        assert "tagging" in html


def test_route_order_reaches_the_bulk_tags_handler(client):
    """items.py's POST /items/{item_id} also matches this path; the first full
    match must be the static route, or every bulk-tag click answers 422."""
    from starlette.routing import Match

    from app.main import app

    scope = {"type": "http", "method": "POST", "path": URL, "root_path": ""}
    first = next(r for r in app.router.routes
                 if hasattr(r, "matches") and r.matches(scope)[0] == Match.FULL)
    assert f"{first.endpoint.__module__}.{first.endpoint.__name__}" == \
        "app.routers.tags.bulk_tags"
