from app.core.db import get_db
from app.engine.rng import RNGProvider, SecureRNG

__all__ = ["get_db", "get_rng"]


def get_rng() -> RNGProvider:
    """FastAPI dependency, overridable in tests for deterministic spins."""
    return SecureRNG()
