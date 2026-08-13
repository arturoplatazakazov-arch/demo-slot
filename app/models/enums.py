import enum


class SymbolType(str, enum.Enum):
    REGULAR = "regular"
    WILD = "wild"
    SCATTER = "scatter"
    BONUS = "bonus"


class SymbolTier(str, enum.Enum):
    LOW = "low"
    HIGH = "high"


class WildSubtype(str, enum.Enum):
    STANDARD = "standard"
    EXPANDING = "expanding"
    STICKY = "sticky"
    MULTIPLIER = "multiplier"


class GameConfigStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class FeatureType(str, enum.Enum):
    FREE_SPINS = "free_spins"
    HOLD_AND_WIN = "hold_and_win"
    BONUS_BUY = "bonus_buy"
    GAMBLE = "gamble"
    JACKPOT = "jackpot"
    EXPANDING_WILD = "expanding_wild"
    MULTIPLIER_WILD = "multiplier_wild"
    COIN_MULTIPLIER = "coin_multiplier"
    WHEEL_OF_FORTUNE = "wheel_of_fortune"
    # Not a BonusFeature plugin (no is_triggered/execute) — a pure config
    # carrier spin_service.py looks up directly to know a game's base win
    # mechanic is avalanche/cascade (app/engine/avalanche.py) instead of the
    # default line-pay + count-pay evaluation.
    AVALANCHE = "avalanche"


class SimulationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
