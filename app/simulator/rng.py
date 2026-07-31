"""Fast RNG for bulk simulation. TZ §10's cryptographic-RNG requirement is
about real-money spins (SecureRNG, app/engine/rng.py) — a math-validation
tool just needs statistically sound randomness, and secrets.randbelow is
~7x slower than random.Random in this environment, which matters when
running tens/hundreds of thousands of spins in one request."""

import random


class FastRNG:
    """random.Random-backed RNGProvider (duck-typed, no shared base class
    needed — app.engine.rng.RNGProvider is a Protocol)."""

    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        return self._random.randrange(n)
