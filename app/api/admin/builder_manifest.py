"""Manifest, slug and on-disk asset-file helpers behind the slot-builder
routes (app/api/admin/builder.py). The manifest lives in the
`builder_drafts` table (app/models/builder_draft.py), keyed to the Game row
by `game_id` — not as a `front/builder/<slug>.spec.json` file (the wizard's
original storage): a DB row can't race a concurrent read-modify-write the
way a plain file can, and it can never end up orphaned from its Game row by
a crash between two separate writes. It's the single artifact meant to carry
everything needed to hand the finished game off for real front/back wiring,
so later stages should keep extending it rather than inventing parallel
state. Actual uploaded media (images/sounds/animations) still lives on disk
under front/img|sound/<slug>/ — only this bookkeeping JSON moved to the DB."""

import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.admin.builder_schemas import BuilderGameOut
from app.models.builder_draft import BuilderDraft
from app.models.game import Game

# app/api/admin/builder_manifest.py -> parents[3] is the repo root.
FRONT_DIR = Path(__file__).resolve().parents[3] / "front"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
SOUND_EXTENSIONS = {".mp3", ".wav", ".ogg", ".opus", ".m4a"}
# Filenames rescan auto-tags as the games.html catalog cover instead of
# leaving them unassigned (front/img/<slug>/img/logo_<Name>-hero.jpg's existing
# naming pattern, loosened to a plain stem match).
CATALOG_FILENAME_STEMS = {"logo", "cover", "catalog"}

_CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(name: str) -> str:
    """Transliterates Cyrillic to Latin, then reduces to the kebab-case
    format the existing game codes use (amys-fruit-farm, east-discovery).
    Truncated to leave room for a numeric uniqueness suffix under the
    Game.code column's 64-char limit."""
    transliterated = "".join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in name.lower())
    normalized = unicodedata.normalize("NFKD", transliterated).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return (slug or "slot")[:56]


async def unique_slug(db: AsyncSession, base: str) -> str:
    candidate = base
    suffix = 2
    while True:
        result = await db.execute(select(Game.id).where(Game.code == candidate))
        if result.scalars().first() is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def empty_manifest(game_id: uuid.UUID, slug: str, name: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "meta": {
            "slug": slug,
            "display_name": name,
            "game_id": str(game_id),
            "stage_completed": 1,
            "created_at": now,
            "updated_at": now,
        },
        "assets": {"images": [], "sounds": [], "animations": []},
        "grid": None,
        "mechanics": [],
        "layouts": {
            "desktop": {"w": 1932, "h": 940, "screens": {"base": [], "bonus": []}},
            "mobile": {"w": 780, "h": 1416, "screens": {"base": [], "bonus": []}},
        },
        # Wizard step ids (e.g. "buybonus-desktop") the user explicitly marked
        # as "this element doesn't exist for this slot" — see set_layout_skip
        # in builder.py. Only ever set for the optional ui/hud-kind steps
        # (buy-bonus/free-spins-counter/multiplier); backgrounds and the slot
        # step are never skippable.
        "layout_skips": [],
        "popups": {},
    }


def migrate_manifest(manifest: dict) -> dict:
    """Backfills keys added after a manifest was first created (e.g.
    neon-reels predates Stage 4's layouts.<device>.backgrounds) so older
    rows don't need a one-time migration script — every load just sees the
    current shape, with sane defaults for anything missing."""
    for device in ("desktop", "mobile"):
        layout = manifest["layouts"][device]
        layout.setdefault("backgrounds", {"base": None, "bonus": None})
        for screen in ("base", "bonus"):
            bg = layout["backgrounds"].get(screen)
            if isinstance(bg, str):
                # Predates the background becoming a positionable object
                # (used to be just the asset_id) — same visual result
                # (full-screen, centered) expressed in the new shape.
                layout["backgrounds"][screen] = {
                    "asset_id": bg, "x": layout["w"] / 2, "y": layout["h"] / 2, "w": layout["w"], "h": layout["h"],
                }
    manifest.setdefault("layout_skips", [])
    return manifest


async def require_manifest(db: AsyncSession, slug: str) -> tuple[BuilderDraft, dict]:
    if not SLUG_RE.match(slug):
        raise HTTPException(status_code=404, detail="not found")
    result = await db.execute(
        select(BuilderDraft).join(Game, Game.id == BuilderDraft.game_id).where(Game.code == slug)
    )
    draft = result.scalars().first()
    if draft is None:
        raise HTTPException(status_code=404, detail=f"builder game '{slug}' not found")
    return draft, migrate_manifest(draft.manifest)


async def save_manifest(db: AsyncSession, draft: BuilderDraft, manifest: dict) -> None:
    manifest["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    draft.manifest = manifest
    # JSON columns don't auto-track in-place dict mutation (most callers
    # mutate `manifest` before calling this rather than building a fresh
    # dict) — flag_modified makes sure the UPDATE actually fires either way.
    flag_modified(draft, "manifest")
    await db.commit()


def bump_stage(manifest: dict, stage: int) -> None:
    manifest["meta"]["stage_completed"] = max(manifest["meta"]["stage_completed"], stage)


def manifest_to_out(manifest: dict) -> BuilderGameOut:
    meta = manifest["meta"]
    return BuilderGameOut(
        game_id=uuid.UUID(meta["game_id"]),
        slug=meta["slug"],
        name=meta["display_name"],
        stage_completed=meta["stage_completed"],
        created_at=meta["created_at"],
        updated_at=meta["updated_at"],
    )


def save_bytes(dest_dir: Path, filename: str | None, content: bytes) -> str:
    """Writes content under its own filename, deduping on collision
    (existing repo assets already use spaces/Cyrillic in filenames, so only
    directory components are stripped — otherwise names are left alone).
    Only called once the caller has already decided this content isn't a
    byte-for-byte duplicate of something already uploaded (see
    find_by_hash) — this alone doesn't dedupe."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    original = Path(filename or "file").name or "file"
    stem, suffix = Path(original).stem, Path(original).suffix
    candidate = original
    n = 2
    while (dest_dir / candidate).exists():
        candidate = f"{stem}-{n}{suffix}"
        n += 1
    (dest_dir / candidate).write_bytes(content)
    return candidate


async def save_upload(dest_dir: Path, upload: UploadFile) -> str:
    return save_bytes(dest_dir, upload.filename, await upload.read())


def find_by_hash(entries: list[dict], sha256: str) -> dict | None:
    return next((e for e in entries if e.get("sha256") == sha256), None)
