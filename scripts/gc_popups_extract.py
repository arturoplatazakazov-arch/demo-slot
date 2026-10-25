"""Cut the popups out of the designer's PSB (Desk_Gangsta_Slot_F.psb, group
"Popup's"): every visible leaf layer of each popup as a PNG at its own bbox,
bottom to top, + layout.json (name, file, bbox, opacity, kind; type layers
keep their text — they are drawn by code, not baked). Also a flat reference
composite of each popup. Run with a python that has psd-tools.
Usage: python scripts/gc_popups_extract.py <file.psb> <out_dir>"""
import json, os, re, sys
from psd_tools import PSDImage

PSB, OUT = sys.argv[1], sys.argv[2]
POPUPS = ['Big_win', 'Mega_Win', 'Epic_Win', 'Buy Free Spins', 'bonus_spins_win', 'bonus_spins_total_win']
psd = PSDImage.open(PSB)
root = next(l for l in psd if l.name == "Popup's")
os.makedirs(OUT, exist_ok=True)
summary = {}
for gname in POPUPS:
    g = next(l for l in root if l.name == gname)
    slug = re.sub(r'[^a-z0-9]+', '_', gname.lower()).strip('_')
    d = os.path.join(OUT, slug); os.makedirs(d, exist_ok=True)
    layers, used = [], {}

    def walk(group, path):
        for l in group:  # psd-tools iterates bottom -> top
            if not l.visible: continue
            if l.is_group():
                walk(l, path + [l.name]); continue
            base = re.sub(r'[^a-z0-9]+', '_', l.name.lower()).strip('_') or 'layer'
            used[base] = used.get(base, 0) + 1
            name = base if used[base] == 1 else f'{base}_{used[base]}'
            entry = {'name': name, 'psd': l.name, 'group': '/'.join(path), 'kind': l.kind,
                     'bbox': list(l.bbox), 'opacity': l.opacity / 255}
            if l.kind == 'type':
                entry['text'] = l.text
                try:
                    ss = l.engine_dict['StyleRun']['RunArray'][0]['StyleSheet']['StyleSheetData']
                    entry['font_size'] = float(ss.get('FontSize'))
                except Exception:
                    pass
            if l.kind == 'solidcolorfill':
                entry['file'] = None
            else:
                im = l.topil()
                if im is None: continue
                fn = f'{name}.png'
                im.convert('RGBA').save(os.path.join(d, fn))
                entry['file'] = fn
            layers.append(entry)

    walk(g, [])
    json.dump({'popup': gname, 'layers': layers}, open(os.path.join(d, 'layout.json'), 'w'), indent=1, ensure_ascii=False)
    # reference: the popup alone, flattened by psd-tools
    def only(layer):
        p = layer
        while p is not None:
            if p is g: return True
            p = p.parent
        return False
    try:
        ref = psd.composite(layer_filter=lambda l: (l.visible or l is g) and only(l) or l is g, force=True)
        ref.save(os.path.join(d, '_reference.png'))
    except Exception as e:
        print('ref failed', gname, e)
    summary[slug] = [(e['name'], e['kind'], e['bbox']) for e in layers]
    print(slug, len(layers), 'layers')
