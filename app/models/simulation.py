import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONVariant, TimestampMixin, UUIDPKMixin
from app.models.enums import SimulationStatus


class SimulationRun(UUIDPKMixin, TimestampMixin, Base):
    """One RTP-simulator execution against a specific config version
    (TZ §7, §9) — used both for pre-publish validation and for regression
    testing against a stored baseline."""

    __tablename__ = "simulation_runs"

    game_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("game_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    num_spins: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SimulationStatus.PENDING.value)

    # Run inputs, e.g. {"rng_seed": .., "bonus_buy_only": false}.
    params: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    # Report output, e.g. {"rtp": .., "hit_frequency": .., "rtp_by_mechanic": {...},
    # "win_histogram": [...], "max_win_multiplier": .., "volatility_index": ..,
    # "bonus_buy_rtp": ..}. Populated once status == COMPLETED.
    results: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    game_config: Mapped["GameConfig"] = relationship()  # noqa: F821
