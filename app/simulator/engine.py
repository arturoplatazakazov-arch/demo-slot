"""Bulk spin simulation for RTP / volatility / hit-frequency / bonus-frequency
validation (TZ §7). Reuses the exact same pure engine + feature-plugin calls
as the real spin endpoint (app/api/v1/spin_service.py:run_spin) — spin_reels,
apply_reel_caps, apply_expanding_wild, evaluate_spin, and the free_spins
feature's is_triggered/execute — so the simulator can never silently drift
from production math.
What it skips is everything DB/HTTP-shaped: no Session, no SpinRecord, no
db.commit(). Free-spins state (remaining count, multiplier) is tracked in a
plain dict across iterations, exactly like Session.state is in production,
just held in memory instead of persisted.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.services.config_adapter import to_paylines, to_reel_set_config
from app.services.spin_features import apply_expanding_wild, apply_reel_caps
from app.engine.avalanche import run_avalanche
from app.engine.reels import spin_reels
from app.engine.rng import RNGProvider
from app.engine.types import PaylineDef, ReelSetConfig
from app.engine.wins import evaluate_spin
from app.features import default_registry
from app.features.base import FeatureContext
from app.models.config import GameConfig

# (lo, hi_exclusive, label) — hi=None means open-ended. The "0x" bucket is a
# total miss; buckets are otherwise win/bet ratio ranges, widening at the
# top since big multipliers are rare by construction.
_HISTOGRAM_BUCKETS: list[tuple[float, float | None, str]] = [
    (0, 0, "0x"),
    (0, 1, "0x-1x"),
    (1, 2, "1x-2x"),
    (2, 5, "2x-5x"),
    (5, 10, "5x-10x"),
    (10, 20, "10x-20x"),
    (20, 50, "20x-50x"),
    (50, 100, "50x-100x"),
    (100, 500, "100x-500x"),
    (500, None, "500x+"),
]


class FeatureConfigLike(Protocol):
    feature_type: str
    enabled: bool
    params: dict


@dataclass
class SimulationReport:
    num_spins: int
    total_wagered: str
    total_win: str
    rtp: float
    hit_frequency: float
    bonus_frequency: float
    volatility_stddev: float
    volatility_label: str
    max_win_multiplier: float
    rtp_by_mechanic: dict[str, float]
    win_histogram: list[dict]

    def to_dict(self) -> dict:
        return {
            "num_spins": self.num_spins,
            "total_wagered": self.total_wagered,
            "total_win": self.total_win,
            "rtp": self.rtp,
            "hit_frequency": self.hit_frequency,
            "bonus_frequency": self.bonus_frequency,
            "volatility_stddev": self.volatility_stddev,
            "volatility_label": self.volatility_label,
            "max_win_multiplier": self.max_win_multiplier,
            "rtp_by_mechanic": self.rtp_by_mechanic,
            "win_histogram": self.win_histogram,
        }


def _volatility_label(stddev: float) -> str:
    """Rough categorical read on the win/bet-ratio stddev — thresholds are a
    reasonable starting point (TZ leaves exact numbers to product/admin
    judgment, same as target_rtp's tolerance), not an industry standard."""
    if stddev < 1.5:
        return "low"
    if stddev < 4:
        return "medium"
    return "high"


def _histogram(ratios: list[float]) -> list[dict]:
    counts = {label: 0 for _, _, label in _HISTOGRAM_BUCKETS}
    for r in ratios:
        for lo, hi, label in _HISTOGRAM_BUCKETS:
            if lo == 0 and hi == 0:
                if r == 0:
                    counts[label] += 1
                    break
                continue
            lower_ok = r > lo if lo == 0 else r >= lo
            upper_ok = hi is None or r < hi
            if lower_ok and upper_ok:
                counts[label] += 1
                break
    return [{"label": label, "count": counts[label]} for _, _, label in _HISTOGRAM_BUCKETS]


def run_simulation(
    reel_set: ReelSetConfig,
    paylines: list[PaylineDef],
    free_spins_config: FeatureConfigLike | None,
    rng: RNGProvider,
    num_spins: int,
    bet_amount: Decimal,
    wild_config: FeatureConfigLike | None = None,
) -> SimulationReport:
    """Runs `num_spins` *base-game* bets (i.e. `num_spins` real wagers — any
    free spins a bet triggers happen in addition, fully simulated for
    accurate RTP, but don't themselves count against `num_spins`)."""
    if num_spins <= 0:
        raise ValueError("num_spins must be positive")
    if bet_amount <= 0:
        raise ValueError("bet_amount must be positive")

    free_spins_feature = default_registry.get("free_spins")
    bet_per_line = bet_amount / Decimal(len(paylines))

    state: dict = {}
    total_wagered = Decimal(0)
    base_win = Decimal(0)
    free_spins_win = Decimal(0)
    hits = 0
    bonus_triggers = 0
    total_spins_run = 0
    ratios: list[float] = []

    base_spins_done = 0
    while base_spins_done < num_spins:
        was_in_free_spins = state.get("free_spins_remaining", 0) > 0
        total_spins_run += 1
        if not was_in_free_spins:
            base_spins_done += 1
            total_wagered += bet_amount

        grid = spin_reels(reel_set, rng)
        grid = apply_reel_caps(grid, reel_set, rng)
        apply_expanding_wild(grid, wild_config, state, rng, bet_amount, reel_set)
        evaluation = evaluate_spin(grid, reel_set.symbols, paylines, bet_per_line, bet_amount)

        multiplier = Decimal(str(state.get("free_spins_multiplier", "1"))) if was_in_free_spins else Decimal(1)
        spin_win = evaluation.total_win * multiplier

        if free_spins_feature is not None and free_spins_config is not None:
            ctx = FeatureContext(
                session_state=state, rng=rng, bet_amount=bet_amount,
                symbols=reel_set.symbols, grid=grid, win_evaluation=evaluation,
            )
            if free_spins_feature.is_triggered(ctx, free_spins_config.params):
                result = free_spins_feature.execute(ctx, free_spins_config.params)
                state.update(result.state_patch)
                if not was_in_free_spins:
                    bonus_triggers += 1

        if was_in_free_spins:
            state["free_spins_remaining"] = max(0, int(state.get("free_spins_remaining", 0)) - 1)
            free_spins_win += spin_win
        else:
            base_win += spin_win

        if spin_win > 0:
            hits += 1
        ratios.append(float(spin_win / bet_amount))

    total_win = base_win + free_spins_win
    rtp = float(total_win / total_wagered)
    stddev = statistics.pstdev(ratios) if len(ratios) > 1 else 0.0

    return SimulationReport(
        num_spins=num_spins,
        total_wagered=str(total_wagered),
        total_win=str(total_win),
        rtp=rtp,
        hit_frequency=hits / total_spins_run,
        bonus_frequency=bonus_triggers / num_spins,
        volatility_stddev=stddev,
        volatility_label=_volatility_label(stddev),
        max_win_multiplier=max(ratios) if ratios else 0.0,
        rtp_by_mechanic={
            "base": float(base_win / total_wagered),
            "free_spins": float(free_spins_win / total_wagered),
        },
        win_histogram=_histogram(ratios),
    )


def run_avalanche_simulation(
    reel_set: ReelSetConfig,
    avalanche_config: FeatureConfigLike,
    free_spins_config: FeatureConfigLike | None,
    rng: RNGProvider,
    num_spins: int,
    bet_amount: Decimal,
) -> SimulationReport:
    """Avalanche counterpart of `run_simulation` above — same "num_spins
    base-game bets, free spins run in addition" contract, just calling
    app/engine/avalanche.py:run_avalanche per round instead of
    evaluate_spin, mirroring exactly what
    app/api/v1/spin_avalanche.py:run_avalanche_spin does in production (same
    "simulator never drifts from production math" guarantee as the
    line-pay path above)."""
    if num_spins <= 0:
        raise ValueError("num_spins must be positive")
    if bet_amount <= 0:
        raise ValueError("bet_amount must be positive")

    free_spins_feature = default_registry.get("free_spins")
    params = avalanche_config.params
    multiplier_steps = params.get("multiplier_steps", [1])
    max_cascades = params.get("max_cascades", 20)

    state: dict = {}
    total_wagered = Decimal(0)
    base_win = Decimal(0)
    free_spins_win = Decimal(0)
    hits = 0
    bonus_triggers = 0
    total_spins_run = 0
    ratios: list[float] = []

    base_spins_done = 0
    while base_spins_done < num_spins:
        was_in_free_spins = state.get("free_spins_remaining", 0) > 0
        total_spins_run += 1
        if not was_in_free_spins:
            base_spins_done += 1
            total_wagered += bet_amount

        grid = spin_reels(reel_set, rng)
        grid = apply_reel_caps(grid, reel_set, rng)
        result = run_avalanche(
            grid, reel_set, reel_set.symbols, rng, bet_amount,
            multiplier_steps=multiplier_steps, max_cascades=max_cascades,
        )

        multiplier = Decimal(str(state.get("free_spins_multiplier", "1"))) if was_in_free_spins else Decimal(1)
        spin_win = result.total_win * multiplier

        if free_spins_feature is not None and free_spins_config is not None:
            ctx = FeatureContext(
                session_state=state, rng=rng, bet_amount=bet_amount,
                symbols=reel_set.symbols, grid=result.initial_grid,
            )
            if free_spins_feature.is_triggered(ctx, free_spins_config.params):
                fs_result = free_spins_feature.execute(ctx, free_spins_config.params)
                state.update(fs_result.state_patch)
                if not was_in_free_spins:
                    bonus_triggers += 1

        if was_in_free_spins:
            state["free_spins_remaining"] = max(0, int(state.get("free_spins_remaining", 0)) - 1)
            free_spins_win += spin_win
        else:
            base_win += spin_win

        if spin_win > 0:
            hits += 1
        ratios.append(float(spin_win / bet_amount))

    total_win = base_win + free_spins_win
    rtp = float(total_win / total_wagered)
    stddev = statistics.pstdev(ratios) if len(ratios) > 1 else 0.0

    return SimulationReport(
        num_spins=num_spins,
        total_wagered=str(total_wagered),
        total_win=str(total_win),
        rtp=rtp,
        hit_frequency=hits / total_spins_run,
        bonus_frequency=bonus_triggers / num_spins,
        volatility_stddev=stddev,
        volatility_label=_volatility_label(stddev),
        max_win_multiplier=max(ratios) if ratios else 0.0,
        rtp_by_mechanic={
            "base": float(base_win / total_wagered),
            "free_spins": float(free_spins_win / total_wagered),
        },
        win_histogram=_histogram(ratios),
    )


def simulate_game_config(
    game_config: GameConfig,
    num_spins: int,
    rng: RNGProvider,
    bet_amount: Decimal | None = None,
) -> SimulationReport:
    """Convenience wrapper: ORM `GameConfig` (with symbols/paylines/
    feature_configs eagerly loaded, same as spin_service.load_active_config)
    -> SimulationReport. `bet_amount` defaults to the config's own min_bet
    (a fixed stake throughout the run — RTP is stake-independent since every
    payout is itself bet-proportional)."""
    reel_set = to_reel_set_config(game_config)
    free_spins_config = next(
        (fc for fc in game_config.feature_configs if fc.feature_type == "free_spins" and fc.enabled), None
    )
    stake = bet_amount if bet_amount is not None else Decimal(str(game_config.min_bet))

    avalanche_config = next(
        (fc for fc in game_config.feature_configs if fc.feature_type == "avalanche" and fc.enabled), None
    )
    if avalanche_config is not None:
        return run_avalanche_simulation(reel_set, avalanche_config, free_spins_config, rng, num_spins, stake)

    paylines = to_paylines(game_config)
    wild_config = next(
        (fc for fc in game_config.feature_configs if fc.feature_type == "expanding_wild" and fc.enabled), None
    )
    return run_simulation(reel_set, paylines, free_spins_config, rng, num_spins, stake, wild_config=wild_config)
