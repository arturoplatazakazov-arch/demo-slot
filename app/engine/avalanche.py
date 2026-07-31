"""Avalanche/cascade mechanic: unlike `app/engine/wins.py`'s count-pay,
which pays only on an *exact* count match (3/4/5), a symbol here pays for
meeting or exceeding the highest threshold key in its own `pays` dict —
{8: Decimal("1"), 10: Decimal("2.5"), 12: Decimal("5"), 14: Decimal("15")}
means 8-9 pays 1x, 10-11 pays 2.5x, ..., 14+ pays 15x (open-ended top tier).
A count below the lowest configured threshold doesn't win at all.

REGULAR symbols compete for this the normal way (count-anywhere, own
paytable). WILD never forms its own combination — it has no independent
count-pay of its own — it *substitutes into* whichever REGULAR symbol
currently has the most positions on the grid (product, this session: "уайлд
... заменяет собой любой элемент кроме бомбы и скаттера. идет в учет той
комбинации, элементов которой в данный момент больше всего на слоте"): every
wild position is added to that one majority symbol's count and its own
`positions` (so the wild cells get swept up in that win too), then the
combined count is scored against the *majority symbol's* paytable, never
wild's own. "Currently the most" is measured on REGULAR counts alone, before
any wild joins; ties are broken by scan order (first such symbol encountered
walking the grid reel-by-reel, row-by-row). A grid with wilds but no REGULAR
symbol at all has nothing for them to join, so they simply don't win.
SCATTER/BONUS symbols carry an empty `pays` dict for this mechanic (same as
the coin/collector_tiger convention in app/seed/east_discovery.py) so
they're never swept up by a cascade and a wild never joins them either,
matching wins.py's "symbol type decides the bucket" rule.

One round (`run_avalanche`) repeats: evaluate the current grid for tier
wins -> if none, the round is over -> else remove every winning position,
collapse the reels down and refill from the top
(app/engine/reels.py:collapse_and_refill), record the step, repeat. Each
step's win multiplies by that step's position in `multiplier_steps` (index
clamped to the last entry once the trail runs out) plus a running total of
every multiplier token swept up so far *this round* (SymbolDef.
multiplier_value — party-of-goods' x2/x3/x5/x7, product, this session: "он
должен суммировать все множители которые выпадут до следующего спина") —
this running total only resets at the start of the *next spin* (a fresh
`run_avalanche` call), not between cascade steps within the same round: if
step 1 sweeps up a x3 token, step 2's win (if any) is multiplied by
trail[1] + 3, not just trail[1]. If the round ends without any of that
running total ever landing alongside a further win, it's simply never
applied to anything and is gone once the next spin starts fresh (product:
"если нет - множитель обнуляется"). This is base-game behavior only — the
free-spins session-wide token accumulator (FeatureOut.multiplier, product:
"на бонусном множитель копится до конца фри спин сессии") is a separate,
already-existing mechanism in app/api/v1/spin_service.py that persists
*across* spins instead, untouched by this.

The "bomb" symbol (party-of-goods' "boom", SymbolDef.is_bomb) is a third
removal source, but a *lower-priority* one (product, this session): tier
wins on the current grid always resolve first — a bomb sitting on a grid
that also has a win just waits, untouched, for its own later step where
that grid has no win left. Only once a step's grid is completely win-free
does any bomb on it get to detonate — clearing its own cell plus its entire
row and column (see `_cross_positions`), except WILD/SCATTER cells, which
are bomb-proof (product: "бомба не взрывает уайлд и скаттер") — and it
carries no payout of its own ("только расчищает, без выплаты"). A bomb's
refill can itself produce a fresh win, which the next loop iteration will
find and resolve first, same as any other grid. A step with only bomb
detonations and no tier win still counts as a step (advances the multiplier
trail index and keeps the round going), it just has a step_win of 0.
"""

from decimal import Decimal
from typing import Mapping, Sequence

from app.engine.reels import collapse_and_refill
from app.engine.rng import RNGProvider
from app.engine.types import (
    AvalancheResult,
    BombDetonation,
    CascadeStep,
    CountWin,
    ReelSetConfig,
    SpinGrid,
    SymbolDef,
    SymbolType,
    TokenConsumption,
)

_BOMB_PROOF_TYPES = {SymbolType.WILD.value, SymbolType.SCATTER.value}


def _best_tier(pays: Mapping[int, Decimal], count: int) -> Decimal | None:
    applicable = [threshold for threshold in pays if threshold <= count]
    if not applicable:
        return None
    return pays[max(applicable)]


