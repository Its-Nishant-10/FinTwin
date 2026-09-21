"""OWNER: Member 5. Reproducibility tests here protect the whole benchmark."""

from __future__ import annotations

import numpy as np
import pytest

from app.simulation import montecarlo

BASE = dict(
    initial_value=300_000,
    monthly_contribution=15_000,
    horizon_months=60,
    expected_annual_return=0.12,
    annual_volatility=0.18,
    n_paths=1_000,
    seed=42,
)


def test_paths_have_expected_shape():
    paths = montecarlo.simulate_paths(**{**BASE, "n_paths": 500})
    assert paths.shape == (500, 61)
    assert np.all(paths[:, 0] == 300_000)


def test_same_seed_is_reproducible():
    assert np.array_equal(montecarlo.simulate_paths(**BASE), montecarlo.simulate_paths(**BASE))


def test_different_seeds_diverge():
    a = montecarlo.simulate_paths(**{**BASE, "seed": 1})
    b = montecarlo.simulate_paths(**{**BASE, "seed": 2})
    assert not np.array_equal(a, b)


def test_zero_volatility_matches_deterministic_compounding():
    """With no randomness the simulation must equal the closed-form calculation."""
    paths = montecarlo.simulate_paths(
        initial_value=100_000,
        monthly_contribution=10_000,
        horizon_months=3,
        expected_annual_return=0.12,
        annual_volatility=0.0,
        n_paths=1,
        seed=0,
    )
    monthly = 0.12 / 12
    expected = 100_000.0
    for _ in range(3):
        expected = (expected + 10_000) * (1 + monthly)
    assert paths[0, -1] == pytest.approx(expected, rel=1e-9)


def test_market_shock_reduces_outcomes():
    normal = montecarlo.simulate_paths(**BASE)
    crashed = montecarlo.simulate_paths(**BASE, shock_pct=-0.30, shock_at_month=0)
    assert np.median(crashed[:, -1]) < np.median(normal[:, -1])


def test_shock_is_exact_with_zero_volatility():
    """A -30% shock at month 0 with no contributions leaves exactly 70% (times growth)."""
    kwargs = dict(
        initial_value=100_000,
        monthly_contribution=0,
        horizon_months=1,
        expected_annual_return=0.0,
        annual_volatility=0.0,
        n_paths=1,
    )
    paths = montecarlo.simulate_paths(**kwargs, shock_pct=-0.30, shock_at_month=0)
    assert paths[0, -1] == pytest.approx(70_000)


def test_full_recovery_restores_level_with_zero_volatility():
    """No contributions, no drift: a shock that fully recovers ends where it started."""
    paths = montecarlo.simulate_paths(
        initial_value=100_000,
        monthly_contribution=0,
        horizon_months=13,
        expected_annual_return=0.0,
        annual_volatility=0.0,
        n_paths=1,
        shock_pct=-0.30,
        shock_at_month=0,
        recovery_months=12,
    )
    assert paths[0, 1] == pytest.approx(70_000)
    assert paths[0, -1] == pytest.approx(100_000)


def test_recovery_beats_permanent_loss():
    permanent = montecarlo.simulate_paths(**BASE, shock_pct=-0.30)
    recovered = montecarlo.simulate_paths(**BASE, shock_pct=-0.30, recovery_months=12)
    assert np.median(recovered[:, -1]) > np.median(permanent[:, -1])


def test_student_t_is_reproducible_and_fatter_tailed():
    gbm = montecarlo.standard_shocks(20_000, 60, seed=7)
    fat = montecarlo.standard_shocks(20_000, 60, seed=7, return_model="student_t", t_df=4)
    assert np.array_equal(
        fat, montecarlo.standard_shocks(20_000, 60, seed=7, return_model="student_t", t_df=4)
    )
    # Same variance, heavier tails: more mass beyond 3 standard deviations.
    assert fat.std() == pytest.approx(1.0, abs=0.05)
    assert (np.abs(fat) > 3).mean() > 2 * (np.abs(gbm) > 3).mean()
    assert np.abs(fat).max() <= 6.0


def test_unknown_return_model_rejected():
    with pytest.raises(ValueError):
        montecarlo.standard_shocks(10, 10, seed=0, return_model="magic")


def test_contribution_schedule_length_is_validated():
    with pytest.raises(ValueError):
        montecarlo.simulate_paths(**BASE, contribution_schedule=np.zeros(5))


def test_path_percentiles_are_ordered_and_start_together():
    paths = montecarlo.simulate_paths(**BASE)
    bands = montecarlo.path_percentiles(paths, [10, 50, 90])
    assert set(bands) == {10, 50, 90}
    assert all(len(values) == 61 for values in bands.values())
    # Everyone starts from today's portfolio, so the band opens from a single point.
    assert bands[10][0] == bands[50][0] == bands[90][0] == 300_000
    assert np.all(bands[10] <= bands[50]) and np.all(bands[50] <= bands[90])


def test_path_percentiles_agree_with_terminal_summary():
    paths = montecarlo.simulate_paths(**BASE)
    terminal = montecarlo.summarize(paths, [10, 50, 90])
    bands = montecarlo.path_percentiles(paths, [10, 50, 90])
    for p, value in terminal.items():
        assert bands[p][-1] == pytest.approx(value)


def test_path_percentiles_with_none_requested_is_empty():
    assert montecarlo.path_percentiles(montecarlo.simulate_paths(**BASE), []) == {}


def test_success_probability_at_month():
    paths = np.array([[0, 5, 10], [0, 15, 20]], dtype=float)
    assert montecarlo.success_probability(paths, 10) == 1.0
    assert montecarlo.success_probability(paths, 10, month=1) == 0.5
