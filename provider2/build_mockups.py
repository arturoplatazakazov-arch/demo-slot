"""Sort the ChatGPT art dump into per-game folders, cut the sheets into single
sprites and compose a base-game and a bonus-game mockup per slot.

    python3 provider2/build_mockups.py <folder with the unsorted PNGs>

Writes provider2/art/<slug>/{src,cut}/ and provider2/mockups/<slug>_{base,bonus}.png.
The prefix map below ties each downloaded file (ChatGPT names them by uuid)
to its game and art job; extend it when more files arrive.
"""

from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
W, H = 1920, 1080

# file-name prefix -> (slug, job)
FILES = {
    "Неоновая": ("rad-raiders", "symbols_hp"),
    "cba12df9": ("rad-raiders", "logo"),
    "e3435d1f": ("rad-raiders", "symbols_lp"),
    "1b3e3f45": ("rad-raiders", "frame"),
    "d054b5f3": ("rad-raiders", "bg_base"),
    "2862b6b8": ("rad-raiders", "characters"),
    "60ca45e1": ("rad-raiders", "bg_bonus"),
    "dd8e4a7a": ("jade-paws", "symbols_lp"),
    "ac637bf3": ("jade-paws", "logo"),
    "8b80823f": ("jade-paws", "symbols_hp"),
    "065ddb5c": ("jade-paws", "frame"),
    "a4e2ded1": ("jade-paws", "characters"),
    "7fbc90d6": ("jade-paws", "bg_bonus"),
    "ebc729dc": ("jade-paws", "bg_base"),
    "76d36bd9": ("gummy-gold-rush", "logo"),
    "76b10640": ("gummy-gold-rush", "logo_alt"),
    "9a4bd521": ("gummy-gold-rush", "symbols_hp"),
    "5432bd9f": ("gummy-gold-rush", "symbols_lp"),
    "dd1b7f5e": ("gummy-gold-rush", "frame"),
    "a45a0ba2": ("gummy-gold-rush", "bg_base"),
    "1700f02c": ("gummy-gold-rush", "characters"),
    "3c6469a8": ("gummy-gold-rush", "bg_bonus"),
    "4ae89560": ("ghoul-groove", "symbols_hp"),
    "4b1699f4": ("ghoul-groove", "logo"),
    "fc52c1e1": ("ghoul-groove", "symbols_lp"),
    "6670191e": ("ghoul-groove", "characters"),
    "a7d87d6f": ("ghoul-groove", "frame"),
    "d4632119": ("ghoul-groove", "bg_base"),
    "fea9da8e": ("ghoul-groove", "bg_bonus"),
    "3b072249": ("whisker-noir", "symbols_hp"),
    "cfde09aa": ("whisker-noir", "logo"),
    "db6927ac": ("whisker-noir", "symbols_lp"),
    "7ada4d15": ("whisker-noir", "characters"),
    "f0fff804": ("whisker-noir", "frame"),
    "1de337af": ("whisker-noir", "bg_base"),
    "3a2899f2": ("whisker-noir", "bg_bonus"),
    "5296ae3b": ("cogwork-skies", "symbols_hp"),
    "a1dcc288": ("cogwork-skies", "logo"),
    "6772ee98": ("cogwork-skies", "symbols_lp"),
    "7e6557ae": ("cogwork-skies", "characters"),
    "46ce607c": ("cogwork-skies", "frame"),
    "a3a8eb8f": ("cogwork-skies", "bg_base"),
    "30764fe6": ("cogwork-skies", "bg_bonus"),
    "4ff419fc": ("bayou-bedlam", "logo"),
    "4d2e89d2": ("bayou-bedlam", "symbols_hp"),
    "b2c71b88": ("bayou-bedlam", "characters"),
    "ad6ff72b": ("bayou-bedlam", "frame"),
    "ed0a3624": ("bayou-bedlam", "symbols_lp"),
    "2bc3dc57": ("bayou-bedlam", "bg_base"),
    "fc8220f2": ("bayou-bedlam", "bg_bonus"),
    "a6412abf": ("trident-vs-titan", "logo"),
    "7b1400aa": ("trident-vs-titan", "symbols_lp"),
    "16d95e2e": ("trident-vs-titan", "characters"),
    "bd464cf8": ("trident-vs-titan", "symbols_hp"),
    "bbc4df4f": ("trident-vs-titan", "frame"),
    "fdfaddab": ("trident-vs-titan", "bg_base"),
    "1c2de41b": ("trident-vs-titan", "bg_bonus"),
    "9a382634": ("hex-hollow", "logo"),
    "dff65c68": ("hex-hollow", "symbols_hp"),
    "74c7e81e": ("hex-hollow", "symbols_lp"),
    "4b91b74e": ("hex-hollow", "characters"),
    "536da13c": ("hex-hollow", "bg_base"),
    "a36fe8c4": ("jaguar-eclipse", "logo"),
    "ae02d077": ("jaguar-eclipse", "symbols_hp"),
    "1fbbac41": ("jaguar-eclipse", "symbols_lp"),
    "ac505a7e": ("whisker-noir", "symbols_hp_alt"),
    "11c54636": ("jaguar-eclipse", "characters"),
    "162cd193": ("jaguar-eclipse", "frame"),
    "495160b9": ("jaguar-eclipse", "bg_base"),
    "b7b6a54a": ("jaguar-eclipse", "bg_bonus"),
    "4bd636aa": ("hex-hollow", "bg_bonus"),
    "54d3b872": ("gummy-gold-rush", "bg_bonus_mob"),
    "6f80f1be": ("gummy-gold-rush", "ui_kit"),
    "0bf47e0c": ("rad-raiders", "bg_base_mob"),
    "3809e13f": ("gummy-gold-rush", "bg_base_mob"),
    "2fe4b5d5": ("rad-raiders", "bg_bonus_mob"),
    "4dd86239": ("jade-paws", "bg_base_mob"),
    "673428aa": ("jade-paws", "bg_bonus_mob"),
    "7a06f2ac": ("rad-raiders", "ui_kit"),
    "4e7eda4f": ("jade-paws", "ui_kit"),
    "3b727742": ("cogwork-skies", "bg_base_mob"),
    "68ee5cdc": ("ghoul-groove", "bg_base_mob"),
    "4e43367f": ("cogwork-skies", "bg_bonus_mob"),
    "044f6023": ("ghoul-groove", "bg_bonus_mob"),
    "becd7385": ("cogwork-skies", "ui_kit"),
    "730f413a": ("ghoul-groove", "ui_kit"),
    "1c73accc": ("whisker-noir", "bg_base_mob"),
    "9d4eb61d": ("whisker-noir", "bg_bonus_mob"),
    "66607f5c": ("whisker-noir", "ui_kit"),
    "83659574": ("hex-hollow", "bg_base_mob"),
    "dd0da622": ("bayou-bedlam", "bg_base_mob"),
    "39f969c1": ("hex-hollow", "bg_bonus_mob"),
    "bada13cf": ("bayou-bedlam", "bg_bonus_mob"),
    "5f15bd08": ("hex-hollow", "ui_kit"),
    "4d641ecd": ("bayou-bedlam", "ui_kit"),
    "60e76a5b": ("jaguar-eclipse", "bg_base_mob"),
    "2d389178": ("jaguar-eclipse", "bg_bonus_mob"),
    "104801e4": ("jaguar-eclipse", "ui_kit"),
    "b6064d87": ("trident-vs-titan", "bg_base_mob"),
    "12530a3e": ("trident-vs-titan", "bg_bonus_mob"),
    "f0ef20f5": ("trident-vs-titan", "ui_kit"),
}


