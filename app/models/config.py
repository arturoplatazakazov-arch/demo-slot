import uuid

from sqlalchemy import ForeignKey, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONVariant, TimestampMixin, UUIDPKMixin
from app.models.enums import GameConfigStatus, SymbolType


class GameConfig(UUIDPKMixin, TimestampMixin, Base):
    """A versioned snapshot of a game's math (TZ §5, §9). Immutable once ACTIVE
    or ARCHIVED — publishing a change means creating a new version, never
    editing an existing one, so a SpinRecord can always point at the exact
    config that produced it (TZ §11 audit requirement)."""

    __tablename__ = "game_configs"
    __table_args__ = (UniqueConstraint("game_id", "version", name="uq_game_config_version"),)

    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=GameConfigStatus.DRAFT.value
    )

    num_reels: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)
    num_rows: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)

    # Target RTP as a fraction (0.96 == 96%), the ceiling the simulator checks against (TZ §7).
    target_rtp: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)

    # Bet amounts are internal credit units, not tied to a currency (TZ §13);
    # currency is a display label on Session only. Confirm if this is sufficient.
    min_bet: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    max_bet: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    bet_step: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    # Explicit stepped bet amounts for clients with a fixed picker UI (not a
    # uniform min/max/step arithmetic sequence). Falls back to generating
    # from min/max/step when unset (stage 5 addition — the front's bet
    # stepper ships a hardcoded, non-arithmetic list that must be echoed
    # verbatim rather than reconstructed).
    bet_steps: Mapped[list[float] | None] = mapped_column(JSONVariant, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    game: Mapped["Game"] = relationship(back_populates="configs")  # noqa: F821
    symbols: Mapped[list["Symbol"]] = relationship(
        back_populates="game_config", cascade="all, delete-orphan", order_by="Symbol.display_order"
    )
    paylines: Mapped[list["Payline"]] = relationship(
        back_populates="game_config", cascade="all, delete-orphan", order_by="Payline.index"
    )
    feature_configs: Mapped[list["FeatureConfig"]] = relationship(
        back_populates="game_config", cascade="all, delete-orphan", order_by="FeatureConfig.display_order"
    )


class Symbol(UUIDPKMixin, Base):
    """One symbol definition for a given config version (TZ §5, §9).

    reel_weights: list[int] of length num_reels — RNG weight of this symbol on
    each reel independently (TZ §4.1). A weight of 0 means "never on this reel".

    paytable: dict mapping match-count ("3"/"4"/"5") to a payout multiplier.
    For line-pay symbols (regular/wild) the multiplier applies to the bet
    staked *per line*; for count-pay symbols (scatter/bonus) it applies to
    the *total* bet (TZ §4.2). Stored as JSON floats for editability from the
    admin UI; convert via Decimal(str(x)) at spin-evaluation time to avoid
    binary-float drift in money math — never do float arithmetic on payouts.
    """

    __tablename__ = "symbols"
    __table_args__ = (UniqueConstraint("game_config_id", "code", name="uq_symbol_code_per_config"),)

    game_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("game_configs.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol_type: Mapped[str] = mapped_column(String(16), nullable=False, default=SymbolType.REGULAR.value)
    wild_subtype: Mapped[str | None] = mapped_column(String(16), nullable=True)

    reel_weights: Mapped[list[int]] = mapped_column(JSONVariant, nullable=False)
    paytable: Mapped[dict[str, float]] = mapped_column(JSONVariant, nullable=False, default=dict)

    # Admin-configurable cap: at most this many of this symbol per reel
    # (post-draw redraw, see app/services/scatter_cap.py:cap_symbol_per_reel).
    # None/unset means no cap. Generic per-symbol replacement for what used
    # to be a scatter-only rule piggybacked on free_spins FeatureConfig params.
    max_per_reel: Mapped[int | None] = mapped_column(nullable=True)

    # Set only for avalanche "multiplier token" symbols (party-of-goods'
    # x2/x3/x5/x7) — see app/engine/avalanche.py: never count-pays on its
    # own (paytable stays empty), instead sums into the cascade step's
    # multiplier whenever a win occurs while it's on the grid. None for
    # every other symbol/game.
    multiplier_value: Mapped[int | None] = mapped_column(nullable=True)

    # Set only for the avalanche "bomb" symbol (party-of-goods' "boom") —
    # see app/engine/avalanche.py: detonates on every cascade step where
    # it's present on the grid, regardless of whether anything else won
    # that step, clearing its own cell plus its entire row and column (no
    # payout of its own — see app/engine/types.py:BombDetonation). False
    # for every other symbol/game.
    is_bomb: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Presentation/win-tier classification ("low"/"high") — drives which
    # line wins qualify for a big/mega/epic win popup (stage 5 addition,
    # product hasn't formalized this beyond "cheap" vs "premium" symbols).
    # Purely cosmetic: never read by app/engine or app/features.
    tier: Mapped[str] = mapped_column(String(16), nullable=False, default="low")

    # A slot-builder asset id (app/api/admin/builder.py's manifest
    # assets.images[].id, category "symbol") — resolved to an actual image
    # file only by the frontend player via that manifest. None for the 4
    # hand-built demo games (their art is wired directly in front/js/slot.js)
    # and for any builder-generated symbol beyond however many symbol images
    # were actually uploaded. Never read by app/engine or app/features.
    image_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    game_config: Mapped["GameConfig"] = relationship(back_populates="symbols")


class Payline(UUIDPKMixin, Base):
    """One active payline for a config version (TZ §4.2, §5, §9).

    positions: list[int] of length num_reels, each value the row index (0-based,
    top to bottom) the line passes through on that reel.
    """

    __tablename__ = "paylines"
    __table_args__ = (UniqueConstraint("game_config_id", "index", name="uq_payline_index_per_config"),)

    game_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("game_configs.id", ondelete="CASCADE"), nullable=False
    )
    index: Mapped[int] = mapped_column(nullable=False)
    positions: Mapped[list[int]] = mapped_column(JSONVariant, nullable=False)

    game_config: Mapped["GameConfig"] = relationship(back_populates="paylines")


class FeatureConfig(UUIDPKMixin, Base):
    """Enable/configure one bonus module for a config version (TZ §6.1, §9).
    The engine's feature registry (stage 4) reads these rows to know which
    BonusFeature implementations are active for a spin — no hardcoded list
    in the core engine."""

    __tablename__ = "feature_configs"
    __table_args__ = (
        UniqueConstraint("game_config_id", "feature_type", name="uq_feature_type_per_config"),
    )

    game_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("game_configs.id", ondelete="CASCADE"), nullable=False
    )
    feature_type: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    # Validated at the application layer against the feature module's
    # get_config_schema() (TZ §6.1) — not enforced at the DB level.
    params: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    game_config: Mapped["GameConfig"] = relationship(back_populates="feature_configs")


__all__ = ["GameConfig", "Symbol", "Payline", "FeatureConfig"]
