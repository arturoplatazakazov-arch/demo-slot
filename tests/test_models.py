import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import FeatureConfig, Game, GameConfig, Payline, Session, SimulationRun, SpinRecord, Symbol
from app.models.enums import FeatureType, GameConfigStatus, SimulationStatus, SymbolType


async def _make_full_config(db_session):
    game = Game(code="aphrodite", name="For the Love of Aphrodite")
    config = GameConfig(
        game=game,
        version=1,
        status=GameConfigStatus.ACTIVE.value,
        target_rtp=0.96,
        min_bet=0.20,
        max_bet=100,
        bet_step=0.20,
    )
    wild = Symbol(
        game_config=config,
        code="WILD",
        name="Wild",
        symbol_type=SymbolType.WILD.value,
        reel_weights=[2, 2, 2, 2, 2],
        paytable={"3": 5, "4": 25, "5": 100},
    )
    scatter = Symbol(
        game_config=config,
        code="SCAT",
        name="Scatter",
        symbol_type=SymbolType.SCATTER.value,
        reel_weights=[3, 3, 3, 3, 3],
        paytable={"3": 2, "4": 10, "5": 50},
    )
    payline = Payline(game_config=config, index=1, positions=[1, 1, 1, 1, 1])
    feature = FeatureConfig(
        game_config=config,
        feature_type=FeatureType.FREE_SPINS.value,
        enabled=True,
        params={"trigger_count": 3, "spins_awarded": 10},
    )
    db_session.add_all([game, config, wild, scatter, payline, feature])
    await db_session.commit()
    return game, config


async def test_full_entity_graph_round_trip(db_session):
    game, config = await _make_full_config(db_session)

    loaded = (await db_session.execute(select(GameConfig).where(GameConfig.id == config.id))).scalar_one()
    assert loaded.game_id == game.id
    assert len(loaded.symbols) == 2
    assert len(loaded.paylines) == 1
    assert len(loaded.feature_configs) == 1
    assert loaded.feature_configs[0].params["spins_awarded"] == 10
    assert loaded.symbols[0].reel_weights == [2, 2, 2, 2, 2]


async def test_session_and_spin_record(db_session):
    game, config = await _make_full_config(db_session)

    session = Session(game=game, balance=100, currency="USD")
    db_session.add(session)
    await db_session.commit()

    spin = SpinRecord(
        session=session,
        game_config_id=config.id,
        bet_amount=1,
        grid=[["WILD", "SCAT", "H1"], ["H1", "H1", "H1"], ["H1", "H1", "H1"], ["H1", "H1", "H1"], ["H1", "H1", "H1"]],
        win_amount=5,
        win_breakdown={"line_pay": 5, "count_pay": 0},
        features_triggered=[],
        rng_proof={"draws": [1, 2, 3, 4, 5]},
        balance_before=100,
        balance_after=105,
    )
    db_session.add(spin)
    await db_session.commit()

    loaded = (await db_session.execute(select(SpinRecord).where(SpinRecord.id == spin.id))).scalar_one()
    assert loaded.session_id == session.id
    assert float(loaded.win_amount) == 5
    assert loaded.win_breakdown["line_pay"] == 5


async def test_simulation_run(db_session):
    _, config = await _make_full_config(db_session)

    run = SimulationRun(
        game_config_id=config.id,
        num_spins=1_000_000,
        status=SimulationStatus.COMPLETED.value,
        params={"rng_seed": 42},
        results={"rtp": 0.958, "hit_frequency": 0.24},
    )
    db_session.add(run)
    await db_session.commit()

    loaded = (await db_session.execute(select(SimulationRun).where(SimulationRun.id == run.id))).scalar_one()
    assert loaded.results["rtp"] == pytest.approx(0.958)


async def test_duplicate_payline_index_rejected(db_session):
    game, config = await _make_full_config(db_session)

    duplicate = Payline(game_config=config, index=1, positions=[0, 0, 0, 0, 0])
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_duplicate_game_config_version_rejected(db_session):
    game, config = await _make_full_config(db_session)

    duplicate = GameConfig(
        game=game,
        version=1,
        status=GameConfigStatus.DRAFT.value,
        target_rtp=0.96,
        min_bet=0.20,
        max_bet=100,
        bet_step=0.20,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