def spans(profile: np.ndarray, min_gap: int, min_len: int) -> list[tuple[int, int]]:
    """Runs of non-empty entries in a 1D occupancy profile, merging gaps < min_gap."""
    on = profile > 0
    runs, start, gap = [], None, 0
    for i, v in enumerate(on):
        if v:
            if start is None:
                start = i
            gap = 0
            end = i
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                runs.append((start, end + 1))
                start, gap = None, 0
    if start is not None:
        runs.append((start, end + 1))
    return [r for r in runs if r[1] - r[0] >= min_len]


def components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """4-connected components of a boolean mask -> (area, x0, y0, x1, y1)."""
    from collections import deque
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        q = deque([(y, x)]); seen[y, x] = True
        area, x0, y0, x1, y1 = 0, x, y, x, y
        while q:
            cy, cx = q.popleft(); area += 1
            x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; q.append((ny, nx))
        out.append((area, x0, y0, x1 + 1, y1 + 1))
    return out


def cut_sheet(img: Image.Image, alpha_cut: int = 90, split_wide: bool = True, min_frac: float = 0.025) -> list[Image.Image]:
    """Split a transparent sprite sheet into its items: big alpha blobs (on a
    1/4 scale mask, ignoring faint glow), small bits glued to the blob whose
    box they sit in; items returned in reading order."""
    k = 4
    small = img.getchannel("A").resize((img.width // k, img.height // k), Image.BOX)
    mask = np.array(small) > alpha_cut
    comps = components(mask)
    total = mask.sum() or 1
    big = [c for c in comps if c[0] > total * min_frac]
    boxes = [list(c[1:]) for c in big]
    for c in comps:
        if c[0] > total * min_frac:
            continue
        cx, cy = (c[1] + c[3]) / 2, (c[2] + c[4]) / 2
        for b in boxes:
            m = 0.12 * max(b[2] - b[0], b[3] - b[1])
            if b[0] - m <= cx <= b[2] + m and b[1] - m <= cy <= b[3] + m:
                b[0], b[1], b[2], b[3] = min(b[0], c[1]), min(b[1], c[2]), max(b[2], c[3]), max(b[3], c[4])
                break
    # rows: sort by centre y and start a new row at a gap bigger than a third
    # of the typical item height, then read each row left to right
    boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
    hs = sorted(b[3] - b[1] for b in boxes)
    typ = hs[len(hs) // 2] if hs else 1
    rows, last = [], None
    for b in boxes:
        cy = (b[1] + b[3]) / 2
        if last is None or cy - last > typ * 0.45:
            rows.append([])
        rows[-1].append(b)
        last = cy
    boxes = [b for row in rows for b in sorted(row, key=lambda b: b[0])]
    out = []
    for b in boxes:
        x0, y0, x1, y1 = (max(0, b[0] * k - 6), max(0, b[1] * k - 6),
                          min(img.width, b[2] * k + 6), min(img.height, b[3] * k + 6))
        out.append(img.crop((x0, y0, x1, y1)))
    # tiles that touch come out as one wide blob: split by the typical width
    if split_wide and len(out) > 2:
        typical = sorted(o.width / o.height for o in out)[len(out) // 2]
        split = []
        for o in out:
            r = (o.width / o.height) / typical
            n = round(r)
            if r >= 1.7:
                step = o.width / n
                split += [o.crop((round(i * step), 0, round((i + 1) * step), o.height)) for i in range(n)]
            else:
                split.append(o)
        out = split
    return [o.crop(o.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox() or (0, 0, o.width, o.height))
            for o in out]


def fix_rows(items: list[Image.Image], expect: list[int]) -> list[Image.Image]:
    """Items are in reading order; when a row came out short, the widest blob
    in it holds several touching tiles - cut it into the missing count."""
    out, i = [], 0
    for want in expect:
        row = items[i:i + want]
        # the row really holds fewer blobs: take blobs until their summed width
        # ratio covers `want` tiles
        k, acc = 0, 0.0
        while i + k < len(items) and acc < want - 0.5:
            acc += items[i + k].width / items[i + k].height
            k += 1
        row = items[i:i + k]
        i += k
        while len(row) < want:
            j = max(range(len(row)), key=lambda n: row[n].width / row[n].height)
            o = row[j]
            parts = want - len(row) + 1
            step = o.width / parts
            row[j:j + 1] = [o.crop((round(n * step), 0, round((n + 1) * step), o.height)) for n in range(parts)]
        out += row
    return out + items[i:]


def grid_cut(img: Image.Image, cols: list[int]) -> list[Image.Image]:
    """Fallback for sheets whose tiles touch: rows split at the emptiest line
    near the expected border, then each row into equal columns over its extent."""
    a = np.array(img.getchannel("A")) > 60
    occ = a.sum(1)
    n = len(cols)
    cuts = [0]
    for k in range(1, n):
        y = img.height * k // n
        lo, hi = y - img.height // (4 * n), y + img.height // (4 * n)
        cuts.append(lo + int(np.argmin(occ[lo:hi])))
    cuts.append(img.height)
    out = []
    for k, c in enumerate(cols):
        band = a[cuts[k]:cuts[k + 1]]
        xs = np.nonzero(band.sum(0))[0]
        x0, x1 = xs.min(), xs.max() + 1
        step = (x1 - x0) / c
        for i in range(c):
            tile = img.crop((round(x0 + i * step), cuts[k], round(x0 + (i + 1) * step), cuts[k + 1]))
            bb = tile.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
            out.append(tile.crop(bb) if bb else tile)
    return out


def cover(img: Image.Image, w: int, h: int) -> Image.Image:
    s = max(w / img.width, h / img.height)
    im = img.convert("RGB").resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def frame_window(frame: Image.Image) -> tuple[int, int, int, int]:
    """Inner window of a reel frame: walk out from the centre until the
    ornament (opaque, not dark) takes over a band."""
    arr = np.asarray(frame.convert("RGBA")).astype(int)
    lum = arr[..., :3].mean(2)
    solid = (arr[..., 3] > 160) & (lum > 70)
    h, w = solid.shape
    cy, cx = h // 2, w // 2
    bh, bw = max(8, h // 10), max(8, w // 10)

    def walk(get, n, step):
        i = 0
        while 0 < i + step * 1 < n and abs(i) < n:
            if get(i) > 0.35:
                return i
            i += step
        return i

    col = lambda x: solid[cy - bh:cy + bh, x].mean()
    row = lambda y: solid[y, cx - bw:cx + bw].mean()
    left = next(x for x in range(cx, -1, -1) if x == 0 or col(x) > 0.35)
    right = next(x for x in range(cx, w) if x == w - 1 or col(x) > 0.35)
    top = next(y for y in range(cy, -1, -1) if y == 0 or row(y) > 0.35)
    bottom = next(y for y in range(cy, h) if y == h - 1 or row(y) > 0.35)
    return left, top, right, bottom


def reframe(frame: Image.Image, ww: int, wh: int, wall: int) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Rebuild a reel frame around a ww x wh window.

    The frame is scaled so its mean wall is `wall` px, then cut 5x5: corners
    and the centre ornament of every side keep their (scaled) size, only the
    plain runs between them stretch to reach the target window size."""
    frame = frame.crop(frame.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox())
    l, t, r, b = frame_window(frame)
    W0, H0 = frame.size
    walls = [l, t, W0 - r, H0 - b]
    s = wall / (sum(walls) / 4)
    # centre ornaments: middle 22% of each side
    cx0, cx1 = l + (r - l) * 0.39, l + (r - l) * 0.61
    cy0, cy1 = t + (b - t) * 0.39, t + (b - t) * 0.61
    xs = [0, l, cx0, cx1, r, W0]
    ys = [0, t, cy0, cy1, b, H0]

    def sizes(cuts, target):
        w = [(cuts[i + 1] - cuts[i]) * s for i in range(5)]
        plain = (target - w[2]) / 2
        if plain < 8:          # window target narrower than the scaled ornament
            w[2] = target - 16
            plain = 8
        w[1] = w[3] = plain
        return [max(1, round(v)) for v in w]

    nw, nh = sizes(xs, ww), sizes(ys, wh)
    out = Image.new("RGBA", (sum(nw), sum(nh)), (0, 0, 0, 0))
    oy = 0
    for j in range(5):
        ox = 0
        for i in range(5):
            if not (i in (1, 2, 3) and j in (1, 2, 3)):   # skip the window itself
                box = (round(xs[i]), round(ys[j]), round(xs[i + 1]), round(ys[j + 1]))
                if box[2] > box[0] and box[3] > box[1]:
                    out.alpha_composite(frame.crop(box).resize((nw[i], nh[j]), Image.LANCZOS), (ox, oy))
            ox += nw[i]
        oy += nh[j]
    wl, wt = nw[0], nh[0]
    return out, (wl, wt, wl + sum(nw[1:4]), wt + sum(nh[1:4]))


def fit(img: Image.Image, w: int, h: int) -> Image.Image:
    s = min(w / img.width, h / img.height)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)


def paste_c(dst: Image.Image, img: Image.Image, cx: int, cy: int) -> None:
    dst.alpha_composite(img, (round(cx - img.width / 2), round(cy - img.height / 2)))


def shadow(img: Image.Image, r: int = 18, a: int = 150) -> Image.Image:
    pad = r * 2
    sh = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    m = img.getchannel("A").point(lambda v: v * a // 255)
    sh.paste(Image.new("RGBA", img.size, (0, 0, 0, 255)), (pad, pad), m)
    return sh.filter(ImageFilter.GaussianBlur(r))


def mockup(slug: str, d: dict[str, Image.Image], cut: dict[str, list], bonus: bool) -> Image.Image:
    bg_key = "bg_bonus" if bonus and "bg_bonus" in d else "bg_base"
    canvas = cover(d[bg_key], W, H).convert("RGBA")
    rnd = random.Random(slug + str(bonus))

    hp, lp = cut.get("symbols_hp", []), cut.get("symbols_lp", [])
    pays, specials = hp[:4], hp[4:7]
    pool = pays * 2 + lp
    grid = [[rnd.choice(pool) for _ in range(3)] for _ in range(5)]
    if specials:
        grid[1][1] = specials[0]                 # wild
        grid[3][0] = specials[min(1, len(specials) - 1)]  # scatter
        if bonus:
            grid[0][2] = grid[2][0] = grid[4][1] = specials[0]
        else:
            grid[4][2] = specials[-1]

    # reel area: centred, leaves room for the logo on top
    # reel window: 5x3 square cells, frame rebuilt around it (9-slice with
    # thinner walls - ChatGPT frames come with a narrow window and heavy walls)
    cell = 196
    ww, wh = cell * 5, cell * 3
    frame = d.get("frame")
    if frame is not None:
        fr, (l, t, r, b) = reframe(frame.convert("RGBA"), ww, wh, wall=72)
        fx, fy = (W - fr.width) // 2, 250 + wh // 2 - (t + b) // 2
        win = (fx + l, fy + t, fx + r, fy + b)
    else:
        fr = None
        fx, fy = (W - ww) // 2, 250
        win = (fx, fy, fx + ww, fy + wh)
    # dark glass behind the reels
    panel = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(panel).rectangle(win, fill=(8, 6, 16, 225))
    canvas.alpha_composite(panel)

    x0, y0, x1, y1 = win
    pad = 0.04
    cw, ch = (x1 - x0) / 5, (y1 - y0) / 3
    for c in range(5):
        for rr in range(3):
            s = fit(grid[c][rr], int(cw * (1 - pad * 2)), int(ch * (1 - pad * 2)))
            paste_c(canvas, s, x0 + cw * (c + 0.5), y0 + ch * (rr + 0.5))
    if fr is not None:
        canvas.alpha_composite(shadow(fr), (fx - 36, fy - 26))
        canvas.alpha_composite(fr, (fx, fy))

    chars = cut.get("characters", [])
    if chars:
        hero = chars[1 if bonus and len(chars) > 1 else 0]
        hero = fit(hero, 420, 640)
        hx = 40 if not bonus else W - 40 - hero.width
        canvas.alpha_composite(shadow(hero, 24, 120), (hx - 48, H - hero.height - 70))
        canvas.alpha_composite(hero, (hx, H - hero.height - 30))

    logo = d.get("logo")
    if logo is not None:
        lg = fit(logo.convert("RGBA"), 640, 175)
        canvas.alpha_composite(shadow(lg, 14, 140), (round((W - lg.width) / 2) - 28, 100 - lg.height // 2 - 28))
        paste_c(canvas, lg, W // 2, 100)
    return canvas.convert("RGB")


def main(src_dir: str) -> None:
    files = sorted(Path(src_dir).glob("*.png"))
    games: dict[str, dict[str, Path]] = {}
    for f in files:
        key = next((k for k in FILES if f.name.startswith(k)), None)
        if key is None:
            print("unmapped:", f.name)
            continue
        slug, job = FILES[key]
        games.setdefault(slug, {})[job] = f

    (HERE / "mockups").mkdir(exist_ok=True)
    for slug, jobs in sorted(games.items()):
        src = HERE / "art" / slug / "src"
        cutd = HERE / "art" / slug / "cut"
        src.mkdir(parents=True, exist_ok=True)
        cutd.mkdir(parents=True, exist_ok=True)
        d, cut = {}, {}
        for job, f in jobs.items():
            shutil.copy2(f, src / f"{job}.png")
            d[job] = Image.open(f)
            if job in ("symbols_hp", "symbols_lp", "characters") and d[job].mode == "RGBA":
                items = cut_sheet(d[job], split_wide=job != "characters")
                if job == "symbols_hp" and len(items) < 7:
                    items = grid_cut(d[job], [4, 3])
                cut[job] = items
                for i, it in enumerate(items):
                    it.save(cutd / f"{job}_{i + 1}.png")
        missing = [j for j in ("logo", "symbols_hp", "symbols_lp", "characters", "frame",
                               "bg_base", "bg_bonus") if j not in d]
        for bonus in (False, True):
            if bonus and "bg_bonus" not in d:
                continue
            mockup(slug, d, cut, bonus).save(
                HERE / "mockups" / f"{slug}_{'bonus' if bonus else 'base'}.jpg", quality=90)
        print(f"{slug:18} cut hp={len(cut.get('symbols_hp', []))} lp={len(cut.get('symbols_lp', []))} "
              f"chars={len(cut.get('characters', []))} missing={missing}")


if __name__ == "__main__":
    main(sys.argv[1])
