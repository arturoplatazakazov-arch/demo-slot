from decimal import Decimal
from typing import Sequence

from app.engine.types import (
    CountWin,
    LineWin,
    PaylineDef,
    SpinGrid,
    SymbolDef,
    SymbolType,
    WinEvaluation,
)

# Symbol types eligible for each mechanic — this is the single place that
# enforces "no double payout" (TZ §4.2): a symbol's type puts it in exactly
# one bucket, never both.
_LINE_PAY_TYPES = {SymbolType.REGULAR.value, SymbolType.WILD.value}
_COUNT_PAY_TYPES = {SymbolType.SCATTER.value, SymbolType.BONUS.value}


def evaluate_line_wins(
    grid: SpinGrid,
    symbols: Sequence[SymbolDef],
    paylines: Sequence[PaylineDef],
    bet_per_line: Decimal,
) -> tuple[LineWin, ...]:
    """Line-pay (TZ §4.2, §4.3): for each active payline, scan left to right
    and count a run of matching REGULAR/WILD symbols starting at reel 0.

    Wild substitutes for any regular symbol. If the run is wild-only end to
    end, it pays as WILD itself (using WILD's own paytable) — an assumption
    (TZ §14 doesn't specify this), confirm if a different rule is wanted
    (e.g. "wild always pays as the best available regular symbol").
    """
    symbols_by_code = {s.code: s for s in symbols}
    wins: list[LineWin] = []

    for payline in paylines:
        line_cells = [(reel, payline.positions[reel]) for reel in range(len(payline.positions))]
        line_codes = [grid.reels[reel][row] for reel, row in line_cells]

        target_code: str | None = None  # first concrete (non-wild) symbol matched so far
        wild_code: str | None = None  # remembered in case the whole run turns out wild-only
        run_length = 0

        for code in line_codes:
            symbol = symbols_by_code.get(code)
            if symbol is None or symbol.symbol_type not in _LINE_PAY_TYPES:
                break  # count-pay symbols (scatter/bonus) never participate in line-pay

            if symbol.symbol_type == SymbolType.WILD.value:
                wild_code = wild_code or code
                run_length += 1
                continue

            if target_code is None:
                target_code = code
                run_length += 1
            elif code == target_code:
                run_length += 1
            else:
                break

        pay_code = target_code or wild_code
        if pay_code is None or run_length < 1:
            continue

        pay_symbol = symbols_by_code[pay_code]
        multiplier = pay_symbol.pays.get(run_length)
        if multiplier is None:
            continue

        win_amount = multiplier * bet_per_line
        wins.append(
            LineWin(
                payline_index=payline.index,
                symbol_code=pay_code,
                count=run_length,
                payout_multiplier=multiplier,
                win_amount=win_amount,
                positions=tuple(line_cells[:run_length]),
            )
        )

    return tuple(wins)


def evaluate_count_wins(
    grid: SpinGrid,
    symbols: Sequence[SymbolDef],
    total_bet: Decimal,
) -> tuple[CountWin, ...]:
    """Count-pay (TZ §4.2): SCATTER/BONUS symbols pay for how many appear
    anywhere on the grid, regardless of paylines or adjacency."""
    symbols_by_code = {s.code: s for s in symbols}
    positions_by_code: dict[str, list[tuple[int, int]]] = {}

    for reel_index, column in enumerate(grid.reels):
        for row_index, code in enumerate(column):
            symbol = symbols_by_code.get(code)
            if symbol is not None and symbol.symbol_type in _COUNT_PAY_TYPES:
                positions_by_code.setdefault(code, []).append((reel_index, row_index))

    wins: list[CountWin] = []
    for code, positions in positions_by_code.items():
        symbol = symbols_by_code[code]
        count = len(positions)
        multiplier = symbol.pays.get(count)
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


def evaluate_spin(
    grid: SpinGrid,
    symbols: Sequence[SymbolDef],
    paylines: Sequence[PaylineDef],
    bet_per_line: Decimal,
    total_bet: Decimal,
) -> WinEvaluation:
    line_wins = evaluate_line_wins(grid, symbols, paylines, bet_per_line)
    count_wins = evaluate_count_wins(grid, symbols, total_bet)
    return WinEvaluation(line_wins=line_wins, count_wins=count_wins)
