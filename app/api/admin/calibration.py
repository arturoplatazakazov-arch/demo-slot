"""Symbol position calibration — per-symbol {dx, dy} pixel nudges for two
independently-positioned layers of a resting grid symbol: 'static' (the
resting <img>) and 'anim' (the win-animation's Spine anchor). Written by
Anim Lab's "Калибровать" button (front/js/anim-lab.js) and read by every
game's front/js/slot-calibration.js at startup.

Plain JSON on disk (front/calibration.json), not a DB table, mirroring
builder.py's manifest pattern (front/builder/<slug>.spec.json) — this is a
display-nudge dev tool, not versioned math/paytable data, and staying
file-based means it works the same for both DB-seeded games
(amys-fruit-farm/east-discovery/party-of-goods) and builder-created games,
with zero Alembic migration needed. Also, unlike GameConfig, front/*.html is
served as plain static files independent of this backend — writing straight
into front/calibration.json means every game's own page can read the
current calibration via a plain same-origin fetch, no backend round-trip
(and no backend dependency) needed just to *play* with a calibrated demo."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# app/api/admin/calibration.py -> parents[3] is the repo root.
FRONT_DIR = Path(__file__).resolve().parents[3] / "front"
CALIBRATION_PATH = FRONT_DIR / "calibration.json"

router = APIRouter(prefix="/calibration")


class Offset(BaseModel):
    dx: float = 0
    dy: float = 0


def _load() -> dict:
    if not CALIBRATION_PATH.exists():
        return {}
    return json.loads(CALIBRATION_PATH.read_text())


def _save(data: dict) -> None:
    CALIBRATION_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


@router.get("/{game}")
def get_game_calibration(game: str) -> dict:
    """Every symbol's calibration for one game, e.g. {"blueberry": {"static": {"dx": -8, "dy": 0}}}."""
    return _load().get(game, {})


@router.put("/{game}/{code}/{kind}")
def set_calibration(game: str, code: str, kind: str, offset: Offset) -> dict:
    if kind not in ("static", "anim"):
        raise HTTPException(status_code=400, detail="kind must be 'static' or 'anim'")
    data = _load()
    data.setdefault(game, {}).setdefault(code, {})[kind] = {"dx": offset.dx, "dy": offset.dy}
    _save(data)
    return data[game][code][kind]


@router.delete("/{game}/{code}/{kind}")
def clear_calibration(game: str, code: str, kind: str) -> dict:
    data = _load()
    symbol = data.get(game, {}).get(code, {})
    if kind in symbol:
        del symbol[kind]
        if not symbol:
            del data[game][code]
        if not data[game]:
            del data[game]
        _save(data)
    return {"ok": True}
