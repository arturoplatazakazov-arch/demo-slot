"""Scatter-pays tumble with multiplier orbs — Olympus Thunder (GDD-04).

Different enough from app/engine/avalanche.py that it is its own engine
rather than more flags on that one:

- every position is drawn independently from a per-MODE weight table
  (base / fs / super), not from the game's Symbol.reel_weights — the GDD
  re-weights low symbols and orbs inside free spins;
- a REGULAR symbol pays when 8+ of it sit anywhere on the grid (tiers 8 / 10
  / 12, open-ended top tier, several symbols can pay in one step);
- scatter, orb and eagle never pay as symbols and never tumble away: they
  ride the cascade down and stay on the board until the series is over;
- an orb rolls its value the moment it lands ("orb_25" on the grid) and is
  only cashed once, at the END of the series: the series win is multiplied
  by the sum of every orb on the final board (base game) or by the round's
  accumulated TOTAL MULTIPLIER (free spins — see apply_series_multiplier).

The engine is pure: grids are reel-major `list[list[str]]`
(`grid[reel][row]`, row 0 on top), money is Decimal, randomness comes only
from `rng.randbelow`. Weights in the config may be fractional (0.6, 3.9);
they are scaled to integers once in `WeightTable`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from app.engine.rng import RNGProvider

SCATTER = "scatter"
ORB = "orb"
EAGLE = "eagle"
ORB_PREFIX = "orb_"
STICKY = (SCATTER, EAGLE)

_WEIGHT_SCALE = 1000


def orb_value(code: str) -> int | None:
    return int(code[len(ORB_PREFIX):]) if code.startswith(ORB_PREFIX) else None


def is_sticky(code: str) -> bool:
    """Symbols the tumble never removes: scatter, eagle and any orb."""
    return code in STICKY or code.startswith(ORB_PREFIX)


class WeightTable:
    """Integer-scaled weighted draw over a {key: weight} mapping."""

    def __init__(self, weights: Mapping[str, float] | Iterable[tuple[object, float]]):
        items = weights.items() if isinstance(weights, Mapping) else weights
        self.keys: list = []
        self.cumulative: list[int] = []
        total = 0
        for key, weight in items:
            scaled = int(round(float(weight) * _WEIGHT_SCALE))
            if scaled <= 0:
                continue
            total += scaled
            self.keys.append(key)
            self.cumulative.append(total)
        if total <= 0:
            raise ValueError("weight table is empty")
        self.total = total

    def draw(self, rng: RNGProvider):
        roll = rng.randbelow(self.total)
        for key, edge in zip(self.keys, self.cumulative):
            if roll < edge:
                return key
        return self.keys[-1]  # unreachable

    def without(self, excluded: Iterable[str]) -> WeightTable:
        drop = set(excluded)
        pairs = []
        previous = 0
        for key, edge in zip(self.keys, self.cumulative):
            if key not in drop:
                pairs.append((key, (edge - previous) / _WEIGHT_SCALE))
            previous = edge
        return WeightTable(pairs)


@dataclass(frozen=True)
class TumbleRules:
    num_reels: int
    num_rows: int
    paytable: Mapping[str, Mapping[int, Decimal]]  # regular code -> {threshold: x bet}
    orb_values: WeightTable

    @classmethod
    def from_params(cls, params: Mapping, num_reels: int, num_rows: int) -> TumbleRules:
        return cls(
            num_reels=num_reels,
            num_rows=num_rows,
            paytable={
                code: {int(k): Decimal(str(v)) for k, v in tiers.items()}
                for code, tiers in params["paytable"].items()
            },
            orb_values=WeightTable([(int(v), w) for v, w in params["orb_values"]]),
        )


@dataclass(frozen=True)
class SymbolWin:
    symbol: str
    count: int
    pay: Decimal  # x bet, before any multiplier
    positions: tuple[tuple[int, int], ...]  # (reel, row)


@dataclass(frozen=True)
class TumbleStep:
    wins: tuple[SymbolWin, ...]
    removed: tuple[tuple[int, int], ...]
    grid_after: list[list[str]]

    @property
    def pay(self) -> Decimal:
        return sum((w.pay for w in self.wins), Decimal(0))


@dataclass
class SeriesResult:
    initial: list[list[str]]
    steps: list[TumbleStep] = field(default_factory=list)

    @property
    def final(self) -> list[list[str]]:
        return self.steps[-1].grid_after if self.steps else self.initial

    @property
    def base_pay(self) -> Decimal:
        """Sum of every step's pay in x bet, no multiplier applied."""
        return sum((s.pay for s in self.steps), Decimal(0))

    def orbs(self) -> list[tuple[int, int, int]]:
        """(reel, row, value) of every orb on the final board — orbs never
        tumble away, so this is every orb that landed during the series."""
        out = []
        for reel, column in enumerate(self.final):
            for row, code in enumerate(column):
                value = orb_value(code)
                if value is not None:
                    out.append((reel, row, value))
        return out

    @property
    def orb_sum(self) -> int:
        return sum(v for _, _, v in self.orbs())

    def count(self, code: str) -> int:
        return sum(column.count(code) for column in self.final)


