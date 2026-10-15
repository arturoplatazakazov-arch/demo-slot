"""Copy generated Provider 2 games into another checkout (the pages worktree).

    python3 provider2/sync.py <dest_repo_root> <slug ...|all>
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from pset import DIR, GAMES, NAME  # noqa: E402

dest = Path(sys.argv[1])
slugs = list(GAMES) if sys.argv[2:] == ['all'] else sys.argv[2:]
files = ['front/js/provider2-fx.js', f'app/seed/{NAME}.py', f'tests/test_api_spin_{NAME}.py']
for s in slugs:
    seed = s.replace('-', '_')
    files += [f'front/{s}.html', f'front/css/{s}.css', f'app/seed/{seed}.py']
    for d in (f'front/js/{s}', f'front/img/{s}'):
        tgt = dest / d
        if tgt.exists():
            shutil.rmtree(tgt)
        shutil.copytree(ROOT / d, tgt, ignore=shutil.ignore_patterns('layout.json'))
for f in files:
    (dest / f).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / f, dest / f)
print('synced', len(slugs), 'games ->', dest)
