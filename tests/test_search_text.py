"""Unicode-folded Collection search and its visible highlighting."""

from app.services.search_text import folded_match_ranges


def test_folded_ranges_map_an_ascii_query_back_to_the_accented_title():
    assert folded_match_ranges("Pokémon Shining Pearl", "Poke") == [(0, 4)]


def test_highlight_preserves_the_original_accented_text():
    # app.main creates its runtime cover directory at import time, so import
    # after pytest's isolated-database fixture has redirected that path.
    from app.main import highlight_search

    rendered = str(highlight_search("Pokémon Shining Pearl", "Poke"))
    assert "<mark" in rendered
    assert "Poké</mark>mon Shining Pearl" in rendered


def test_highlight_escapes_untrusted_title_text():
    from app.main import highlight_search

    rendered = str(highlight_search("<Pokémon>", "Poke"))
    assert "&lt;" in rendered
    assert "<Pokémon>" not in rendered
