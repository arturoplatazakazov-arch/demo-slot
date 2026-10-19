"""Round rules of the scatter-tumble game on top of app/engine/scatter_tumble.py:
free spins with the accumulating TOTAL MULTIPLIER, scatter pays, the jackpot
wheel, the three bonus-buy SKUs and the 10 000x round cap.

Everything here is in "x bet" units (Decimal) and free of DB/HTTP, so the
API orchestration (app/api/v1/spin_tumble.py) and the RTP simulator
(scripts/olympus_thunder_rtp.py) run the exact same code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from app.engine.rng import RNGProvider
from app.engine.scatter_tumble import (
    EAGLE,
    SCATTER,
    SeriesResult,
    TumbleRules,
    WeightTable,
    apply_series_multiplier,
    run_series,
    scatter_pay,
    service_grid,
)

MODES = ("base", "fs", "super")


@dataclass(frozen=True)
class BuyProduct:
    buy_id: str
    cost: Decimal  # x bet
    kind: str  # "free_spins" | "super_free_spins" | "jackpot"
    enabled: bool = True


@dataclass(frozen=True)
class Wheel:
    trigger_count: int
    prizes: Mapping[str, Decimal]
    sectors: tuple[str, ...]  # tier per visual sector, clockwise from 12 o'clock
    natural: WeightTable
    bought: WeightTable

    def spin(self, rng: RNGProvider, bought: bool) -> tuple[str, int]:
        """Server-side outcome (tier by the odds table), then one of that
        tier's visual sectors for the client to land on."""
        tier = (self.bought if bought else self.natural).draw(rng)
        sectors = [i for i, t in enumerate(self.sectors) if t == tier]
        return tier, sectors[rng.randbelow(len(sectors))]


@dataclass(frozen=True)
class TumbleGame:
    rules: TumbleRules
    weights: Mapping[str, WeightTable]
    scatter_pays: Mapping[int, Decimal]
    fs_trigger: int
    fs_spins: int
    retrigger_count: int
    retrigger_spins: int
    wheel: Wheel
    products: tuple[BuyProduct, ...]
    buy_enabled: bool
    max_win: Decimal

    @classmethod
    def from_params(cls, params: Mapping, num_reels: int, num_rows: int) -> TumbleGame:
        fs = params["free_spins"]
        jp = params["jackpot"]
        buy = params.get("bonus_buy", {})
        return cls(
            rules=TumbleRules.from_params(params, num_reels, num_rows),
            weights={mode: WeightTable([tuple(p) for p in params["weights"][mode]]) for mode in MODES},
            scatter_pays={int(k): Decimal(str(v)) for k, v in params["scatter_pays"].items()},
            fs_trigger=int(fs["trigger_count"]),
            fs_spins=int(fs["spins"]),
            retrigger_count=int(fs["retrigger_count"]),
            retrigger_spins=int(fs["retrigger_spins"]),
            wheel=Wheel(
                trigger_count=int(jp["trigger_count"]),
                prizes={k: Decimal(str(v)) for k, v in jp["prizes"].items()},
                sectors=tuple(jp["sectors"]),
                natural=WeightTable([tuple(p) for p in jp["natural_odds"]]),
                bought=WeightTable([tuple(p) for p in jp["buy_odds"]]),
            ),
            products=tuple(
                BuyProduct(p["buy_id"], Decimal(str(p["cost_multiplier"])), p["kind"], p.get("enabled", True))
                for p in buy.get("products", [])
            ),
            buy_enabled=bool(buy.get("enabled", True)),
            max_win=Decimal(str(params.get("max_win_multiplier", 10000))),
        )

    def product(self, buy_id: str) -> BuyProduct | None:
        if not self.buy_enabled:
            return None
        for p in self.products:
            if p.buy_id == buy_id and p.enabled:
                return p
        return None


@dataclass
class JackpotHit:
    tier: str
    sector: int
    pay: Decimal


