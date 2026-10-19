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
    # Neon Joker Spins: what is left of round_max_win_multiplier x bet.
    "free_spins_cap_left",
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


def apply_cap(
    state: dict, spin_win: Decimal, bet_amount: int, cap_multiplier: int | None,
    was_in_free_spins: bool, entered_now: bool,
) -> tuple[Decimal, bool]:
    """Max win per round (GDD-02 §1): the paid spin plus every feature it
    started never pays more than cap_multiplier x bet. Returns the (possibly
    clipped) spin win and whether the cap was hit. Hitting it inside a round
    ends the round (one spin left, which settle() consumes); hitting it on
    the entry spin cancels the round it would have opened."""
    if not cap_multiplier:
        return spin_win, False
    if was_in_free_spins:
        cap_left = Decimal(str(state.get("free_spins_cap_left", Decimal(cap_multiplier) * bet_amount)))
    else:
        cap_left = Decimal(cap_multiplier) * bet_amount
    if spin_win >= cap_left:
        if was_in_free_spins:
            state["free_spins_remaining"] = 1
        elif entered_now:
            for key in STATE_KEYS:
                state.pop(key, None)
        return cap_left, True
    if was_in_free_spins or entered_now:
        state["free_spins_cap_left"] = str(cap_left - spin_win)
    return spin_win, False
