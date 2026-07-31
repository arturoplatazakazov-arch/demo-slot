"""Service-layer tests for the admin config/simulate/publish workflow
(app/api/admin/service.py), against the isolated in-memory SQLite db_session
fixture — not the shared dev Postgres — so publishing/archiving here can't
disturb the real active config other tests or the running dev server rely
on. Route-registration wiring is covered separately below via api_client."""

import pytest
from fastapi import HTTPException

from app.api.admin import schemas, service
from app.models.enums import GameConfigStatus
from app.seed.amys_fruit_farm import build_game_config


@pytest.fixture
async def seeded_game(db_session):
    game, config = build_game_config()
    db_session.add(config)
    await db_session.commit()
    return game, config


async def test_get_or_create_draft_clones_active_config(db_session, seeded_game):
    game, active = seeded_game
    draft = await service.get_or_create_draft(db_session, game.code)

    assert draft.status == GameConfigStatus.DRAFT.value
    assert draft.version == active.version + 1
    assert {s.code for s in draft.symbols} == {s.code for s in active.symbols}
    duck = next(s for s in draft.symbols if s.code == "duck")
    active_duck = next(s for s in active.symbols if s.code == "duck")
    assert duck.reel_weights == active_duck.reel_weights
    assert duck.id != active_duck.id  # a real clone, not the same row


async def test_get_or_create_draft_is_idempotent(db_session, seeded_game):
    game, _ = seeded_game
    first = await service.get_or_create_draft(db_session, game.code)
    second = await service.get_or_create_draft(db_session, game.code)
    assert first.id == second.id


async def test_update_symbols_rejects_editing_a_non_draft_config(db_session, seeded_game):
    _, active = seeded_game
    symbol = active.symbols[0]
    update = schemas.UpdateSymbolsRequest(
        symbols=[schemas.SymbolUpdateIn(id=symbol.id, reel_weights=[1] * 5, paytable={"3": 2})]
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.update_symbols(db_session, active.id, update)
    assert exc_info.value.status_code == 409


async def test_update_symbols_validates_reel_weights_length(db_session, seeded_game):
    game, _ = seeded_game
    draft = await service.get_or_create_draft(db_session, game.code)
    symbol = draft.symbols[0]
    update = schemas.UpdateSymbolsRequest(
        symbols=[schemas.SymbolUpdateIn(id=symbol.id, reel_weights=[1, 2, 3], paytable={"3": 2})]
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.update_symbols(db_session, draft.id, update)
    assert exc_info.value.status_code == 400


async def test_update_symbols_persists_weights_paytable_and_cap(db_session, seeded_game):
    game, _ = seeded_game
    draft = await service.get_or_create_draft(db_session, game.code)
    duck = next(s for s in draft.symbols if s.code == "duck")

    update = schemas.UpdateSymbolsRequest(
        symbols=[
            schemas.SymbolUpdateIn(
                id=duck.id, reel_weights=[20, 20, 20, 20, 20], paytable={"3": 15, "4": 30, "5": 60},
                max_per_reel=2,
            )
        ]
    )
    updated = await service.update_symbols(db_session, draft.id, update)
    updated_duck = next(s for s in updated.symbols if s.code == "duck")
    assert updated_duck.reel_weights == [20, 20, 20, 20, 20]
    assert updated_duck.paytable == {"3": 15, "4": 30, "5": 60}
    assert updated_duck.max_per_reel == 2


async def test_update_symbols_persists_image_ref(db_session, seeded_game):
    game, _ = seeded_game
    draft = await service.get_or_create_draft(db_session, game.code)
    duck = next(s for s in draft.symbols if s.code == "duck")

    update = schemas.UpdateSymbolsRequest(
        symbols=[
            schemas.SymbolUpdateIn(
                id=duck.id, reel_weights=duck.reel_weights, paytable=duck.paytable,
                image_ref="builder-asset-123",
            )
        ]
    )
    updated = await service.update_symbols(db_session, draft.id, update)
    updated_duck = next(s for s in updated.symbols if s.code == "duck")
    assert updated_duck.image_ref == "builder-asset-123"

    # Clearing it back to None must round-trip too, not just setting it.
    clear_update = schemas.UpdateSymbolsRequest(
        symbols=[
            schemas.SymbolUpdateIn(
                id=duck.id, reel_weights=duck.reel_weights, paytable=duck.paytable, image_ref=None,
            )
        ]
    )
    cleared = await service.update_symbols(db_session, draft.id, clear_update)
    cleared_duck = next(s for s in cleared.symbols if s.code == "duck")
    assert cleared_duck.image_ref is None


async def test_run_and_record_simulation_persists_a_completed_run(db_session, seeded_game):
    game, _ = seeded_game
    draft = await service.get_or_create_draft(db_session, game.code)

    request = schemas.SimulateRequest(num_spins=500, seed=1)
    run = await service.run_and_record_simulation(db_session, draft.id, request)

    assert run.status == "completed"
    assert run.num_spins == 500
    assert run.results["num_spins"] == 500
    assert 0 <= run.results["rtp"]
    assert 0 <= run.results["hit_frequency"] <= 1
    assert 0 <= run.results["bonus_frequency"] <= 1

    history = await service.list_simulations(db_session, draft.id)
    assert len(history) == 1
    assert history[0].id == run.id


async def test_publish_activates_draft_and_archives_previous_active(db_session, seeded_game):
    game, active = seeded_game
    draft = await service.get_or_create_draft(db_session, game.code)

    published, archived_id = await service.publish_config(db_session, draft.id)

    assert published.status == GameConfigStatus.ACTIVE.value
    assert archived_id == active.id

    refreshed_active = await service.get_config(db_session, active.id)
    assert refreshed_active.status == GameConfigStatus.ARCHIVED.value


async def test_publish_rejects_a_config_that_is_not_a_draft(db_session, seeded_game):
    _, active = seeded_game
    with pytest.raises(HTTPException) as exc_info:
        await service.publish_config(db_session, active.id)
    assert exc_info.value.status_code == 409


async def test_get_config_404s_for_an_unknown_id(db_session, seeded_game):
    import uuid

    _ = seeded_game
    with pytest.raises(HTTPException) as exc_info:
        await service.get_config(db_session, uuid.uuid4())
    assert exc_info.value.status_code == 404


async def test_list_configs_orders_newest_version_first(db_session, seeded_game):
    game, _ = seeded_game
    await service.get_or_create_draft(db_session, game.code)
    configs = await service.list_configs(db_session, game.code)
    versions = [c.version for c in configs]
    assert versions == sorted(versions, reverse=True)


class TestAdminRouterWiring:
    """Route-registration smoke tests against the real dev Postgres
    (api_client) — read-only / additive only (draft creation is idempotent
    and never published here), so it can't disturb the active config other
    integration tests rely on."""

    async def test_list_configs_route(self, api_client):
        response = await api_client.get("/api/admin/games/amys-fruit-farm/configs")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list) and len(body) >= 1

    async def test_get_unknown_config_404s(self, api_client):
        import uuid

        response = await api_client.get(f"/api/admin/configs/{uuid.uuid4()}")
        assert response.status_code == 404

    async def test_create_and_fetch_draft_route(self, api_client):
        create_response = await api_client.post("/api/admin/games/amys-fruit-farm/draft")
        assert create_response.status_code == 200
        draft = create_response.json()
        assert draft["status"] == "draft"
        assert len(draft["symbols"]) > 0

        get_response = await api_client.get(f"/api/admin/configs/{draft['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == draft["id"]
