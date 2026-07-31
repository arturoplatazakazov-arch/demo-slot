from decimal import Decimal

from app.engine.types import PaylineDef, SpinGrid, SymbolDef
from app.engine.wins import evaluate_count_wins, evaluate_line_wins, evaluate_spin

H1 = SymbolDef(
    code="H1", symbol_type="regular", weights=[1] * 5,
    pays={3: Decimal("5"), 4: Decimal("25"), 5: Decimal("100")},
)
H2 = SymbolDef(
    code="H2", symbol_type="regular", weights=[1] * 5,
    pays={3: Decimal("4"), 4: Decimal("20"), 5: Decimal("80")},
)
WILD = SymbolDef(
    code="WILD", symbol_type="wild", weights=[1] * 5,
    pays={3: Decimal("10"), 4: Decimal("50"), 5: Decimal("200")},
)
SCAT = SymbolDef(
    code="SCAT", symbol_type="scatter", weights=[1] * 5,
    pays={3: Decimal("2"), 4: Decimal("10"), 5: Decimal("50")},
)
SYMBOLS = [H1, H2, WILD, SCAT]

LOW_ROW_PAYLINE = PaylineDef(index=1, positions=[0, 0, 0, 0, 0])


def _grid(*columns: list[str]) -> SpinGrid:
    return SpinGrid(reels=[list(col) for col in columns], draws=[])


# --- line-pay -----------------------------------------------------------


def test_line_win_basic_three_of_a_kind():
    grid = _grid(["H1", "x", "x"], ["H1", "x", "x"], ["H1", "x", "x"], ["H2", "x", "x"], ["H2", "x", "x"])
    wins = evaluate_line_wins(grid, SYMBOLS, [LOW_ROW_PAYLINE], bet_per_line=Decimal("1"))
    assert len(wins) == 1
    assert wins[0].symbol_code == "H1"
    assert wins[0].count == 3
    assert wins[0].win_amount == Decimal("5")


def test_line_win_no_match_below_minimum_count():
    # Only two H1s in a row (position 2 breaks) — no paytable entry for count=2.
    grid = _grid(["H1", "x", "x"], ["H1", "x", "x"], ["H2", "x", "x"], ["H1", "x", "x"], ["H1", "x", "x"])
    wins = evaluate_line_wins(grid, SYMBOLS, [LOW_ROW_PAYLINE], bet_per_line=Decimal("1"))
    assert wins == ()


def test_wild_extends_a_regular_run():
    grid = _grid(["H1", "x", "x"], ["WILD", "x", "x"], ["H1", "x", "x"], ["H1", "x", "x"], ["H2", "x", "x"])
    wins = evaluate_line_wins(grid, SYMBOLS, [LOW_ROW_PAYLINE], bet_per_line=Decimal("2"))
    assert len(wins) == 1
    assert wins[0].symbol_code == "H1"
    assert wins[0].count == 4
    assert wins[0].win_amount == Decimal("25") * Decimal("2")


def test_wild_before_any_regular_symbol_still_counts():
    grid = _grid(["WILD", "x", "x"], ["H1", "x", "x"], ["H1", "x", "x"], ["H2", "x", "x"], ["H2", "x", "x"])
    wins = evaluate_line_wins(grid, SYMBOLS, [LOW_ROW_PAYLINE], bet_per_line=Decimal("1"))
    assert len(wins) == 1
    assert wins[0].symbol_code == "H1"
    assert wins[0].count == 3


def test_all_wild_line_pays_as_wild():
    grid = _grid(*[["WILD", "x", "x"]] * 5)
    wins = evaluate_line_wins(grid, SYMBOLS, [LOW_ROW_PAYLINE], bet_per_line=Decimal("1"))
    assert len(wins) == 1
    assert wins[0].symbol_code == "WILD"
    assert wins[0].count == 5
    assert wins[0].win_amount == Decimal("200")


def test_scatter_on_payline_breaks_the_line_and_does_not_pay_as_line():
    grid = _grid(["SCAT", "x", "x"], ["H1", "x", "x"], ["H1", "x", "x"], ["H1", "x", "x"], ["H1", "x", "x"])
    wins = evaluate_line_wins(grid, SYMBOLS, [LOW_ROW_PAYLINE], bet_per_line=Decimal("1"))
    assert wins == ()


# --- count-pay ------------------------------------------------------------


def test_count_pay_scatter_anywhere_on_grid():
    grid = _grid(
        ["SCAT", "x", "x"],
        ["x", "SCAT", "x"],
        ["x", "x", "H1"],
        ["x", "x", "SCAT"],
        ["H1", "H1", "H1"],
    )
    wins = evaluate_count_wins(grid, SYMBOLS, total_bet=Decimal("2"))
    assert len(wins) == 1
    assert wins[0].symbol_code == "SCAT"
    assert wins[0].count == 3
    assert wins[0].win_amount == Decimal("2") * Decimal("2")  # pays[3]=2 * total_bet


def test_count_pay_below_minimum_does_not_pay():
    grid = _grid(["SCAT", "x", "x"], ["x", "x", "x"], ["x", "x", "x"], ["x", "x", "x"], ["x", "x", "x"])
    wins = evaluate_count_wins(grid, SYMBOLS, total_bet=Decimal("2"))
    assert wins == ()


# --- combined: no double payout -------------------------------------------


def test_line_and_count_pay_combine_without_double_counting():
    # Payline (row 0): H1,H1,H1,H2,H2 -> line win. Scatter appears 3x off the
    # payline row -> separate count win. Total must be the sum of both, and
    # the scatter symbols must never appear in the line-win breakdown.
    grid = _grid(
        ["H1", "SCAT", "x"],
        ["H1", "x", "SCAT"],
        ["H1", "SCAT", "x"],
        ["H2", "x", "x"],
        ["H2", "x", "x"],
    )
    evaluation = evaluate_spin(
        grid, SYMBOLS, [LOW_ROW_PAYLINE], bet_per_line=Decimal("1"), total_bet=Decimal("5")
    )

    assert len(evaluation.line_wins) == 1
    assert evaluation.line_wins[0].symbol_code == "H1"
    assert len(evaluation.count_wins) == 1
    assert evaluation.count_wins[0].symbol_code == "SCAT"

    assert evaluation.line_pay_total == Decimal("5")
    assert evaluation.count_pay_total == Decimal("2") * Decimal("5")
    assert evaluation.total_win == evaluation.line_pay_total + evaluation.count_pay_total

    all_line_codes = {w.symbol_code for w in evaluation.line_wins}
    assert "SCAT" not in all_line_codes
