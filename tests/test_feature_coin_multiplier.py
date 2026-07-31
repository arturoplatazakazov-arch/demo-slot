from decimal import Decimal

from app.engine.types import LineWin, SpinGrid, WinEvaluation
from app.features.base import FeatureContext
from app.features.coin_multiplier import CoinMultiplierFeature
from tests.fakes import FakeRNG


def _grid(*columns):
    return SpinGrid(reels=[list(c) for c in columns], draws=[])


def _win_eval(line_pay_amount):
    line_win = LineWin(
        payline_index=1,
        symbol_code="rare_cat",
        count=3,
        payout_multiplier=Decimal(10),
        win_amount=Decimal(line_pay_amount),
        positions=((0, 1), (1, 1), (2, 1)),
    )
    wins = (line_win,) if line_pay_amount else ()
    return WinEvaluation(line_wins=wins, count_wins=())


def test_not_triggered_without_any_coin():
    grid = _grid(["x", "x"], ["collector_tiger", "x"])
    ctx = FeatureContext(
        session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid, win_evaluation=_win_eval(10)
    )
    assert CoinMultiplierFeature().is_triggered(ctx, {}) is False


def test_triggered_by_a_coin_alone_even_without_a_line_win_or_collector():
    # A coin's value always draws/shows regardless of a win or a collector —
    # only whether it *pays out* (execute()'s "applied") is gated on those.
    grid = _grid(["coin", "x"], ["x", "x"])
    ctx = FeatureContext(
        session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid, win_evaluation=_win_eval(0)
    )
    assert CoinMultiplierFeature().is_triggered(ctx, {}) is True


def test_triggered_when_line_win_coin_and_collector_all_present():
    grid = _grid(["coin", "x"], ["collector_tiger", "x"])
    ctx = FeatureContext(
        session_state={}, rng=FakeRNG([]), bet_amount=Decimal("1"), grid=grid, win_evaluation=_win_eval(10)
    )
    assert CoinMultiplierFeature().is_triggered(ctx, {}) is True


def test_execute_shows_coin_value_but_does_not_apply_without_a_collector():
    grid = _grid(["coin", "x"], ["x", "x"])  # no collector_tiger, but there is a line win
    ctx = FeatureContext(
        session_state={},
        rng=FakeRNG([1]),  # -> index 1 ("10")
        bet_amount=Decimal("1"),
        grid=grid,
        win_evaluation=_win_eval(20),
    )
    result = CoinMultiplierFeature().execute(ctx, {"value_weights": {"5": 1, "10": 1}})

    assert result.details["applied"] is False
    assert result.details["coin_positions"] == [{"reel": 0, "row": 0, "value": "10"}]
    assert result.win_amount == Decimal(0)


def test_execute_shows_coin_value_but_does_not_apply_without_a_line_win():
    grid = _grid(["coin", "collector_tiger"], ["x", "x"])  # collector present, no win
    ctx = FeatureContext(
        session_state={},
        rng=FakeRNG([1]),
        bet_amount=Decimal("1"),
        grid=grid,
        win_evaluation=_win_eval(0),
    )
    result = CoinMultiplierFeature().execute(ctx, {"value_weights": {"5": 1, "10": 1}})

    assert result.details["applied"] is False
    assert result.win_amount == Decimal(0)


def test_execute_multiplies_line_pay_by_sum_of_coin_multipliers():
    # Two coins: values 5 and 10 (deterministic via a 2-key weight table and
    # FakeRNG raw draws), collector present. multiplier_sum = 15.
    grid = _grid(["coin", "collector_tiger"], ["coin", "x"])
    ctx = FeatureContext(
        session_state={},
        rng=FakeRNG([0, 1]),  # first coin -> index 0 ("5"), second coin -> index 1 ("10")
        bet_amount=Decimal("1"),
        grid=grid,
        win_evaluation=_win_eval(20),
    )
    config = {"value_weights": {"5": 1, "10": 1}}
    result = CoinMultiplierFeature().execute(ctx, config)

    assert result.details["multiplier_sum"] == "15"
    assert len(result.details["coin_positions"]) == 2
    assert result.details["applied"] is True
    # delta over the already-computed line_pay_total: 20 * (15 - 1) = 280
    assert result.win_amount == Decimal(20) * Decimal(14)


def test_config_schema_lists_expected_fields():
    schema = CoinMultiplierFeature().get_config_schema()
    assert set(schema["required"]) <= set(schema["properties"].keys())
    assert "coin_symbol_code" in schema["properties"]
    assert "collector_symbol_code" in schema["properties"]
