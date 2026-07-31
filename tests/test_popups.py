from decimal import Decimal

from app.services.popups import select_popup
from app.engine.types import LineWin

TIERS = {"duck": "high", "pear": "low"}


def _line_win(symbol, count):
    return LineWin(
        payline_index=1, symbol_code=symbol, count=count,
        payout_multiplier=Decimal(1), win_amount=Decimal(count), positions=(),
    )


def _select(line_wins, total_win, **kwargs):
    defaults = dict(
        in_free_spins=False,
        free_spins_remaining_after=0,
        free_spins_round_total_win=Decimal(0),
    )
    defaults.update(kwargs)
    return select_popup(line_wins=line_wins, total_win=total_win, tiers=TIERS, **defaults)


def test_low_tier_win_never_gets_a_popup():
    assert _select([_line_win("pear", 3)], Decimal(10)) is None
    assert _select([_line_win("pear", 5)], Decimal(50)) is None


def test_high_tier_three_of_a_kind_is_big_win():
    popup = _select([_line_win("duck", 3)], Decimal(100))
    assert popup == {"type": "bigWin", "amount": Decimal(100)}


def test_high_tier_four_of_a_kind_is_mega_win():
    popup = _select([_line_win("duck", 4)], Decimal(250))
    assert popup == {"type": "megaWin", "amount": Decimal(250)}


def test_high_tier_five_of_a_kind_is_epic_win():
    popup = _select([_line_win("duck", 5)], Decimal(500))
    assert popup == {"type": "epicWin", "amount": Decimal(500)}


def test_best_tier_wins_when_multiple_lines_hit():
    popup = _select([_line_win("duck", 3), _line_win("duck", 5)], Decimal(600))
    assert popup["type"] == "epicWin"


def test_no_win_no_popup():
    assert _select([], Decimal(0)) is None


def test_free_spins_last_spin_shows_total_win_popup():
    popup = _select(
        [], Decimal(20),
        in_free_spins=True, free_spins_remaining_after=0, free_spins_round_total_win=Decimal(500),
    )
    assert popup == {"type": "bonusSpinsTotalWin", "amount": Decimal(500)}


def test_free_spins_mid_round_win_gets_no_popup():
    # A plain win mid-round (no (re)trigger this spin, spins_awarded unset)
    # isn't a bonusSpinsWin — that popup announces spins just awarded, not a
    # per-spin cash win (the inline win-amount display covers that instead).
    popup = _select(
        [], Decimal(20),
        in_free_spins=True, free_spins_remaining_after=3, free_spins_round_total_win=Decimal(80),
    )
    assert popup is None


def test_free_spins_zero_win_spin_has_no_popup():
    popup = _select(
        [], Decimal(0),
        in_free_spins=True, free_spins_remaining_after=5, free_spins_round_total_win=Decimal(80),
    )
    assert popup is None


def test_free_spins_retrigger_shows_spins_awarded_popup():
    # bonusSpinsWin's amount is the spins-awarded count, not the cash win —
    # confirmed regardless of how big total_win was this spin.
    popup = _select(
        [], Decimal(500),
        in_free_spins=True, free_spins_remaining_after=13, free_spins_round_total_win=Decimal(900),
        spins_awarded=10,
    )
    assert popup == {"type": "bonusSpinsWin", "amount": 10}


def test_free_spins_mode_ignores_tier_popups_even_on_premium_win():
    # Documented assumption: bonusSpinsWin/Total replace big/mega/epic during
    # the bonus round rather than stacking with them — and without an actual
    # (re)trigger this spin, no popup fires at all (not even bonusSpinsWin).
    popup = _select(
        [_line_win("duck", 5)], Decimal(500),
        in_free_spins=True, free_spins_remaining_after=2, free_spins_round_total_win=Decimal(900),
    )
    assert popup is None
