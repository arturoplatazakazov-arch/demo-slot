from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

from app.engine.rng import RNGProvider
from app.engine.types import SpinGrid, SymbolDef, WinEvaluation


@dataclass
class FeatureContext:
    """Everything a bonus module needs to decide whether it fires and to run
    itself. One shared shape used for both the `spin_result` argument to
    `is_triggered` and the `game_state` argument to `execute` (TZ §6.1 names
    them differently, but in practice they're the same context passed
    through the same spin) — kept as one type to avoid duplicating fields.

    `session_state` is the same dict that lives on `Session.state`; features
    read/mutate it directly for anything that must survive across calls
    within one orchestration step (e.g. Jackpot stashing which level hit
    between `is_triggered` and `execute`). Persisting the resulting patch
    back to the DB is the API layer's job (stage 5), not this module's.
    """

    session_state: dict
    rng: RNGProvider
    bet_amount: Decimal
    symbols: Sequence[SymbolDef] = ()
    grid: SpinGrid | None = None
    win_evaluation: WinEvaluation | None = None
    is_bonus_buy: bool = False


@dataclass
class FeatureResult:
    feature_id: str
    triggered: bool
    win_amount: Decimal = Decimal(0)
    # Keys to merge into `Session.state` after this call.
    state_patch: dict = field(default_factory=dict)
    # Free-form, JSON-serializable detail for the API response / audit log.
    details: dict = field(default_factory=dict)


class BonusFeature(ABC):
    """Plugin interface for a bonus module (TZ §6.1). Enabling/disabling and
    parameterizing an implementation happens entirely through `FeatureConfig`
    rows in the admin (TZ §5, §8.2) — adding a new feature *type* still means
    shipping a new module and registering it (TZ §6.1's own stated scope:
    admin configures already-implemented features, it doesn't author new
    logic from scratch)."""

    feature_id: str

    @abstractmethod
    def is_triggered(self, spin_result: FeatureContext, config: dict) -> bool:
        """Whether this feature should fire for the given spin/context."""

    @abstractmethod
    def execute(self, game_state: FeatureContext, config: dict) -> FeatureResult:
        """Run the feature. Only called after `is_triggered` returned True,
        or in response to an explicit player action (Gamble, Bonus Buy)."""

    @abstractmethod
    def get_config_schema(self) -> dict:
        """JSON-schema-shaped dict describing `config`, for admin-side
        validation (TZ §6.1) when editing this feature's parameters."""
