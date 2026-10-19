"""Neon Joker Spins (GDD-02) additions to the shared features, pinned without
a database: the Hold & Win respin COLLECTOR, one jackpot tier per round, the
flat free-spins retrigger and the per-round max-win cap.

RNG draws are scripted with FakeRNG; every weight table below is chosen so
each draw is a single obvious index (weighted_pick: raw < cumulative)."""

from decimal import Decimal

from app.engine.types import SpinGrid
from app.features.base import FeatureContext
from app.features.free_spins import FreeSpinsFeature
from app.features.hold_and_win import HoldAndWinFeature
from app.services import free_spins_round

from tests.fakes import FakeRNG

# raw 0 -> "2", 1 -> "5", 2 -> "mini"
_VALUES = {"2": 1, "5": 1, "mini": 1}
# raw 0 -> lands, 1 -> blank
_LAND = {"coin": 1, "blank": 1}
# raw 0 -> coin, 1 -> collector (asked only once a symbol landed)
_SHARE = {"coin": 1, "collector": 1}


def _grid(*columns):
    return SpinGrid(reels=[list(c) for c in columns], draws=[])


def _config(**extra):
    return {
        "trigger_symbol_code": "coin",
        "respin_count": 3,
        "coin_value_weights": _VALUES,
        "respin_land_weights": _LAND,
        "jackpot_values": {"mini": 20},
        "respin_collector": {"symbol_code": "collector", "share_weights": _SHARE, "max_per_round": 2},
        **extra,
    }


def _run(grid, draws, **extra):
    ctx = FeatureContext(session_state={}, rng=FakeRNG(draws), bet_amount=Decimal(1), grid=grid)
    return HoldAndWinFeature().execute(ctx, _config(**extra))


def test_collector_sums_every_plain_coin_including_the_same_respin():
    # initial coins 2 and 5; one respin lands a collector at (0,1) and a 5 at
    # (1,1) — the collector counts that 5 too: 2 + 5 + 5 = 12.
    result = _run(_grid(["coin", "x"], ["coin", "x"]), [0, 1, 0, 1, 0, 0, 1])
    landed = result.details["respins"][0]["landed"]
    collector = next(c for c in landed if c["kind"] == "collector")
    assert collector["value"] == "12"
    assert result.details["collector_total"] == "12"
    assert result.win_amount == Decimal(2 + 5 + 5 + 12)


def test_collector_skips_jackpot_coins_and_one_tier_per_round():
    # initial: MINI (20) then — jackpot already on the grid — only plain faces:
    # 5. Respin: collector + a 2. The collector takes 5 + 2, never the MINI.
    result = _run(_grid(["coin", "x"], ["coin", "x"]), [2, 1, 0, 1, 0, 0, 0], one_jackpot_per_round=True)
    kinds = [c["kind"] for c in result.details["initial"]]
    assert kinds == ["mini", "5"]
    collector = next(c for c in result.details["respins"][0]["landed"] if c["kind"] == "collector")
    assert collector["value"] == "7"
    assert result.win_amount == Decimal(20 + 5 + 2 + 7)


def test_collector_limit_stops_asking_once_reached():
    # max 1 per round: after the first collector no share draw is made at all,
    # every later landing is a coin.
    cfg_collector = {"symbol_code": "collector", "share_weights": _SHARE, "max_per_round": 1}
    result = _run(_grid(["coin", "x", "x", "x"]), [0, 0, 1, 0, 0, 0, 0], respin_collector=cfg_collector)
    landed = result.details["respins"][0]["landed"]
    assert [c["kind"] for c in landed] == ["2", "2", "collector"]
    assert landed[-1]["value"] == "6"  # 2 (initial) + 2 + 2 of the same respin


def test_games_without_respin_collector_are_unchanged():
    ctx = FeatureContext(session_state={}, rng=FakeRNG([0] * 6), bet_amount=Decimal(1),
                         grid=_grid(["coin", "x"], ["coin", "x"]))
    cfg = {"trigger_symbol_code": "coin", "respin_count": 1, "coin_value_weights": {"1": 1},
           "respin_land_weights": {"coin": 1, "blank": 0}}
    result = HoldAndWinFeature().execute(ctx, cfg)
    assert "collector_total" not in result.details
    assert result.win_amount == Decimal(4)


def test_retrigger_awards_its_own_flat_count():
    grid = _grid(["scatter"], ["scatter"], ["scatter"])
    cfg = {"trigger_symbol_code": "scatter", "trigger_count": 3, "spins_awarded": 10, "retrigger_spins": 5}
    entry = FreeSpinsFeature().execute(FeatureContext(session_state={}, rng=FakeRNG([]), bet_amount=Decimal(1), grid=grid), cfg)
    assert entry.details["spins_awarded"] == 10
    again = FreeSpinsFeature().execute(
        FeatureContext(session_state={"free_spins_remaining": 3}, rng=FakeRNG([]), bet_amount=Decimal(1), grid=grid), cfg)
    assert again.details == {"spins_awarded": 5, "total_remaining": 8}


def test_round_cap_clips_the_entry_spin_and_cancels_its_round():
    state = {"free_spins_remaining": 10, "free_spins_total_win": "0", "free_spins_bet_amount": 10}
    win, hit = free_spins_round.apply_cap(state, Decimal(30000), 10, 2500, False, True)
    assert (win, hit) == (Decimal(25000), True)
    assert "free_spins_remaining" not in state


def test_round_cap_carries_across_free_spins_and_ends_the_round():
    state = {"free_spins_remaining": 10}
    win, hit = free_spins_round.apply_cap(state, Decimal(4000), 10, 2500, False, True)
    assert (win, hit) == (Decimal(4000), False)
    assert state["free_spins_cap_left"] == "21000"
    win, hit = free_spins_round.apply_cap(state, Decimal(30000), 10, 2500, True, False)
    assert (win, hit) == (Decimal(21000), True)
    assert state["free_spins_remaining"] == 1  # settle() consumes it and closes the round
    status = free_spins_round.settle(state, win, True)
    assert status.remaining_after == 0 and "free_spins_cap_left" not in state


def test_no_cap_configured_is_a_no_op():
    state = {}
    assert free_spins_round.apply_cap(state, Decimal(10**9), 10, None, False, False) == (Decimal(10**9), False)
    assert state == {}
