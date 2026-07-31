"""Validates Spine WebGL asset folders (animation.atlas + animation.json +
animation.png) against two upload mistakes that have already silently broken
this project's rendering multiple times (front/img/east-discovery's wild/
coin folders, more than once each) — worth catching before they reach the
browser, since a single broken atlas kills the *entire* page's animation,
not just the one symbol: spine-webgl's SpineCanvas only starts its update/
render loop once, the first time its whole asset queue reports zero errors
(see front/js/spine-engine.js + vendor/spine-webgl.js's SpineCanvas
constructor) — one 404'd atlas anywhere on the page means nothing animates
anywhere, ever, for that page load.

The two mistakes:
1. The atlas file uploaded with a stray ".txt" extension
   (animation.atlas.txt instead of animation.atlas) — some export/upload
   pipeline keeps appending this on re-upload.
2. The atlas file's internal declared texture-page name (its first line)
   not matching the actual delivered image filename (usually
   animation.png) — the artist's Spine project's own internal page name
   leaks through instead of being renamed to match delivery convention.

Shared by scripts/check_spine_assets.py (CLI) and the builder's animation
upload/rescan endpoints (app/api/admin/builder.py), which call check_dir
right after saving a bundle so bad uploads get caught immediately instead
of silently breaking Spine rendering later."""

from pathlib import Path


def find_atlas_dirs(root: Path) -> list[Path]:
    """Every directory containing animation.atlas and/or animation.atlas.txt."""
    dirs = {p.parent for p in root.rglob("animation.atlas")}
    dirs |= {p.parent for p in root.rglob("animation.atlas.txt")}
    return sorted(dirs)


def check_dir(d: Path, fix: bool) -> list[str]:
    issues: list[str] = []
    txt_path = d / "animation.atlas.txt"
    atlas_path = d / "animation.atlas"

    if txt_path.exists():
        if fix:
            if atlas_path.exists():
                atlas_path.unlink()  # stale copy from a previous fix, superseded by this re-upload
            txt_path.rename(atlas_path)
            issues.append(f"{d}: renamed animation.atlas.txt -> animation.atlas")
        else:
            issues.append(f"{d}: animation.atlas.txt should be animation.atlas")

    if not atlas_path.exists():
        return issues  # nothing more to check without an atlas file in place

    lines = atlas_path.read_text().splitlines(keepends=True)
    page_line_index = None
    declared_page = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.endswith(".png"):
            page_line_index = i
            declared_page = stripped
            break

    if declared_page is None or (d / declared_page).exists():
        return issues  # no page line, or it already points at a real file

    actual_png = d / "animation.png"
    if fix and actual_png.exists():
        lines[page_line_index] = "animation.png\n"
        atlas_path.write_text("".join(lines))
        issues.append(f"{d}: fixed atlas page-name '{declared_page}' -> 'animation.png'")
    else:
        missing_note = "" if actual_png.exists() else " (animation.png is also missing here!)"
        issues.append(f"{d}: atlas declares page '{declared_page}', which doesn't exist{missing_note}")

    return issues
