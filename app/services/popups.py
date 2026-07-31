"""Win-tier popup selection for the frontend (front/js/slot.js POPUP_FOLDERS).

Rule, as specified by product (not a bet-multiplier threshold): a line win
only qualifies for a popup when the winning symbol is "high" tier —
3-of-a-kind cheap symbols are a plain base win with no popup.
  - high-tier, count 3 -> bigWin
  - high-tier, count 4 -> megaWin
  - high-tier, count 5 -> epicWin
During an active free-spins round this is superseded by bonusSpinsWin /
bonusSpinsTotalWin (see `select_popup` docstring for the exact precedence
this assumes — flagged as an open question, product hasn't specified
whether big/mega/epic should still fire mid-bonus).
"""

from decimal import Decimal
from typing import Sequence

from app.engine.types import LineWin

_TIER_POPUP_BY_COUNT = {5: "epicWin", 4: "megaWin", 3: "bigWin"}


def select_base_game_popup(
    line_wins: Sequence[LineWin], total_win: Decimal, tiers: dict[str, str]
) -> dict | None:
    best_count = max(
        (win.count for win in line_wins if tiers.get(win.symbol_code) == "high"),
        default=0,
    )
    for threshold in (5, 4, 3):
        if best_count >= threshold:
            return {"type": _TIER_POPUP_BY_COUNT[threshold], "amount": total_win}
    return None


def select_popup(
    *,
    line_wins: Sequence[LineWin],
    total_win: Decimal,
    tiers: dict[str, str],
    in_free_spins: bool,
    free_spins_remaining_after: int,
    free_spins_round_total_win: Decimal,
    spins_awarded: int | None = None,
) -> dict | None:
    if in_free_spins:
        # Assumption: bonusSpinsWin/bonusSpinsTotalWin replace big/mega/epic
        # during the bonus round rather than stacking with them — confirm.
        if free_spins_remaining_after == 0:
            return {"type": "bonusSpinsTotalWin", "amount": free_spins_round_total_win}
        # bonusSpinsWin announces a (re)trigger — "you won N free spins" —
        # not a per-spin cash win (that's just the plain inline win-amount
        # display, no popup). Only fires on the spin that actually (re)awards
        # spins; a spins_awarded of 0/None means no trigger happened this
        # spin, so no popup at all.
        if spins_awarded:
            return {"type": "bonusSpinsWin", "amount": spins_awarded}
        return None

    return select_base_game_popup(line_wins, total_win, tiers)


# Avalanche games have no paylines/symbol tiers to key a popup off of (see
# app/engine/avalanche.py) — win-to-bet ratio stands in for "how big was
# this win" instead. Thresholds are a starting point (same status as
# _TIER_POPUP_BY_COUNT above), not RTP-tuned.
_AVALANCHE_TIER_POPUP_BY_RATIO = ((50, "epicWin"), (25, "megaWin"), (10, "bigWin"))


def select_avalanche_base_popup(total_win: Decimal, bet_amount: Decimal) -> dict | None:
    if bet_amount <= 0:
        return None
    ratio = total_win / bet_amount
    for threshold, popup_type in _AVALANCHE_TIER_POPUP_BY_RATIO:
        if ratio >= threshold:
            return {"type": popup_type, "amount": total_win}
    return None


def select_avalanche_popup(
    *,
    total_win: Decimal,
    bet_amount: Decimal,
    in_free_spins: bool,
    free_spins_remaining_after: int,
    free_spins_round_total_win: Decimal,
    spins_awarded: int | None = None,
) -> dict | None:
    """Mirrors `select_popup` above, swapping the base-game branch for
    `select_avalanche_base_popup` (no line_wins/tiers to key off)."""
    if in_free_spins:
        if free_spins_remaining_after == 0:
            return {"type": "bonusSpinsTotalWin", "amount": free_spins_round_total_win}
        # See select_popup's comment: bonusSpinsWin announces a (re)trigger's
        # spins-awarded count, not a per-spin cash win.
        if spins_awarded:
            return {"type": "bonusSpinsWin", "amount": spins_awarded}
        return None

    return select_avalanche_base_popup(total_win, bet_amount)
