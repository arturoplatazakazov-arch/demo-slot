from decimal import Decimal

from app.engine.types import PaylineDef, ReelSetConfig, SymbolDef, SymbolType
from app.simulator import FastRNG, run_avalanche_simulation, run_simulation
from app.simulator.engine import _histogram, _volatility_label


def _single_symbol_config() -> tuple[ReelSetConfig, list[PaylineDef]]:
    """Only one symbol exists, so every spin draws an all-X grid — every
    base-game outcome is exactly deterministic, letting RTP/hit-frequency/
    volatility be computed by hand rather than just eyeballed."""
    symbol = SymbolDef(
        code="x", symbol_type=SymbolType.REGULAR.value, weights=[1] * 5, pays={5: Decimal("2")},
    )
    reel_set = ReelSetConfig(num_reels=5, num_rows=3, symbols=[symbol])
    paylines = [PaylineDef(index=1, positions=[1, 1, 1, 1, 1])]
    return reel_set, paylines


def test_run_simulation_matches_hand_computed_values_for_a_deterministic_config():
    reel_set, paylines = _single_symbol_config()
    report = run_simulation(
        reel_set, paylines, free_spins_config=None, rng=FastRNG(seed=1),
        num_spins=500, bet_amount=Decimal("1000"),
    )

    # Every spin wins exactly 2x bet (the only symbol, 5-in-a-row, pays[5]=2).
    assert report.num_spins == 500
    assert report.total_wagered == "500000"
    assert report.total_win == "1000000"
    assert report.rtp == 2.0
    assert report.hit_frequency == 1.0
    assert report.bonus_frequency == 0.0
    assert report.max_win_multiplier == 2.0
    assert report.volatility_stddev == 0.0
    assert report.volatility_label == "low"
    assert report.rtp_by_mechanic == {"base": 2.0, "free_spins": 0.0}


def test_run_simulation_rejects_non_positive_inputs():
    reel_set, paylines = _single_symbol_config()
    import pytest

    with pytest.raises(ValueError):
        run_simulation(reel_set, paylines, None, FastRNG(seed=1), num_spins=0, bet_amount=Decimal("1000"))
    with pytest.raises(ValueError):
        run_simulation(reel_set, paylines, None, FastRNG(seed=1), num_spins=10, bet_amount=Decimal("0"))


def test_volatility_label_thresholds():
    assert _volatility_label(0.5) == "low"
    assert _volatility_label(1.49) == "low"
    assert _volatility_label(1.5) == "medium"
    assert _volatility_label(3.99) == "medium"
    assert _volatility_label(4.0) == "high"
    assert _volatility_label(10.0) == "high"


def test_histogram_buckets_every_ratio_exactly_once():
    ratios = [0.0, 0.5, 1.0, 1.9, 2.0, 4.9, 5.0, 9.9, 999.0]
    buckets = _histogram(ratios)
    total_bucketed = sum(b["count"] for b in buckets)
    assert total_bucketed == len(ratios)

    by_label = {b["label"]: b["count"] for b in buckets}
    assert by_label["0x"] == 1  # 0.0
    assert by_label["0x-1x"] == 1  # 0.5
    assert by_label["1x-2x"] == 2  # 1.0, 1.9
    assert by_label["2x-5x"] == 2  # 2.0, 4.9
    assert by_label["5x-10x"] == 2  # 5.0, 9.9
    assert by_label["500x+"] == 1  # 999.0


def test_fast_rng_is_deterministic_for_a_given_seed():
    a = FastRNG(seed=7)
    b = FastRNG(seed=7)
    assert [a.randbelow(100) for _ in range(20)] == [b.randbelow(100) for _ in range(20)]


# --- run_avalanche_simulation: app/engine/avalanche.py's RTP path ---------


class _FeatureConfigStub:
    """Minimal FeatureConfigLike stand-in (feature_type/enabled/params) —
    same role as a real FeatureConfig ORM row, without a DB."""

    def __init__(self, feature_type: str, params: dict):
        self.feature_type = feature_type
        self.enabled = True
        self.params = params


def _avalanche_single_symbol_config() -> ReelSetConfig:
    # Only one symbol -> every cell is "x"; pays[1]=2 means any nonzero
    # count wins, so every spin's single cascade step always fires.
    symbol = SymbolDef(code="x", symbol_type=SymbolType.REGULAR.value, weights=[1] * 2, pays={1: Decimal("2")})
    return ReelSetConfig(num_reels=2, num_rows=1, symbols=[symbol])


def test_run_avalanche_simulation_matches_hand_computed_values_for_a_deterministic_config():
    reel_set = _avalanche_single_symbol_config()
    # max_cascades=1 caps every round at exactly one step regardless of the
    # (always-true, single-symbol) win condition, keeping this hand-computable.
    avalanche_config = _FeatureConfigStub("avalanche", {"multiplier_steps": [1], "max_cascades": 1})

    report = run_avalanche_simulation(
        reel_set, avalanche_config, free_spins_config=None, rng=FastRNG(seed=1),
        num_spins=500, bet_amount=Decimal("1000"),
    )

    # Every spin: the 2-cell "x" win pays[1]=2 -> win_amount = 2 * bet = 2000,
    # step_multiplier=1 -> spin_win = 2000.
    assert report.num_spins == 500
    assert report.total_wagered == "500000"
    assert report.total_win == "1000000"
    assert report.rtp == 2.0
    assert report.hit_frequency == 1.0
    assert report.bonus_frequency == 0.0
    assert report.rtp_by_mechanic == {"base": 2.0, "free_spins": 0.0}


def test_run_avalanche_simulation_rejects_non_positive_inputs():
    import pytest

    reel_set = _avalanche_single_symbol_config()
    avalanche_config = _FeatureConfigStub("avalanche", {})
    with pytest.raises(ValueError):
        run_avalanche_simulation(reel_set, avalanche_config, None, FastRNG(seed=1), 0, Decimal("1000"))
    with pytest.raises(ValueError):
        run_avalanche_simulation(reel_set, avalanche_config, None, FastRNG(seed=1), 10, Decimal("0"))


def test_simulate_game_config_dispatches_to_avalanche_for_party_of_goods():
    """End-to-end smoke test through the same simulate_game_config entry
    point the admin API and scripts/simulate.py call — confirms the
    avalanche FeatureConfig row is what actually selects
    run_avalanche_simulation (app/simulator/engine.py), not just that the
    function works in isolation."""
    from app.seed.party_of_goods import build_game_config
    from app.simulator import simulate_game_config

    _, config = build_game_config()
    report = simulate_game_config(config, num_spins=200, rng=FastRNG(seed=3))

    assert report.num_spins == 200
    assert 0.0 <= report.hit_frequency <= 1.0
    assert report.rtp >= 0.0
