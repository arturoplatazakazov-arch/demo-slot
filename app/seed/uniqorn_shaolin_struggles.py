"""Seed data for the "uniqorn-shaolin-struggles" game
(front/uniqorn-shaolin-struggles.html).

A 3x3 Hold & Win built to the same product spec as the reference
api.dreamplay.games/hell-coins, i.e. the mechanic app/seed/lucky_joker_3h3.py
already implements — but stripped down to what that reference actually ships:

  * FOUR low symbols + THREE high symbols, one COIN and one COLLECTOR. No
    scatter, therefore no free-spins round at all (product: "скаттер тут не
    нужен"), and no wild either — the reel set is exactly the eight codes
    above. Everything the game pays out comes from line pay, the coin
    multiplier and the Hold & Win round;
  * COIN is a base-game symbol on all three reels carrying its own multiplier
    (x1..x15 plus the four jackpot tiers). It never pays by itself:
    coin_multiplier multiplies a WINNING LINE by the sum of every coin's
    multiplier, with no collector needed on the grid (requires_collector=False);
  * a COLLECTOR on the middle reel (its per-reel weights pin it there) plus a
    coin on each of the outer two opens Hold & Win in the feature's `collector`
    mode: the grid opens empty except that collector, the middle reel then
    takes only collectors and the outer two only coins, and EVERY collector is
    worth the sum of all coin multipliers (two collectors pay it twice, three
    pay it three times). 3 respins, reset by any new landing;
  * the only thing on sale is the round itself (bonus_buy ->
    target_feature_id="hold_and_win"), since there is no other feature to buy.

Symbol codes are a fixed contract with SYMBOL_CODES in
front/js/uniqorn-shaolin-struggles/slot.js (each code == its PNG file name) —
do not rename them.

3 reels x 3 rows means a payline is either a 3-of-a-kind or nothing, so the
paytable has a single "3" entry per symbol — see the RTP note on _PAYS.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType

GAME_CODE = "uniqorn-shaolin-struggles"
GAME_NAME = "Uniqorn Shaolin Struggles"
CATALOG_BADGE = "Hold & Win"
CATALOG_DESCRIPTION = "Единорог-шаолинец, монеты-множители и коллектор в Hold'n'Win 3x3."
CATALOG_COVER_PATH = "img/uniqorn-shaolin-struggles/img/cover.jpg"
CATALOG_PLAY_URL = "uniqorn-shaolin-struggles.html"

NUM_REELS = 3
NUM_ROWS = 3

# 5 lines: the three rows plus both diagonals — everything a 3x3 grid has room
# for. row index: 0=top, 1=mid, 2=bottom.
PAYLINES: list[list[int]] = [
    [1, 1, 1],
    [0, 0, 0],
    [2, 2, 2],
    [0, 1, 2],
    [2, 1, 0],
]

# Bet is split evenly across the 5 paylines (bet_per_line = bet / 5), so every
# step is a multiple of 5 — otherwise each line win carries a fractional
# remainder that the API response truncates away on its way to `int`.
BET_STEPS = [10000, 25000, 50000, 100000, 250000, 500000]

# The jackpot ladder, name -> bet multiplier. Unlike lucky-joker-3h3 (whose
# amounts were baked into delivered plate art) these plates are DOM text
# rendered from this table, so the two can't drift — but front's
# JACKPOT_LADDER mirrors them for the ladder display, keep both in step.
JACKPOT_VALUES = {"mini": 25, "minor": 50, "major": 150, "grand": 1000}

# Payouts are per LINE (multiplied by bet/5), and only a full 3-of-a-kind pays
# — a 3-reel line is all-or-nothing.
#
# The table is deliberately LOW for a 3x3, because coin_multiplier amplifies
# it: a coin is on the grid on 48% of spins and multiplies the whole line pay
# by the sum of the coins' multipliers (~2.7 each on average), so line pay is
# worth roughly 1.75x what this table says by the time it reaches the player.
# Tuning these numbers without re-measuring that amplification is how the donor
# game (lucky-joker-3h3) ended up at RTP 2.9 on its first pass.
#
# Measured over 300k spins per seed (7 / 21 / 42 / 99), running the real
# features over the real drawn grids:
#   line pay                          0.359 - 0.365
#   coin multiplier on winning lines  0.253 - 0.286  (pays on 4.6% of spins)
#   Hold & Win (collector round)      0.293 - 0.346  (1 spin in ~147)
#   TOTAL RTP           0.918 / 0.969 / 0.958 / 0.951  -> mean ~0.949
# Hit frequency 12.6%, average round ~47x the bet, biggest observed round
# ~3100x. The spread between seeds is the GRAND coin (x1000): a run either
# catches a few or it doesn't.
#
# NB: scripts/simulate.py knows nothing about the two coin mechanics, so its
# RTP number is the line-pay part alone. The figures above came from running
# app/features/coin_multiplier.py and hold_and_win.py over the same drawn grids
# alongside it; do the same after touching any weight or payout.
_PAYS = {
    "noodles": {"3": 8.9},
    "bamboo": {"3": 10.9},
    "nunchaku": {"3": 14.8},
    "bucket": {"3": 20.3},
    "bell": {"3": 40.5},
    "dragon": {"3": 81.0},
    "pagoda": {"3": 229.0},
    # COIN never pays a cent through the standard engine
    # (evaluate_line_wins/evaluate_count_wins both skip a symbol with no
    # matching pays entry) — it earns its keep through coin_multiplier (it
    # multiplies a winning line) and hold_and_win (it fills the round), both of
    # which scan for it by code.
    "coin": {},
    # COLLECTOR — same deal, and it only ever appears on the middle reel (see
    # its reel_weights). It opens the round and then collects inside it.
    "collector": {},
}

# code -> (display name, symbol type, tier, weight, max_per_reel). `weight` is
# either one number used on every reel, or one per reel — which is how the
# COLLECTOR is pinned to the middle reel and nowhere else ([0, w, 0]).
_SYMBOLS: list[tuple[str, str, str, str, int | list[int], int | None]] = [
    ("noodles", "Лапша", SymbolType.REGULAR.value, "low", 26, None),
    ("bamboo", "Бамбук", SymbolType.REGULAR.value, "low", 22, None),
    ("nunchaku", "Нунчаки", SymbolType.REGULAR.value, "low", 18, None),
    ("bucket", "Ведро", SymbolType.REGULAR.value, "low", 15, None),
    ("bell", "Колокол", SymbolType.REGULAR.value, "high", 11, None),
    ("dragon", "Дракон", SymbolType.REGULAR.value, "high", 7, None),
    ("pagoda", "Пагода", SymbolType.REGULAR.value, "high", 4, None),
    # Coin. Not capped per reel: two coins in one column are a perfectly good
    # outcome (they both multiply the line). The round needs one on each of the
    # OUTER reels, so this weight sets P(coin in a column) = 1-(1-p)^3 and the
    # trigger rate goes as that squared, times the collector below.
    ("coin", "Монета", SymbolType.BONUS.value, "high", 8, None),
    # Collector — ONLY on the middle reel, hence the per-reel weights. Capped
    # at 1: a second one on the triggering grid would have nowhere to go, the
    # round starts from exactly one.
    ("collector", "Коллектор", SymbolType.BONUS.value, "high", [0, 7, 0], 1),
]

# What a bought Hold & Win costs, in bets. A bought round is worth 47.6x the
# bet on average (measured the same way as _PAYS; unlike a natural trigger it
# isn't charged a bet on top of the price — see run_feature_buy), so 50x sells
# it at ~0.95, the game's own RTP, rather than at a discount or a rip-off.
# Mirrored by BUY_BONUS_COST_MULTIPLIER in
# front/js/uniqorn-shaolin-struggles/app.js (display only — the server charges
# this number).
BONUS_BUY_COST_MULTIPLIER = 50


def build_game_config() -> tuple[Game, GameConfig]:
    """Construct (unpersisted) ORM objects for this game's v1 config."""
    game = Game(
        code=GAME_CODE, name=GAME_NAME,
        catalog_badge=CATALOG_BADGE, catalog_description=CATALOG_DESCRIPTION,
        catalog_cover_path=CATALOG_COVER_PATH, catalog_play_url=CATALOG_PLAY_URL,
    )
    config = GameConfig(
        game=game,
        version=1,
        status=GameConfigStatus.ACTIVE.value,
        num_reels=NUM_REELS,
        num_rows=NUM_ROWS,
        target_rtp=0.96,
        min_bet=BET_STEPS[0],
        max_bet=BET_STEPS[-1],
        bet_step=BET_STEPS[0],
        bet_steps=BET_STEPS,
        notes=(
            "Seed config — hand-tuned; measured RTP ~0.95 (line pay 0.36 + coin multiplier ~0.27 "
            "+ Hold & Win ~0.32), hit frequency 12.6%, Hold & Win 1 in ~147 spins. "
            "No scatter and no free spins by design. See the note on _PAYS."
        ),
    )

    for order, (code, name, symbol_type, tier, weight, max_per_reel) in enumerate(_SYMBOLS):
        Symbol(
            game_config=config,
            code=code,
            name=name,
            symbol_type=symbol_type,
            tier=tier,
            reel_weights=list(weight) if isinstance(weight, list) else [weight] * NUM_REELS,
            paytable=_PAYS[code],
            max_per_reel=max_per_reel,
            display_order=order,
        )

    for index, positions in enumerate(PAYLINES, start=1):
        Payline(game_config=config, index=index, positions=positions)

    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.COIN_MULTIPLIER.value,
        enabled=True,
        params={
            "coin_symbol_code": "coin",
            # No collector on the base reels — a coin multiplies a winning line
            # on its own. The code is still named so the feature has something
            # to report; nothing on the base grid ever matches it.
            "collector_symbol_code": "collector",
            "requires_collector": False,
            # Base-game coin faces. Jackpot tiers can land here too, but they
            # have to stay RARE — a GRAND coin multiplies the line by 1000, so
            # its weight alone drives the tail of the whole game. Weighted
            # against a big denominator so the tiers can be genuinely rare:
            # GRAND is 2 in 9168 draws per coin. Average multiplier per coin at
            # these weights: ~2.7.
            "value_weights": {
                "1": 4600, "2": 2400, "3": 1200, "5": 600, "10": 200, "15": 80,
                "mini": 60, "minor": 20, "major": 6, "grand": 2,
            },
            "jackpot_values": JACKPOT_VALUES,
        },
        display_order=0,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.HOLD_AND_WIN.value,
        enabled=True,
        params={
            "trigger_symbol_code": "coin",
            # A COLLECTOR on the middle reel plus a coin on each of the outer
            # two — the collector is what opens the round, the coins are what it
            # will collect.
            "trigger_mode": "collector_and_coins",
            "mode": "collector",
            "collector_reel": 1,          # the middle reel of three
            "collector_symbol_code": "collector",
            "respin_count": 3,
            # Per-cell land roll on the two coin reels...
            "respin_land_weights": {"blank": 84, "coin": 16},
            # ...and a rarer one on the collector reel: every extra collector
            # multiplies the ENTIRE round's payout, so these are the most
            # valuable cells on the grid.
            "collector_land_weights": {"blank": 93, "coin": 7},
            # Coin faces inside the round. Same tiers as the base game, but
            # weighted its own way — here the values are summed and then
            # multiplied by the number of collectors.
            "coin_value_weights": {
                "1": 300, "2": 200, "3": 130, "5": 80, "10": 34, "15": 16,
                "mini": 18, "minor": 8, "major": 3, "grand": 1,
            },
            "jackpot_values": JACKPOT_VALUES,
        },
        display_order=1,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.BONUS_BUY.value,
        enabled=True,
        # `products` list shape (not the flat single-product one) — the buy_id
        # is what front/js/uniqorn-shaolin-struggles/app.js posts. There is
        # exactly one product here: with no free-spins round in the game, the
        # Hold & Win round is the only thing there is to buy.
        params={
            "products": [
                {
                    "buy_id": "hold_and_win_buy",
                    "cost_multiplier": BONUS_BUY_COST_MULTIPLIER,
                    "target_feature_id": "hold_and_win",
                },
            ],
        },
        display_order=2,
    )

    return game, config