def evaluate_cascade_wins(
    grid: SpinGrid, symbols: Sequence[SymbolDef], total_bet: Decimal
) -> tuple[CountWin, ...]:
    """One cascade step's win scan: every REGULAR symbol code present on the
    grid, count-anywhere (adjacency doesn't matter), scored against its own
    tiered paytable via `_best_tier` — with every WILD position folded into
    whichever REGULAR symbol currently has the most positions before it
    joins (see module docstring)."""
    symbols_by_code = {s.code: s for s in symbols}
    regular_positions: dict[str, list[tuple[int, int]]] = {}
    wild_positions: list[tuple[int, int]] = []

    for reel_index, column in enumerate(grid.reels):
        for row_index, code in enumerate(column):
            symbol = symbols_by_code.get(code)
            if symbol is None:
                continue
            if symbol.symbol_type == SymbolType.REGULAR.value:
                regular_positions.setdefault(code, []).append((reel_index, row_index))
            elif symbol.symbol_type == SymbolType.WILD.value:
                wild_positions.append((reel_index, row_index))

    if regular_positions and wild_positions:
        majority_code = max(regular_positions, key=lambda code: len(regular_positions[code]))
        regular_positions[majority_code] = regular_positions[majority_code] + wild_positions

    wins: list[CountWin] = []
    for code, positions in regular_positions.items():
        symbol = symbols_by_code[code]
        count = len(positions)
        multiplier = _best_tier(symbol.pays, count)
        if multiplier is None:
            continue
        wins.append(
            CountWin(
                symbol_code=code,
                count=count,
                payout_multiplier=multiplier,
                win_amount=multiplier * total_bet,
                positions=tuple(positions),
            )
        )

    return tuple(wins)


def _cross_positions(reel_index: int, row_index: int, num_reels: int, num_rows: int) -> set[tuple[int, int]]:
    """Every position a bomb at (reel_index, row_index) clears: its entire
    column, its entire row, and (via either of those) itself."""
    positions = {(reel_index, r) for r in range(num_rows)}
    positions |= {(r, row_index) for r in range(num_reels)}
    return positions


def _is_bomb_proof(code: str, symbols_by_code: Mapping[str, SymbolDef]) -> bool:
    symbol = symbols_by_code.get(code)
    return symbol is not None and symbol.symbol_type in _BOMB_PROOF_TYPES


def run_avalanche(
    grid: SpinGrid,
    reel_set: ReelSetConfig,
    symbols: Sequence[SymbolDef],
    rng: RNGProvider,
    total_bet: Decimal,
    multiplier_steps: Sequence[int] = (1,),
    max_cascades: int = 20,
) -> AvalancheResult:
    """Runs cascade steps against `grid` until a step finds no tier win and
    no bomb to detonate, or `max_cascades` is hit (pure safety cap — a
    correctly configured paytable/bomb weight always drains eventually
    since each step removes at least one position, but a misconfigured one
    shouldn't be able to hang a spin)."""
    steps: list[CascadeStep] = []
    current = grid
    steps_trail = tuple(multiplier_steps) or (1,)
    symbols_by_code = {s.code: s for s in symbols}
    token_multiplier_total = 0

    for step_index in range(max_cascades):
        wins = evaluate_cascade_wins(current, symbols, total_bet)
        trail_multiplier = steps_trail[min(step_index, len(steps_trail) - 1)]

        if wins:
            # Multiplier tokens (party-of-goods' x2/x3/x5/x7, SymbolDef.
            # multiplier_value set): every instance currently on the grid
            # sums into this step's multiplier and gets swept up alongside
            # the winning positions. A token that never sees a win before
            # the round ends just never contributes.
            tokens_consumed: list[TokenConsumption] = []
            token_positions: set[tuple[int, int]] = set()
            for reel_index, column in enumerate(current.reels):
                for row_index, code in enumerate(column):
                    symbol = symbols_by_code.get(code)
                    if symbol is not None and symbol.multiplier_value is not None:
                        tokens_consumed.append(
                            TokenConsumption(reel=reel_index, row=row_index, value=symbol.multiplier_value)
                        )
                        token_positions.add((reel_index, row_index))

            removed = {position for win in wins for position in win.positions} | token_positions
            token_multiplier_total += sum(t.value for t in tokens_consumed)
            step_multiplier = trail_multiplier + token_multiplier_total
            current = collapse_and_refill(current, reel_set, rng, removed)
            steps.append(
                CascadeStep(
                    wins=wins,
                    multiplier=step_multiplier,
                    grid_after=current,
                    tokens_consumed=tuple(tokens_consumed),
                )
            )
            continue

        # No win on this grid — only now does any bomb (party-of-goods'
        # "boom", SymbolDef.is_bomb) get to detonate. Its cross clears
        # every cell in its row+column except WILD/SCATTER (bomb-proof) —
        # excluded from both the actual removal and the reported `cleared`
        # list, since nothing actually explodes there.
        bombs_detonated: list[BombDetonation] = []
        bomb_cleared_positions: set[tuple[int, int]] = set()
        for reel_index, column in enumerate(current.reels):
            for row_index, code in enumerate(column):
                symbol = symbols_by_code.get(code)
                if symbol is not None and symbol.is_bomb:
                    cross = _cross_positions(reel_index, row_index, reel_set.num_reels, reel_set.num_rows)
                    cross = {(r, c) for r, c in cross if not _is_bomb_proof(current.reels[r][c], symbols_by_code)}
                    bombs_detonated.append(
                        BombDetonation(reel=reel_index, row=row_index, cleared=tuple(sorted(cross)))
                    )
                    bomb_cleared_positions |= cross

        if not bombs_detonated:
            break  # no win, no bomb — round over

        current = collapse_and_refill(current, reel_set, rng, bomb_cleared_positions)
        steps.append(
            CascadeStep(
                wins=(),
                multiplier=trail_multiplier,
                grid_after=current,
                bombs_detonated=tuple(bombs_detonated),
            )
        )

    return AvalancheResult(initial_grid=grid, steps=tuple(steps))
