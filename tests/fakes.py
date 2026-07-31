class FakeRNG:
    """Deterministic RNGProvider stub for exact-value assertions in tests."""

    def __init__(self, values):
        self._values = iter(values)

    def randbelow(self, n: int) -> int:
        return next(self._values)