async def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Reconcile an existing ACTIVE config to this file — symbols, paylines,
    bet ladder and feature params — so an already-seeded database (local or
    Railway) picks up edits here without a manual migration.

    Safe because this game's config is a dev seed like every other one here: a
    real deploy publishes new versions through the admin API instead."""
    _, fresh = build_game_config()

    config.num_reels = fresh.num_reels
    config.num_rows = fresh.num_rows
    config.min_bet = fresh.min_bet
    config.max_bet = fresh.max_bet
    config.bet_step = fresh.bet_step
    config.bet_steps = fresh.bet_steps
    config.notes = fresh.notes

    fresh_paylines = {p.index: p for p in fresh.paylines}
    for payline in list(config.paylines):
        f = fresh_paylines.get(payline.index)
        if f is None:
            config.paylines.remove(payline)
        else:
            payline.positions = f.positions
    existing_indices = {p.index for p in config.paylines}
    for index, f in fresh_paylines.items():
        if index not in existing_indices:
            config.paylines.append(Payline(index=index, positions=f.positions))

    fresh_symbols = {s.code: s for s in fresh.symbols}
    for symbol in list(config.symbols):
        f = fresh_symbols.pop(symbol.code, None)
        if f is None:
            continue
        symbol.name = f.name
        symbol.symbol_type = f.symbol_type
        symbol.reel_weights = f.reel_weights
        symbol.paytable = f.paytable
        symbol.max_per_reel = f.max_per_reel
        symbol.tier = f.tier
        symbol.display_order = f.display_order
    for f in fresh_symbols.values():
        db.add(
            Symbol(
                game_config=config, code=f.code, name=f.name, symbol_type=f.symbol_type,
                tier=f.tier, reel_weights=f.reel_weights, paytable=f.paytable,
                max_per_reel=f.max_per_reel, display_order=f.display_order,
            )
        )

    fresh_features = {fc.feature_type: fc for fc in fresh.feature_configs}
    for feature_config in config.feature_configs:
        f = fresh_features.pop(feature_config.feature_type, None)
        if f is None:
            continue
        feature_config.enabled = f.enabled
        feature_config.params = f.params
        feature_config.display_order = f.display_order
    for f in fresh_features.values():
        # game_config=config alone doesn't cascade a new row into the session
        # here (config was loaded via selectinload, not freshly constructed) —
        # db.add() explicitly, or it silently never persists.
        db.add(
            FeatureConfig(
                game_config=config, feature_type=f.feature_type,
                enabled=f.enabled, params=f.params, display_order=f.display_order,
            )
        )


async def get_or_seed_active_config(db: AsyncSession) -> GameConfig:
    """Idempotent: return the active config for this game, creating the game +
    seed config on first call (dev/test convenience — a real deploy manages
    configs through the admin API)."""
    existing = await db.execute(
        select(GameConfig)
        .join(Game)
        .where(Game.code == GAME_CODE, GameConfig.status == GameConfigStatus.ACTIVE.value)
        .options(
            selectinload(GameConfig.symbols),
            selectinload(GameConfig.paylines),
            selectinload(GameConfig.feature_configs),
            selectinload(GameConfig.game),
        )
    )
    config = existing.scalars().first()
    if config is not None:
        await _sync_from_seed(db, config)
        await db.commit()
        return config

    _, config = build_game_config()
    db.add(config)
    await db.commit()
    # expire_on_commit=False (app/core/db.py) keeps the in-memory relationship
    # collections populated during construction above — no reload needed.
    return config
