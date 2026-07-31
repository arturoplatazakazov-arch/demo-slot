"""Tests for the slot-builder wizard's stage-1 endpoint (app/api/admin/builder.py):
slug generation/uniqueness as pure unit tests against the isolated in-memory
SQLite db_session, and the HTTP route against a tmp_path standing in for
front/ so a test run never writes into the real repo."""

import hashlib

import pytest
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.api.admin import builder, builder_manifest
from app.api.deps import get_db
from app.main import app
from app.models.builder_draft import BuilderDraft
from app.models.game import Game


# ---------- slugify (pure function, no fixtures needed) ----------

def test_slugify_transliterates_cyrillic():
    assert builder_manifest.slugify("Дикий Восток") == "dikii-vostok"


def test_slugify_falls_back_when_nothing_survives():
    assert builder_manifest.slugify("!!!") == "slot"


def test_slugify_collapses_punctuation_and_case():
    assert builder_manifest.slugify("  Amy's   Fruit Farm!! ") == "amy-s-fruit-farm"


# ---------- _unique_slug (needs a db session) ----------

async def test_unique_slug_returns_base_when_free(db_session):
    assert await builder_manifest.unique_slug(db_session, "wild-west") == "wild-west"


async def test_unique_slug_appends_suffix_on_collision(db_session):
    db_session.add(Game(code="wild-west", name="Wild West"))
    await db_session.commit()

    assert await builder_manifest.unique_slug(db_session, "wild-west") == "wild-west-2"


async def test_unique_slug_skips_taken_suffixes_too(db_session):
    db_session.add(Game(code="wild-west", name="Wild West"))
    db_session.add(Game(code="wild-west-2", name="Wild West (2)"))
    await db_session.commit()

    assert await builder_manifest.unique_slug(db_session, "wild-west") == "wild-west-3"


# ---------- HTTP routes ----------

