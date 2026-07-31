from decimal import Decimal

from app.engine.types import LineWin, WinEvaluation
from app.features.base import FeatureContext
from app.features.gamble import GambleFeature
from tests.fakes import FakeRNG

_WIN = WinEvaluation(
    line_wins=(
        LineWin(
            payline_index=1, symbol_code="H1", count=3,
            payout_multiplier=Decimal(5), win_amount=Decimal(5), positions=(),
        ),
    ),
    count_wins=(),
)
_NO_WIN = WinEvaluation(line_wins=(), count_wins=())


def _ctx(session_state, rng_values=(), bet_amount="1", win_evaluation=None):
    return FeatureContext(
        session_state=session_state,
        rng=FakeRNG(list(rng_values)),
        bet_amount=Decimal(bet_amount),
        win_evaluation=win_evaluation,
    )


def test_offered_only_when_last_spin_won():
    feature = GambleFeature()
    assert feature.is_triggered(_ctx({}, win_evaluation=_WIN), {}) is True
    assert feature.is_triggered(_ctx({}, win_evaluation=_NO_WIN), {}) is False
    assert feature.is_triggered(_ctx({}, win_evaluation=None), {}) is False


def test_color_mode_win_doubles_stake():
    state = {"gamble_stake": "5", "gamble_guess": "red"}
    result = GambleFeature().execute(_ctx(state, rng_values=[0]), {"mode": "color"})
    assert result.triggered is True
    assert result.details["outcome"] == "red"
    assert result.details["won"] is True
    assert result.win_amount == Decimal(10)
    assert result.state_patch["gamble_rounds_played"] == 1


def test_color_mode_loss_forfeits_stake():
    state = {"gamble_stake": "5", "gamble_guess": "red"}
    result = GambleFeature().execute(_ctx(state, rng_values=[1]), {"mode": "color"})
    assert result.details["outcome"] == "black"
    assert result.details["won"] is False
    assert result.win_amount == Decimal(0)


def test_suit_mode_quadruples_stake_on_win():
    state = {"gamble_stake": "5", "gamble_guess": "spades"}
    result = GambleFeature().execute(_ctx(state, rng_values=[3]), {"mode": "suit"})
    assert result.details["outcome"] == "spades"
    assert result.win_amount == Decimal(20)


def test_max_rounds_blocks_further_gambling():
    state = {"gamble_stake": "5", "gamble_guess": "red", "gamble_rounds_played": 2}
    result = GambleFeature().execute(_ctx(state), {"mode": "color", "max_rounds": 2})
    assert result.triggered is False
    assert result.details["reason"] == "max_rounds_reached"


def test_max_win_multiplier_blocks_further_gambling():
    state = {"gamble_stake": "10", "gamble_guess": "red"}
    result = GambleFeature().execute(
        _ctx(state, bet_amount="1"), {"mode": "color", "max_win_multiplier": 5}
    )
    assert result.triggered is False
    assert result.details["reason"] == "max_win_reached"


def test_config_schema_lists_expected_fields():
    schema = GambleFeature().get_config_schema()
    assert set(schema["required"]) <= set(schema["properties"].keys())
    assert "mode" in schema["properties"]
