"""Request/response schemas and tagging enums for the slot-builder wizard
(app/api/admin/builder.py)."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

# line_pay/scatter are the two core win mechanics (TZ §4.2); the rest match
# app/features/registry.py's feature_id values 1:1 so a Stage 3 selection
# can later become FeatureConfig rows without renaming anything.
ALLOWED_MECHANICS = {
    "line_pay", "scatter", "expanding_wild", "free_spins",
    "hold_and_win", "bonus_buy", "gamble", "jackpot", "coin_multiplier", "avalanche",
}


class BuilderCreateGameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class BuilderGameOut(BaseModel):
    game_id: uuid.UUID
    slug: str
    name: str
    stage_completed: int
    created_at: datetime
    updated_at: datetime


class AssetKind(str, Enum):
    image = "image"
    sound = "sound"


class AssetCategory(str, Enum):
    background = "background"
    symbol = "symbol"
    ui = "ui"
    hero = "hero"
    logo = "logo"
    frame = "frame"
    reel_background = "reel_background"
    hud = "hud"
    catalog = "catalog"


class AssetScreen(str, Enum):
    base = "base"
    bonus = "bonus"


class AssetScreenTag(str, Enum):
    """Same two screens as AssetScreen, plus "both" for materials shared
    across base and bonus (mirrors AssetDevice.both) — this is why files
    were getting re-uploaded/duplicated: sharing one asset across screens
    had no tag for it, so the only way was uploading it a second time.
    Used only for tagging/uploading an asset; picking which screen's canvas
    to edit (LayoutObjectsRequest/LayoutBackgroundRequest) stays
    AssetScreen-only, same split as LayoutDevice vs AssetDevice."""

    base = "base"
    bonus = "bonus"
    both = "both"


class AssetDevice(str, Enum):
    desktop = "desktop"
    mobile = "mobile"
    both = "both"


class BuilderStageRequest(BaseModel):
    stage: int = Field(ge=1, le=5)


class AssetTagRequest(BaseModel):
    category: AssetCategory
    screen: AssetScreenTag
    device: AssetDevice


class BuilderGridRequest(BaseModel):
    reels: int = Field(ge=1, le=10)
    rows: int = Field(ge=1, le=10)
    mechanics: list[str] = Field(default_factory=list)

    @field_validator("mechanics")
    @classmethod
    def _known_mechanics_only(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - ALLOWED_MECHANICS)
        if unknown:
            raise ValueError(f"unknown mechanics: {unknown}")
        return value


class LayoutDevice(str, Enum):
    desktop = "desktop"
    mobile = "mobile"


class LayoutObjectType(str, Enum):
    reel_block = "system.reel_block"
    button = "system.button"
    hero = "decor.hero"
    frame = "decor.frame"
    reel_background = "decor.reel_background"
    hud = "decor.hud"
    image = "decor.image"
    spine = "decor.spine"


class LayoutObjectIn(BaseModel):
    """x/y is always the object's CENTER point (a uniform convention, not a
    per-object anchor choice — simpler than the anchor field floated in
    early planning, and it's what "set its centering via coordinates" (the
    double-click edit) actually means in practice). w/h is its rendered
    size (for reel_block, derived from cell_w/cell_h/gap_x/gap_y and the
    Stage 3 grid size rather than freely set). cell_w/cell_h/gap_x/gap_y
    only apply to system.reel_block — null for every other type."""

    id: str
    type: LayoutObjectType
    image_ref: str | None = None
    # animation_ref/animation_name only apply to decor.spine — an animated
    # overlay layer (e.g. ambient decoration on top of the background),
    # parallel to how LayoutBackgroundRequest lets a background be a Spine
    # animation instead of an image.
    animation_ref: str | None = None
    animation_name: str | None = Field(default=None, max_length=100)
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)
    z_index: int = 0
    cell_w: float | None = Field(default=None, gt=0)
    cell_h: float | None = Field(default=None, gt=0)
    gap_x: float | None = Field(default=None, ge=0)
    gap_y: float | None = Field(default=None, ge=0)
    # Free-form bookkeeping tag (e.g. "slot_reel_block", "slot_frame",
    # "slot_logo", "buy_bonus", "free_spins_counter", "multiplier") the
    # Stage 4 wizard uses to tell which objects belong to which guided step
    # and which ones to mirror between base/bonus — not validated against an
    # enum since it's metadata, not something the engine reads.
    role: str | None = None


class LayoutObjectsRequest(BaseModel):
    device: LayoutDevice
    screen: AssetScreen
    objects: list[LayoutObjectIn]


class LayoutSkipRequest(BaseModel):
    """Marks (or unmarks) one wizard step id as "this element doesn't exist
    for this slot" — buy-bonus/free-spins-counter/multiplier may not apply
    to every game. step_id is the wizard's own free-form id (e.g.
    "buybonus-desktop"), not validated against an enum here since the set of
    steps is entirely a frontend concern (app/builder/layout.js)."""

    step_id: str = Field(min_length=1, max_length=100)
    skipped: bool = True


class LayoutBackgroundRequest(BaseModel):
    """x/y/w/h are optional: omitting them (e.g. picking a background from
    the dropdown) defaults to covering the whole screen, centered — the
    old fixed behavior. Passing them (dragging/resizing the background
    node) is what makes it a positionable object instead of forced
    full-screen.

    A background is either a static image (asset_id) or a looping Spine
    animation (animation_ref + animation_name, the skeleton's own animation
    to play) — never both, since there's only one background slot per
    screen."""

    device: LayoutDevice
    screen: AssetScreen
    asset_id: str | None = None
    animation_ref: str | None = None
    animation_name: str | None = Field(default=None, max_length=100)
    x: float | None = None
    y: float | None = None
    w: float | None = Field(default=None, gt=0)
    h: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _asset_xor_animation(self) -> "LayoutBackgroundRequest":
        if self.asset_id is not None and self.animation_ref is not None:
            raise ValueError("asset_id and animation_ref are mutually exclusive")
        return self


class PublishLiveRequest(BaseModel):
    """Stage 5's "all OK" action (app/api/admin/builder.py's publish_live
    route): catalog metadata only, since Stage 1 already captured the
    slot's identity (name/slug) — badge is the short genre chip
    (front/games.html's game-card__badge, e.g. "Hold & Win"), description
    the one-line blurb under the title."""

    badge: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=512)
