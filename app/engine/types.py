from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence

from app.models.enums import SymbolType


@dataclass(frozen=True)
class SymbolDef:
    """Full config for one symbol, decoupled from the `Symbol` ORM model on
    purpose (TZ §2: math lives in config, and the engine should be testable
    without a database) — stage 5 builds this from `GameConfig` rows before
    calling into the engine.

    weights: RNG weight on each reel independently, length == num_reels.
    pays: match-count -> payout multiplier. For REGULAR/WILD (line-pay) the
    multiplier is applied to the bet staked per line; for SCATTER/BONUS
    (count-pay) it's applied to the total bet (TZ §4.2, confirmed with
    product). A count with no entry in `pays` does not win.
    """

    code: str
    symbol_type: str  # SymbolType value
    weights: Sequence[int]
    pays: Mapping[int, Decimal] = field(default_factory=dict)
    # At most this many of this symbol per reel (None == no cap) — admin-
    # configurable, applied as a post-draw cap (see
    # app/services/scatter_cap.py:cap_symbol_per_reel), not a reel-strip rule.
    max_per_reel: int | None = None
    # Set (party-of-goods' x2/x3/x5/x7 tokens) marks this as a "multiplier
    # token" for app/engine/avalanche.py: never count-pays on its own
    # (pays stays empty, same BONUS-type convention as coin/collector_tiger
    # in east_discovery.py), instead every instance currently on the grid
    # sums into that cascade step's multiplier whenever *any* win occurs,
    # and gets consumed (removed) alongside it. None for every other symbol.
    multiplier_value: int | None = None
    # Set (party-of-goods' "boom") marks this as the "bomb" symbol for
    # app/engine/avalanche.py: detonates on every cascade step where it's
    # present on the grid, regardless of whether anything else won that
    # step, clearing its own cell plus its entire row and column — no
    # payout of its own (pays stays empty, same trigger-only convention as
    # scatter/coin). False for every other symbol.
    is_bomb: bool = False


@dataclass(frozen=True)
class ReelSetConfig:
    num_reels: int
    num_rows: int
    symbols: Sequence[SymbolDef]


@dataclass(frozen=True)
class PositionDraw:
    """One RNG draw for one grid position — the raw value + the weights it
    was drawn against, kept for audit/reproducibility (TZ §10, §11)."""

    reel: int
    row: int
    raw_value: int
    total_weight: int
    symbol_code: str


@dataclass(frozen=True)
class SpinGrid:
    reels: list[list[str]]  # reels[reel_index][row_index] = symbol code, top to bottom
    draws: list[PositionDraw]  # rng proof, one entry per grid position


@dataclass(frozen=True)
class PaylineDef:
    index: int
    positions: Sequence[int]  # row index per reel, length == num_reels


@dataclass(frozen=True)
class LineWin:
    payline_index: int
    symbol_code: str
    count: int
    payout_multiplier: Decimal
    win_amount: Decimal
    positions: tuple[tuple[int, int], ...]  # (reel, row) cells that contributed, left to right


@dataclass(frozen=True)
class CountWin:
    symbol_code: str
    count: int
    payout_multiplier: Decimal
    win_amount: Decimal
    positions: tuple[tuple[int, int], ...]  # every (reel, row) cell holding the symbol


@dataclass(frozen=True)
class WinEvaluation:
    line_wins: tuple[LineWin, ...]
    count_wins: tuple[CountWin, ...]

    @property
    def line_pay_total(self) -> Decimal:
        return sum((w.win_amount for w in self.line_wins), Decimal(0))

    @property
    def count_pay_total(self) -> Decimal:
        return sum((w.win_amount for w in self.count_wins), Decimal(0))

    @property
    def total_win(self) -> Decimal:
        return self.line_pay_total + self.count_pay_total


@dataclass(frozen=True)
class TokenConsumption:
    """One multiplier-token (party-of-goods' x2/x3/x5/x7) swept up this
    cascade step — it was on the grid when a win occurred, contributed its
    value to the step's multiplier, and got removed (see
    app/engine/avalanche.py) alongside the winning positions."""

    reel: int
    row: int
    value: int


@dataclass(frozen=True)
class BombDetonation:
    """One "bomb" symbol (party-of-goods' "boom") detonating this cascade
    step — its own position, plus every position it cleared (its full row
    and column, itself included). Fires whenever the bomb is on the grid,
    independent of any win (see app/engine/avalanche.py); carries no payout
    of its own."""

    reel: int
    row: int
    cleared: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class CascadeStep:
    """One avalanche cascade: the tier wins found on the grid *before* this
    step's removal, the multiplier this step's position in the round's
    trail applies (plus any multiplier tokens present, see
    `tokens_consumed`), and the grid *after* removing those wins/tokens/
    bomb-cleared cells and refilling (app/engine/reels.py:collapse_and_refill)
    — the grid the next step (or the round's final state) evaluates
    against."""

    wins: tuple[CountWin, ...]
    multiplier: int
    grid_after: SpinGrid
    tokens_consumed: tuple[TokenConsumption, ...] = ()
    bombs_detonated: tuple[BombDetonation, ...] = ()

    @property
    def raw_win(self) -> Decimal:
        return sum((w.win_amount for w in self.wins), Decimal(0))

    @property
    def step_win(self) -> Decimal:
        return self.raw_win * self.multiplier


@dataclass(frozen=True)
class AvalancheResult:
    """One full avalanche round: every cascade step run until no symbol on
    the grid meets its lowest paytable tier anymore (or `max_cascades`
    safety cap is hit), plus the grid the round started from."""

    initial_grid: SpinGrid
    steps: tuple[CascadeStep, ...]

    @property
    def final_grid(self) -> SpinGrid:
        return self.steps[-1].grid_after if self.steps else self.initial_grid

    @property
    def total_win(self) -> Decimal:
        return sum((s.step_win for s in self.steps), Decimal(0))


__all__ = [
    "SymbolDef",
    "ReelSetConfig",
    "PositionDraw",
    "SpinGrid",
    "PaylineDef",
    "LineWin",
    "CountWin",
    "WinEvaluation",
    "CascadeStep",
    "TokenConsumption",
    "BombDetonation",
    "AvalancheResult",
    "SymbolType",
]
