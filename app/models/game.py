from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Game(UUIDPKMixin, TimestampMixin, Base):
    """A game the engine can serve. The engine supports multiple games; each
    game has its own line of versioned GameConfig rows (TZ §1, §9)."""

    __tablename__ = "games"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Catalog display fields (front/games.html) — all nullable since only a
    # published (has an ACTIVE config) game needs them; see
    # app/api/v1/catalog.py for the endpoint that reads them and
    # app/api/admin/builder.py's publish-live route for the writer.
    # catalog_play_url is the game's own play page: the 4 hand-built demo
    # games point at their bespoke HTML page, a slot-builder game points at
    # the generic front/play.html?slug=<code> player.
    catalog_badge: Mapped[str | None] = mapped_column(String(64), nullable=True)
    catalog_description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    catalog_cover_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    catalog_play_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    configs: Mapped[list["GameConfig"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship(back_populates="game", cascade="all, delete-orphan")
