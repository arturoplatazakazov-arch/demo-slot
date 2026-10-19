"""RTP simulation for Olympus Thunder (GDD-04) on the real engine code.

    python scripts/olympus_thunder_rtp.py [spins=1000000] [buys=20000] [workers=8]
    OT_FS_ORB=4.4 python scripts/olympus_thunder_rtp.py ...   # try another FS orb weight

Natural play: every paid spin plus the whole free-spins round it opens counts
toward that spin's return (round cap 10 000x). Buys: forced service spin +
round, return divided by the SKU price.
"""

from __future__ import annotations

import os
import random
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.scatter_tumble_game import (  # noqa: E402
    TumbleGame,
    play_base_spin,
    play_free_spin,
    play_service_spin,
)
from app.seed import olympus_thunder as seed  # noqa: E402


class Rng:
    def __init__(self, seed_value: int):
        self._r = random.Random(seed_value)

    def randbelow(self, n: int) -> int:
        return self._r.randrange(n)


def _params() -> dict:
    params = dict(seed.PARAMS)
    weights = {k: dict(v) for k, v in params["weights"].items()}
    if os.environ.get("OT_FS_ORB"):
        weights["fs"]["orb"] = float(os.environ["OT_FS_ORB"])
    if os.environ.get("OT_SUPER_ORB"):
        weights["super"]["orb"] = float(os.environ["OT_SUPER_ORB"])
    params["weights"] = {k: list(v.items()) for k, v in weights.items()}
    return params


def _game() -> TumbleGame:
    return TumbleGame.from_params(_params(), seed.NUM_REELS, seed.NUM_ROWS)


def play_round(game: TumbleGame, rng: Rng, spins: int, super_mode: bool, so_far: Decimal, stats: Counter) -> Decimal:
    total_mult = 1
    paid = Decimal(0)
    remaining = spins
    played = 0
    while remaining > 0:
        remaining -= 1
        played += 1
        out = play_free_spin(game, rng, super_mode=super_mode, total_multiplier=total_mult, round_so_far=so_far + paid)
        total_mult = out.total_multiplier_after
        paid += out.paid
        stats["fs_jackpot"] += float(out.jackpot.pay) if out.jackpot else 0
        if out.fs_awarded:
            remaining += out.fs_awarded
            stats["retriggers"] += 1
        if out.capped:
            stats["capped"] += 1
            break
    stats["rounds"] += 1
    stats["round_spins"] += played
    stats["final_mult"] += total_mult
    stats["final_mult_sq"] += total_mult * total_mult
    stats["round_win"] += float(paid)
    return paid


def natural(args) -> Counter:
    seed_value, n = args
    game = _game()
    rng = Rng(seed_value)
    s = Counter()
    for _ in range(n):
        out = play_base_spin(game, rng)
        win = out.paid
        s["base"] += float(min(out.series_pay, out.paid))
        s["scatter"] += float(out.scatter_pay)
        if out.series_pay > 0:
            s["hits"] += 1
        if out.orb_sum:
            s["orb_spins"] += 1
        if out.jackpot:
            s["jackpot"] += float(out.jackpot.pay)
            s["wheel"] += 1
            s[f"jp_{out.jackpot.tier}"] += 1
        if out.fs_awarded:
            s["triggers"] += 1
            fs = play_round(game, rng, out.fs_awarded, False, out.paid, s)
            s["fs"] += float(fs)
            win += fs
        if win == 0:
            s["b_0"] += 1
        else:
            for edge in (1, 2, 5, 10, 20, 50, 100, 250, 1000, 10**9):
                if win <= edge:
                    s[f"b_{edge}"] += 1
                    break
        s["win"] += float(win)
        s["max"] = max(s["max"], float(win))
    s["spins"] = n
    return s


def bought(args) -> Counter:
    seed_value, n, buy_id = args
    game = _game()
    rng = Rng(seed_value)
    product = game.product(buy_id)
    s = Counter()
    for _ in range(n):
        out = play_service_spin(game, product, rng)
        win = out.paid
        if product.kind != "jackpot":
            win += play_round(game, rng, out.fs_awarded, product.kind == "super_free_spins", Decimal(0), s)
        s["win"] += float(win)
        s["max"] = max(s["max"], float(win))
    s["buys"] = n
    s["cost"] = float(product.cost) * n
    return s


def _merge(parts: list[Counter]) -> Counter:
    total = Counter()
    for p in parts:
        mx = max(total.get("max", 0), p.get("max", 0))
        total.update(p)
        total["max"] = mx
    return total


def main() -> None:
    spins = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
    buys = int(sys.argv[2]) if len(sys.argv) > 2 else 20_000
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    with ProcessPoolExecutor(workers) as pool:
        chunk = spins // workers
        s = _merge(list(pool.map(natural, [(1000 + i, chunk) for i in range(workers)])))
        n = s["spins"]
        print(f"natural {n} spins: RTP {s['win'] / n:.4f}  base {s['base'] / n:.4f}  scatter {s['scatter'] / n:.4f}"
              f"  fs {s['fs'] / n:.4f}  jackpot {(s['jackpot'] + s['fs_jackpot']) / n:.4f}")
        print(f"  hit {s['hits'] / n:.3f}  orb spins {s['orb_spins'] / n:.3f}  FS 1/{n / max(1, s['triggers']):.0f}"
              f"  wheel 1/{n / max(1, s['wheel']):.0f}  max {s['max']:.0f}x")
        if s["rounds"]:
            r = s["rounds"]
            print(f"  FS: avg win {s['round_win'] / r:.1f}x  avg len {s['round_spins'] / r:.1f}"
                  f"  avg final mult {s['final_mult'] / r:.1f}  retrigger {s['retriggers'] / r:.2f}/round")
        dist = "  ".join(f"<={k[2:]}:{s[k] / n * 100:.2f}%" for k in sorted((k for k in s if k.startswith("b_")), key=lambda k: int(k[2:])))
        print("  dist", dist)
        for buy_id in ("free_spins", "super_free_spins", "jackpot_chance"):
            chunk = buys // workers
            b = _merge(list(pool.map(bought, [(5000 + i, chunk, buy_id) for i in range(workers)])))
            avg = b["win"] / b["buys"]
            extra = ""
            if b["rounds"]:
                extra = f"  avg final mult {b['final_mult'] / b['rounds']:.1f}"
            print(f"buy {buy_id}: avg {avg:.1f}x  RTP {b['win'] / b['cost']:.4f}  max {b['max']:.0f}x{extra}")


if __name__ == "__main__":
    main()
