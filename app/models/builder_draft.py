import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONVariant, UUIDPKMixin


class BuilderDraft(UUIDPKMixin, Base):
    """The slot-builder wizard's per-game state (app/api/admin/builder.py):
    assets, grid/mechanics, layout — everything Stages 1-5 accumulate before
    a real `GameConfig` exists. One row per `Game`, keyed by `game_id`.

    Lives in the DB rather than as a `front/builder/<slug>.spec.json` file
    (the wizard's original storage) so a read-modify-write from one admin
    request can't race another's on the same file, and so the manifest can
    never end up orphaned from its `Game` row by a crash between the two
    writes. The actual uploaded media (images/sounds) still lives on disk
    under front/img|sound/<slug>/ — only this bookkeeping JSON moved.
    """

    __tablename__ = "builder_drafts"

    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    manifest: Mapped[dict] = mapped_column(JSONVariant, nullable=False)


__all__ = ["BuilderDraft"]
