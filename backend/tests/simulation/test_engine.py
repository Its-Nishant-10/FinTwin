from __future__ import annotations

from app.schemas.scenario import (
    ContributionChangeParams,
    MarketStressParams,
    ScenarioRequest,
    ScenarioType,
    SimulationSettings,
)
from app.simulation import engine

SETTINGS = SimulationSettings(n_paths=500, seed=42)


def test_baseline_returns_percentiles_and_path(profile):
    result = engine.run(
        ScenarioRequest(profile=profile, horizon_months=60, settings=SETTINGS)
    )
    assert len(result.median_path) == 61
    assert [p.p for p in result.terminal_percentiles] == [10, 25, 50, 75, 90]
    assert result.assumptions.seed == 42


def test_sip_pause_lowers_total_contributed(profile):
    paused = engine.run(
        ScenarioRequest(
            profile=profile, scenario_type=ScenarioType.SIP_INTERRUPTION,
            horizon_months=60, settings=SETTINGS,
            contribution_change=ContributionChangeParams(pause_months=6, pause_start_month=0),
        )
    )
    assert paused.total_contributed == 15_000 * 54


def test_market_stress_beats_baseline_downward(profile):
    baseline = ScenarioRequest(profile=profile, horizon_months=60, settings=SETTINGS)
    stressed = ScenarioRequest(
        profile=profile, scenario_type=ScenarioType.MARKET_STRESS,
        horizon_months=60, settings=SETTINGS,
        market_stress=MarketStressParams(shock_pct=-0.30, shock_at_month=0),
    )
    comparison = engine.compare([baseline, stressed])
    assert len(comparison.alternatives) == 1
    assert next(iter(comparison.deltas.values())) < 0


def test_goal_outcome_is_attached(profile):
    result = engine.run(ScenarioRequest(profile=profile, horizon_months=60, settings=SETTINGS))
    assert len(result.goal_outcomes) == 1
    assert 0.0 <= result.goal_outcomes[0].success_probability <= 1.0
