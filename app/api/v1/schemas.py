import uuid

from pydantic import BaseModel, Field

# All monetary fields are plain integers on the wire (confirmed: bet amounts
# and payout multipliers are always whole numbers, so there's never a
# fractional credit to represent — no float/Decimal ambiguity in the JSON).


class BetConfig(BaseModel):
    min: int
    max: int
    step: int
    default: int
    steps: list[int]


class PaytableSymbolOut(BaseModel):
    """Display-only paytable info for the player-facing info popup — not
    used for any gameplay math client-side (the server is authoritative for
    every payout). Mirrors Symbol.paytable's own shape (match-count string
    -> multiplier)."""

    code: str
    name: str
    symbol_type: str
    paytable: dict[str, float]


class FreeSpinsTriggerOut(BaseModel):
    """Display-only free-spins trigger info — lets the client compute
    "anticipation" (suspense on remaining reels once landed scatters are one
    short of triggering) without hardcoding the trigger symbol/count, which
    are admin-configurable (FeatureConfig.params). Not gameplay math: the
    server still decides the actual trigger, this is purely cosmetic."""

    trigger_symbol_code: str
    trigger_count: int


class HoldAndWinTriggerOut(BaseModel):
    """Mirrors FreeSpinsTriggerOut — display-only trigger info for the
    collector-tiger count, so the client can compute anticipation the same
    way it already does for the scatter/free-spins trigger."""

    trigger_symbol_code: str
    trigger_count: int


class SessionStartRequest(BaseModel):
    game_id: str


class SessionStartResponse(BaseModel):
    session_id: uuid.UUID
    balance: int
    currency: str
    bet: BetConfig
    symbols: list[PaytableSymbolOut]
    free_spins_trigger: FreeSpinsTriggerOut | None = None
    hold_and_win_trigger: HoldAndWinTriggerOut | None = None


class ActiveFeatureState(BaseModel):
    type: str
    spins_remaining: int
    total_win: int


class SessionStateResponse(BaseModel):
    session_id: uuid.UUID
    balance: int
    currency: str
    active_feature: ActiveFeatureState | None = None


class SpinRequest(BaseModel):
    session_id: uuid.UUID
    bet_amount: int = Field(gt=0)


class FeatureBuyRequest(BaseModel):
    session_id: uuid.UUID
    feature_id: str
    bet_amount: int = Field(gt=0)


class WinningCellOut(BaseModel):
    row: int
    col: int
    symbol: str


class CellPosOut(BaseModel):
    row: int
    col: int


class LineWinOut(BaseModel):
    payline: int
    symbol: str
    count: int
    amount: int
    positions: list[CellPosOut]


class CountWinOut(BaseModel):
    symbol: str
    count: int
    amount: int
    positions: list[CellPosOut]


class FeatureOut(BaseModel):
    type: str
    triggered: bool
    spins_awarded: int | None = None
    spins_remaining: int
    total_win: int
    # party-of-goods only: the session-wide multiplier accumulator (multiplier
    # tokens landed during this free-spins round carry over and compound
    # across every remaining spin — see spin_avalanche.py's
    # run_avalanche_spin). None for every other game/feature type.
    multiplier: int | None = None


class PopupOut(BaseModel):
    type: str
    amount: int


class WildEventOut(BaseModel):
    reel: int
    event: str  # "expanded" | "walked" | "expired"


class MultiplierWildOut(BaseModel):
    """A wild and the multiplier it rolled this spin (app/features/
    multiplier_wild.py). `multiplier` is 1 when it stayed a plain WILD — the
    client still needs that case, it picks the Spine skin from this value."""

    row: int
    col: int
    multiplier: int


class CoinMultiplierPositionOut(BaseModel):
    row: int
    col: int
    value: int


class CoinMultiplierOut(BaseModel):
    multiplier_sum: int
    positions: list[CoinMultiplierPositionOut]
    # Whether this multiplier actually boosted the payout this spin (collector
    # symbol present + a line win) vs. positions/values just being shown on
    # the coins with no payout effect yet — see coin_multiplier.py.
    applied: bool


class HoldAndWinLandedCoinOut(BaseModel):
    row: int
    col: int
    value: int


class HoldAndWinRespinOut(BaseModel):
    """One entry per respin actually run (see hold_and_win.py — the counter
    resets on a new landing, so this can be longer than the configured
    respin_count) — lets the client replay the round respin-by-respin with
    its own pacing/pauses even though the whole thing resolved server-side
    in one call."""

    landed: list[HoldAndWinLandedCoinOut]


