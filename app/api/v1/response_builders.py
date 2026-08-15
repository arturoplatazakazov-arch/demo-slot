"""Engine/feature result -> response schema mapping, shared by both spin
orchestrations (spin_service.py, spin_avalanche.py). Pure formatting — no
state, no DB."""

from decimal import Decimal
from typing import Sequence

from app.api.v1 import schemas
from app.engine.types import AvalancheResult, CountWin, LineWin
from app.features.base import FeatureResult
from app.services.grid_format import to_frontend_grid


def line_wins_out(line_wins: Sequence[LineWin]) -> list[schemas.LineWinOut]:
    return [
        schemas.LineWinOut(
            payline=w.payline_index,
            symbol=w.symbol_code,
            count=w.count,
            amount=int(w.win_amount),
            positions=[schemas.CellPosOut(row=row, col=reel) for reel, row in w.positions],
        )
        for w in line_wins
    ]


def count_wins_out(count_wins: Sequence[CountWin]) -> list[schemas.CountWinOut]:
    return [
        schemas.CountWinOut(
            symbol=w.symbol_code,
            count=w.count,
            amount=int(w.win_amount),
            positions=[schemas.CellPosOut(row=row, col=reel) for reel, row in w.positions],
        )
        for w in count_wins
    ]


def free_spins_feature_out(
    *,
    triggered_now: bool,
    was_in_free_spins: bool,
    trigger_result: FeatureResult | None,
    remaining_after: int,
    round_total_win: Decimal,
    multiplier: int | None = None,
) -> schemas.FeatureOut | None:
    """The free-spins block of a SpinResponse: present on the triggering spin
    and on every spin inside the round, absent otherwise. `multiplier` is
    only reported by games with a session-wide accumulator (avalanche path)."""
    if not (triggered_now or was_in_free_spins):
        return None
    return schemas.FeatureOut(
        type="free_spins",
        triggered=triggered_now,
        spins_awarded=trigger_result.details.get("spins_awarded") if triggered_now else None,
        spins_remaining=remaining_after,
        total_win=int(round_total_win),
        multiplier=multiplier,
    )


def multiplier_wilds_out(details: dict | None) -> list[schemas.MultiplierWildOut]:
    if details is None:
        return []
    return [
        schemas.MultiplierWildOut(row=w["row"], col=w["reel"], multiplier=int(Decimal(w["multiplier"])))
        for w in details["wilds"]
    ]


def coin_multiplier_out(details: dict | None) -> schemas.CoinMultiplierOut | None:
    if details is None:
        return None
    return schemas.CoinMultiplierOut(
        multiplier_sum=int(Decimal(details["multiplier_sum"])),
        positions=[
            schemas.CoinMultiplierPositionOut(
                row=p["row"], col=p["reel"], value=int(Decimal(p["value"])), kind=p.get("kind")
            )
            for p in details["coin_positions"]
        ],
        applied=bool(details["applied"]),
    )


def hold_and_win_out(result) -> schemas.HoldAndWinOut | None:
    if result is None:
        return None
    def coin_out(c: dict) -> schemas.HoldAndWinLandedCoinOut:
        return schemas.HoldAndWinLandedCoinOut(
            row=c["row"], col=c["reel"], value=int(Decimal(c["value"])), kind=c.get("kind")
        )

    return schemas.HoldAndWinOut(
        triggered=True,
        initial=[coin_out(c) for c in result.details.get("initial", [])],
        respins=[
            schemas.HoldAndWinRespinOut(landed=[coin_out(c) for c in respin["landed"]])
            for respin in result.details["respins"]
        ],
        total_win=int(result.win_amount),
        full_grid=result.details["full_grid"],
    )


def wheel_of_fortune_out(result) -> schemas.WheelOfFortuneOut | None:
    if result is None:
        return None
    details = result.details
    return schemas.WheelOfFortuneOut(
        segment_index=details["segment_index"],
        prize_type=details["prize_type"],
        multiplier=details.get("multiplier"),
        win_amount=int(result.win_amount),
        segments=[schemas.WheelSegmentOut(**s) for s in details["segments"]],
    )


def avalanche_out(result: AvalancheResult) -> schemas.AvalancheOut:
    return schemas.AvalancheOut(
        steps=[
            schemas.CascadeStepOut(
                wins=[
                    schemas.CountWinOut(
                        symbol=w.symbol_code,
                        count=w.count,
                        amount=int(w.win_amount),
                        positions=[schemas.CellPosOut(row=row, col=reel) for reel, row in w.positions],
                    )
                    for w in step.wins
                ],
                step_multiplier=step.multiplier,
                step_win=int(step.step_win),
                grid_after=to_frontend_grid(step.grid_after),
                tokens_consumed=[
                    schemas.TokenConsumedOut(row=t.row, col=t.reel, value=t.value)
                    for t in step.tokens_consumed
                ],
                bombs_detonated=[
                    schemas.BombDetonationOut(
                        row=b.row,
                        col=b.reel,
                        cleared=[schemas.CellPosOut(row=row, col=reel) for reel, row in b.cleared],
                    )
                    for b in step.bombs_detonated
                ],
            )
            for step in result.steps
        ],
        total_win=int(result.total_win),
    )


def avalanche_win_breakdown(result: AvalancheResult) -> dict:
    """JSON-serializable audit breakdown for SpinRecord.win_breakdown."""
    return {
        "avalanche_steps": [
            {
                "multiplier": step.multiplier,
                "step_win": str(step.step_win),
                "wins": [
                    {"symbol": w.symbol_code, "count": w.count, "amount": str(w.win_amount)}
                    for w in step.wins
                ],
                "tokens_consumed": [
                    {"reel": t.reel, "row": t.row, "value": t.value} for t in step.tokens_consumed
                ],
                "bombs_detonated": [
                    {"reel": b.reel, "row": b.row, "cleared": list(b.cleared)} for b in step.bombs_detonated
                ],
            }
            for step in result.steps
        ],
    }