def draw_symbol(table: WeightTable, rules: TumbleRules, rng: RNGProvider) -> str:
    code = table.draw(rng)
    if code == ORB:
        return f"{ORB_PREFIX}{rules.orb_values.draw(rng)}"
    return code


def draw_grid(table: WeightTable, rules: TumbleRules, rng: RNGProvider) -> list[list[str]]:
    return [
        [draw_symbol(table, rules, rng) for _ in range(rules.num_rows)]
        for _ in range(rules.num_reels)
    ]


def evaluate(grid: Sequence[Sequence[str]], rules: TumbleRules) -> tuple[SymbolWin, ...]:
    """Every regular symbol with 8+ copies anywhere on the grid, scored on
    its own tier table (highest threshold <= count)."""
    positions: dict[str, list[tuple[int, int]]] = {}
    for reel, column in enumerate(grid):
        for row, code in enumerate(column):
            if code in rules.paytable:
                positions.setdefault(code, []).append((reel, row))
    wins = []
    for code in rules.paytable:  # paytable order = stable output order
        cells = positions.get(code)
        if not cells:
            continue
        tiers = rules.paytable[code]
        reached = [t for t in tiers if t <= len(cells)]
        if not reached:
            continue
        wins.append(SymbolWin(code, len(cells), tiers[max(reached)], tuple(cells)))
    return tuple(wins)


def collapse(
    grid: Sequence[Sequence[str]],
    removed: set[tuple[int, int]],
    table: WeightTable,
    rules: TumbleRules,
    rng: RNGProvider,
) -> list[list[str]]:
    """Removed cells vanish, everything above falls down (sticky symbols
    included), the gap at the top of each reel refills from `table`."""
    out = []
    for reel, column in enumerate(grid):
        kept = [code for row, code in enumerate(column) if (reel, row) not in removed]
        fresh = [draw_symbol(table, rules, rng) for _ in range(len(column) - len(kept))]
        out.append(fresh + kept)
    return out


def ensure_orb(grid: list[list[str]], rules: TumbleRules, rng: RNGProvider) -> list[list[str]]:
    """Super Free Spins guarantee: at least one orb on the initial board.
    If none landed, one random non-special cell becomes an orb."""
    if any(orb_value(code) is not None for column in grid for code in column):
        return grid
    free = [(r, w) for r, column in enumerate(grid) for w, code in enumerate(column) if not is_sticky(code)]
    reel, row = free[rng.randbelow(len(free))]
    grid = [list(column) for column in grid]
    grid[reel][row] = f"{ORB_PREFIX}{rules.orb_values.draw(rng)}"
    return grid


def run_series(
    table: WeightTable,
    rules: TumbleRules,
    rng: RNGProvider,
    *,
    guarantee_orb: bool = False,
    max_steps: int = 40,
) -> SeriesResult:
    """One paid / free spin: draw, then tumble until a step finds no win."""
    grid = draw_grid(table, rules, rng)
    if guarantee_orb:
        grid = ensure_orb(grid, rules, rng)
    result = SeriesResult(initial=grid)
    current = grid
    for _ in range(max_steps):
        wins = evaluate(current, rules)
        if not wins:
            break
        removed = {cell for win in wins for cell in win.positions}
        current = collapse(current, removed, table, rules, rng)
        result.steps.append(TumbleStep(wins=wins, removed=tuple(sorted(removed)), grid_after=current))
    return result


def service_grid(
    table: WeightTable,
    rules: TumbleRules,
    rng: RNGProvider,
    *,
    force_code: str,
    force_count: int,
) -> list[list[str]]:
    """Bonus-buy service spin (GDD §9.1): no tumble, no symbols of any other
    feature, no orbs, and exactly `force_count` copies of the trigger symbol
    on random cells. Its wins are never paid, so the filler is free to be
    anything regular."""
    filler = table.without([SCATTER, EAGLE, ORB])
    grid = draw_grid(filler, rules, rng)
    cells = [(reel, row) for reel in range(rules.num_reels) for row in range(rules.num_rows)]
    for _ in range(force_count):
        reel, row = cells.pop(rng.randbelow(len(cells)))
        grid[reel][row] = force_code
    return grid


def apply_series_multiplier(base_pay: Decimal, orb_sum: int, total_multiplier: int | None) -> tuple[Decimal, int, int | None]:
    """(paid x bet, multiplier applied, new total multiplier).

    Base game (`total_multiplier` None): a winning series with at least one
    orb is multiplied by the orbs' sum; otherwise it pays as is.

    Free spins (GDD §7.2, decision 25.09.2026): the TOTAL MULTIPLIER starts
    at x1; a WINNING series with orbs adds their sum to it and is then
    multiplied by it; a winning series without orbs pays as is and leaves
    it untouched; orbs of a losing series fade and count for nothing."""
    if total_multiplier is None:
        if base_pay > 0 and orb_sum > 0:
            return base_pay * orb_sum, orb_sum, None
        return base_pay, 1, None
    if base_pay > 0 and orb_sum > 0:
        total_multiplier += orb_sum
        return base_pay * total_multiplier, total_multiplier, total_multiplier
    return base_pay, 1, total_multiplier


def scatter_pay(count: int, pays: Mapping[int, Decimal]) -> Decimal:
    reached = [t for t in pays if t <= count]
    return pays[max(reached)] if reached else Decimal(0)