class HoldAndWinOut(BaseModel):
    triggered: bool
    respins: list[HoldAndWinRespinOut]
    total_win: int
    full_grid: bool


class WheelSegmentOut(BaseModel):
    """One slot on the Wheel of Fortune drum, in drum order — the client
    renders these as the labels on the (deliberately blank) bullet art. Only
    the prize is exposed; the segment weights stay server-side so the odds
    can't be read off the wire."""

    type: str  # "multiplier" | "free_spins"
    value: int | None = None


class WheelOfFortuneOut(BaseModel):
    """Result of one wheel spin, drawn server-side (app/features/
    wheel_of_fortune.py). The client animates the drum to `segment_index` and
    reveals what's already decided here — it never picks the prize.

    `win_amount` is 0 for a free-spins outcome: there the prize is the round
    itself, and `feature` carries the awarded spins as usual."""

    segment_index: int
    prize_type: str  # "multiplier" | "free_spins"
    multiplier: int | None = None
    win_amount: int = 0
    segments: list[WheelSegmentOut]


class TokenConsumedOut(BaseModel):
    """One multiplier token (party-of-goods' x2/x3/x5/x7) swept up this
    cascade step — was on the grid, contributed `value` into
    step_multiplier, and got removed alongside the winning positions (see
    app/engine/avalanche.py:TokenConsumption)."""

    row: int
    col: int
    value: int


class BombDetonationOut(BaseModel):
    """One "boom" symbol detonating this cascade step (see
    app/engine/avalanche.py:BombDetonation) — fires regardless of any win,
    pays nothing itself. `cleared` is every cell it removed: its own
    position plus its full row and column."""

    row: int
    col: int
    cleared: list[CellPosOut]


class CascadeStepOut(BaseModel):
    """One avalanche cascade (app/engine/avalanche.py:CascadeStep): the tier
    wins found before this step's removal, the multiplier this step's
    position in the round's trail applied (plus any multiplier tokens
    consumed, see `tokens_consumed`), and the grid after removing those
    wins/tokens/bomb-cleared cells and refilling — what the client animates
    toward next."""

    wins: list[CountWinOut]
    step_multiplier: int
    step_win: int  # already multiplier-applied
    grid_after: list[list[str]]
    tokens_consumed: list[TokenConsumedOut] = []
    bombs_detonated: list[BombDetonationOut] = []


class AvalancheOut(BaseModel):
    steps: list[CascadeStepOut]
    total_win: int


class SpinResponse(BaseModel):
    # For an avalanche game (`avalanche` set below) this is the INITIAL,
    # pre-cascade grid — the client animates forward through
    # `avalanche.steps` from there instead of reading `line_wins`/
    # `count_wins`/`winning_cells`, which stay empty for this mechanic.
    grid: list[list[str]]
    winning_cells: list[WinningCellOut]
    line_wins: list[LineWinOut]
    count_wins: list[CountWinOut]
    total_win: int
    balance: int
    feature: FeatureOut | None = None
    popup: PopupOut | None = None
    wild_events: list[WildEventOut] = []
    coin_multiplier: CoinMultiplierOut | None = None
    # One entry per WILD on the grid, whatever it rolled — including the ones
    # that stayed a plain wild (multiplier 1). Empty when the game has no
    # multiplier_wild feature or no wild landed.
    multiplier_wilds: list[MultiplierWildOut] = []
    hold_and_win: HoldAndWinOut | None = None
    wheel_of_fortune: WheelOfFortuneOut | None = None
    avalanche: AvalancheOut | None = None


class SymbolArtOut(BaseModel):
    """code + image_ref only (app/api/v1/catalog.py's list_symbol_art) — the
    generic front/play.html player's symbol-art resolver. Deliberately
    excludes weights/paytable (that's PaytableSymbolOut's job, returned as
    part of session/start) since this is purely a code->art lookup."""

    code: str
    image_ref: str | None = None


class CatalogEntryOut(BaseModel):
    """One playable/published game for front/games.html's catalog listing
    (app/api/v1/catalog.py) — only games with an ACTIVE GameConfig show up."""

    code: str
    name: str
    catalog_badge: str | None = None
    catalog_description: str | None = None
    catalog_cover_path: str | None = None
    catalog_play_url: str | None = None
