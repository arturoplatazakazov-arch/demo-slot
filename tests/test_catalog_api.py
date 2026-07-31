"""Tests for GET /api/v1/catalog (app/api/v1/catalog.py) — the public
listing front/games.html fetches instead of hardcoding game cards."""


async def test_catalog_lists_all_seeded_demo_games(api_client):
    response = await api_client.get("/api/v1/catalog")
    assert response.status_code == 200
    body = response.json()

    codes = {entry["code"] for entry in body}
    assert {"amys-fruit-farm", "east-discovery", "party-of-goods", "wild-western-story"} <= codes


async def test_catalog_entry_has_expected_fields(api_client):
    response = await api_client.get("/api/v1/catalog")
    entry = next(e for e in response.json() if e["code"] == "amys-fruit-farm")

    assert entry["name"] == "Amy's Fruit Farm"
    assert entry["catalog_badge"] == "Farm"
    assert entry["catalog_description"] == "Классический слот с бонусной игрой на ферме"
    assert entry["catalog_cover_path"] == "img/amys-fruit-farm/img/logo_AmysFruitFarm-hero.jpg"
    assert entry["catalog_play_url"] == "index.html"


async def test_symbol_art_lists_codes_for_active_config(api_client):
    response = await api_client.get("/api/v1/config/amys-fruit-farm/symbols")
    assert response.status_code == 200
    body = response.json()
    codes = {entry["code"] for entry in body}
    assert "duck" in codes
    # The 4 hand-built demo games never set image_ref — their art is wired
    # directly in front/js/slot.js, not through the builder pipeline.
    assert all(entry["image_ref"] is None for entry in body)


async def test_symbol_art_404s_for_unknown_game(api_client):
    response = await api_client.get("/api/v1/config/does-not-exist/symbols")
    assert response.status_code == 404
