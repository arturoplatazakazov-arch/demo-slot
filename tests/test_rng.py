import pytest

from app.engine.rng import SecureRNG


def test_randbelow_stays_in_range():
    rng = SecureRNG()
    for _ in range(2000):
        value = rng.randbelow(7)
        assert 0 <= value < 7


def test_randbelow_rejects_non_positive_n():
    rng = SecureRNG()
    with pytest.raises(ValueError):
        rng.randbelow(0)
    with pytest.raises(ValueError):
        rng.randbelow(-1)


def test_randbelow_can_reach_both_ends_of_the_range():
    # Statistical, not exact: over enough draws a small range must be hit
    # fully. n=2 gives a fair coin flip, so both outcomes should show up.
    rng = SecureRNG()
    seen = {rng.randbelow(2) for _ in range(500)}
    assert seen == {0, 1}


def test_distribution_is_roughly_uniform():
    # Chi-square-style tolerance check on a real, unseeded CSPRNG — not exact
    # equality, since the RNG is intentionally non-deterministic.
    rng = SecureRNG()
    n = 10
    draws = 200_000
    counts = [0] * n
    for _ in range(draws):
        counts[rng.randbelow(n)] += 1

    expected = draws / n
    for count in counts:
        # 6-sigma band around the expected count under a binomial(draws, 1/n)
        # model; astronomically unlikely to flake for a genuinely uniform RNG.
        se = (draws * (1 / n) * (1 - 1 / n)) ** 0.5
        assert abs(count - expected) < 6 * se
