"""Which game set the provider2 tools work on: P_SET=provider3 points every
script at provider3/ (its games.py and art/); default provider2."""
import importlib.util
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = os.environ.get('P_SET', 'provider2')
DIR = HERE.parent / NAME
_spec = importlib.util.spec_from_file_location(f'{NAME}_games', DIR / 'games.py')
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
GAMES = _mod.GAMES
