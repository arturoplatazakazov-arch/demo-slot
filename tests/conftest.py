import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base


@pytest.fixture
async def db_session():
    """In-memory SQLite for model-level tests: fast and isolated, no external
    service needed. Real Postgres-specific behaviour (JSONB, migrations) is
    exercised separately via Alembic against Postgres, not here."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def api_client():
    """Integration-test client for the stage-5 API: hits the real Postgres
    configured in .env (same DB the dev server uses), with the demo game
    seeded up front. ASGITransport doesn't run FastAPI's lifespan, so the
    seed that normally happens on app startup is triggered explicitly here."""
    from app.core.db import AsyncSessionLocal
    from app.seed.amys_fruit_farm import get_or_seed_active_config as get_or_seed_amys_fruit_farm
    from app.seed.east_discovery import get_or_seed_active_config as get_or_seed_east_discovery
    from app.seed.party_of_goods import get_or_seed_active_config as get_or_seed_party_of_goods

    async with AsyncSessionLocal() as db:
        await get_or_seed_amys_fruit_farm(db)
        await get_or_seed_east_discovery(db)
        await get_or_seed_party_of_goods(db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def set_rng():
    """Force deterministic spins for one test via dependency override;
    cleaned up automatically afterward."""
    from app.api.deps import get_rng
    from tests.fakes import FakeRNG

    def _set(values):
        app.dependency_overrides[get_rng] = lambda: FakeRNG(list(values))

    yield _set
    app.dependency_overrides.pop(get_rng, None)
