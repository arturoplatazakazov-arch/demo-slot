from decimal import Decimal

from app.engine.avalanche import _best_tier, evaluate_cascade_wins, run_avalanche
from app.engine.types import ReelSetConfig, SpinGrid, SymbolDef
from tests.fakes import FakeRNG

REGULAR = SymbolDef(
    code="cake", symbol_type="regular", weights=[1] * 4,
    pays={8: Decimal("1"), 10: Decimal("2.5"), 12: Decimal("5")},
)
OTHER = SymbolDef(code="gift", symbol_type="regular", weights=[1] * 4, pays={8: Decimal("1")})
WILD = SymbolDef(code="wild", symbol_type="wild", weights=[1] * 4, pays={})
SCATTER = SymbolDef(code="scatter", symbol_type="scatter", weights=[1] * 4, pays={})
SYMBOLS = [REGULAR, OTHER, WILD, SCATTER]


def _grid(*columns: list[str]) -> SpinGrid:
    return SpinGrid(reels=[list(col) for col in columns], draws=[])


# --- _best_tier: threshold lookup ------------------------------------------


def test_best_tier_picks_highest_threshold_met():
    pays = {8: Decimal("1"), 10: Decimal("2.5"), 12: Decimal("5")}
    assert _best_tier(pays, 7) is None
    assert _best_tier(pays, 8) == Decimal("1")
    assert _best_tier(pays, 9) == Decimal("1")
    assert _best_tier(pays, 10) == Decimal("2.5")
    assert _best_tier(pays, 11) == Decimal("2.5")
    assert _best_tier(pays, 12) == Decimal("5")
    assert _best_tier(pays, 100) == Decimal("5")  # open-ended top tier


def test_best_tier_empty_paytable_never_wins():
    assert _best_tier({}, 30) is None


# --- evaluate_cascade_wins: count-anywhere, type bucketing ------------------


def test_cascade_win_counts_symbol_anywhere_regardless_of_adjacency():
    # 8 "cake" scattered non-contiguously across a 4x4 grid, interleaved
    # with "gift" — proves the count ignores adjacency entirely.
    grid = _grid(
        ["cake", "gift", "cake", "gift"],
        ["gift", "cake", "gift", "cake"],
        ["cake", "gift", "cake", "gift"],
        ["gift", "cake", "gift", "cake"],
    )
    wins = evaluate_cascade_wins(grid, SYMBOLS, total_bet=Decimal("10"))
    by_code = {w.symbol_code: w for w in wins}
    assert by_code["cake"].count == 8
    assert by_code["cake"].win_amount == Decimal("1") * Decimal("10")
    assert by_code["gift"].count == 8


def test_cascade_win_below_lowest_threshold_does_not_win():
    grid = _grid(["cake", "cake", "x", "x"], ["x", "x", "x", "x"])
    wins = evaluate_cascade_wins(grid, SYMBOLS, total_bet=Decimal("10"))
    assert wins == ()


def test_scatter_never_wins_via_cascade_even_at_high_count():
    columns = [["scatter"] * 4 for _ in range(4)]
    grid = _grid(*columns)
    wins = evaluate_cascade_wins(grid, SYMBOLS, total_bet=Decimal("10"))
    assert wins == ()


