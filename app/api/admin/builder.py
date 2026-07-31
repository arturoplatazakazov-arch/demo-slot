"""Slot builder wizard routes: create a game (a DB Game row, its front/
asset folders, and a build-spec manifest that later stages append to),
upload/tag/rescan assets, set grid+mechanics, generate a playable config,
lay out screens, and test-spin the draft. The manifest storage story and
all non-HTTP helpers live in builder_manifest.py; request/response schemas
in builder_schemas.py."""

import hashlib
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import service
from app.api.admin.builder_config import run_builder_test_spin
from app.api.admin.builder_manifest import (
    FRONT_DIR,
    IMAGE_EXTENSIONS,
    SLUG_RE,
    SOUND_EXTENSIONS,
    CATALOG_FILENAME_STEMS,
    bump_stage,
    empty_manifest,
    find_by_hash,
    manifest_to_out,
    migrate_manifest,
    require_manifest,
    save_bytes,
    save_manifest,
    save_upload,
    slugify,
    unique_slug,
)
from app.api.admin.builder_schemas import (
    AssetCategory,
    AssetDevice,
    AssetKind,
    AssetScreenTag,
    AssetTagRequest,
    BuilderCreateGameRequest,
    BuilderGameOut,
    BuilderGridRequest,
    BuilderStageRequest,
    LayoutBackgroundRequest,
    LayoutObjectsRequest,
    LayoutSkipRequest,
    PublishLiveRequest,
)
from app.api.deps import get_db, get_rng
from app.engine.rng import RNGProvider
from app.models.builder_draft import BuilderDraft
from app.models.config import GameConfig
from app.models.enums import GameConfigStatus
from app.models.game import Game
from app.services.spine_assets import check_dir, find_atlas_dirs

router = APIRouter(prefix="/builder")


@router.post("/games", response_model=BuilderGameOut)
async def create_game(body: BuilderCreateGameRequest, db: AsyncSession = Depends(get_db)) -> BuilderGameOut:
    base_slug = slugify(body.name)
    slug = await unique_slug(db, base_slug)

    game = Game(code=slug, name=body.name)
    db.add(game)
    await db.flush()

    for sub in ("img", "sound", "js"):
        (FRONT_DIR / sub / slug).mkdir(parents=True, exist_ok=True)

    manifest = empty_manifest(game.id, slug, body.name)
    db.add(BuilderDraft(game_id=game.id, manifest=manifest))

    await db.commit()
    return manifest_to_out(manifest)


@router.get("/games", response_model=list[BuilderGameOut])
async def list_games(db: AsyncSession = Depends(get_db)) -> list[BuilderGameOut]:
    result = await db.execute(select(BuilderDraft))
    games = [manifest_to_out(migrate_manifest(d.manifest)) for d in result.scalars().all()]
    games.sort(key=lambda g: g.updated_at, reverse=True)
    return games


