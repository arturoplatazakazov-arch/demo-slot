"""Grid post-processing shared by every spin path (production API, bulk
simulator, builder test-spin): per-symbol reel caps and the pre-evaluation
expanding/walking wild. Lives here rather than in the API layer so
app/simulator and the admin builder consume the exact same functions as
production and can't silently drift from real math."""

from decimal import Decimal

from app.engine.rng import RNGProvider
from app.engine.types import ReelSetConfig, SpinGrid
from app.features import default_registry
from app.features.base import FeatureContext
from app.services.scatter_cap import cap_symbol_per_reel


def apply_reel_caps(grid: SpinGrid, reel_set: ReelSetConfig, rng: RNGProvider) -> SpinGrid:
    """Admin-configurable per-symbol reel cap (Symbol.max_per_reel), applied
    to every symbol that has one set — not just scatter. Order is
    deterministic (reel_set.symbols' own order) so results are reproducible
    for a given RNG sequence."""
    for symbol in reel_set.symbols:
        if symbol.max_per_reel is not None:
            grid = cap_symbol_per_reel(grid, reel_set, rng, symbol.code, symbol.max_per_reel)
    return grid


def apply_expanding_wild(
    grid: SpinGrid,
    wild_config,
    state: dict,
    rng: RNGProvider,
    bet_amount: Decimal,
    reel_set: ReelSetConfig,
    is_bonus_buy: bool = False,
) -> list[dict]:
    """Reshapes `grid` in place (expanding/walking wild) *before* win
    evaluation — unlike free_spins/hold_and_win, which only attach side info
    after a grid has already been scored. Mutates `state` with the carried
    walker positions for the next spin. Returns the wild events for this
    spin (empty if the feature isn't configured or didn't fire).

    Takes an already-resolved `wild_config` (an enabled FeatureConfig row, or
    None) rather than the whole GameConfig, so app/simulator/engine.py can
    call this exact same function — same as it already does for
    `apply_reel_caps` above — and stay honest with production math instead
    of silently drifting (see that module's docstring)."""
    feature = default_registry.get("expanding_wild")
    if feature is None or wild_config is None:
        return []

    ctx = FeatureContext(
        session_state=state,
        rng=rng,
        bet_amount=bet_amount,
        symbols=reel_set.symbols,
        grid=grid,
        is_bonus_buy=is_bonus_buy,
    )
    if not feature.is_triggered(ctx, wild_config.params):
        return []

    result = feature.execute(ctx, wild_config.params)
    state.update(result.state_patch)
    return result.details.get("events", [])
