import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.models.base import Base, JSONVariant, TimestampMixin, UUIDPKMixin, utcnow


class Session(UUIDPKMixin, TimestampMixin, Base):
    """A player's (or anonymous) play session: balance + running feature state
    (TZ §9). `state` holds things like "free spins remaining" / an in-progress
    hold-and-win grid between requests."""

    __tablename__ = "sessions"

    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default=lambda: get_settings().default_currency
    )
    state: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    game: Mapped["Game"] = relationship(back_populates="sessions")  # noqa: F821
    spins: Mapped[list["SpinRecord"]] = relationship(back_populates="session")  # noqa: F821