@dataclass
class SpinOutcome:
    """One paid spin, one free spin or one service (buy) spin, in x bet."""

    mode: str
    series: SeriesResult
    base_pay: Decimal = Decimal(0)
    orb_sum: int = 0
    applied_multiplier: int = 1
    series_pay: Decimal = Decimal(0)  # base_pay after the multiplier
    total_multiplier_before: int | None = None
    total_multiplier_after: int | None = None
    scatter_count: int = 0
    scatter_pay: Decimal = Decimal(0)
    fs_awarded: int = 0
    eagle_count: int = 0
    jackpot: JackpotHit | None = None
    paid: Decimal = Decimal(0)  # what this spin adds to the balance, after the cap
    capped: bool = False
    service: bool = False
    extra: dict = field(default_factory=dict)


def _resolve_jackpot(game: TumbleGame, out: SpinOutcome, rng: RNGProvider, bought: bool) -> Decimal:
    out.eagle_count = out.series.count(EAGLE)
    if out.eagle_count < game.wheel.trigger_count:
        return Decimal(0)
    tier, sector = game.wheel.spin(rng, bought)
    out.jackpot = JackpotHit(tier, sector, game.wheel.prizes[tier])
    return out.jackpot.pay


def _cap(game: TumbleGame, out: SpinOutcome, gross: Decimal, round_so_far: Decimal) -> None:
    room = max(Decimal(0), game.max_win - round_so_far)
    out.paid = min(gross, room)
    out.capped = gross >= room


def play_base_spin(game: TumbleGame, rng: RNGProvider) -> SpinOutcome:
    series = run_series(game.weights["base"], game.rules, rng)
    out = SpinOutcome(mode="base", series=series)
    out.base_pay = series.base_pay
    out.orb_sum = series.orb_sum
    out.series_pay, out.applied_multiplier, _ = apply_series_multiplier(out.base_pay, out.orb_sum, None)
    out.scatter_count = series.count(SCATTER)
    if out.scatter_count >= game.fs_trigger:
        out.scatter_pay = scatter_pay(out.scatter_count, game.scatter_pays)
        out.fs_awarded = game.fs_spins
    jackpot = _resolve_jackpot(game, out, rng, bought=False)
    _cap(game, out, out.series_pay + out.scatter_pay + jackpot, Decimal(0))
    return out


def play_free_spin(
    game: TumbleGame, rng: RNGProvider, *, super_mode: bool, total_multiplier: int, round_so_far: Decimal
) -> SpinOutcome:
    """`round_so_far` = everything the round already paid (trigger spin
    included) — the 10 000x cap is per round, not per spin."""
    mode = "super" if super_mode else "fs"
    series = run_series(game.weights[mode], game.rules, rng, guarantee_orb=super_mode)
    out = SpinOutcome(mode=mode, series=series, total_multiplier_before=total_multiplier)
    out.base_pay = series.base_pay
    out.orb_sum = series.orb_sum
    out.series_pay, out.applied_multiplier, out.total_multiplier_after = apply_series_multiplier(
        out.base_pay, out.orb_sum, total_multiplier
    )
    out.scatter_count = series.count(SCATTER)
    if out.scatter_count >= game.retrigger_count:
        out.scatter_pay = scatter_pay(out.scatter_count, game.scatter_pays)
        out.fs_awarded = game.retrigger_spins
    jackpot = _resolve_jackpot(game, out, rng, bought=False)
    _cap(game, out, out.series_pay + out.scatter_pay + jackpot, round_so_far)
    return out


def play_service_spin(game: TumbleGame, product: BuyProduct, rng: RNGProvider) -> SpinOutcome:
    """Bonus-buy service spin: guaranteed trigger, no tumble, no wins paid.
    A bought wheel is resolved (and paid) right here on its own odds."""
    if product.kind == "jackpot":
        grid = service_grid(game.weights["base"], game.rules, rng, force_code=EAGLE, force_count=game.wheel.trigger_count)
    else:
        grid = service_grid(game.weights["base"], game.rules, rng, force_code=SCATTER, force_count=game.fs_trigger)
    out = SpinOutcome(mode="base", series=SeriesResult(initial=grid), service=True)
    out.scatter_count = out.series.count(SCATTER)
    if product.kind == "jackpot":
        jackpot = _resolve_jackpot(game, out, rng, bought=True)
        _cap(game, out, jackpot, Decimal(0))
    else:
        out.fs_awarded = game.fs_spins
    return out
