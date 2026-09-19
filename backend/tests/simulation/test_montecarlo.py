"""OWNER: Member 5. Reproducibility tests here protect the whole benchmark."""

from __future__ import annotations

import numpy as np
import pytest

from app.simulation import montecarlo


def test_paths_have_expected_shape():
    paths = montecarlo.simulate_paths(
        initial_value=300_000, monthly_contribution=15_000, horizon_months=60,
        expected_annual_return=0.12, annual_volatility=0.18, n_paths=500, seed=42,
    )
    assert paths.shape == (500, 61)
    assert np.all(paths[:, 0] == 300_000)


def test_same_seed_is_reproducible():
    kwargs = dict(
        initial_value=300_000, monthly_contribution=15_000, horizon_months=12,
        expected_annual_return=0.12, annual_volatility=0.18, n_paths=200, seed=42,
    )
    assert np.array_equal(montecarlo.simulate_paths(**kwargs), montecarlo.simulate_paths(**kwargs))


def test_different_seeds_diverge():
    base = dict(
        initial_value=300_000, monthly_contribution=15_000, horizon_months=12,
        expected_annual_return=0.12, annual_volatility=0.18, n_paths=200,
    )
    a = montecarlo.simulate_paths(**base, seed=1)
    b = montecarlo.simulate_paths(**base, seed=2)
    assert not np.array_equal(a, b)


def test_zero_volatility_matches_deterministic_compounding():
    """With no randomness the simulation must equal the closed-form calculation."""
    paths = montecarlo.simulate_paths(
        initial_value=100_000, monthly_contribution=10_000, horizon_months=3,
        expected_annual_return=0.12, annual_volatility=0.0, n_paths=1, seed=0,
    )
    monthly = 0.12 / 12
    expected = 100_000.0
    for _ in range(3):
        expected = (expected + 10_000) * (1 + monthly)
    assert paths[0, -1] == pytest.approx(expected, rel=1e-9)


def test_market_shock_reduces_outcomes():
    base = dict(
        initial_value=300_000, monthly_contribution=15_000, horizon_months=60,
        expected_annual_return=0.12, annual_volatility=0.18, n_paths=1_000, seed=42,
    )
    normal = montecarlo.simulate_paths(**base)
    crashed = montecarlo.simulate_paths(**base, shock_pct=-0.30, shock_at_month=0)
    assert np.median(crashed[:, -1]) < np.median(normal[:, -1])


def test_contribution_schedule_length_is_validated():
    with pytest.raises(ValueError):
        montecarlo.simulate_paths(
            initial_value=1000, monthly_contribution=100, horizon_months=12,
            expected_annual_return=0.1, annual_volatility=0.1,
            contribution_schedule=np.zeros(5),
        )
