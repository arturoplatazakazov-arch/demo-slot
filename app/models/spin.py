import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONVariant, TimestampMixin, UUIDPKMixin


class SpinRecord(UUIDPKMixin, TimestampMixin, Base):
    """Append-only audit log of one spin (TZ §9, §11). Rows are never updated
    or deleted by the application; immutability is enforced at the repository
    layer in stage 5/7 (no UPDATE/DELETE statements issued against this
    table). Consider adding a DB-level trigger to make that a hard guarantee
    before going to production — open item, see end-of-stage notes.
    """

    __tablename__ = "spin_records"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    game_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("game_configs.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    bet_amount: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    is_bonus_buy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    feature_buy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 5x3 grid of symbol codes, e.g. [["H1","H1","WILD"], [...], ...] (reel-major).
    grid: Mapped[list] = mapped_column(JSONVariant, nullable=False)

    win_amount: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    # Per-mechanic breakdown, e.g. {"line_pay": .., "count_pay": .., "free_spins": ..}.
    win_breakdown: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    features_triggered: Mapped[list] = mapped_column(JSONVariant, nullable=False, default=list)

    # Raw RNG draws (per-position weighted-pick inputs/outputs) for reproducibility (TZ §10).
    rng_proof: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)

    balance_before: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    balance_after: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)

    session: Mapped["Session"] = relationship(back_populates="spins")  # noqa: F821