@pytest.fixture
async def builder_client(client, db_session, tmp_path, monkeypatch):
    """The shared `client` fixture (ASGITransport, no lifespan) with get_db
    swapped for the isolated db_session and FRONT_DIR redirected to a
    tmp_path, so route tests never touch the real Postgres or front/."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr(builder, "FRONT_DIR", tmp_path)
    yield client
    app.dependency_overrides.pop(get_db, None)


async def test_create_game_creates_folders_and_manifest(builder_client, tmp_path):
    response = await builder_client.post("/api/admin/builder/games", json={"name": "Тест Слот"})
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "test-slot"
    assert body["name"] == "Тест Слот"
    assert body["stage_completed"] == 1

    for sub in ("img", "sound", "js"):
        assert (tmp_path / sub / "test-slot").is_dir()

    manifest = (await builder_client.get("/api/admin/builder/games/test-slot")).json()
    assert manifest["meta"]["slug"] == "test-slot"
    assert manifest["meta"]["stage_completed"] == 1
    assert manifest["layouts"]["desktop"] == {
        "w": 1932, "h": 940, "screens": {"base": [], "bonus": []},
        "backgrounds": {"base": None, "bonus": None},
    }
    assert manifest["layouts"]["mobile"] == {
        "w": 780, "h": 1416, "screens": {"base": [], "bonus": []},
        "backgrounds": {"base": None, "bonus": None},
    }


async def test_create_game_dedupes_slug_for_repeated_names(builder_client):
    first = await builder_client.post("/api/admin/builder/games", json={"name": "Test Slot"})
    second = await builder_client.post("/api/admin/builder/games", json={"name": "Test Slot"})
    assert first.json()["slug"] == "test-slot"
    assert second.json()["slug"] == "test-slot-2"


async def test_create_game_rejects_blank_name(builder_client):
    response = await builder_client.post("/api/admin/builder/games", json={"name": ""})
    assert response.status_code == 422


async def test_list_games_includes_created_game(builder_client):
    await builder_client.post("/api/admin/builder/games", json={"name": "Listed Slot"})
    response = await builder_client.get("/api/admin/builder/games")
    assert response.status_code == 200
    slugs = [g["slug"] for g in response.json()]
    assert "listed-slot" in slugs


async def test_list_games_empty_when_no_builder_dir(builder_client):
    response = await builder_client.get("/api/admin/builder/games")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_game_returns_full_manifest(builder_client):
    created = await builder_client.post("/api/admin/builder/games", json={"name": "Fetchable Slot"})
    slug = created.json()["slug"]

    response = await builder_client.get(f"/api/admin/builder/games/{slug}")
    assert response.status_code == 200
    assert response.json()["meta"]["slug"] == slug


async def test_get_game_404s_for_unknown_slug(builder_client):
    response = await builder_client.get("/api/admin/builder/games/does-not-exist")
    assert response.status_code == 404


async def test_get_game_404s_for_path_traversal_attempt(builder_client):
    response = await builder_client.get("/api/admin/builder/games/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404


# ---------- delete_game ----------

async def test_delete_game_removes_it_from_the_list(builder_client, tmp_path):
    created = await builder_client.post("/api/admin/builder/games", json={"name": "Doomed Slot"})
    slug = created.json()["slug"]
    for sub in ("img", "sound", "js"):
        assert (tmp_path / sub / slug).is_dir()

    response = await builder_client.delete(f"/api/admin/builder/games/{slug}")
    assert response.status_code == 200
    assert response.json() == {"deleted": slug}

    assert (await builder_client.get("/api/admin/builder/games")).json() == []
    assert (await builder_client.get(f"/api/admin/builder/games/{slug}")).status_code == 404
    for sub in ("img", "sound", "js"):
        assert not (tmp_path / sub / slug).exists()


async def test_delete_game_removes_builder_draft_row(builder_client, db_session):
    created = await builder_client.post("/api/admin/builder/games", json={"name": "Draft Row Slot"})
    slug = created.json()["slug"]

    await builder_client.delete(f"/api/admin/builder/games/{slug}")

    game = (await db_session.execute(select(Game).where(Game.code == slug))).scalars().first()
    assert game is None
    drafts = (await db_session.execute(select(BuilderDraft))).scalars().all()
    assert drafts == []


async def test_delete_game_404s_for_unknown_slug(builder_client):
    response = await builder_client.delete("/api/admin/builder/games/does-not-exist")
    assert response.status_code == 404


async def test_delete_game_refuses_when_config_is_active(builder_client, db_session):
    from app.models.config import GameConfig
    from app.models.enums import GameConfigStatus

    created = await builder_client.post("/api/admin/builder/games", json={"name": "Published Slot"})
    slug = created.json()["slug"]
    game = (await db_session.execute(select(Game).where(Game.code == slug))).scalars().first()

    db_session.add(GameConfig(
        game_id=game.id, version=1, status=GameConfigStatus.ACTIVE.value,
        num_reels=5, num_rows=3, target_rtp=0.96, min_bet=1, max_bet=100, bet_step=1,
    ))
    await db_session.commit()

    response = await builder_client.delete(f"/api/admin/builder/games/{slug}")
    assert response.status_code == 409

    # Still there afterwards.
    assert (await builder_client.get(f"/api/admin/builder/games/{slug}")).status_code == 200


# ---------- Stage 2: asset uploads ----------

async def _create(builder_client, name="Asset Slot"):
    response = await builder_client.post("/api/admin/builder/games", json={"name": name})
    return response.json()["slug"]


async def test_upload_image_asset_saves_file_and_manifest_entry(builder_client, tmp_path):
    slug = await _create(builder_client)

    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "background", "screen": "base", "device": "desktop"},
        files={"file": ("bg.png", b"fake-png-bytes", "image/png")},
    )
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["meta"]["stage_completed"] == 2
    images = manifest["assets"]["images"]
    assert len(images) == 1
    assert images[0]["file"] == "bg.png"
    assert images[0]["category"] == "background"
    assert images[0]["screen"] == "base"
    assert images[0]["device"] == "desktop"

    saved = tmp_path / "img" / slug / "bg.png"
    assert saved.read_bytes() == b"fake-png-bytes"


async def test_upload_ui_asset_shared_across_desktop_and_mobile(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "ui", "screen": "base", "device": "both"},
        files={"file": ("spin-btn.png", b"x", "image/png")},
    )
    assert response.status_code == 200
    image = response.json()["assets"]["images"][0]
    assert image["category"] == "ui"
    assert image["device"] == "both"


async def test_upload_image_asset_requires_category_screen_device(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image"},
        files={"file": ("bg.png", b"x", "image/png")},
    )
    assert response.status_code == 422


async def test_upload_sound_asset_needs_no_category(builder_client, tmp_path):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "sound"},
        files={"file": ("click.mp3", b"fake-mp3-bytes", "audio/mpeg")},
    )
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["assets"]["sounds"][0]["file"] == "click.mp3"
    assert (tmp_path / "sound" / slug / "click.mp3").read_bytes() == b"fake-mp3-bytes"


async def test_upload_asset_dedupes_filename_collision(builder_client):
    slug = await _create(builder_client)
    kwargs = dict(data={"kind": "sound"}, files={"file": ("click.mp3", b"first", "audio/mpeg")})
    await builder_client.post(f"/api/admin/builder/games/{slug}/assets", **kwargs)

    second = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "sound"},
        files={"file": ("click.mp3", b"second", "audio/mpeg")},
    )
    sounds = second.json()["assets"]["sounds"]
    assert sorted(s["file"] for s in sounds) == ["click-2.mp3", "click.mp3"]


async def test_upload_asset_404s_for_unknown_slug(builder_client):
    response = await builder_client.post(
        "/api/admin/builder/games/does-not-exist/assets",
        data={"kind": "sound"},
        files={"file": ("click.mp3", b"x", "audio/mpeg")},
    )
    assert response.status_code == 404


async def test_upload_animation_saves_multi_file_bundle(builder_client, tmp_path):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/animations",
        data={"name": "Wild"},
        files=[
            ("files", ("animation.atlas", b"atlas-bytes", "text/plain")),
            ("files", ("animation.png", b"png-bytes", "image/png")),
        ],
    )
    assert response.status_code == 200
    manifest = response.json()
    anim = manifest["assets"]["animations"][0]
    assert anim["name"] == "Wild"
    assert anim["folder"] == "wild"
    assert sorted(anim["files"]) == ["animation.atlas", "animation.png"]

    anim_dir = tmp_path / "img" / slug / "wild"
    assert (anim_dir / "animation.atlas").read_bytes() == b"atlas-bytes"
    assert (anim_dir / "animation.png").read_bytes() == b"png-bytes"


# ---------- Stage 2 -> later stage transitions ----------

async def test_set_stage_bumps_forward(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(f"/api/admin/builder/games/{slug}/stage", json={"stage": 3})
    assert response.status_code == 200
    assert response.json()["stage_completed"] == 3


async def test_set_stage_never_regresses(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(f"/api/admin/builder/games/{slug}/stage", json={"stage": 3})
    response = await builder_client.post(f"/api/admin/builder/games/{slug}/stage", json={"stage": 1})
    assert response.json()["stage_completed"] == 3


async def test_set_stage_rejects_out_of_range(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(f"/api/admin/builder/games/{slug}/stage", json={"stage": 6})
    assert response.status_code == 422


async def test_set_stage_404s_for_unknown_slug(builder_client):
    response = await builder_client.post("/api/admin/builder/games/does-not-exist/stage", json={"stage": 2})
    assert response.status_code == 404


# ---------- rescan + tag (materials dropped straight into the folders) ----------

async def test_rescan_picks_up_manually_dropped_image(builder_client, tmp_path):
    slug = await _create(builder_client)
    (tmp_path / "img" / slug / "hero.png").write_bytes(b"manual-drop")

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["meta"]["stage_completed"] == 2
    images = manifest["assets"]["images"]
    assert len(images) == 1
    assert images[0]["file"] == "hero.png"
    assert images[0]["category"] is None
    assert images[0]["screen"] is None
    assert images[0]["device"] is None
    assert images[0]["sha256"] == hashlib.sha256(b"manual-drop").hexdigest()


async def test_rescan_picks_up_manually_dropped_sound(builder_client, tmp_path):
    slug = await _create(builder_client)
    (tmp_path / "sound" / slug / "click.mp3").write_bytes(b"manual-drop")

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    sounds = response.json()["assets"]["sounds"]
    assert len(sounds) == 1
    assert sounds[0]["file"] == "click.mp3"
    assert sounds[0]["sha256"] == hashlib.sha256(b"manual-drop").hexdigest()


async def test_uploading_bytes_already_picked_up_by_rescan_reuses_the_entry(builder_client, tmp_path):
    """Regression test: rescanned entries used to be saved without a sha256,
    so a later upload of byte-identical content (e.g. via a Stage 4
    quick-add button) could never find_by_hash() its way to them and wrote
    a fresh frame-2.png-style duplicate instead of reusing the asset."""
    slug = await _create(builder_client)
    (tmp_path / "img" / slug / "hero.png").write_bytes(b"same-bytes")
    rescanned = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    rescanned_id = rescanned.json()["assets"]["images"][0]["id"]

    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "frame", "screen": "base", "device": "desktop"},
        files={"file": ("hero-again.png", b"same-bytes", "image/png")},
    )
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["_uploaded_asset_id"] == rescanned_id
    assert len(manifest["assets"]["images"]) == 1
    assert (tmp_path / "img" / slug / "hero-again.png").exists() is False


async def test_rescan_ignores_ds_store_and_unknown_extensions(builder_client, tmp_path):
    slug = await _create(builder_client)
    img_dir = tmp_path / "img" / slug
    (img_dir / ".DS_Store").write_bytes(b"junk")
    (img_dir / "notes.txt").write_bytes(b"junk")

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    manifest = response.json()
    assert manifest["assets"]["images"] == []
    assert manifest["meta"]["stage_completed"] == 1


async def test_rescan_treats_subdirectory_as_animation_bundle(builder_client, tmp_path):
    slug = await _create(builder_client)
    anim_dir = tmp_path / "img" / slug / "wild"
    anim_dir.mkdir(parents=True)
    (anim_dir / "animation.atlas").write_bytes(b"atlas")
    (anim_dir / "animation.png").write_bytes(b"png")

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    animations = response.json()["assets"]["animations"]
    assert len(animations) == 1
    assert animations[0]["folder"] == "wild"
    assert sorted(animations[0]["files"]) == ["animation.atlas", "animation.png"]


async def test_rescan_is_idempotent(builder_client, tmp_path):
    slug = await _create(builder_client)
    (tmp_path / "img" / slug / "hero.png").write_bytes(b"manual-drop")

    await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    second = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    assert len(second.json()["assets"]["images"]) == 1


async def test_rescan_404s_for_unknown_slug(builder_client):
    response = await builder_client.post("/api/admin/builder/games/does-not-exist/rescan")
    assert response.status_code == 404


async def test_tag_asset_assigns_category_screen_device(builder_client, tmp_path):
    slug = await _create(builder_client)
    (tmp_path / "img" / slug / "hero.png").write_bytes(b"manual-drop")
    rescanned = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    asset_id = rescanned.json()["assets"]["images"][0]["id"]

    response = await builder_client.patch(
        f"/api/admin/builder/games/{slug}/assets/{asset_id}",
        json={"category": "hero", "screen": "base", "device": "desktop"},
    )
    assert response.status_code == 200
    image = response.json()["assets"]["images"][0]
    assert image["category"] == "hero"
    assert image["screen"] == "base"
    assert image["device"] == "desktop"


async def test_tag_asset_404s_for_unknown_asset_id(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.patch(
        f"/api/admin/builder/games/{slug}/assets/does-not-exist",
        json={"category": "hero", "screen": "base", "device": "desktop"},
    )
    assert response.status_code == 404


# ---------- catalog cover category (games.html card image) ----------

async def test_upload_catalog_asset_needs_no_screen_or_device(builder_client, tmp_path):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "catalog"},
        files={"file": ("logo.jpg", b"cover-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    image = response.json()["assets"]["images"][0]
    assert image["category"] == "catalog"
    assert image["screen"] is None
    assert image["device"] is None
    assert (tmp_path / "img" / slug / "logo.jpg").read_bytes() == b"cover-bytes"


async def test_rescan_auto_tags_conventional_catalog_filenames(builder_client, tmp_path):
    slug = await _create(builder_client)
    (tmp_path / "img" / slug / "logo.jpg").write_bytes(b"logo")
    (tmp_path / "img" / slug / "cover.png").write_bytes(b"cover")
    (tmp_path / "img" / slug / "reel_frame.png").write_bytes(b"unrelated")

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    images = {img["file"]: img for img in response.json()["assets"]["images"]}
    assert images["logo.jpg"]["category"] == "catalog"
    assert images["cover.png"]["category"] == "catalog"
    assert images["reel_frame.png"]["category"] is None


async def test_tag_asset_to_catalog_clears_screen_and_device(builder_client, tmp_path):
    slug = await _create(builder_client)
    (tmp_path / "img" / slug / "art.png").write_bytes(b"x")
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "background", "screen": "base", "device": "desktop"},
        files={"file": ("art.png", b"x", "image/png")},
    )
    asset_id = uploaded.json()["assets"]["images"][0]["id"]

    response = await builder_client.patch(
        f"/api/admin/builder/games/{slug}/assets/{asset_id}",
        json={"category": "catalog", "screen": "base", "device": "desktop"},
    )
    image = response.json()["assets"]["images"][0]
    assert image["category"] == "catalog"
    assert image["screen"] is None
    assert image["device"] is None


# ---------- Stage 3: grid + mechanics ----------

async def test_set_grid_saves_reels_rows_mechanics_and_bumps_stage(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/grid",
        json={"reels": 5, "rows": 3, "mechanics": ["line_pay", "scatter", "free_spins"]},
    )
    assert response.status_code == 200
    assert response.json()["stage_completed"] == 3

    manifest = await builder_client.get(f"/api/admin/builder/games/{slug}")
    body = manifest.json()
    assert body["grid"] == {"reels": 5, "rows": 3}
    assert body["mechanics"] == ["line_pay", "scatter", "free_spins"]


async def test_set_grid_rejects_unknown_mechanic(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/grid",
        json={"reels": 5, "rows": 3, "mechanics": ["teleport_wild"]},
    )
    assert response.status_code == 422


async def test_set_grid_rejects_reels_out_of_bounds(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/grid",
        json={"reels": 0, "rows": 3, "mechanics": []},
    )
    assert response.status_code == 422


async def test_set_grid_404s_for_unknown_slug(builder_client):
    response = await builder_client.post(
        "/api/admin/builder/games/does-not-exist/grid",
        json={"reels": 5, "rows": 3, "mechanics": []},
    )
    assert response.status_code == 404


async def test_set_grid_allows_empty_mechanics_list(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/grid",
        json={"reels": 3, "rows": 3, "mechanics": []},
    )
    assert response.status_code == 200


# ---------- logo category (in-game logo, distinct from the catalog cover) ----------

# ---------- generate-config: builder -> real GameConfig ----------

async def test_generate_config_requires_grid_saved_first(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")
    assert response.status_code == 400


async def test_generate_config_creates_real_game_config(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(
        f"/api/admin/builder/games/{slug}/grid",
        json={"reels": 5, "rows": 3, "mechanics": ["free_spins", "scatter"]},
    )

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")
    assert response.status_code == 200
    body = response.json()
    assert body["num_symbols"] > 0
    assert body["num_paylines"] == 3
    assert body["num_features"] == 1
    assert body["status"] == "draft"

    manifest = (await builder_client.get(f"/api/admin/builder/games/{slug}")).json()
    assert manifest["game_config_id"] == body["config_id"]

    configs = await builder_client.get(f"/api/admin/games/{slug}/configs")
    assert configs.status_code == 200
    assert len(configs.json()) == 1


async def test_generate_config_avalanche_has_no_paylines(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(
        f"/api/admin/builder/games/{slug}/grid",
        json={"reels": 6, "rows": 5, "mechanics": ["avalanche", "scatter", "free_spins"]},
    )

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")
    assert response.status_code == 200
    body = response.json()
    assert body["num_paylines"] == 0
    assert body["num_symbols"] > 0
    assert body["num_features"] == 2  # avalanche + free_spins


async def test_test_spin_returns_cascade_steps_for_avalanche_config(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(
        f"/api/admin/builder/games/{slug}/grid", json={"reels": 6, "rows": 5, "mechanics": ["avalanche"]},
    )
    await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/test-spin")
    assert response.status_code == 200
    body = response.json()
    assert body["line_wins"] == []
    assert body["count_wins"] == []
    assert isinstance(body["avalanche"]["steps"], list)


async def test_generate_config_wires_symbol_image_ref_from_uploaded_symbol_assets(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(
        f"/api/admin/builder/games/{slug}/grid", json={"reels": 5, "rows": 3, "mechanics": []},
    )
    upload = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "symbol", "screen": "both", "device": "both"},
        files={"file": ("cherry.png", b"symbol-bytes", "image/png")},
    )
    asset_id = upload.json()["_uploaded_asset_id"]

    generated = await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")
    config_id = generated.json()["config_id"]

    detail = await builder_client.get(f"/api/admin/configs/{config_id}")
    symbols = sorted(detail.json()["symbols"], key=lambda s: s["code"])
    # display_order 0 is "low_a" — the first synthesized symbol, so it's the
    # one that gets the one uploaded symbol asset.
    first_symbol = next(s for s in detail.json()["symbols"] if s["image_ref"] is not None)
    assert first_symbol["image_ref"] == asset_id
    assert sum(1 for s in symbols if s["image_ref"] is not None) == 1


async def test_generate_config_404s_for_unknown_slug(builder_client):
    response = await builder_client.post("/api/admin/builder/games/does-not-exist/generate-config")
    assert response.status_code == 404


async def test_generate_config_409s_on_second_call_after_publish(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(f"/api/admin/builder/games/{slug}/grid", json={"reels": 5, "rows": 3, "mechanics": []})
    first = await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")
    config_id = first.json()["config_id"]

    publish = await builder_client.post(f"/api/admin/configs/{config_id}/publish")
    assert publish.status_code == 200

    second = await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")
    assert second.status_code == 409


# ---------- publish-live: Stage 5's "all OK" action ----------

async def test_publish_live_requires_generated_config_first(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/publish-live", json={"badge": "Farm", "description": "desc"},
    )
    assert response.status_code == 400


async def test_publish_live_activates_config_and_stamps_catalog_fields(builder_client, db_session):
    slug = await _create(builder_client)
    await builder_client.post(f"/api/admin/builder/games/{slug}/grid", json={"reels": 5, "rows": 3, "mechanics": []})
    generated = await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")
    config_id = generated.json()["config_id"]

    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/publish-live",
        json={"badge": "Farm", "description": "Классический слот"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"code": slug, "status": "active", "catalog_play_url": f"play.html?slug={slug}"}

    config_detail = await builder_client.get(f"/api/admin/configs/{config_id}")
    assert config_detail.json()["status"] == "active"

    game = (await db_session.execute(select(Game).where(Game.code == slug))).scalars().first()
    assert game.catalog_badge == "Farm"
    assert game.catalog_description == "Классический слот"
    assert game.catalog_cover_path is None
    assert game.catalog_play_url == f"play.html?slug={slug}"


async def test_publish_live_sets_catalog_cover_from_catalog_category_asset(builder_client, db_session):
    slug = await _create(builder_client)
    await builder_client.post(f"/api/admin/builder/games/{slug}/grid", json={"reels": 5, "rows": 3, "mechanics": []})
    await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "catalog"},
        files={"file": ("cover.png", b"cover-bytes", "image/png")},
    )
    await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")

    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/publish-live", json={"badge": "Farm", "description": "desc"},
    )
    assert response.status_code == 200

    game = (await db_session.execute(select(Game).where(Game.code == slug))).scalars().first()
    assert game.catalog_cover_path == f"img/{slug}/cover.png"


async def test_publish_live_404s_for_unknown_slug(builder_client):
    response = await builder_client.post(
        "/api/admin/builder/games/does-not-exist/publish-live", json={"badge": "Farm", "description": "desc"},
    )
    assert response.status_code == 404


# ---------- test-spin: one ad-hoc spin against the generated config ----------

async def test_test_spin_requires_generated_config_first(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(f"/api/admin/builder/games/{slug}/grid", json={"reels": 5, "rows": 3, "mechanics": []})
    response = await builder_client.post(f"/api/admin/builder/games/{slug}/test-spin")
    assert response.status_code == 400


async def test_test_spin_returns_a_full_grid_after_generate_config(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(f"/api/admin/builder/games/{slug}/grid", json={"reels": 4, "rows": 3, "mechanics": []})
    await builder_client.post(f"/api/admin/builder/games/{slug}/generate-config")

    response = await builder_client.post(f"/api/admin/builder/games/{slug}/test-spin")
    assert response.status_code == 200
    body = response.json()
    assert len(body["grid"]) == 4
    assert all(len(column) == 3 for column in body["grid"])
    assert isinstance(body["total_win"], int)


async def test_test_spin_404s_for_unknown_slug(builder_client):
    response = await builder_client.post("/api/admin/builder/games/does-not-exist/test-spin")
    assert response.status_code == 404


async def test_upload_logo_asset_requires_screen_and_device(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "logo"},
        files={"file": ("logo.png", b"x", "image/png")},
    )
    assert response.status_code == 422


async def test_upload_logo_asset_saves_with_placement(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "logo", "screen": "base", "device": "both"},
        files={"file": ("logo.png", b"x", "image/png")},
    )
    assert response.status_code == 200
    image = response.json()["assets"]["images"][0]
    assert image["category"] == "logo"
    assert image["screen"] == "base"
    assert image["device"] == "both"


# ---------- delete asset / animation ----------

async def test_delete_image_asset_removes_entry_and_file(builder_client, tmp_path):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "background", "screen": "base", "device": "desktop"},
        files={"file": ("bg.png", b"x", "image/png")},
    )
    asset_id = uploaded.json()["assets"]["images"][0]["id"]
    assert (tmp_path / "img" / slug / "bg.png").exists()

    response = await builder_client.delete(f"/api/admin/builder/games/{slug}/assets/{asset_id}")
    assert response.status_code == 200
    assert response.json()["assets"]["images"] == []
    assert not (tmp_path / "img" / slug / "bg.png").exists()


async def test_delete_sound_asset_removes_entry_and_file(builder_client, tmp_path):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "sound"},
        files={"file": ("click.mp3", b"x", "audio/mpeg")},
    )
    asset_id = uploaded.json()["assets"]["sounds"][0]["id"]

    response = await builder_client.delete(f"/api/admin/builder/games/{slug}/assets/{asset_id}")
    assert response.json()["assets"]["sounds"] == []
    assert not (tmp_path / "sound" / slug / "click.mp3").exists()


async def test_delete_asset_404s_for_unknown_id(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.delete(f"/api/admin/builder/games/{slug}/assets/does-not-exist")
    assert response.status_code == 404


async def test_delete_animation_removes_entry_and_folder(builder_client, tmp_path):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/animations",
        data={"name": "wild"},
        files=[("files", ("animation.atlas", b"x", "text/plain"))],
    )
    anim_id = uploaded.json()["assets"]["animations"][0]["id"]
    anim_dir = tmp_path / "img" / slug / "wild"
    assert anim_dir.exists()

    response = await builder_client.delete(f"/api/admin/builder/games/{slug}/animations/{anim_id}")
    assert response.status_code == 200
    assert response.json()["assets"]["animations"] == []
    assert not anim_dir.exists()


async def test_delete_animation_404s_for_unknown_id(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.delete(f"/api/admin/builder/games/{slug}/animations/does-not-exist")
    assert response.status_code == 404


# ---------- Stage 4: layout (background + objects) ----------

async def test_get_game_migrates_pre_stage4_manifest(builder_client):
    # A freshly created manifest already predates the "backgrounds" key
    # (_empty_manifest was never updated to add it — migration is the only
    # thing that backfills it), so this exercises the same path neon-reels
    # hits: nothing to fake, the pre-Stage-4 shape is just what create leaves.
    slug = await _create(builder_client)

    response = await builder_client.get(f"/api/admin/builder/games/{slug}")
    assert response.status_code == 200
    body = response.json()
    assert body["layouts"]["desktop"]["backgrounds"] == {"base": None, "bonus": None}
    assert body["layouts"]["mobile"]["backgrounds"] == {"base": None, "bonus": None}


async def test_set_layout_background_with_valid_asset(builder_client):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "background", "screen": "base", "device": "desktop"},
        files={"file": ("bg.jpg", b"x", "image/jpeg")},
    )
    asset_id = uploaded.json()["assets"]["images"][0]["id"]

    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/background",
        json={"device": "desktop", "screen": "base", "asset_id": asset_id},
    )
    assert response.status_code == 200
    manifest = response.json()
    bg = manifest["layouts"]["desktop"]["backgrounds"]["base"]
    assert bg["asset_id"] == asset_id
    assert bg == {"asset_id": asset_id, "x": 966, "y": 470, "w": 1932, "h": 940}
    assert manifest["meta"]["stage_completed"] == 4


async def test_set_layout_background_with_explicit_position(builder_client):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "background", "screen": "base", "device": "desktop"},
        files={"file": ("bg.jpg", b"x", "image/jpeg")},
    )
    asset_id = uploaded.json()["assets"]["images"][0]["id"]

    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/background",
        json={"device": "desktop", "screen": "base", "asset_id": asset_id, "x": 500, "y": 300, "w": 800, "h": 600},
    )
    bg = response.json()["layouts"]["desktop"]["backgrounds"]["base"]
    assert bg == {"asset_id": asset_id, "x": 500, "y": 300, "w": 800, "h": 600}


async def test_migrate_manifest_upgrades_plain_string_background(builder_client, db_session):
    slug = await _create(builder_client)
    result = await db_session.execute(select(BuilderDraft).join(Game).where(Game.code == slug))
    draft = result.scalars().one()
    draft.manifest["layouts"]["desktop"]["backgrounds"] = {"base": "some-asset-id", "bonus": None}
    flag_modified(draft, "manifest")
    await db_session.commit()

    response = await builder_client.get(f"/api/admin/builder/games/{slug}")
    bg = response.json()["layouts"]["desktop"]["backgrounds"]["base"]
    assert bg == {"asset_id": "some-asset-id", "x": 966, "y": 470, "w": 1932, "h": 940}


async def test_set_layout_background_rejects_unknown_asset(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/background",
        json={"device": "desktop", "screen": "base", "asset_id": "does-not-exist"},
    )
    assert response.status_code == 422


async def test_set_layout_background_can_be_cleared(builder_client):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "background", "screen": "base", "device": "desktop"},
        files={"file": ("bg.jpg", b"x", "image/jpeg")},
    )
    asset_id = uploaded.json()["assets"]["images"][0]["id"]
    await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/background",
        json={"device": "desktop", "screen": "base", "asset_id": asset_id},
    )
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/background",
        json={"device": "desktop", "screen": "base", "asset_id": None},
    )
    assert response.json()["layouts"]["desktop"]["backgrounds"]["base"] is None


async def test_set_layout_background_with_valid_animation(builder_client):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/animations",
        data={"name": "Ambient BG"},
        files=[
            ("files", ("animation.atlas", b"atlas-bytes", "text/plain")),
            ("files", ("animation.json", b"{}", "application/json")),
            ("files", ("animation.png", b"png-bytes", "image/png")),
        ],
    )
    anim_id = uploaded.json()["assets"]["animations"][0]["id"]

    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/background",
        json={"device": "desktop", "screen": "base", "animation_ref": anim_id, "animation_name": "idle"},
    )
    assert response.status_code == 200
    bg = response.json()["layouts"]["desktop"]["backgrounds"]["base"]
    assert bg == {"animation_ref": anim_id, "animation_name": "idle", "x": 966, "y": 470, "w": 1932, "h": 940}

    # round-trips via GET too
    fetched = await builder_client.get(f"/api/admin/builder/games/{slug}")
    assert fetched.json()["layouts"]["desktop"]["backgrounds"]["base"] == bg


async def test_set_layout_background_rejects_unknown_animation(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/background",
        json={"device": "desktop", "screen": "base", "animation_ref": "does-not-exist"},
    )
    assert response.status_code == 422


async def test_set_layout_background_rejects_both_asset_and_animation(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/background",
        json={"device": "desktop", "screen": "base", "asset_id": "img-1", "animation_ref": "anim-1"},
    )
    assert response.status_code == 422


async def test_set_layout_objects_saves_and_round_trips(builder_client):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "hero", "screen": "base", "device": "desktop"},
        files={"file": ("hero.png", b"x", "image/png")},
    )
    asset_id = uploaded.json()["assets"]["images"][0]["id"]

    objects = [
        {"id": "obj-1", "type": "decor.hero", "image_ref": asset_id, "x": 500, "y": 300, "w": 200, "h": 250, "z_index": 2},
        {"id": "obj-2", "type": "system.reel_block", "image_ref": None, "x": 966, "y": 470, "w": 900, "h": 700, "z_index": 1},
    ]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 200
    assert response.json()["meta"]["stage_completed"] == 4

    manifest = await builder_client.get(f"/api/admin/builder/games/{slug}")
    saved = manifest.json()["layouts"]["desktop"]["screens"]["base"]
    assert len(saved) == 2
    assert saved[0]["id"] == "obj-1"
    assert saved[0]["x"] == 500
    assert saved[1]["type"] == "system.reel_block"
    assert saved[1]["image_ref"] is None


async def test_set_layout_objects_rejects_unknown_image_ref(builder_client):
    slug = await _create(builder_client)
    objects = [{"id": "obj-1", "type": "decor.image", "image_ref": "does-not-exist", "x": 0, "y": 0, "w": 10, "h": 10, "z_index": 0}]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 422


async def test_set_layout_objects_saves_decor_spine_with_valid_animation(builder_client):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/animations",
        data={"name": "Lanterns"},
        files=[
            ("files", ("animation.atlas", b"atlas-bytes", "text/plain")),
            ("files", ("animation.json", b"{}", "application/json")),
            ("files", ("animation.png", b"png-bytes", "image/png")),
        ],
    )
    anim_id = uploaded.json()["assets"]["animations"][0]["id"]

    objects = [{
        "id": "obj-1", "type": "decor.spine", "animation_ref": anim_id, "animation_name": "idle",
        "x": 500, "y": 300, "w": 200, "h": 200, "z_index": 1,
    }]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 200

    manifest = await builder_client.get(f"/api/admin/builder/games/{slug}")
    saved = manifest.json()["layouts"]["desktop"]["screens"]["base"]
    assert saved == [{
        "id": "obj-1", "type": "decor.spine", "image_ref": None,
        "animation_ref": anim_id, "animation_name": "idle",
        "role": None, "x": 500, "y": 300, "w": 200, "h": 200, "z_index": 1,
        "cell_w": None, "cell_h": None, "gap_x": None, "gap_y": None,
    }]


async def test_set_layout_objects_rejects_unknown_animation_ref(builder_client):
    slug = await _create(builder_client)
    objects = [{
        "id": "obj-1", "type": "decor.spine", "animation_ref": "does-not-exist",
        "x": 0, "y": 0, "w": 10, "h": 10, "z_index": 0,
    }]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 422


async def test_set_layout_objects_rejects_non_positive_size(builder_client):
    slug = await _create(builder_client)
    objects = [{"id": "obj-1", "type": "decor.image", "image_ref": None, "x": 0, "y": 0, "w": 0, "h": 10, "z_index": 0}]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 422


async def test_set_layout_objects_replaces_previous_list(builder_client):
    slug = await _create(builder_client)
    first = [{"id": "obj-1", "type": "decor.image", "image_ref": None, "x": 0, "y": 0, "w": 10, "h": 10, "z_index": 0}]
    await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "mobile", "screen": "bonus", "objects": first},
    )
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "mobile", "screen": "bonus", "objects": []},
    )
    assert response.json()["layouts"]["mobile"]["screens"]["bonus"] == []


async def test_layout_endpoints_404_for_unknown_slug(builder_client):
    response = await builder_client.post(
        "/api/admin/builder/games/does-not-exist/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": []},
    )
    assert response.status_code == 404


# ---------- layout/skip (optional wizard steps like buy-bonus/fs-counter/multiplier) ----------

async def test_set_layout_skip_marks_step_skipped(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/skip", json={"step_id": "buybonus-desktop"},
    )
    assert response.status_code == 200
    assert response.json()["layout_skips"] == ["buybonus-desktop"]

    fetched = await builder_client.get(f"/api/admin/builder/games/{slug}")
    assert fetched.json()["layout_skips"] == ["buybonus-desktop"]


async def test_set_layout_skip_can_be_undone(builder_client):
    slug = await _create(builder_client)
    await builder_client.post(f"/api/admin/builder/games/{slug}/layout/skip", json={"step_id": "multiplier-mobile"})
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/skip",
        json={"step_id": "multiplier-mobile", "skipped": False},
    )
    assert response.json()["layout_skips"] == []


async def test_set_layout_skip_404s_for_unknown_slug(builder_client):
    response = await builder_client.post(
        "/api/admin/builder/games/does-not-exist/layout/skip", json={"step_id": "buybonus-desktop"},
    )
    assert response.status_code == 404


async def test_new_game_manifest_has_empty_layout_skips(builder_client):
    slug = await _create(builder_client)
    manifest = (await builder_client.get(f"/api/admin/builder/games/{slug}")).json()
    assert manifest["layout_skips"] == []


# ---------- frame category ----------

async def test_upload_frame_asset_requires_screen_and_device(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "frame"},
        files={"file": ("frame.png", b"x", "image/png")},
    )
    assert response.status_code == 422


async def test_upload_frame_asset_saves_with_placement(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "frame", "screen": "base", "device": "desktop"},
        files={"file": ("frame.png", b"x", "image/png")},
    )
    assert response.status_code == 200
    image = response.json()["assets"]["images"][0]
    assert image["category"] == "frame"
    assert image["screen"] == "base"
    assert image["device"] == "desktop"


# ---------- reel_block cell/gap fields ----------

async def test_set_layout_objects_saves_reel_block_cell_and_gap(builder_client):
    slug = await _create(builder_client)
    objects = [{
        "id": "obj-1", "type": "system.reel_block", "image_ref": None,
        "x": 966, "y": 470, "w": 900, "h": 650, "z_index": 0,
        "cell_w": 170, "cell_h": 200, "gap_x": 10, "gap_y": 12,
    }]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 200

    manifest = await builder_client.get(f"/api/admin/builder/games/{slug}")
    saved = manifest.json()["layouts"]["desktop"]["screens"]["base"][0]
    assert saved["cell_w"] == 170
    assert saved["cell_h"] == 200
    assert saved["gap_x"] == 10
    assert saved["gap_y"] == 12


async def test_set_layout_objects_defaults_cell_gap_to_null_for_non_reel_block(builder_client):
    slug = await _create(builder_client)
    objects = [{"id": "obj-1", "type": "decor.image", "image_ref": None, "x": 0, "y": 0, "w": 10, "h": 10, "z_index": 0}]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    saved = response.json()["layouts"]["desktop"]["screens"]["base"][0]
    assert saved["cell_w"] is None
    assert saved["cell_h"] is None
    assert saved["gap_x"] is None
    assert saved["gap_y"] is None


async def test_set_layout_objects_reel_block_without_cell_gap_still_works(builder_client):
    """Mirrors a reel_block saved before this feature existed (neon-reels'
    real one) — no cell/gap keys at all, just x/y/w/h/z_index."""
    slug = await _create(builder_client)
    objects = [{"id": "obj-1", "type": "system.reel_block", "image_ref": None, "x": 966, "y": 470, "w": 900, "h": 650, "z_index": 0}]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 200
    saved = response.json()["layouts"]["desktop"]["screens"]["base"][0]
    assert saved["cell_w"] is None


# ---------- content-hash dedup ----------

async def test_uploading_identical_bytes_twice_reuses_the_same_asset(builder_client, tmp_path):
    slug = await _create(builder_client)
    kwargs = dict(
        data={"kind": "image", "category": "frame", "screen": "base", "device": "desktop"},
        files={"file": ("frame.png", b"same-bytes", "image/png")},
    )
    first = await builder_client.post(f"/api/admin/builder/games/{slug}/assets", **kwargs)
    second = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "frame", "screen": "base", "device": "desktop"},
        files={"file": ("frame-renamed.png", b"same-bytes", "image/png")},
    )
    images = second.json()["assets"]["images"]
    assert len(images) == 1
    assert first.json()["_uploaded_asset_id"] == second.json()["_uploaded_asset_id"]
    # Only the first upload's file exists — no "-2" copy was written.
    assert (tmp_path / "img" / slug / "frame.png").exists()
    assert not (tmp_path / "img" / slug / "frame-renamed.png").exists()


async def test_uploading_different_bytes_creates_separate_assets(builder_client):
    slug = await _create(builder_client)
    kwargs = dict(data={"kind": "image", "category": "frame", "screen": "base", "device": "desktop"})
    await builder_client.post(f"/api/admin/builder/games/{slug}/assets", files={"file": ("a.png", b"aaa", "image/png")}, **kwargs)
    response = await builder_client.post(f"/api/admin/builder/games/{slug}/assets", files={"file": ("b.png", b"bbb", "image/png")}, **kwargs)
    assert len(response.json()["assets"]["images"]) == 2


async def test_uploading_identical_sound_bytes_twice_reuses_the_same_asset(builder_client, tmp_path):
    slug = await _create(builder_client)
    await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "sound"}, files={"file": ("click.mp3", b"same-audio", "audio/mpeg")},
    )
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "sound"}, files={"file": ("click2.mp3", b"same-audio", "audio/mpeg")},
    )
    assert len(response.json()["assets"]["sounds"]) == 1
    assert not (tmp_path / "sound" / slug / "click2.mp3").exists()


# ---------- screen "both" tag ----------

async def test_upload_with_screen_both_round_trips(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "ui", "screen": "both", "device": "both"},
        files={"file": ("spin.png", b"x", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["assets"]["images"][0]["screen"] == "both"


async def test_tag_asset_accepts_screen_both(builder_client, tmp_path):
    slug = await _create(builder_client)
    (tmp_path / "img" / slug / "hero.png").write_bytes(b"manual-drop")
    rescanned = await builder_client.post(f"/api/admin/builder/games/{slug}/rescan")
    asset_id = rescanned.json()["assets"]["images"][0]["id"]

    response = await builder_client.patch(
        f"/api/admin/builder/games/{slug}/assets/{asset_id}",
        json={"category": "ui", "screen": "both", "device": "both"},
    )
    assert response.status_code == 200
    assert response.json()["assets"]["images"][0]["screen"] == "both"


# ---------- reel_background / hud categories ----------

async def test_upload_reel_background_asset(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "reel_background", "screen": "base", "device": "desktop"},
        files={"file": ("reel_bg.png", b"x", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["assets"]["images"][0]["category"] == "reel_background"


async def test_upload_hud_asset(builder_client):
    slug = await _create(builder_client)
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "hud", "screen": "bonus", "device": "both"},
        files={"file": ("fs_counter.png", b"x", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["assets"]["images"][0]["category"] == "hud"


async def test_set_layout_objects_accepts_reel_background_and_hud_types(builder_client):
    slug = await _create(builder_client)
    uploaded = await builder_client.post(
        f"/api/admin/builder/games/{slug}/assets",
        data={"kind": "image", "category": "reel_background", "screen": "base", "device": "desktop"},
        files={"file": ("reel_bg.png", b"x", "image/png")},
    )
    asset_id = uploaded.json()["assets"]["images"][0]["id"]
    objects = [{
        "id": "obj-1", "type": "decor.reel_background", "image_ref": asset_id,
        "x": 966, "y": 470, "w": 1200, "h": 800, "z_index": 0,
    }]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 200
    assert response.json()["layouts"]["desktop"]["screens"]["base"][0]["type"] == "decor.reel_background"


# ---------- role field (Stage 4 wizard bookkeeping) ----------

async def test_layout_object_role_round_trips(builder_client):
    slug = await _create(builder_client)
    objects = [{
        "id": "obj-1", "type": "system.button", "image_ref": None,
        "x": 100, "y": 100, "w": 50, "h": 50, "z_index": 0, "role": "buy_bonus",
    }]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.status_code == 200
    saved = response.json()["layouts"]["desktop"]["screens"]["base"][0]
    assert saved["role"] == "buy_bonus"

    fetched = await builder_client.get(f"/api/admin/builder/games/{slug}")
    assert fetched.json()["layouts"]["desktop"]["screens"]["base"][0]["role"] == "buy_bonus"


async def test_layout_object_role_defaults_to_null(builder_client):
    slug = await _create(builder_client)
    objects = [{"id": "obj-1", "type": "decor.image", "image_ref": None, "x": 0, "y": 0, "w": 10, "h": 10, "z_index": 0}]
    response = await builder_client.post(
        f"/api/admin/builder/games/{slug}/layout/objects",
        json={"device": "desktop", "screen": "base", "objects": objects},
    )
    assert response.json()["layouts"]["desktop"]["screens"]["base"][0]["role"] is None
