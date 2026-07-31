import secrets
from typing import Protocol


class RNGProvider(Protocol):
    """Source of randomness for the engine. Swap the implementation (e.g. for
    a certified/lab-audited RNG, TZ §10) without touching engine code — the
    engine only ever depends on this interface, never on `secrets` directly.
    """

    def randbelow(self, n: int) -> int:
        """Return a uniformly random integer in [0, n)."""
        ...


class SecureRNG:
    """Default RNG: `secrets`, backed by `os.urandom` — cryptographically
    strong, unlike `random.Random` with a predictable/weak seed (TZ §10)."""

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        return secrets.randbelow(n)
