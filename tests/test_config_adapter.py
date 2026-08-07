from decimal import Decimal

from app.services.config_adapter import symbol_tiers, to_paylines, to_reel_set_config
from app.seed.amys_fruit_farm import NUM_REELS, NUM_ROWS, PAYLINES, build_game_config


def test_to_reel_set_config_matches_seed_shape():
    _, game_config = build_game_config()
    reel_set = to_reel_set_config(game_config)

    assert reel_set.num_reels == NUM_REELS
    assert reel_set.num_rows == NUM_ROWS
    assert {s.code for s in reel_set.symbols} == {
        "scatter", "wild", "duck", "watermelon", "corn", "blueberry", "strawberry", "cow", "pear", "dog",
    }
    duck = next(s for s in reel_set.symbols if s.code == "duck")
    assert duck.weights == [744] * NUM_REELS
    assert duck.pays[3] == Decimal("10")


def test_to_paylines_preserves_index_and_positions():
    _, game_config = build_game_config()
    paylines = to_paylines(game_config)
    assert len(paylines) == len(PAYLINES)
    assert paylines[0].index == 1
    assert list(paylines[0].positions) == PAYLINES[0]


def test_symbol_tiers_splits_low_and_high():
    _, game_config = build_game_config()
    tiers = symbol_tiers(game_config)
    assert tiers["duck"] == "high"
    assert tiers["cow"] == "high"
    assert tiers["dog"] == "high"
    assert tiers["watermelon"] == "low"
    assert tiers["pear"] == "low"
