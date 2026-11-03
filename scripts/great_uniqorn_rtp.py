#!/usr/bin/env python3
"""RTP check for great-uniqorn straight from the seed (no database needed).

Runs app.simulator over build_game_config()'s unpersisted ORM objects — the
same engine scripts/simulate.py drives against the DB-backed active config.

usage: python scripts/great_uniqorn_rtp.py [spins] [seed]
"""
import json
import sys
from decimal import Decimal

from app.seed.great_uniqorn import build_game_config
from app.simulator import FastRNG, simulate_game_config

spins = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
_, config = build_game_config()
report = simulate_game_config(config, spins, FastRNG(seed), Decimal(config.min_bet))
data = report.model_dump() if hasattr(report, "model_dump") else report.__dict__
print(json.dumps(data, default=str, indent=1))
