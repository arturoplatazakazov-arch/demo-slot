"""Free-spins round lifecycle on `Session.state` — the one place that knows
which keys a round keeps on the session dict and how they move through
enter -> accumulate -> decrement -> cleanup. Both spin orchestrations
(line-pay and avalanche, app/api/v1/) drive the exact same lifecycle; only
what happens *between* these calls differs per game type."""

from dataclasses import dataclass
from decimal import Decimal

STATE_KEYS = (
    "free_spins_remaining",
    "free_spins_multiplier",
    "free_spins_total_win",
    "free_spins_bet_amount",
)


def is_active(state: dict) -> bool:
    return state.get("free_spins_remaining", 0) > 0


def locked_bet_amount(state: dict) -> int:
    """The bet the round was entered with — every spin of the round replays
    it (no re-betting mid-round)."""
    return int(state["free_spins_bet_amount"])


def enter_round(state: dict, bet_amount: int) -> None:
    """Fresh (non-retrigger) entry: zero the round accumulator and lock the
    bet. The feature's own state_patch (spins awarded, base multiplier) has
    already been merged by the caller."""
    state["free_spins_total_win"] = "0"
    state["free_spins_bet_amount"] = bet_amount


def win_multiplier(state: dict, in_round: bool) -> Decimal:
    """The round's win multiplier, or 1 outside a round."""
    if not in_round:
        return Decimal(1)
    return Decimal(str(state.get("free_spins_multiplier", "1")))


@dataclass
class RoundStatus:
    remaining_after: int
    round_total_win: Decimal


def settle(state: dict, spin_win: Decimal, was_in_free_spins: bool) -> RoundStatus:
    """Accumulate this spin's win into the round total and consume one spin
    (no-op outside a round), then clear the round keys once the last spin is
    played. Returns what the response/popup layer needs — captured before
    the cleanup pops the keys, so the final spin of a round can still report
    the round's totals."""
    if was_in_free_spins:
        state["free_spins_total_win"] = str(
            Decimal(str(state.get("free_spins_total_win", "0"))) + spin_win
        )
        state["free_spins_remaining"] = max(0, int(state.get("free_spins_remaining", 0)) - 1)

    remaining_after = int(state.get("free_spins_remaining", 0))
    round_total_win = Decimal(str(state.get("free_spins_total_win", "0")))

    if remaining_after == 0:
        for key in STATE_KEYS:
            state.pop(key, None)

    return RoundStatus(remaining_after=remaining_after, round_total_win=round_total_win)
