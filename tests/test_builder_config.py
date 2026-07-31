"""Tests for app/api/admin/builder_config.py (pure generation) and
service.generate_config_from_builder (the DB-facing wrapper that turns a
slot-builder Stage 3 selection into a real GameConfig) — the "close the
loop" piece connecting the wizard to an actually simulatable/playable game.
"""

import pytest
from fastapi import HTTPException

from app.api.admin import service
from app.api.admin.builder_config import AUTO_NOTE_PREFIX, generate_default_config, run_builder_test_spin
from app.models.enums import GameConfigStatus, SymbolType
from app.models.game import Game
from app.simulator import FastRNG


# ---------- generate_default_config (pure function, no DB) ----------

def test_generates_base_symbols_and_paylines_with_no_mechanics():
    game = Game(code="plain-slot", name="Plain Slot")
    config = generate_default_config(game, reels=5, rows=3, mechanics=[])

    codes = {s.code for s in config.symbols}
    assert {"low_a", "low_b", "low_c", "low_d", "high_a", "high_b", "wild"} <= codes
    assert "scatter" not in codes
    assert "coin" not in codes
    assert len(config.paylines) == 3
    assert [p.positions for p in config.paylines] == [[0] * 5, [1] * 5, [2] * 5]
    assert config.feature_configs == []
    assert config.notes.startswith(AUTO_NOTE_PREFIX)


def test_symbol_assets_populate_image_ref_in_display_order():
    game = Game(code="art-slot", name="Art Slot")
    symbol_assets = [{"id": f"asset-{i}", "file": f"symbol{i}.png"} for i in range(3)]
    config = generate_default_config(game, reels=5, rows=3, mechanics=[], symbol_assets=symbol_assets)

    by_order = sorted(config.symbols, key=lambda s: s.display_order)
    assert [s.image_ref for s in by_order[:3]] == ["asset-0", "asset-1", "asset-2"]
    assert all(s.image_ref is None for s in by_order[3:])


def test_symbol_assets_none_or_absent_leaves_image_ref_none():
    game = Game(code="no-art-slot", name="No Art Slot")
    config_absent = generate_default_config(game, reels=5, rows=3, mechanics=[])
    config_none = generate_default_config(game, reels=5, rows=3, mechanics=[], symbol_assets=None)

    assert all(s.image_ref is None for s in config_absent.symbols)
    assert all(s.image_ref is None for s in config_none.symbols)


def test_scatter_symbol_added_for_scatter_or_free_spins():
    game = Game(code="s1", name="S1")
    assert "scatter" in {s.code for s in generate_default_config(game, 5, 3, ["scatter"]).symbols}
    assert "scatter" in {s.code for s in generate_default_config(game, 5, 3, ["free_spins"]).symbols}
    assert "scatter" not in {s.code for s in generate_default_config(game, 5, 3, ["gamble"]).symbols}


def test_wild_marked_expanding_only_when_selected():
    game = Game(code="s2", name="S2")
    plain = next(s for s in generate_default_config(game, 5, 3, []).symbols if s.code == "wild")
    expanding = next(s for s in generate_default_config(game, 5, 3, ["expanding_wild"]).symbols if s.code == "wild")
    assert plain.wild_subtype is None
    assert expanding.wild_subtype == "expanding"


def test_coin_and_collector_symbols_for_hold_and_win_and_coin_multiplier():
    game = Game(code="s3", name="S3")
    hold_and_win_only = generate_default_config(game, 5, 3, ["hold_and_win"])
    assert "coin" in {s.code for s in hold_and_win_only.symbols}
    assert "collector" not in {s.code for s in hold_and_win_only.symbols}

    both = generate_default_config(game, 5, 3, ["hold_and_win", "coin_multiplier"])
    codes = {s.code for s in both.symbols}
    assert "coin" in codes and "collector" in codes
    coin = next(s for s in both.symbols if s.code == "coin")
    assert coin.symbol_type == SymbolType.BONUS.value
    assert coin.paytable == {}  # never pays its own count-pay win


def test_feature_configs_match_selected_mechanics():
    game = Game(code="s4", name="S4")
    config = generate_default_config(game, 5, 3, ["free_spins", "gamble", "jackpot"])
    types = {fc.feature_type for fc in config.feature_configs}
    assert types == {"free_spins", "gamble", "jackpot"}


def test_bonus_buy_targets_free_spins_when_available():
    game = Game(code="s5", name="S5")
    config = generate_default_config(game, 5, 3, ["free_spins", "bonus_buy"])
    bonus_buy = next(fc for fc in config.feature_configs if fc.feature_type == "bonus_buy")
    assert bonus_buy.enabled is True
    assert bonus_buy.params["target_feature_id"] == "free_spins"
    # Without this, /api/v1/feature/buy can never match this product (see
    # app/api/v1/bonus_buy.py's resolve_bonus_buy_product fallback path).
    assert bonus_buy.params["buy_id"] == "bonus_buy"


