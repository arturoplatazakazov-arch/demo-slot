"""ORM `GameConfig` -> engine config dataclasses. The engine (app/engine) is
deliberately DB-agnostic (TZ §2: math lives in config, engine stays
testable without a database) — this module is the one place that bridges
persisted config rows into the shapes `app.engine` and `app.features`
actually consume."""

from decimal import Decimal

from app.engine.types import PaylineDef, ReelSetConfig, SymbolDef
from app.models.config import GameConfig


def to_reel_set_config(game_config: GameConfig) -> ReelSetConfig:
    symbols = [
        SymbolDef(
            code=s.code,
            symbol_type=s.symbol_type,
            weights=s.reel_weights,
            pays={int(count): Decimal(str(mult)) for count, mult in s.paytable.items()},
            max_per_reel=s.max_per_reel,
            multiplier_value=s.multiplier_value,
            is_bomb=s.is_bomb,
        )
        for s in game_config.symbols
    ]
    return ReelSetConfig(num_reels=game_config.num_reels, num_rows=game_config.num_rows, symbols=symbols)


def to_paylines(game_config: GameConfig) -> list[PaylineDef]:
    return [PaylineDef(index=p.index, positions=p.positions) for p in game_config.paylines]


def symbol_tiers(game_config: GameConfig) -> dict[str, str]:
    """code -> "low"/"high", for popup win-tier selection (API-layer only;
    app/engine and app/features never see this)."""
    return {s.code: s.tier for s in game_config.symbols}
