# Generates every bitmap the preview-screen skeletons need into gfx/.
import os, math, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
S = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(S, 'gfx'); P = os.path.join(S, 'parts')
A = '/Users/arturkasian/demo_slot/front/img/amys-fruit-farm'
LG = os.path.join(S, 'fonts/luckiest-guy-latin-fe2ede07.ttf')
FR = os.path.join(S, 'fonts/fredoka-latin-849e3a33.ttf')

def save(im, name): im.save(os.path.join(G, name + '.png'))

def font(path, size, wght=None):
    f = ImageFont.truetype(path, size)
    if wght: f.set_variation_by_axes([wght])
    return f

def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def styled(lines, size, *, fnt=LG, wght=None, grad=((255, 248, 170), (255, 196, 30), (232, 112, 0)),
           stroke=(74, 30, 4), sw=None, shadow=6, spacing=0.05, line_h=1.0, align='center'):
    """Gold-gradient game-title text: gradient fill, thick dark stroke, drop shadow."""
    if isinstance(lines, str): lines = lines.split('\n')
    f = font(fnt, size, wght)
    sw = sw if sw is not None else max(2, round(size * 0.11))
    lh = int(size * line_h)
    widths = [f.getlength(l) + spacing * size * max(0, len(l) - 1) for l in lines]
    W = int(max(widths) + sw * 2 + shadow + 16); H = int(lh * len(lines) + size * 0.35 + sw * 2 + shadow + 16)
    def draw_text(dr, fill, stroke_w, off=(0, 0), col=None):
        for i, l in enumerate(lines):
            x = (W - shadow - widths[i]) / 2 if align == 'center' else sw + 8
            y = 8 + sw + i * lh
            for ch in l:
                dr.text((x + off[0], y + off[1]), ch, font=f, fill=col or fill, stroke_width=stroke_w, stroke_fill=col or fill)
                x += f.getlength(ch) + spacing * size
    # outline + shadow
    base = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(base)
    draw_text(d, None, sw, (shadow * 0.6, shadow), (0, 0, 0, 150))
    base = base.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(base); draw_text(d, None, sw, (0, 0), stroke + (255,))
    # gradient fill masked by glyphs
    mask = Image.new('L', (W, H)); draw_text(ImageDraw.Draw(mask), None, 0, (0, 0), 255)
    gr = Image.new('RGBA', (W, H))
    px = gr.load()
    for y in range(H):
        # per-line vertical gradient
        t = ((y - 8 - sw) % lh) / (size * 1.0)
        t = min(1, max(0, t))
        c = lerp(grad[0], grad[1], t / 0.5) if t < 0.5 else lerp(grad[1], grad[2], (t - 0.5) / 0.5)
        for x in range(W): px[x, y] = c + (255,)
    base.paste(gr, (0, 0), mask)
    # soft top highlight
    hl = Image.new('L', (W, H)); draw_text(ImageDraw.Draw(hl), None, 0, (0, -max(1, size // 22)), 255)
    hl = Image.fromarray((np.asarray(mask).astype(int) - np.asarray(hl).astype(int)).clip(0, 255).astype(np.uint8))
    white = Image.new('RGBA', (W, H), (255, 255, 235, 200)); base.paste(white, (0, 0), hl.filter(ImageFilter.GaussianBlur(0.6)))
    return base.crop(base.getbbox())

def body(lines, size, color=(255, 250, 235), stroke=(60, 26, 4), wght=650, line_h=1.18, hi=None):
    """Description copy: rounded bold Fredoka, cream with a brown stroke. `hi` words are tinted gold."""
    if isinstance(lines, str): lines = lines.split('\n')
    f = font(FR, size, wght); sw = max(2, round(size * 0.14)); lh = int(size * line_h)
    widths = [f.getlength(l) for l in lines]
    W = int(max(widths) + sw * 2 + 20); H = int(lh * len(lines) + size * 0.4 + sw * 2 + 20)
    im = Image.new('RGBA', (W, H)); sh = Image.new('RGBA', (W, H))
    ds, d = ImageDraw.Draw(sh), ImageDraw.Draw(im)
    hi = set(hi or [])
    for i, l in enumerate(lines):
        x = (W - widths[i]) / 2; y = 10 + sw + i * lh
        ds.text((x + 2, y + 4), l, font=f, fill=(0, 0, 0, 170), stroke_width=sw, stroke_fill=(0, 0, 0, 170))
        for w in l.split(' '):
            col = (255, 206, 48) if w.strip(',.!') in hi else color
            d.text((x, y), w, font=f, fill=col, stroke_width=sw, stroke_fill=stroke)
            x += f.getlength(w + ' ')
    sh = sh.filter(ImageFilter.GaussianBlur(2)); sh.alpha_composite(im)
    return sh.crop(sh.getbbox())

def radial(size, stops, name):
    """Soft radial blob; stops = [(r 0..1, alpha 0..255)]."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.hypot(x - size / 2 + .5, y - size / 2 + .5) / (size / 2)
    a = np.interp(r, [s[0] for s in stops], [s[1] for s in stops])
    im = np.zeros((size, size, 4), np.uint8); im[..., :3] = 255; im[..., 3] = a.clip(0, 255)
    save(Image.fromarray(im), name)

def sparkle(size, name):
    """Four-point star flare with a hot core (drawn white, tinted per slot)."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = size / 2 - .5; dx, dy = np.abs(x - c) / c, np.abs(y - c) / c
    arm = np.maximum(np.exp(-(dy / 0.05) ** 2) * (1 - dx).clip(0) ** 1.6, np.exp(-(dx / 0.05) ** 2) * (1 - dy).clip(0) ** 1.6)
    d2 = (dx * 0.7071 + dy * 0.7071); dd = np.abs(dx - dy) / 1.4142
    diag = np.exp(-(dd / 0.035) ** 2) * (1 - np.hypot(dx, dy) / 0.75).clip(0) ** 2 * 0.55
    core = np.exp(-(np.hypot(dx, dy) / 0.16) ** 2)
    a = np.clip(arm + diag + core, 0, 1)
    im = np.zeros((size, size, 4), np.uint8); im[..., :3] = 255; im[..., 3] = (a * 255).astype(np.uint8)
    save(Image.fromarray(im), name)

def main():
    os.makedirs(G, exist_ok=True)
    # --- straight copies of game art -------------------------------------------------
    for src, name in [('img/bg_base_game.png', 'bg_base_desk'), ('img/Mob_Base_bg.png', 'bg_base_mob'),
                      ('img/bg_freespins.png', 'bg_bonus_desk'), ('img/Mob_Bonus_bg.png', 'bg_bonus_mob'),
                      ('img/amy_base.png', 'amy_base'), ('img/amy_freespins.png', 'amy_bonus'),
                      ('img/logo_amys_fruit_farm.png', 'logo'), ('Export/Wild/static.png', 'icon_wild'),
                      ('Export/Scatter/static.png', 'icon_scatter')]:
        save(Image.open(os.path.join(A, src)).convert('RGBA'), name)
    for src, name in [('buy_free_spins_rays1', 'rays1'), ('buy_free_spins_rays2', 'rays2'),
                      ('bonus_spins_total_win_input_copy', 'plaque'), ('bonus_spins_win_bg', 'honey_frame')]:
        save(Image.open(os.path.join(P, src + '.png')), name)
    for i, src in enumerate(['coins-L_1', 'coins-L_2', 'coins-L_3', 'coins-R_2', 'coins-R_3', 'coins_bot_2', 'coins_bot_3', 'clins_top_5']):
        save(Image.open(os.path.join(P, 'bonus_spins_total_win_' + src + '.png')), f'coin{i + 1}')
    # logo glow: blurred alpha silhouette
    lg = Image.open(os.path.join(A, 'img/logo_amys_fruit_farm.png')).convert('RGBA')
    pad = 60; m = Image.new('L', (lg.width + pad * 2, lg.height + pad * 2)); m.paste(lg.getchannel('A'), (pad, pad))
    m = m.filter(ImageFilter.GaussianBlur(22)); m = m.point(lambda v: min(255, int(v * 1.6)))
    gl = Image.new('RGBA', m.size, (255, 255, 255, 0)); gl.putalpha(m); save(gl, 'logo_glow')
    # buy-bonus sign with its label baked in (in-game it is a DOM overlay)
    sign = Image.open(os.path.join(A, 'img/sign_buy_bonus.png')).convert('RGBA')
    lab = styled('BUY\nBONUS', 64, grad=((255, 250, 205), (255, 214, 80), (240, 150, 10)), line_h=0.95, shadow=4)
    lab = lab.resize((int(lab.width * 0.9), int(lab.height * 0.9)), Image.LANCZOS)
    sign.alpha_composite(lab, ((sign.width - lab.width) // 2, int(sign.height * 0.48) - lab.height // 2))
    save(sign, 'icon_buy')
    # --- copy ------------------------------------------------------------------------
    save(styled('EXPANDING WILD', 50), 't_wild')
    save(styled('FREE SPINS', 50), 't_fs')
    save(styled('BUY BONUS', 50), 't_buy')
    save(body('WILD grows to fill the whole\nreel, then walks one reel to\nthe right on every spin', 30, hi=['WILD']), 'd_wild_desk')
    save(body('3, 4 or 5 SCATTERS award\n10, 15 or 20 FREE SPINS.\nScatters retrigger the bonus!', 30, hi=['SCATTERS', 'FREE', 'SPINS.', '10,', '15', '20']), 'd_fs_desk')
    save(body('Skip the wait: buy\nFREE SPINS straight away\nfor 100x your bet', 30, hi=['FREE', 'SPINS', '100x']), 'd_buy_desk')
    save(body('WILD fills the whole reel,\nthen walks one reel right\non every spin', 30, hi=['WILD']), 'd_wild_mob')
    save(body('3, 4 or 5 SCATTERS award\n10, 15 or 20 FREE SPINS.\nScatters retrigger!', 30, hi=['SCATTERS', 'FREE', 'SPINS.', '10,', '15', '20']), 'd_fs_mob')
    save(body('Buy FREE SPINS straight\naway for 100x your bet', 30, hi=['FREE', 'SPINS', '100x']), 'd_buy_mob')
    save(styled('CLICK ANYWHERE TO CONTINUE', 44, grad=((255, 255, 240), (255, 236, 160), (255, 200, 70))), 'cont_desk')
    save(styled('TAP ANYWHERE\nTO CONTINUE', 50, grad=((255, 255, 240), (255, 236, 160), (255, 200, 70))), 'cont_mob')
    save(styled('CLICK ANYWHERE TO START', 44, grad=((255, 255, 240), (255, 236, 160), (255, 200, 70))), 'start_desk')
    save(styled('TAP ANYWHERE\nTO START', 50, grad=((255, 255, 240), (255, 236, 160), (255, 200, 70))), 'start_mob')
    save(styled('CONGRATULATIONS!', 84), 't_congrats')
    save(styled('YOU WON', 46, grad=((255, 250, 225), (255, 222, 120), (246, 170, 30))), 't_youwon')
    save(styled('FREE SPINS', 50, grad=((255, 250, 225), (255, 222, 120), (246, 170, 30))), 't_freespins')
    save(body('WILDS EXPAND & WALK', 34, hi=['WILDS']), 'b_wild')
    save(body('3+ SCATTERS = MORE SPINS', 34, hi=['SCATTERS']), 'b_fs')
    for d in '0123456789':
        save(styled(d, 150, grad=((255, 252, 215), (255, 206, 40), (226, 96, 0)), shadow=8, spacing=0), 'n' + d)
    # --- fx ----------------------------------------------------------------------------
    radial(256, [(0, 255), (0.25, 190), (0.6, 60), (1, 0)], 'glow')
    radial(64, [(0, 255), (0.5, 120), (1, 0)], 'dot')
    sparkle(128, 'sparkle')
    v = 256; y, x = np.mgrid[0:v, 0:v].astype(np.float32)
    r = np.hypot((x - v / 2) / (v / 2), (y - v / 2) / (v / 2))
    a = (np.clip((r - 0.45) / 0.75, 0, 1) ** 1.5 * 235)
    im = np.zeros((v, v, 4), np.uint8); im[..., 3] = a.astype(np.uint8); save(Image.fromarray(im), 'vignette')
    save(Image.new('RGBA', (8, 8), (255, 255, 255, 255)), 'white')

if __name__ == '__main__':
    main()
