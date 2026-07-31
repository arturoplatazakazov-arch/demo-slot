import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SymbolOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    symbol_type: str
    reel_weights: list[int]
    paytable: dict[str, float]
    max_per_reel: int | None
    tier: str
    image_ref: str | None = None


class ConfigSummaryOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    version: int
    status: str
    target_rtp: float
    notes: str | None = None
    created_at: datetime


class ConfigDetailOut(ConfigSummaryOut):
    num_reels: int
    num_rows: int
    symbols: list[SymbolOut]


class SymbolUpdateIn(BaseModel):
    id: uuid.UUID
    reel_weights: list[int]
    paytable: dict[str, float]
    max_per_reel: int | None = None
    image_ref: str | None = None


class UpdateSymbolsRequest(BaseModel):
    symbols: list[SymbolUpdateIn]


class SimulateRequest(BaseModel):
    # 100k is the recommended default (a few seconds on a fast in-process
    # RNG) — see app/simulator. Capped well above that so an admin can push
    # for a tighter confidence interval without accidentally DoS-ing the
    # request with an unbounded number.
    num_spins: int = Field(default=100_000, gt=0, le=5_000_000)
    bet_amount: int | None = Field(default=None, gt=0)
    seed: int | None = None


class SimulationReportOut(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    num_spins: int
    total_wagered: str
    total_win: str
    rtp: float
    hit_frequency: float
    bonus_frequency: float
    volatility_stddev: float
    volatility_label: str
    max_win_multiplier: float
    rtp_by_mechanic: dict[str, float]
    win_histogram: list[dict]
    target_rtp: float
    created_at: datetime


class PublishResponse(BaseModel):
    config_id: uuid.UUID
    status: str
    archived_config_id: uuid.UUID | None = None
