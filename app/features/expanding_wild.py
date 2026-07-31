from decimal import Decimal

from app.engine.reels import weighted_pick
from app.features.base import BonusFeature, FeatureContext, FeatureResult
from app.features.registry import default_registry

_STATE_KEY = "walking_wilds"


def _roll(chance: float, rng) -> bool:
    """True with probability `chance` (0.0-1.0). Short-circuits at the 0/1
    extremes without touching `rng` at all, so a config that doesn't set
    expand_chance/walk_chance (both default to 1.0 — see East Discovery's
    seed for the 0.5/0.5 config that actually uses this) behaves exactly
    like before this feature became probabilistic, consuming no extra RNG
    draws and requiring no test changes for existing always-expand/always-
    walk callers (e.g. Amy's Fruit Farm)."""
    if chance >= 1:
        return True
    if chance <= 0:
        return False
    hit_weight = round(chance * 1000)
    index, _, _ = weighted_pick([hit_weight, 1000 - hit_weight], rng)
    return index == 0


class ExpandingWildFeature(BonusFeature):
    """When the wild lands on a reel it *may* expand to fill the whole reel
    (all rows) — `expand_chance`, default 1.0 (always) — then, once
    expanded, *may* walk one reel to the right on each subsequent spin —
    `walk_chance`, also default 1.0 — in both the base game and Free Spins,
    until a successful walk-roll would push it off the right edge of the
    grid. A missed walk-roll just leaves it on the same reel to try again
    next spin, rather than disappearing (confirmed with product).

    Unlike free_spins/hold_and_win, this feature must run *before*
    evaluate_spin() — it reshapes the grid itself rather than scoring a win,
    so `execute()` mutates `game_state.grid.reels` in place and always
    returns `win_amount=0`; the win comes from evaluating the reshaped grid
    afterward.
    """

    feature_id = "expanding_wild"

    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        if spin_result.session_state.get(_STATE_KEY):
            return True
        if spin_result.grid is None:
            return False
        trigger_code = config.get("trigger_symbol_code", "wild")
        return any(trigger_code in column for column in spin_result.grid.reels)

    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        if game_state.grid is None:
            raise ValueError("expanding_wild.execute requires a grid")

        trigger_code = config.get("trigger_symbol_code", "wild")
        walk_enabled = config.get("walk_enabled", True)
        expand_chance = config.get("expand_chance", 1.0)
        walk_chance = config.get("walk_chance", 1.0)
        num_reels = len(game_state.grid.reels)
        num_rows = len(game_state.grid.reels[0]) if num_reels else 0

        events: list[dict] = []
        active_reels: set[int] = set()

        # Carried-over walkers land first — they're already expanded from a
        # previous spin, so no expand-roll here; they occupy their reel on
        # this spin regardless of what the RNG drew there.
        for reel in game_state.session_state.get(_STATE_KEY, []):
            if 0 <= reel < num_reels:
                self._expand_reel(game_state.grid.reels, reel, num_rows, trigger_code)
                events.append({"reel": reel, "event": "walked"})
                active_reels.add(reel)

        # Then any freshly-landed wild not already covered by a walker — each
        # one independently rolls expand_chance; a miss stays a normal
        # single-cell wild (no event, doesn't become a walker).
        for reel in range(num_reels):
            if reel in active_reels:
                continue
            if trigger_code in game_state.grid.reels[reel]:
                if _roll(expand_chance, game_state.rng):
                    self._expand_reel(game_state.grid.reels, reel, num_rows, trigger_code)
                    events.append({"reel": reel, "event": "expanded"})
                    active_reels.add(reel)

        next_walkers: list[int] = []
        if walk_enabled:
            for reel in sorted(active_reels):
                if not _roll(walk_chance, game_state.rng):
                    next_walkers.append(reel)  # miss: stays put, re-rolls next spin
                    continue
                next_reel = reel + 1
                if next_reel < num_reels:
                    next_walkers.append(next_reel)
                else:
                    events.append({"reel": reel, "event": "expired"})

        return FeatureResult(
            feature_id=self.feature_id,
            triggered=True,
            win_amount=Decimal(0),
            state_patch={_STATE_KEY: next_walkers},
            details={"events": events},
        )

    @staticmethod
    def _expand_reel(reels: list[list[str]], reel: int, num_rows: int, trigger_code: str) -> None:
        for row in range(num_rows):
            reels[reel][row] = trigger_code

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "trigger_symbol_code": {"type": "string", "default": "wild"},
                "walk_enabled": {"type": "boolean", "default": True},
                "walk_direction": {
                    "type": "string",
                    "enum": ["right"],
                    "default": "right",
                    "description": "Only 'right' is currently implemented.",
                },
                "expand_chance": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 1.0,
                    "description": "Probability a freshly-landed wild expands to fill its reel.",
                },
                "walk_chance": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 1.0,
                    "description": "Probability an active walker advances one reel right each spin.",
                },
            },
            "required": ["trigger_symbol_code"],
        }


default_registry.register(ExpandingWildFeature())
