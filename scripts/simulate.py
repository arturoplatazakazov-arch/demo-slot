#!/usr/bin/env python3
"""CLI RTP/volatility/hit-frequency/bonus-frequency simulator (TZ §7 — "Доступен
как CLI-скрипт и как действие в админке"). Same app.simulator engine the
admin API's simulate endpoint uses.

Usage:
    python scripts/simulate.py --game amys-fruit-farm --spins 100000
    python scripts/simulate.py --config-id <uuid> --spins 1000000 --seed 42
"""

import argparse
import asyncio
import json
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.config import GameConfig
from app.models.enums import GameConfigStatus
from app.models.game import Game
from app.simulator import FastRNG, simulate_game_config

# A dedicated echo=False engine rather than app.core.db's shared one — that
# one echoes SQL to stdout when settings.debug is on, which would interleave
# with the JSON report below and break `| jq` / `| python -m json.tool`.
_engine = create_async_engine(get_settings().database_url, echo=False)
_SessionLocal = async_sessionmaker(bind=_engine, expire_on_commit=False)


async def _load_config(config_id: uuid.UUID | None, game_code: str | None) -> GameConfig:
    async with _SessionLocal() as db:
        query = select(GameConfig).options(
            selectinload(GameConfig.symbols),
            selectinload(GameConfig.paylines),
            selectinload(GameConfig.feature_configs),
        )
        if config_id is not None:
            query = query.where(GameConfig.id == config_id)
        else:
            query = query.join(Game).where(
                Game.code == game_code, GameConfig.status == GameConfigStatus.ACTIVE.value
            )
        result = await db.execute(query)
        config = result.scalars().first()
        if config is None:
            target = f"config {config_id}" if config_id else f"active config for game '{game_code}'"
            print(f"error: {target} not found", file=sys.stderr)
            sys.exit(1)
        return config


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--game", default="amys-fruit-farm", help="game code (uses its active config)")
    target.add_argument("--config-id", type=uuid.UUID, help="simulate a specific config version instead")
    parser.add_argument("--spins", type=int, default=100_000, help="number of base-game spins (default: 100000)")
    parser.add_argument("--bet", type=str, default=None, help="fixed bet per spin (default: config's min_bet)")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed, for a reproducible run")
    args = parser.parse_args()

    config = await _load_config(args.config_id, args.game if args.config_id is None else None)
    rng = FastRNG(seed=args.seed)
    bet_amount = Decimal(args.bet) if args.bet is not None else None

    report = simulate_game_config(config, num_spins=args.spins, rng=rng, bet_amount=bet_amount)
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