def test_wild_substitutes_into_the_majority_regular_symbol():
    # cake=6, gift=4, wild=2 — wild joins cake (the bigger group), pushing
    # it to 8 and over its own threshold; gift stays at 4 and never wins.
    grid = _grid(
        ["cake", "cake", "cake", "cake"],
        ["cake", "cake", "gift", "gift"],
        ["wild", "wild", "gift", "gift"],
    )
    wins = evaluate_cascade_wins(grid, SYMBOLS, total_bet=Decimal("10"))
    assert len(wins) == 1
    win = wins[0]
    assert win.symbol_code == "cake"
    assert win.count == 8
    assert win.win_amount == Decimal("1") * Decimal("10")  # cake's own pays[8], not wild's
    assert set(win.positions) == {(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (2, 0), (2, 1)}


def test_wild_with_no_regular_symbol_on_grid_does_not_win():
    # Nothing but wild — no REGULAR group exists for it to substitute into.
    columns = [["wild"] * 4 for _ in range(4)]
    grid = _grid(*columns)
    wins = evaluate_cascade_wins(grid, SYMBOLS, total_bet=Decimal("10"))
    assert wins == ()


def test_wild_does_not_join_scatter_or_bonus_counts():
    # Wild only substitutes into REGULAR symbols — scatter (and bonus-type
    # symbols like multiplier tokens/the bomb) never receive its count,
    # regardless of how many of each are on the grid.
    grid = _grid(
        ["wild", "scatter", "wild", "scatter"],
        ["scatter", "wild", "scatter", "wild"],
    )
    wins = evaluate_cascade_wins(grid, SYMBOLS, total_bet=Decimal("10"))
    assert wins == ()


def test_wild_ties_broken_by_first_symbol_encountered_scanning_the_grid():
    # cake and gift tie at 3 positions each; wild(2) should join whichever
    # was scanned first (reel-major, row-minor) — cake, since it's the first
    # code seen in reel 0's column.
    grid = _grid(
        ["cake", "gift"],
        ["cake", "gift"],
        ["cake", "gift"],
        ["wild", "wild"],
    )
    cake = SymbolDef(code="cake", symbol_type="regular", weights=[1] * 4, pays={5: Decimal("2")})
    gift = SymbolDef(code="gift", symbol_type="regular", weights=[1] * 4, pays={5: Decimal("2")})
    wild = SymbolDef(code="wild", symbol_type="wild", weights=[1] * 4, pays={})
    symbols = [cake, gift, wild]

    wins = evaluate_cascade_wins(grid, symbols, total_bet=Decimal("10"))
    assert len(wins) == 1
    assert wins[0].symbol_code == "cake"
    assert wins[0].count == 5


# --- run_avalanche: cascade loop, gravity/refill, multiplier trail --------


def _config(num_reels: int, num_rows: int) -> ReelSetConfig:
    return ReelSetConfig(num_reels=num_reels, num_rows=num_rows, symbols=SYMBOLS)


def test_run_avalanche_stops_immediately_when_no_win():
    grid = _grid(["cake", "gift"], ["gift", "cake"])
    result = run_avalanche(grid, _config(2, 2), SYMBOLS, FakeRNG([]), Decimal("10"))
    assert result.steps == ()
    assert result.final_grid is grid
    assert result.total_win == Decimal("0")


def test_run_avalanche_one_cascade_removes_wins_and_refills_from_top():
    # 3 reels x 4 rows: reels 0+1 are "cake" (count=8, meets its lowest
    # tier), reel 2 is "gift" at count=4 (below gift's own threshold of 8,
    # so it doesn't win and should survive untouched).
    grid = _grid(
        ["cake", "cake", "cake", "cake"],
        ["cake", "cake", "cake", "cake"],
        ["gift", "gift", "gift", "gift"],
    )
    # 8 replacement draws for reels 0+1's now-empty cells — raw=3 always
    # picks "scatter" (weights [cake,gift,wild,scatter] = [1,1,1,1],
    # cumulative [3,4)), which never wins (SCATTER isn't in the avalanche
    # pay-type bucket at all), so the round stops after exactly one step.
    rng = FakeRNG([3] * 8)
    result = run_avalanche(grid, _config(3, 4), SYMBOLS, rng, Decimal("10"), multiplier_steps=[1])

    assert len(result.steps) == 1
    step = result.steps[0]
    assert len(step.wins) == 1
    assert step.wins[0].symbol_code == "cake"
    assert step.wins[0].count == 8
    assert step.multiplier == 1
    assert step.step_win == Decimal("1") * Decimal("10")  # pays[8]=1

    # reel 2 (gift) untouched; reels 0+1 fully replaced.
    assert step.grid_after.reels[2] == ["gift", "gift", "gift", "gift"]
    assert len(step.grid_after.reels[0]) == 4
    assert len(step.grid_after.reels[1]) == 4
    # New draws recorded in the audit trail on top of the original (empty) set.
    assert len(step.grid_after.draws) == len(grid.draws) + 8


def test_run_avalanche_multiplier_trail_clamps_to_last_entry():
    # Every position wins every cascade (single symbol config), forcing
    # several steps so we can see the trail clamp at its last entry.
    single = [SymbolDef(code="x", symbol_type="regular", weights=[1] * 2, pays={1: Decimal("1")})]
    grid = SpinGrid(reels=[["x"], ["x"]], draws=[])
    rng = FakeRNG([0] * 100)
    result = run_avalanche(
        grid, ReelSetConfig(num_reels=2, num_rows=1, symbols=single), single, rng,
        Decimal("10"), multiplier_steps=[1, 2, 3], max_cascades=5,
    )
    assert len(result.steps) == 5
    assert [s.multiplier for s in result.steps] == [1, 2, 3, 3, 3]


def test_run_avalanche_max_cascades_caps_an_always_winning_config():
    single = [SymbolDef(code="x", symbol_type="regular", weights=[1] * 2, pays={1: Decimal("1")})]
    grid = SpinGrid(reels=[["x"], ["x"]], draws=[])
    rng = FakeRNG([0] * 100)
    result = run_avalanche(
        grid, ReelSetConfig(num_reels=2, num_rows=1, symbols=single), single, rng,
        Decimal("10"), multiplier_steps=[1], max_cascades=3,
    )
    assert len(result.steps) == 3


def test_run_avalanche_total_win_sums_multiplier_applied_steps():
    single = [SymbolDef(code="x", symbol_type="regular", weights=[1] * 2, pays={1: Decimal("2")})]
    grid = SpinGrid(reels=[["x"], ["x"]], draws=[])
    rng = FakeRNG([0] * 100)
    result = run_avalanche(
        grid, ReelSetConfig(num_reels=2, num_rows=1, symbols=single), single, rng,
        Decimal("10"), multiplier_steps=[1, 2], max_cascades=2,
    )
    # Each step: 2 positions of "x" -> one CountWin, win_amount = pays[1]=2 * bet(10) = 20.
    # step1: 20*1=20, step2: 20*2=40 -> total 60.
    assert result.total_win == Decimal("60")


# --- run_avalanche: multiplier tokens (party-of-goods' x2/x3/x5/x7) --------

TOKEN_X3 = SymbolDef(code="x3", symbol_type="bonus", weights=[1] * 3, pays={}, multiplier_value=3)
TOKEN_X5 = SymbolDef(code="x5", symbol_type="bonus", weights=[1] * 3, pays={}, multiplier_value=5)


def test_multiplier_token_sums_into_step_multiplier_and_gets_consumed():
    # 3 reels x 3 rows: reel 0+1 are "cake" (count=6, meets a 6-threshold
    # tier), reel 2 is a single x3 token sitting among cake elsewhere would
    # break the count — put it in its own row instead so it doesn't affect
    # cake's count.
    grid = _grid(
        ["cake", "cake", "cake"],
        ["cake", "cake", "cake"],
        ["x3", "gift", "gift"],
    )
    symbols = [
        SymbolDef(code="cake", symbol_type="regular", weights=[1] * 3, pays={6: Decimal("1")}),
        SymbolDef(code="gift", symbol_type="regular", weights=[1] * 3, pays={8: Decimal("1")}),
        TOKEN_X3,
    ]
    # 7 replacement draws needed (6 cake positions + the 1 token position) —
    # raw=2 always picks "x3" itself (weights [cake,gift,x3]=[1,1,1],
    # cumulative [2,3)) as filler: it never count-pays on its own (empty
    # pays), so no matter how many pile up refilling, they can't re-trigger
    # a second cascade — picking "gift" instead would eventually accumulate
    # past its own 8-threshold and cascade again, which isn't what this test
    # is about.
    rng = FakeRNG([2] * 7)
    result = run_avalanche(grid, ReelSetConfig(num_reels=3, num_rows=3, symbols=symbols), symbols, rng, Decimal("10"), multiplier_steps=[2])

    assert len(result.steps) == 1
    step = result.steps[0]
    assert len(step.wins) == 1 and step.wins[0].symbol_code == "cake"
    # multiplier_steps[0]=2 (trail) + token value 3 = 5.
    assert step.multiplier == 5
    assert len(step.tokens_consumed) == 1
    token = step.tokens_consumed[0]
    assert (token.reel, token.row, token.value) == (2, 0, 3)
    # reel 2's surviving "gift"s (rows 1-2, never touched by removal) are
    # still there, dropped down to the bottom by the refill.
    assert step.grid_after.reels[2][1:] == ["gift", "gift"]


def test_multiple_multiplier_tokens_sum_together():
    grid = _grid(
        ["cake", "cake", "cake"],
        ["cake", "cake", "cake"],
        ["x3", "x5", "gift"],
    )
    symbols = [
        SymbolDef(code="cake", symbol_type="regular", weights=[1] * 3, pays={6: Decimal("1")}),
        SymbolDef(code="gift", symbol_type="regular", weights=[1] * 3, pays={8: Decimal("1")}),
        TOKEN_X3,
        TOKEN_X5,
    ]
    # raw=2 -> "x3" itself as filler (weights [cake,gift,x3,x5]=[1,1,1,1],
    # cumulative [2,3)) — same non-re-triggering reasoning as the test above.
    rng = FakeRNG([2] * 8)
    result = run_avalanche(
        grid, ReelSetConfig(num_reels=3, num_rows=3, symbols=symbols), symbols, rng, Decimal("10"),
        multiplier_steps=[1],
    )
    step = result.steps[0]
    # trail(1) + x3(3) + x5(5) = 9.
    assert step.multiplier == 9
    assert {t.value for t in step.tokens_consumed} == {3, 5}


def test_multiplier_tokens_accumulate_across_cascade_steps_within_one_round():
    # product, this session: "он должен суммировать все множители которые
    # выпадут до следующего спина" — a token's value keeps contributing to
    # every later step's multiplier within the SAME round, not just the
    # step it was swept up on (it only resets when the next spin's own
    # run_avalanche call starts fresh).
    grid = _grid(
        ["cake", "cake", "cake"],
        ["cake", "cake", "cake"],
        ["x3", "gift", "gift"],
    )
    cake = SymbolDef(code="cake", symbol_type="regular", weights=[1] * 5, pays={6: Decimal("1")})
    gift = SymbolDef(code="gift", symbol_type="regular", weights=[1] * 5, pays={8: Decimal("1")})
    filler = SymbolDef(code="filler", symbol_type="regular", weights=[1] * 5, pays={})
    symbols = [cake, gift, TOKEN_X3, TOKEN_X5, filler]

    # Step 1 refill (7 cells: reel0's 3 cake + reel1's 3 cake + reel2's 1
    # token position) — reel0/reel1 come back all "cake" (raw=0), so cake
    # wins AGAIN in step 2; reel2's single refill lands the "x5" token
    # (raw=3) right where the swept x3 token used to sit.
    step1_refill = [0, 0, 0, 0, 0, 0, 3]
    # Step 2 refill (7 cells: another 6 cake + the x5 token) — all "filler"
    # (raw=4, empty pays) so nothing else wins and the round stops after
    # exactly 2 steps.
    step2_refill = [4] * 7
    rng = FakeRNG(step1_refill + step2_refill)

    result = run_avalanche(
        grid, ReelSetConfig(num_reels=3, num_rows=3, symbols=symbols), symbols, rng, Decimal("10"),
        multiplier_steps=[2, 10],
    )

    assert len(result.steps) == 2
    step1, step2 = result.steps
    assert step1.multiplier == 2 + 3  # trail[0](2) + this step's x3(3)
    # trail[1](10) + running total (x3=3 from step1 + x5=5 from step2 = 8),
    # NOT just this step's own x5(5) — that would give 15, the old bug.
    assert step2.multiplier == 10 + 8


def test_multiplier_token_with_no_win_this_round_is_never_consumed():
    # No symbol here meets its own tier threshold (cake needs 6, only has 2) —
    # the round ends immediately with zero steps, so the token sitting on
    # the board is simply never touched (product: it just never contributed).
    grid = _grid(["cake", "x3"], ["cake", "gift"])
    symbols = [
        SymbolDef(code="cake", symbol_type="regular", weights=[1] * 2, pays={6: Decimal("1")}),
        SymbolDef(code="gift", symbol_type="regular", weights=[1] * 2, pays={6: Decimal("1")}),
        TOKEN_X3,
    ]
    result = run_avalanche(grid, ReelSetConfig(num_reels=2, num_rows=2, symbols=symbols), symbols, FakeRNG([]), Decimal("10"))

    assert result.steps == ()
    assert result.final_grid is grid  # completely untouched, token included


def test_multiplier_token_never_count_pays_on_its_own():
    # 8 "x3" tokens on their own tier-eligible board would never win via
    # evaluate_cascade_wins directly, since it's symbol_type="bonus" (same
    # exclusion as SCATTER — see _AVALANCHE_PAY_TYPES).
    columns = [["x3"] * 4 for _ in range(4)]
    grid = _grid(*columns)
    wins = evaluate_cascade_wins(grid, [TOKEN_X3], total_bet=Decimal("10"))
    assert wins == ()


# --- run_avalanche: bomb symbol (party-of-goods' "boom") -------------------

BOOM = SymbolDef(code="boom", symbol_type="bonus", weights=[1] * 3, pays={}, is_bomb=True)
FILLER = SymbolDef(code="filler", symbol_type="regular", weights=[1] * 3, pays={})


def test_bomb_never_count_pays_on_its_own():
    columns = [["boom"] * 4 for _ in range(4)]
    grid = _grid(*columns)
    wins = evaluate_cascade_wins(grid, [BOOM], total_bet=Decimal("10"))
    assert wins == ()


def test_bomb_detonates_and_clears_cross_even_with_no_win_anywhere():
    # 3x3 grid, bomb dead center (reel=1, row=1); every other cell is a
    # "filler" symbol with an empty paytable (can never win on its own) —
    # the round still produces exactly one step, purely from the bomb.
    grid = _grid(
        ["filler", "filler", "filler"],
        ["filler", "boom", "filler"],
        ["filler", "filler", "filler"],
    )
    symbols = [FILLER, BOOM]
    # 5 replacement draws for the cross's cells — raw=0 always picks
    # "filler" (weights [filler, boom] = [1, 1], cumulative [0, 1)), which
    # never wins and isn't a bomb, so the round stops after one step.
    rng = FakeRNG([0] * 5)
    result = run_avalanche(grid, ReelSetConfig(num_reels=3, num_rows=3, symbols=symbols), symbols, rng, Decimal("10"))

    assert len(result.steps) == 1
    step = result.steps[0]
    assert step.wins == ()
    assert step.step_win == Decimal("0")  # clears only, no payout of its own
    assert step.tokens_consumed == ()
    assert len(step.bombs_detonated) == 1
    bomb = step.bombs_detonated[0]
    assert (bomb.reel, bomb.row) == (1, 1)
    assert set(bomb.cleared) == {(1, 0), (1, 1), (1, 2), (0, 1), (2, 1)}

    # Untouched corners survive; the cross's 5 cells were all redrawn.
    assert step.grid_after.reels[0][0] == "filler"
    assert step.grid_after.reels[0][2] == "filler"
    assert step.grid_after.reels[2][0] == "filler"
    assert step.grid_after.reels[2][2] == "filler"
    assert len(step.grid_after.draws) == len(grid.draws) + 5


def test_bomb_alongside_a_win_is_deferred_to_its_own_later_step():
    # 3 reels x 4 rows: reels 0+1 are "cake" (count=8, wins), reel 2 has a
    # bomb at row 0 plus 3 filler cells. Product: wins on a grid always
    # resolve first, so this round's first step is win-only (the bomb sits
    # untouched on reel 2) — only once that grid is refilled and comes back
    # win-free does the bomb get its own, separate step.
    grid = _grid(
        ["cake", "cake", "cake", "cake"],
        ["cake", "cake", "cake", "cake"],
        ["boom", "filler", "filler", "filler"],
    )
    cake = SymbolDef(code="cake", symbol_type="regular", weights=[1] * 3, pays={8: Decimal("1")})
    symbols = [cake, FILLER, BOOM]
    # raw=1 always picks "filler" (weights [cake, filler, boom] = [1, 1, 1],
    # cumulative [1, 2)) — never wins and never a bomb, so refills stay
    # inert. Step 1 refills the 8 cake positions; step 2's bomb cross then
    # clears reel 2's column (4 cells) + row 0 across all reels (2 more new
    # cells) = 6 positions. 8 + 6 = 14 replacement draws total.
    rng = FakeRNG([1] * 14)
    result = run_avalanche(
        grid, ReelSetConfig(num_reels=3, num_rows=4, symbols=symbols), symbols, rng, Decimal("10"),
        multiplier_steps=[2],
    )

    assert len(result.steps) == 2

    win_step = result.steps[0]
    assert len(win_step.wins) == 1 and win_step.wins[0].symbol_code == "cake"
    assert win_step.bombs_detonated == ()
    assert win_step.multiplier == 2
    assert win_step.step_win == Decimal("1") * Decimal("10") * 2  # cake pays[8]=1 * bet * trail(2)
    # reel 2 (with the bomb) untouched by the win step; reels 0-1 refilled.
    assert win_step.grid_after.reels[2] == ["boom", "filler", "filler", "filler"]

    bomb_step = result.steps[1]
    assert bomb_step.wins == ()
    assert bomb_step.step_win == Decimal("0")  # clears only, no payout of its own
    assert len(bomb_step.bombs_detonated) == 1
    bomb = bomb_step.bombs_detonated[0]
    assert (bomb.reel, bomb.row) == (2, 0)
    assert set(bomb.cleared) == {(2, 0), (2, 1), (2, 2), (2, 3), (0, 0), (1, 0)}

    # Whole grid now cleared: the win step took reels 0-1, the bomb step
    # took the rest of reel 2 (its own column) plus row 0.
    assert all(code == "filler" for column in bomb_step.grid_after.reels for code in column)


def test_bomb_does_not_clear_wild_or_scatter_cells_in_its_cross():
    # 3x3 grid, bomb dead center. Its cross would normally hit all four
    # neighbors, but the one directly above is "wild" and the one directly
    # below is "scatter" — both bomb-proof, so they survive untouched and
    # aren't even reported in `cleared`.
    grid = _grid(
        ["filler", "filler", "filler"],
        ["wild", "boom", "scatter"],
        ["filler", "filler", "filler"],
    )
    symbols = [FILLER, BOOM, WILD, SCATTER]
    # raw=0 always picks "filler" (weights [filler,boom,wild,scatter] all 1,
    # cumulative [0,1)) — never wins, never a bomb, so the round stops after
    # exactly this one bomb step.
    rng = FakeRNG([0] * 3)
    result = run_avalanche(grid, ReelSetConfig(num_reels=3, num_rows=3, symbols=symbols), symbols, rng, Decimal("10"))

    assert len(result.steps) == 1
    step = result.steps[0]
    bomb = step.bombs_detonated[0]
    assert (bomb.reel, bomb.row) == (1, 1)
    # Cross would be {(1,0),(1,1),(1,2),(0,1),(2,1)}; (1,0)=wild and
    # (1,2)=scatter are filtered out as bomb-proof.
    assert set(bomb.cleared) == {(1, 1), (0, 1), (2, 1)}

    # Gravity: the cleared middle cell is refilled at the top, and the two
    # bomb-proof survivors (order preserved) drop down beneath it.
    assert step.grid_after.reels[1][1] == "wild"
    assert step.grid_after.reels[1][2] == "scatter"
