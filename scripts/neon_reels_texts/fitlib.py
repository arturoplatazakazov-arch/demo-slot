# Shared text drawing + fixed-size fit for the Neon Reels preview screens.
# Product rule (2026-11-12): the engine never resizes plaques or fonts per language, so every
# field gets ONE font size at which EN and every translation fit its box.
# Used by doc.py (texts table) and by ../neon_reels_screens.py (the screens themselves, in EN
# and in every language), so a string is measured exactly as it is drawn.
import os, re, sys, itertools
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from spine_screen_kit import hexc, vgrad, trim        # noqa: E402
from texts import TEXTS, FIELDS, WHERE, GROUPS        # noqa: E402
from translations import TR, LANGS                    # noqa: E402

F = os.path.join(HERE, 'fonts')
ARIAL_BLACK = '/System/Library/Fonts/Supplemental/Arial Black.ttf'

# --- the game: font and text styles exactly as neon_reels_screens.py draws them ----------------
GAME = dict(slug='neon-reels', xlsx='neon_reels_тексты.xlsx', hdr='#3A1466', tile=(27, 13, 61), sheet=(10, 6, 32))
FAM = {'luckiest': ('Luckiest Guy', 'luckiest-guy', ARIAL_BLACK)}   # family -> (name, file prefix, stand-in)
FAM_USE = {'luckiest': 'все тексты'}
GOLD = [(0, hexc('fff6b8')), (0.45, hexc('ffc928')), (1, hexc('ff7a00'))]
CYAN = [(0, hexc('e9ffff')), (0.5, hexc('5ff4ff')), (1, hexc('1aa8ff'))]
WHITE = [(0, hexc('ffffff')), (1, hexc('dff6ff'))]
_neon = dict(fam='luckiest', render='neon', sw=lambda px: max(2, px // 9), glow_r=lambda px: max(4, px // 5), step=1.0)
STYLES = {
    'cap': dict(_neon, fill=GOLD, stroke='2a0638', glow=None, slant=0.08),
    'sub': dict(_neon, fill=CYAN, stroke='0b0420', glow='1a6bff', slant=0.06),
    'tap': dict(_neon, fill=WHITE, stroke='12052a', glow='35e8ff', slant=0),
    # PSB art: FREE gold / SPINS cyan, slanted, no glow — approximated with the game font
    'fs_art': dict(_neon, fill=GOLD, fill_last=CYAN, stroke='2a0638', glow=None, slant=0.12),
}
# =========================================================================================
# Below: the same machinery as ../dirty_money_mafia_texts/doc.py, generalised to several
# font families / renderers (kit text_img, or the game's own variant) and height-driven slots.
# =========================================================================================
FILES = {fam: sorted((os.path.join(F, n) for n in os.listdir(F) if n.startswith(base + '-latin')),
                     key=lambda p: '-ext' in p) for fam, (_, base, _) in FAM.items()}   # latin, latin-ext
CMAPS = {p: set(TTFont(p).getBestCmap()) for fs in FILES.values() for p in fs}
_fc = {}


def fnt(path, size, wght=None):
    k = (path, size, wght)
    if k not in _fc:
        f = ImageFont.truetype(path, size)
        if wght:
            try: f.set_variation_by_axes([wght])
            except Exception: pass
        _fc[k] = f
    return _fc[k]


def has_glyph(ch, fam):
    return any(ord(ch) in CMAPS[p] for p in FILES[fam])


def font_for(ch, st, size):
    """Game font file that has the glyph (latin, then latin-ext), else the wide stand-in."""
    for p in FILES[st['fam']]:
        if ord(ch) in CMAPS[p]: return fnt(p, size, st.get('wght'))
    return fnt(FAM[st['fam']][2], size)


def _v(x, px):
    return x(px) if callable(x) else x


def text_img(text, st, size, fill):
    """The generator's text_img, but the font is picked per character."""
    sw, gr = _v(st['sw'], size), _v(st.get('glow_r') or 0, size)
    glow, shadow, slant, track = st.get('glow'), st.get('shadow'), st.get('slant', 0), st.get('track', 0)
    neon = st.get('render') == 'neon'
    pad = sw + gr * 3 + 12
    fs = [font_for(ch, st, size) for ch in text]
    if neon:   # neon_reels_screens.text_img: advance = glyph bbox right edge, space = 0.32 em
        widths = [f.getbbox(ch)[2] if ch != ' ' else size * 0.32 for f, ch in zip(fs, text)]
    else:
        widths = [f.getlength(ch) for f, ch in zip(fs, text)]
    w = int(sum(widths) + track * (len(text) - 1)) + pad * 2
    h = int(size * (1.35 if neon else 1.4)) + pad * 2
    mask, smask = Image.new('L', (w, h)), Image.new('L', (w, h))
    d, ds = ImageDraw.Draw(mask), ImageDraw.Draw(smask)
    x = pad
    for ch, f, cw in zip(text, fs, widths):
        d.text((x, pad), ch, font=f, fill=255)
        ds.text((x, pad), ch, font=f, fill=255, stroke_width=sw, stroke_fill=255)
        x += cw + track
    out = Image.new('RGBA', (w, h))
    if glow:
        gl = smask.filter(ImageFilter.GaussianBlur(gr)).point(lambda a: min(255, int(a * (1.6 if neon else 1.5))))
        out.paste(Image.new('RGBA', (w, h), hexc(glow)), (0, 0), gl)
    if shadow:
        sh = ImageChops.offset(smask.filter(ImageFilter.GaussianBlur(max(1, size // 18))), 0, max(2, size // 14))
        out.paste(Image.new('RGBA', (w, h), hexc(shadow, 200)), (0, 0), sh)
    out.paste(Image.new('RGBA', (w, h), hexc(st['stroke'])), (0, 0), smask)
    bb = mask.getbbox() or (0, 0, w, h)
    fill_im = Image.new('RGBA', (w, h)); fill_im.paste(vgrad((w, max(1, bb[3] - bb[1])), fill), (0, bb[1]))
    out.paste(fill_im, (0, 0), mask)
    if slant:
        out = out.transform(out.size, Image.AFFINE, (1, slant, -slant * h / 2, 0, 1, 0), Image.BICUBIC)
    return trim(out, thr=0 if neon else 2)


def hcat(ims, gap):
    w = sum(i.width for i in ims) + gap * (len(ims) - 1); h = max(i.height for i in ims)
    out = Image.new('RGBA', (w, h)); x = 0
    for im in ims: out.alpha_composite(im, (x, (h - im.height) // 2)); x += im.width + gap
    return out


def stack(ims, step):
    w = max(i.width for i in ims); h = step * (len(ims) - 1) + ims[-1].height
    out = Image.new('RGBA', (w, h))
    for k, im in enumerate(ims): out.alpha_composite(im, ((w - im.width) // 2, k * step))
    return out


_ic = {}
def draw(key, lines):
    """The block as the generator draws it (one text_img per line, centred stack)."""
    k = (key, tuple(lines))
    if k in _ic: return _ic[k]
    t = TEXTS[key]; st = STYLES[t['style']]; px = t['px']
    last = ' '.join(lines).split(' ')[-1] if st.get('fill_last') and len(' '.join(lines).split(' ')) > 1 else None
    ims = []
    for n, l in enumerate(lines):
        if last and n == len(lines) - 1 and l != last:      # 2-colour art title: last word in fill_last
            head = l[:-len(last)].rstrip()
            ims.append(hcat([text_img(head, st, px, st['fill']), text_img(last, st, px, st['fill_last'])], int(px * 0.12)))
        else:
            ims.append(text_img(l, st, px, st['fill_last'] if last and l == last and n == len(lines) - 1 else st['fill']))
    im = stack(ims, int(px * st.get('step', 1.0)))
    _ic[k] = im
    return im


GLUE = [(' / ', '⁠/⁠'), (' - ', '⁠-⁠'), ('= ', '=⁠'), (' =', '⁠=')]
FWD = re.compile(r'^(\d|\+\d|x\d|&$)')     # numbers / & stick to the next word,
BACK = {'ДЕЙІН', 'QƏDƏR', 'KADAR', 'GACHA', 'TAGACHA'}   # postpositions stay with their number
XM = re.compile(r'^x\d')                      # x-multipliers only to each other ("x2 x3 x5")


def options(s):
    """Line candidates: 1 line, splits at '·' (dot dropped), or word splits keeping glued groups."""
    if '·' in s:
        parts = [p.strip() for p in s.split('·')]
        return {1: [[s]], len(parts): [parts]}
    for a, b in GLUE: s = s.replace(a, b)
    toks, ws = s.split(' '), []
    for tk in toks:
        prev = ws[-1].split(' ')[-1] if ws else ''
        if ws and (FWD.match(prev) and not XM.match(prev) or XM.match(prev) and XM.match(tk) or tk in BACK):
            ws[-1] += ' ' + tk
        else:
            ws.append(tk)
    ws = [w.replace('⁠', ' ') for w in ws]
    out = {}
    for n in range(1, len(ws) + 1):
        out[n] = []
        for cut in itertools.combinations(range(1, len(ws)), n - 1):
            b = (0,) + cut + (len(ws),)
            out[n].append([' '.join(ws[b[i]:b[i + 1]]) for i in range(n)])
        punct = [c for c in out[n] if any(l.endswith((':', ',')) for l in c[:-1])]
        if punct: out[n] = punct            # "BUY BONUS: / 100x BET", "TAP, / TO ..." — break at punctuation
    return out


def approx_w(line, st, px):
    return sum(font_for(ch, st, px).getlength(ch) for ch in line)


def best(key, text, bw, bh, max_lines):
    """(scale fitting bw x bh, lines) over the narrowest split per line count."""
    t = TEXTS[key]; st = STYLES[t['style']]; out = None
    for n, cands in options(text).items():
        if n > max_lines or not cands: continue
        ls = min(cands, key=lambda L: max(approx_w(x, st, t['px']) for x in L))
        im = draw(key, ls); s = min(bw / im.width, bh / im.height)
        if out is None or s > out[0] + 1e-9: out = (s, ls)
    return out




def fields():
    """One record per text field: its box, the EN scale, and the one fixed scale that fits EN
    and every translation. `s` is design px per image px of draw(). Fields listed together in
    GROUPS (a row of cards) all take the smallest size of the group."""
    recs = []
    for screen, dev, key, slot_w, box_w, bh_spec, bone in FIELDS:
        t = TEXTS[key]; en = draw(key, t['en_lines'])
        s_en = slot_w(en.width, en.height) / en.width
        bw = box_w
        bh = bh_spec if bh_spec > 5 else en.height * s_en * bh_spec
        nl = t.get('max_lines', len(t['en_lines']) + 1)
        fixed, limit = s_en, 'en'
        for L in LANGS:
            sc, _ = best(key, TR[L][key], bw, bh, nl)
            if sc < fixed: fixed, limit = sc, L
        recs.append(dict(screen=screen, dev=dev, key=key, bone=bone, box_w=round(bw), box_h=round(bh),
                         en_px=round(t['px'] * s_en), px=round(t['px'] * fixed, 1), k=fixed / s_en,
                         limit=limit, s=fixed, s_en=s_en, nl=nl, bw=bw, bh=bh))
    for screen, dev, keys in GROUPS:
        grp = [r for r in recs if r['screen'] == screen and r['dev'] == dev and r['key'] in keys]
        if not grp: continue
        lead = min(grp, key=lambda r: r['s'])
        for r in grp:
            if r is not lead: r['limit'] = lead['limit']
            r['s'] = lead['s']
            r['px'], r['k'] = round(TEXTS[r['key']]['px'] * r['s'], 1), r['s'] / r['s_en']
    return recs


def lines_for(key, lang, rec):
    if lang == 'en': return TEXTS[key]['en_lines']
    return best(key, TR[lang][key], rec['bw'], rec['bh'], rec['nl'])[1]


def block(key, lang, rec):
    """(image, scale) for the field: the text at the field's fixed size."""
    return draw(key, lines_for(key, lang, rec)), rec['s']
