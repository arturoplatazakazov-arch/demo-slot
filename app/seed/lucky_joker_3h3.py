"""Seed data for the "lucky-joker-3h3" game (front/lucky-joker-3h3.html).

Third game assembled in the slot-builder wizard (after dirty-money-mafia and
multi-fruits-story): its BuilderDraft manifest holds the layout the frontend
is built from (see css/lucky-joker-3h3.css) and its `mechanics` list —
line_pay, scatter, free_spins, hold_and_win — is what this file implements.
The wizard also published an ACTIVE v1 config of its own, but that config is
the wizard's generic placeholder: anonymous symbol codes (low_a..high_b) that
match no delivered art folder. This module is the hand-written math that
replaces it, keyed to the art actually uploaded
(front/img/lucky-joker-3h3/<code>/) — see `_sync_from_seed` for how the
existing rows get reconciled rather than a second config version published.

It is also the second hand-built 3x3 game after app/seed/multi_fruits_story.py,
and the first one to pair a classic fruit-machine base game with Hold & Win: the
delivered art (front/img/lucky-joker-3h3/) ships a joker COIN plus four
jackpot coins (mini/minor/major/grand) and the matching MINI x25 / MINOR x50
/ MAJOR x150 / GRAND x1000 ladder plates, so the jackpot multipliers below
are NOT free parameters — they're baked into the PNGs.

Symbol codes are a fixed contract with front/js/lucky-joker-3h3/slot.js's
SYMBOL_FOLDERS (each code == its asset folder name) — do not rename them.

Mechanics (product, matched against the reference 3x3 Hold'n Win):
- line_pay over 5 paylines (3 rows + the two diagonals — everything a 3x3
  grid has room for), scatter count win, free_spins, bonus_buy;
- COIN is a base-game symbol on all three reels, each one carrying its own
  multiplier (x1..x15 plus the four jackpot tiers). It pays nothing by itself:
  coin_multiplier multiplies a WINNING LINE by the sum of every coin's
  multiplier, with no collector needed on the grid
  (requires_collector=False — there is no collector symbol on the base reels
  at all, it exists only inside the round);
- a COLLECTOR on the middle reel (it appears nowhere else — see its per-reel
  weights) together with a coin on each of the outer two opens Hold & Win
  (trigger_mode="collector_and_coins"), run in the feature's `collector` mode:
  the grid opens empty except that collector, standing where it landed; from
  then on the middle reel only takes collectors and the outer two only take
  coins, and EVERY collector is worth the sum of all coin multipliers (two
  collectors pay that sum twice, three pay it three times). 3 respins, reset
  by any new landing.

3 reels x 3 rows means a payline is either a 3-of-a-kind or nothing, so the
paytable has a single "3" entry per symbol — see the RTP note on _PAYS.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SymbolType

GAME_CODE = "lucky-joker-3h3"
GAME_NAME = "Lucky Joker"
CATALOG_BADGE = "Hold & Win"
CATALOG_DESCRIPTION = "Классические фрукты, джокер-скаттер и четыре джекпота в Hold'n'Win."
CATALOG_COVER_PATH = "img/lucky-joker-3h3/logo_catalog.jpg"
CATALOG_PLAY_URL = "lucky-joker-3h3.html"

NUM_REELS = 3
NUM_ROWS = 3

# 5 lines: the three rows plus both diagonals. A 3x3 grid has no room for the
# zig-zag sets the 5-reel games use, and the layout draws no win-line art.
# row index: 0=top, 1=mid, 2=bottom.
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

# The jackpot ladder, name -> bet multiplier. Fixed by the delivered plate art
# (front/img/lucky-joker-3h3/jackpot_*.png read MINI x25, MINOR x50,
# MAJOR x150, GRAND x1000) — change the art before changing these.
JACKPOT_VALUES = {"mini": 25, "minor": 50, "major": 150, "grand": 1000}

# Payouts are per LINE (multiplied by bet/5), and only a full 3-of-a-kind
# pays — a 3-reel line is all-or-nothing.
#
# This table is deliberately LOW for a 3x3: coin_multiplier amplifies it. A
# coin rides along on ~5.5% of spins and multiplies the whole line pay by the
# sum of the coins' own multipliers (~2.7 each on average), i.e. line pay is
# worth roughly 1.8x what this table says by the time it reaches the player.
# Tuning the table without re-measuring that amplification is how this game
# ended up at RTP 2.9 on the first pass.
#
# Measured over 300k spins per seed (7 / 21 / 42 / 99):
#   line pay + scatter + free spins   0.351 - 0.360
#   coin multiplier on winning lines  0.234 - 0.262   (applies on 5.1% of spins)
#   Hold & Win (collector round)      0.310 - 0.388   (1 spin in ~141)
#   TOTAL RTP           0.931 / 0.934 / 0.987 / 0.944  -> mean ~0.949
# Hit frequency 14.7%, free-spins trigger 0.085%, average round ~48x the bet,
# biggest observed round ~3030x. The spread between seeds is the GRAND coin
# (x1000): a run either catches a few or doesn't.
#
# NB: scripts/simulate.py only covers line pay + scatter + free spins — it
# knows nothing about the two coin mechanics, so its RTP number is the 0.358
# part alone. The figures above came from running app/features/
# coin_multiplier.py and hold_and_win.py over real drawn grids alongside it;
# do the same after touching any weight or payout.
_PAYS = {
    "cherry": {"3": 5.3},
    "lemon": {"3": 6.3},
    "plum": {"3": 8.7},
    "watermelon": {"3": 11.5},
    "bar": {"3": 21.0},
    "bell": {"3": 35.0},
    "777": {"3": 110.0},
    # Wild pays on its own when a line comes up wild-only (app/engine/wins.py).
    "wild": {"3": 178.0},
    # Scatter is a COUNT win: 3 anywhere on the grid pays 3x the whole bet AND
    # opens the free-spins round. Count pay is NOT multiplied by the coins
    # (coin_multiplier only touches line pay), so it doesn't share in the
    # ~3.4x amplification the line table was tuned down for.
    "scatter": {"3": 3.0},
    # COIN never pays a cent through the standard engine
    # (evaluate_line_wins/evaluate_count_wins both skip a symbol with no
    # matching pays entry) — it earns its keep through coin_multiplier (it
    # multiplies a winning line) and hold_and_win (it opens and fills the
    # round), both of which scan for it by code.
    "coin": {},
    # COLLECTOR — same deal, and it only ever appears on the middle reel (see
    # its reel_weights). It opens the round and then collects inside it.
    "collector": {},
}

# code -> (display name, symbol type, tier, weight, max_per_reel). `weight` is
# either one number used on every reel, or one per reel — which is how the
# COLLECTOR is pinned to the middle reel and nowhere else ([0, w, 0]).
# Four fruits are the low tier, bar/bell/777 the high one — the classic
# fruit-machine ladder, and the order the art reads in.
_SYMBOLS: list[tuple[str, str, str, str, int | list[int], int | None]] = [
    ("cherry", "Вишня", SymbolType.REGULAR.value, "low", 22, None),
    ("lemon", "Лимон", SymbolType.REGULAR.value, "low", 20, None),
    ("plum", "Слива", SymbolType.REGULAR.value, "low", 18, None),
    ("watermelon", "Арбуз", SymbolType.REGULAR.value, "low", 16, None),
    ("bar", "BAR", SymbolType.REGULAR.value, "high", 12, None),
    ("bell", "Колокольчик", SymbolType.REGULAR.value, "high", 9, None),
    ("777", "777", SymbolType.REGULAR.value, "high", 5, None),
    ("wild", "Wild", SymbolType.WILD.value, "high", 4, None),
    # Capped at 1 per reel: the round needs 3 scatters across 3 reels, and
    # letting two stack on one reel would make the trigger far spikier than
    # the weight suggests (same convention as the other games).
    ("scatter", "Scatter", SymbolType.SCATTER.value, "low", 4, 1),
    # Coin. Not capped per reel: two coins in one column are a perfectly good
    # outcome (they both multiply the line). The round needs one on each of
    # the OUTER reels, so its weight sets P(coin in a column) = 1-(1-p)^3 and
    # the trigger rate goes as that squared, times the collector below.
    ("coin", "Монета", SymbolType.BONUS.value, "high", 8, None),
    # Collector — ONLY on the middle reel (product: "на средней линии"), hence
    # the per-reel weights. Capped at 1: a second one on the triggering grid
    # would have nowhere to go, the round starts from exactly one.
    ("collector", "Коллектор", SymbolType.BONUS.value, "high", [0, 9, 0], 1),
]


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
            "+ Hold & Win ~0.32), hit frequency 15.6%, Hold & Win 1 in ~148 spins. "
            "See the note on _PAYS."
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
        feature_type=FeatureType.FREE_SPINS.value,
        enabled=True,
        params={
            "trigger_symbol_code": "scatter",
            "trigger_count": 3,
            # 3 reels x max 1 scatter per reel means 3 is also the maximum, so
            # the by-count table has exactly one entry and `spins_awarded` is
            # the fallback that can never be reached.
            "spins_awarded": 10,
            "spins_awarded_by_count": {"3": 10},
            "retrigger_enabled": True,
            # A 3x3 base game pays rarely; doubling wins is what makes the
            # round feel different from just "10 more spins" (same call as
            # multi-fruits-story, the other 3x3 game).
            "win_multiplier": 2,
        },
        display_order=0,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.BONUS_BUY.value,
        enabled=True,
        # `products` list shape (not the flat single-product one) — the buy_id
        # is what front/js/lucky-joker-3h3/app.js posts. Only free spins are
        # for sale: the delivered button art reads "BUY FREE SPINS".
        #
        # 20x the bet, not the 100x the 5-reel games carry: the purchase buys
        # 10 free spins paying double, i.e. ~10 * 2 * base RTP back on
        # average, so 100x would sell a ~0.2-RTP product. Same reasoning (and
        # price) as multi-fruits-story.
        params={
            "products": [
                {"buy_id": "free_spins_buy", "cost_multiplier": 20, "target_feature_id": "free_spins"},
            ],
        },
        display_order=1,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.COIN_MULTIPLIER.value,
        enabled=True,
        params={
            "coin_symbol_code": "coin",
            # No collector on the base reels — a coin multiplies a winning line
            # on its own (product). The code is still named so the feature has
            # something to report; nothing on the grid ever matches it.
            "collector_symbol_code": "collector",
            "requires_collector": False,
            # Base-game coin faces. Jackpot tiers can land here too (product:
            # "может, если выпадает линия и какая-то монета включая джекпоты"),
            # but they have to stay RARE — a GRAND coin multiplies the line by
            # 1000, so its weight drives the tail of the whole game.
            # Weighted against a big denominator so the jackpot tiers can be
            # genuinely rare: GRAND is 2 in 9168 draws per coin, and it alone
            # would otherwise carry a fifth of the average multiplier.
            # Average multiplier per coin at these weights: ~2.7.
            "value_weights": {
                "1": 4600, "2": 2400, "3": 1200, "5": 600, "10": 200, "15": 80,
                "mini": 60, "minor": 20, "major": 6, "grand": 2,
            },
            "jackpot_values": JACKPOT_VALUES,
        },
        display_order=2,
    )
    FeatureConfig(
        game_config=config,
        feature_type=FeatureType.HOLD_AND_WIN.value,
        enabled=True,
        params={
            "trigger_symbol_code": "coin",
            # A COLLECTOR on the middle reel plus a coin on each of the outer
            # two (product) — the collector is what opens the round, the coins
            # are what it will collect.
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
        display_order=3,
    )

    return game, config


async def _sync_catalog_fields(db: AsyncSession, game: Game) -> None:
    """The builder's publish-live route already filled this game's catalog
    fields in (unlike the hand-built games, which start out NULL), so
    app/seed/__init__.py's backfill — which bails as soon as catalog_badge is
    set — would never correct catalog_play_url from the generic
    "play.html?slug=..." player to this game's own page, nor the badge the
    wizard defaulted to the game's own name. Force-write instead. The name
    goes with them: the wizard's is "Lucky Joker 3х3", with a Cyrillic х in
    the middle of Latin text."""
    if (
        game.name == GAME_NAME
        and game.catalog_play_url == CATALOG_PLAY_URL
        and game.catalog_badge == CATALOG_BADGE
        and game.catalog_cover_path == CATALOG_COVER_PATH
    ):
        return
    game.name = GAME_NAME
    game.catalog_badge = CATALOG_BADGE
    game.catalog_description = CATALOG_DESCRIPTION
    game.catalog_cover_path = CATALOG_COVER_PATH
    game.catalog_play_url = CATALOG_PLAY_URL


async def _sync_from_seed(db: AsyncSession, config: GameConfig) -> None:
    """Reconcile an existing ACTIVE config to this file.

    Same strictness as app/seed/multi_fruits_story.py's namesake and for the
    same reason: the config this one lands on was generated by the slot-builder
    wizard with an entirely different symbol set (low_a..high_b), so matching
    by code alone would leave the placeholder symbols in the reel strips and
    the game would keep dealing codes the frontend has no art for. Symbols and
    paylines are made to match exactly (insert + update + delete); feature
    configs are updated/inserted (no deletes — nothing to remove).

    Safe because this game's config is a dev seed like every other one here: a
    real deploy publishes new versions through the admin API instead."""
    _, fresh = build_game_config()

    config.num_reels = fresh.num_reels
    config.num_rows = fresh.num_rows
    config.min_bet = fresh.min_bet
    config.max_bet = fresh.max_bet
    config.bet_step = fresh.bet_step
    config.bet_steps = fresh.bet_steps

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
            # A wizard placeholder (low_a..high_b): drop it, or the reels keep
            # dealing codes no art folder answers to.
            await db.execute(delete(Symbol).where(Symbol.id == symbol.id))
            config.symbols.remove(symbol)
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
        await _sync_catalog_fields(db, config.game)
        await db.commit()
        return config

    _, config = build_game_config()
    db.add(config)
    await db.commit()
    # expire_on_commit=False (app/core/db.py) keeps the in-memory relationship
    # collections populated during construction above — no reload needed.
    return config