@pytest.mark.parametrize("rows", [1, 2, 3, 4, 5, 6, 7, 10])
def test_bet_steps_always_divisible_by_payline_count(rows):
    # /api/v1's validate_bet_amount (app/api/v1/loaders.py) rejects any
    # bet_amount not evenly divisible by the payline count, and one straight
    # payline gets laid per row — so every real spin against a
    # builder-generated config was silently unplayable for any row count
    # DEFAULT_BET_STEPS didn't happen to divide evenly (e.g. rows=3).
    game = Game(code=f"rows-{rows}", name="Rows")
    config = generate_default_config(game, reels=5, rows=rows, mechanics=[])
    assert len(config.paylines) == rows
    assert all(step % rows == 0 for step in config.bet_steps)
    assert config.min_bet % rows == 0
    assert config.max_bet % rows == 0


def test_bonus_buy_disabled_when_no_purchasable_target():
    game = Game(code="s6", name="S6")
    config = generate_default_config(game, 5, 3, ["bonus_buy"])
    bonus_buy = next(fc for fc in config.feature_configs if fc.feature_type == "bonus_buy")
    assert bonus_buy.enabled is False


def test_paytable_scales_for_non_five_reel_grids():
    game = Game(code="s7", name="S7")
    config = generate_default_config(game, reels=3, rows=3, mechanics=[])
    low_a = next(s for s in config.symbols if s.code == "low_a")
    # Only one achievable match-count (3-of-3) on a 3-reel grid.
    assert set(low_a.paytable.keys()) == {"3"}
    assert all(len(s.reel_weights) == 3 for s in config.symbols)


# ---------- avalanche (cascade) mechanic ----------

def test_avalanche_has_no_paylines_and_a_feature_config():
    game = Game(code="ava-1", name="Ava 1")
    config = generate_default_config(game, reels=6, rows=5, mechanics=["avalanche"])
    assert config.paylines == []
    avalanche_fc = next(fc for fc in config.feature_configs if fc.feature_type == "avalanche")
    assert avalanche_fc.enabled is True
    assert avalanche_fc.params == {"multiplier_steps": [1, 2, 3, 5], "max_cascades": 20}


def test_avalanche_thresholds_scale_to_grid_size_matching_party_of_goods():
    # Party of Goods (6x5=30 cells) uses exactly {8,10,12,15} — this is the
    # reference point the scaling formula must reproduce exactly.
    game = Game(code="ava-2", name="Ava 2")
    config = generate_default_config(game, reels=6, rows=5, mechanics=["avalanche"])
    low_a = next(s for s in config.symbols if s.code == "low_a")
    assert set(int(k) for k in low_a.paytable.keys()) == {8, 10, 12, 15}

    small = generate_default_config(Game(code="ava-3", name="Ava 3"), reels=5, rows=3, mechanics=["avalanche"])
    small_low_a = next(s for s in small.symbols if s.code == "low_a")
    thresholds = sorted(int(k) for k in small_low_a.paytable.keys())
    # 15-cell board: thresholds must be strictly ascending, none exceeding
    # the board size, and roughly the same board-fraction shape as 8/10/12/15
    # scaled down (not the exact 30-cell numbers).
    assert thresholds == sorted(set(thresholds))
    assert all(2 <= t <= 15 for t in thresholds)
    assert thresholds != [8, 10, 12, 15]


def test_avalanche_bomb_symbol_always_present():
    game = Game(code="ava-4", name="Ava 4")
    config = generate_default_config(game, reels=6, rows=5, mechanics=["avalanche"])
    boom = next(s for s in config.symbols if s.code == "boom")
    assert boom.is_bomb is True
    assert boom.paytable == {}


def test_avalanche_multiplier_tokens_only_with_coin_multiplier():
    game = Game(code="ava-5", name="Ava 5")
    without = generate_default_config(game, reels=6, rows=5, mechanics=["avalanche"])
    assert "x2" not in {s.code for s in without.symbols}

    with_tokens = generate_default_config(
        Game(code="ava-6", name="Ava 6"), reels=6, rows=5, mechanics=["avalanche", "coin_multiplier"],
    )
    tokens = {s.code: s.multiplier_value for s in with_tokens.symbols if s.code.startswith("x")}
    assert tokens == {"x2": 2, "x3": 3, "x5": 5, "x7": 7}


