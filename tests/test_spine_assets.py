"""Tests for app/services/spine_assets.py — the two upload mistakes it
guards against (see that module's docstring), shared by scripts/
check_spine_assets.py and the builder's animation upload/rescan endpoints."""

from app.services.spine_assets import check_dir, find_atlas_dirs


def test_find_atlas_dirs_finds_both_atlas_and_atlas_txt(tmp_path):
    (tmp_path / "wild").mkdir()
    (tmp_path / "wild" / "animation.atlas").write_text("animation.png\n")
    (tmp_path / "coin").mkdir()
    (tmp_path / "coin" / "animation.atlas.txt").write_text("animation.png\n")
    (tmp_path / "empty").mkdir()

    dirs = find_atlas_dirs(tmp_path)
    assert dirs == sorted([tmp_path / "coin", tmp_path / "wild"])


def test_check_dir_reports_stray_txt_extension_without_fix(tmp_path):
    d = tmp_path / "wild"
    d.mkdir()
    (d / "animation.atlas.txt").write_text("animation.png\n")

    issues = check_dir(d, fix=False)
    assert len(issues) == 1
    assert "animation.atlas.txt should be animation.atlas" in issues[0]
    assert (d / "animation.atlas.txt").exists()
    assert not (d / "animation.atlas").exists()


def test_check_dir_fixes_stray_txt_extension(tmp_path):
    d = tmp_path / "wild"
    d.mkdir()
    (d / "animation.atlas.txt").write_text("animation.png\n")
    (d / "animation.png").write_bytes(b"png-bytes")

    issues = check_dir(d, fix=True)
    assert len(issues) == 1
    assert "renamed animation.atlas.txt -> animation.atlas" in issues[0]
    assert not (d / "animation.atlas.txt").exists()
    assert (d / "animation.atlas").read_text() == "animation.png\n"


def test_check_dir_reports_mismatched_page_name(tmp_path):
    d = tmp_path / "wild"
    d.mkdir()
    (d / "animation.atlas").write_text("wild_export_v3.png\nsize: 512,512\n")

    issues = check_dir(d, fix=False)
    assert len(issues) == 1
    assert "declares page 'wild_export_v3.png'" in issues[0]
    assert "also missing" in issues[0]  # animation.png doesn't exist either


def test_check_dir_fixes_mismatched_page_name_when_real_png_exists(tmp_path):
    d = tmp_path / "wild"
    d.mkdir()
    (d / "animation.atlas").write_text("wild_export_v3.png\nsize: 512,512\n")
    (d / "animation.png").write_bytes(b"png-bytes")

    issues = check_dir(d, fix=True)
    assert len(issues) == 1
    assert "fixed atlas page-name 'wild_export_v3.png' -> 'animation.png'" in issues[0]
    assert (d / "animation.atlas").read_text().splitlines()[0] == "animation.png"


def test_check_dir_reports_nothing_for_a_correct_bundle(tmp_path):
    d = tmp_path / "wild"
    d.mkdir()
    (d / "animation.atlas").write_text("animation.png\nsize: 512,512\n")
    (d / "animation.png").write_bytes(b"png-bytes")
    (d / "animation.json").write_text("{}")

    assert check_dir(d, fix=True) == []