@router.get("/games/{slug}")
async def get_game(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    _, manifest = await require_manifest(db, slug)
    return manifest


@router.delete("/games/{slug}")
async def delete_game(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Drops an unfinished builder slot entirely: the Game row — its own
    `configs`/`sessions` relationships cascade="all, delete-orphan" so an ORM
    delete takes GameConfig (and, via its own delete-orphan relationships,
    Symbol/Payline/FeatureConfig) and Session with it — plus the BuilderDraft
    row (no ORM relationship wired for that one, so it's dropped explicitly)
    and the front/img|sound|js/<slug> folders. Refuses if a config version
    was ever published (ACTIVE) — that means the slot left "in development"
    and belongs to the real catalog, not this quick-delete."""
    if not SLUG_RE.match(slug):
        raise HTTPException(status_code=404, detail="not found")
    game = (await db.execute(select(Game).where(Game.code == slug))).scalars().first()
    if game is None:
        raise HTTPException(status_code=404, detail=f"builder game '{slug}' not found")

    active_config = (
        await db.execute(
            select(GameConfig.id).where(
                GameConfig.game_id == game.id, GameConfig.status == GameConfigStatus.ACTIVE.value
            )
        )
    ).scalars().first()
    if active_config is not None:
        raise HTTPException(
            status_code=409,
            detail=f"'{slug}' has a published config and is no longer a draft — can't delete it here",
        )

    await db.execute(delete(BuilderDraft).where(BuilderDraft.game_id == game.id))
    await db.delete(game)
    try:
        await db.commit()
    except IntegrityError:
        # SpinRecord.session_id/game_config_id are ondelete=RESTRICT (kept
        # for the TZ §11 audit trail) — the ACTIVE-config guard above should
        # already keep a slot with real play history out of reach, but an
        # archived-then-replaced config's old sessions could still hit this,
        # so surface it as a clean 409 instead of a raw DB error.
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"'{slug}' has real play history (spin records) — can't delete it here",
        )

    for sub in ("img", "sound", "js"):
        shutil.rmtree(FRONT_DIR / sub / slug, ignore_errors=True)

    return {"deleted": slug}


@router.post("/games/{slug}/assets")
async def upload_asset(
    slug: str,
    kind: AssetKind = Form(...),
    category: AssetCategory | None = Form(None),
    screen: AssetScreenTag | None = Form(None),
    device: AssetDevice | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Content-hash deduped: re-uploading bytes that already exist for this
    game reuses that entry instead of writing another copy under a
    -2/-3 suffixed name — that renaming-on-collision behavior is exactly
    what was piling up duplicate files (frame.png / frame-2.png / frame-3.png
    etc., byte-identical every time) whenever the same image got uploaded
    again, e.g. to make it available under a different screen tag before
    "both" (AssetScreenTag) existed."""
    draft, manifest = await require_manifest(db, slug)
    content = await file.read()
    sha256 = hashlib.sha256(content).hexdigest()

    if kind is AssetKind.image:
        if category is None:
            raise HTTPException(status_code=422, detail="image uploads require a category")
        # The catalog cover is one flat image for the games.html card, not
        # per screen/device — those fields don't apply to it.
        needs_placement = category is not AssetCategory.catalog
        if needs_placement and (screen is None or device is None):
            raise HTTPException(status_code=422, detail="image uploads require screen and device")

        # Reuse an existing same-hash entry when it's still unassigned
        # (category None — e.g. a manually-dropped file picked up by rescan,
        # not yet tagged) or already tagged with this same category. But
        # bytes that already serve a DIFFERENT category (e.g. an existing
        # logo now also wanted as the catalog cover) must still get their
        # own manifest entry sharing the file — category is the sole
        # discriminator publish-live uses to find the catalog cover, so
        # silently reusing the logo's id here would leave it tagged "logo"
        # and the catalog cover would never be found.
        existing = find_by_hash(manifest["assets"]["images"], sha256)
        reusable = existing if existing and existing.get("category") in (None, category.value) else None
        if reusable:
            asset_id = reusable["id"]
        else:
            # Reuse the already-saved file on disk when only the category
            # differs — no point writing byte-identical content twice.
            saved_name = existing["file"] if existing else save_bytes(FRONT_DIR / "img" / slug, file.filename, content)
            asset_id = uuid.uuid4().hex
            manifest["assets"]["images"].append({
                "id": asset_id, "file": saved_name,
                "category": category.value,
                "screen": screen.value if needs_placement else None,
                "device": device.value if needs_placement else None,
                "sha256": sha256,
            })
    else:
        existing = find_by_hash(manifest["assets"]["sounds"], sha256)
        if existing:
            asset_id = existing["id"]
        else:
            saved_name = save_bytes(FRONT_DIR / "sound" / slug, file.filename, content)
            asset_id = uuid.uuid4().hex
            manifest["assets"]["sounds"].append({"id": asset_id, "file": saved_name, "sha256": sha256})

    bump_stage(manifest, 2)
    await save_manifest(db, draft, manifest)
    response = dict(manifest)
    response["_uploaded_asset_id"] = asset_id
    return response


@router.post("/games/{slug}/animations")
async def upload_animation(
    slug: str,
    name: str = Form(min_length=1, max_length=100),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Animations are typically multi-file bundles (e.g. Spine's
    animation.atlas + animation.json + animation.png — see
    scripts/check_spine_assets.py), so they land together in their own
    front/img/<slug>/<anim-slug>/ folder rather than as a single file."""
    draft, manifest = await require_manifest(db, slug)
    anim_slug = slugify(name)
    dest_dir = FRONT_DIR / "img" / slug / anim_slug
    saved_names = [await save_upload(dest_dir, f) for f in files]

    manifest["assets"]["animations"].append({
        "id": uuid.uuid4().hex, "name": name, "folder": anim_slug, "files": saved_names,
    })
    bump_stage(manifest, 2)
    await save_manifest(db, draft, manifest)
    response = dict(manifest)
    response["_spine_warnings"] = check_dir(dest_dir, fix=True)
    return response


@router.post("/games/{slug}/stage", response_model=BuilderGameOut)
async def set_stage(slug: str, body: BuilderStageRequest, db: AsyncSession = Depends(get_db)) -> BuilderGameOut:
    draft, manifest = await require_manifest(db, slug)
    bump_stage(manifest, body.stage)
    await save_manifest(db, draft, manifest)
    return manifest_to_out(manifest)


@router.post("/games/{slug}/rescan")
async def rescan_assets(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Materials can also be dropped straight into front/img|sound/<slug>/ by
    hand instead of through the upload forms (that's the workflow this
    endpoint is for) — it picks up anything not already in the manifest.
    Images land as unassigned (category/screen/device null) since a bare
    file on disk carries no metadata; tag_asset fills those in afterward.
    Subdirectories under img/ are treated as animation bundles (Spine's
    atlas+json+png convention — see scripts/check_spine_assets.py)."""
    draft, manifest = await require_manifest(db, slug)

    known_images = {img["file"] for img in manifest["assets"]["images"]}
    known_sounds = {s["file"] for s in manifest["assets"]["sounds"]}
    known_anim_folders = {a["folder"] for a in manifest["assets"]["animations"]}
    spine_warnings: list[str] = []

    img_dir = FRONT_DIR / "img" / slug
    if img_dir.is_dir():
        for entry in sorted(img_dir.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                if entry.name in known_anim_folders:
                    continue
                files = sorted(p.name for p in entry.iterdir() if p.is_file() and not p.name.startswith("."))
                if not files:
                    continue
                manifest["assets"]["animations"].append({
                    "id": uuid.uuid4().hex, "name": entry.name, "folder": entry.name, "files": files,
                })
                for atlas_dir in find_atlas_dirs(entry):
                    spine_warnings.extend(check_dir(atlas_dir, fix=True))
            elif entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS and entry.name not in known_images:
                is_catalog = entry.stem.lower() in CATALOG_FILENAME_STEMS
                manifest["assets"]["images"].append({
                    "id": uuid.uuid4().hex, "file": entry.name,
                    "category": "catalog" if is_catalog else None,
                    "screen": None, "device": None,
                    # Without this, a later upload of the same bytes (e.g. via
                    # a wizard quick-add button) can never find_by_hash() its
                    # way to this entry and instead writes a fresh -2 suffixed
                    # copy — this was the actual source of resurfacing
                    # "duplicate files" reports, not the upload path itself.
                    "sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
                })

    sound_dir = FRONT_DIR / "sound" / slug
    if sound_dir.is_dir():
        for entry in sorted(sound_dir.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_file() and entry.suffix.lower() in SOUND_EXTENSIONS and entry.name not in known_sounds:
                manifest["assets"]["sounds"].append({
                    "id": uuid.uuid4().hex, "file": entry.name,
                    "sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
                })

    total_assets = sum(len(manifest["assets"][k]) for k in ("images", "sounds", "animations"))
    if total_assets > 0:
        bump_stage(manifest, 2)
    await save_manifest(db, draft, manifest)
    response = dict(manifest)
    response["_spine_warnings"] = spine_warnings
    return response


@router.patch("/games/{slug}/assets/{asset_id}")
async def tag_asset(slug: str, asset_id: str, body: AssetTagRequest, db: AsyncSession = Depends(get_db)) -> dict:
    draft, manifest = await require_manifest(db, slug)
    needs_placement = body.category is not AssetCategory.catalog
    for img in manifest["assets"]["images"]:
        if img["id"] == asset_id:
            img["category"] = body.category.value
            img["screen"] = body.screen.value if needs_placement else None
            img["device"] = body.device.value if needs_placement else None
            await save_manifest(db, draft, manifest)
            return manifest
    raise HTTPException(status_code=404, detail=f"image asset '{asset_id}' not found")


@router.post("/games/{slug}/grid", response_model=BuilderGameOut)
async def set_grid(slug: str, body: BuilderGridRequest, db: AsyncSession = Depends(get_db)) -> BuilderGameOut:
    draft, manifest = await require_manifest(db, slug)
    manifest["grid"] = {"reels": body.reels, "rows": body.rows}
    manifest["mechanics"] = body.mechanics
    bump_stage(manifest, 3)
    await save_manifest(db, draft, manifest)
    return manifest_to_out(manifest)


@router.post("/games/{slug}/generate-config")
async def generate_config(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Materializes a real, simulatable `GameConfig` from this game's Stage 3
    grid + mechanics selection (see app/api/admin/builder_config.py) — the
    step that turns the wizard's output into an actually playable game
    instead of just a visual shell. Safe to call again after changing grid/
    mechanics as long as nothing has customized the result since (service
    layer 409s otherwise, pointing at the config editor instead)."""
    draft, manifest = await require_manifest(db, slug)
    if not manifest.get("grid"):
        raise HTTPException(status_code=400, detail="save the grid size and mechanics (stage 3) before generating a config")

    symbol_assets = [
        {"id": img["id"], "file": img["file"]}
        for img in manifest["assets"]["images"]
        if img.get("category") == "symbol"
    ]
    config = await service.generate_config_from_builder(
        db, slug, manifest["grid"]["reels"], manifest["grid"]["rows"], manifest.get("mechanics", []),
        symbol_assets,
    )
    manifest["game_config_id"] = str(config.id)
    await save_manifest(db, draft, manifest)
    return {
        "config_id": str(config.id),
        "status": config.status,
        "num_symbols": len(config.symbols),
        "num_paylines": len(config.paylines),
        "num_features": len(config.feature_configs),
    }


@router.post("/games/{slug}/publish-live")
async def publish_live(slug: str, body: PublishLiveRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Stage 5's single "all OK" action: publishes the Stage-3-generated
    config (DRAFT -> ACTIVE, same as the admin config editor's own publish
    button — service.publish_config) and stamps this game's catalog
    metadata (app/models/game.py's catalog_* columns) so it appears on
    front/games.html and is playable at front/play.html?slug=<slug>
    immediately, with zero manual file edits."""
    draft, manifest = await require_manifest(db, slug)
    config_id = manifest.get("game_config_id")
    if not config_id:
        raise HTTPException(status_code=400, detail="generate a config (stage 3) before publishing")

    # A game that already went through Stage 5 once has its config sitting at
    # ACTIVE, not DRAFT — service.publish_config only accepts DRAFT (409s
    # otherwise), so re-running this endpoint just to update the badge/
    # description/cover (e.g. adding a catalog cover after the fact) would
    # always fail. Only attempt the DRAFT->ACTIVE transition when there's
    # actually one to make; catalog metadata below still gets updated either way.
    config = await service.get_config(db, uuid.UUID(config_id))
    if config.status == GameConfigStatus.DRAFT.value:
        await service.publish_config(db, uuid.UUID(config_id))

    game = (await db.execute(select(Game).where(Game.code == slug))).scalars().first()
    cover_asset = next(
        (img for img in manifest["assets"]["images"] if img.get("category") == "catalog"), None
    )
    game.catalog_badge = body.badge
    game.catalog_description = body.description
    game.catalog_cover_path = f"img/{slug}/{cover_asset['file']}" if cover_asset else None
    game.catalog_play_url = f"play.html?slug={slug}"
    await db.commit()

    return {
        "code": slug,
        "status": "active",
        "catalog_play_url": game.catalog_play_url,
    }


@router.post("/games/{slug}/test-spin")
async def test_spin(
    slug: str, db: AsyncSession = Depends(get_db), rng: RNGProvider = Depends(get_rng)
) -> dict:
    """Stage 5's "test this slot": one real spin against the config Stage 3
    generated, so you can see it actually produce a grid/win before
    publishing — see run_builder_test_spin's docstring for why this can't
    just reuse /api/v1/spin (that endpoint only ever plays the ACTIVE
    config, and this one is still a draft)."""
    _, manifest = await require_manifest(db, slug)
    config_id = manifest.get("game_config_id")
    if not config_id:
        raise HTTPException(status_code=400, detail="generate a config (stage 3) before test-spinning")

    config = await service.get_config(db, uuid.UUID(config_id))
    return run_builder_test_spin(config, rng)


@router.delete("/games/{slug}/assets/{asset_id}")
async def delete_asset(slug: str, asset_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    draft, manifest = await require_manifest(db, slug)

    for img in manifest["assets"]["images"]:
        if img["id"] == asset_id:
            manifest["assets"]["images"].remove(img)
            (FRONT_DIR / "img" / slug / img["file"]).unlink(missing_ok=True)
            await save_manifest(db, draft, manifest)
            return manifest

    for sound in manifest["assets"]["sounds"]:
        if sound["id"] == asset_id:
            manifest["assets"]["sounds"].remove(sound)
            (FRONT_DIR / "sound" / slug / sound["file"]).unlink(missing_ok=True)
            await save_manifest(db, draft, manifest)
            return manifest

    raise HTTPException(status_code=404, detail=f"asset '{asset_id}' not found")


@router.delete("/games/{slug}/animations/{anim_id}")
async def delete_animation(slug: str, anim_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    draft, manifest = await require_manifest(db, slug)

    for anim in manifest["assets"]["animations"]:
        if anim["id"] == anim_id:
            manifest["assets"]["animations"].remove(anim)
            shutil.rmtree(FRONT_DIR / "img" / slug / anim["folder"], ignore_errors=True)
            await save_manifest(db, draft, manifest)
            return manifest

    raise HTTPException(status_code=404, detail=f"animation '{anim_id}' not found")


@router.post("/games/{slug}/layout/background")
async def set_layout_background(slug: str, body: LayoutBackgroundRequest, db: AsyncSession = Depends(get_db)) -> dict:
    draft, manifest = await require_manifest(db, slug)
    layout = manifest["layouts"][body.device.value]

    if body.asset_id is None and body.animation_ref is None:
        layout["backgrounds"][body.screen.value] = None
    elif body.animation_ref is not None:
        if not any(a["id"] == body.animation_ref for a in manifest["assets"]["animations"]):
            raise HTTPException(status_code=422, detail=f"unknown animation_ref '{body.animation_ref}'")
        layout["backgrounds"][body.screen.value] = {
            "animation_ref": body.animation_ref,
            "animation_name": body.animation_name,
            "x": body.x if body.x is not None else layout["w"] / 2,
            "y": body.y if body.y is not None else layout["h"] / 2,
            "w": body.w if body.w is not None else layout["w"],
            "h": body.h if body.h is not None else layout["h"],
        }
    else:
        if not any(img["id"] == body.asset_id for img in manifest["assets"]["images"]):
            raise HTTPException(status_code=422, detail=f"unknown asset_id '{body.asset_id}'")
        layout["backgrounds"][body.screen.value] = {
            "asset_id": body.asset_id,
            "x": body.x if body.x is not None else layout["w"] / 2,
            "y": body.y if body.y is not None else layout["h"] / 2,
            "w": body.w if body.w is not None else layout["w"],
            "h": body.h if body.h is not None else layout["h"],
        }
    bump_stage(manifest, 4)
    await save_manifest(db, draft, manifest)
    return manifest


@router.post("/games/{slug}/layout/skip")
async def set_layout_skip(slug: str, body: LayoutSkipRequest, db: AsyncSession = Depends(get_db)) -> dict:
    draft, manifest = await require_manifest(db, slug)
    skips = set(manifest.get("layout_skips", []))
    if body.skipped:
        skips.add(body.step_id)
    else:
        skips.discard(body.step_id)
    manifest["layout_skips"] = sorted(skips)
    await save_manifest(db, draft, manifest)
    return manifest


@router.post("/games/{slug}/layout/objects")
async def set_layout_objects(slug: str, body: LayoutObjectsRequest, db: AsyncSession = Depends(get_db)) -> dict:
    draft, manifest = await require_manifest(db, slug)
    known_ids = {img["id"] for img in manifest["assets"]["images"]}
    known_anim_ids = {a["id"] for a in manifest["assets"]["animations"]}
    for obj in body.objects:
        if obj.image_ref is not None and obj.image_ref not in known_ids:
            raise HTTPException(status_code=422, detail=f"unknown image_ref '{obj.image_ref}'")
        if obj.animation_ref is not None and obj.animation_ref not in known_anim_ids:
            raise HTTPException(status_code=422, detail=f"unknown animation_ref '{obj.animation_ref}'")

    manifest["layouts"][body.device.value]["screens"][body.screen.value] = [
        o.model_dump(mode="json") for o in body.objects
    ]
    bump_stage(manifest, 4)
    await save_manifest(db, draft, manifest)
    return manifest