def test_avalanche_bonus_buy_never_targets_hold_and_win():
    game = Game(code="ava-7", name="Ava 7")
    config = generate_default_config(
        game, reels=6, rows=5, mechanics=["avalanche", "hold_and_win", "bonus_buy"],
    )
    bonus_buy = next(fc for fc in config.feature_configs if fc.feature_type == "bonus_buy")
    # hold_and_win isn't a purchasable target for an avalanche game (no
    # hold_and_win-compatible symbol/feature gets generated in this branch),
    # and free_spins wasn't selected either, so the product stays disabled.
    assert bonus_buy.params["target_feature_id"] == "free_spins"
    assert bonus_buy.enabled is False
    assert "hold_and_win" not in {fc.feature_type for fc in config.feature_configs}


def test_avalanche_bet_steps_unrounded_since_no_paylines():
    game = Game(code="ava-8", name="Ava 8")
    config = generate_default_config(game, reels=6, rows=5, mechanics=["avalanche"])
    assert config.bet_steps == [10_000, 25_000, 50_000, 100_000, 250_000, 500_000]


# ---------- generate_config_from_builder (DB-facing wrapper) ----------

async def test_generate_config_from_builder_creates_draft(db_session):
    game = Game(code="new-slot", name="New Slot")
    db_session.add(game)
    await db_session.commit()

    config = await service.generate_config_from_builder(db_session, "new-slot", 5, 3, ["free_spins"])

    assert config.status == GameConfigStatus.DRAFT.value
    assert config.num_reels == 5 and config.num_rows == 3
    assert any(fc.feature_type == "free_spins" for fc in config.feature_configs)


async def test_generate_config_from_builder_is_regeneratable_when_untouched(db_session):
    game = Game(code="regen-slot", name="Regen Slot")
    db_session.add(game)
    await db_session.commit()

    first = await service.generate_config_from_builder(db_session, "regen-slot", 5, 3, ["gamble"])
    second = await service.generate_config_from_builder(db_session, "regen-slot", 3, 3, ["jackpot"])

    assert second.id != first.id
    assert second.num_reels == 3
    assert {fc.feature_type for fc in second.feature_configs} == {"jackpot"}


async def test_generate_config_from_builder_refuses_to_clobber_published_config(db_session):
    game = Game(code="published-slot", name="Published Slot")
    db_session.add(game)
    await db_session.commit()

    config = await service.generate_config_from_builder(db_session, "published-slot", 5, 3, [])
    await service.publish_config(db_session, config.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.generate_config_from_builder(db_session, "published-slot", 5, 3, [])
    assert exc_info.value.status_code == 409


async def test_generate_config_from_builder_refuses_to_clobber_hand_edited_draft(db_session):
    game = Game(code="edited-slot", name="Edited Slot")
    db_session.add(game)
    await db_session.commit()

    config = await service.generate_config_from_builder(db_session, "edited-slot", 5, 3, [])
    config.notes = "Hand-tuned by an admin"
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.generate_config_from_builder(db_session, "edited-slot", 5, 3, [])
    assert exc_info.value.status_code == 409


# ---------- run_builder_test_spin (one ad-hoc spin against a draft config) ----------

def test_run_builder_test_spin_returns_a_full_grid():
    game = Game(code="spin-test", name="Spin Test")
    config = generate_default_config(game, reels=5, rows=3, mechanics=["free_spins", "expanding_wild"])

    result = run_builder_test_spin(config, FastRNG(seed=1))

    assert result["bet_amount"] == int(config.min_bet)
    assert len(result["grid"]) == 5
    assert all(len(column) == 3 for column in result["grid"])
    assert isinstance(result["total_win"], int) and result["total_win"] >= 0
    assert "line_wins" in result and "count_wins" in result


def test_run_builder_test_spin_works_on_non_five_reel_grid():
    game = Game(code="spin-test-2", name="Spin Test 2")
    config = generate_default_config(game, reels=3, rows=4, mechanics=[])

    result = run_builder_test_spin(config, FastRNG(seed=2))

    assert len(result["grid"]) == 3
    assert all(len(column) == 4 for column in result["grid"])


def test_run_builder_test_spin_returns_cascade_steps_for_avalanche():
    game = Game(code="spin-test-avalanche", name="Spin Test Avalanche")
    config = generate_default_config(game, reels=6, rows=5, mechanics=["avalanche", "coin_multiplier"])

    result = run_builder_test_spin(config, FastRNG(seed=3))

    assert result["line_wins"] == []
    assert result["count_wins"] == []
    assert "avalanche" in result
    assert isinstance(result["avalanche"]["steps"], list)
    # Row-major, matching production's to_frontend_grid convention (the
    # avalanche branch adopts this even though the older line-pay branch
    # above keeps its own historical reel-major shape).
    assert len(result["grid"]) == 5
    assert all(len(row) == 6 for row in result["grid"])
