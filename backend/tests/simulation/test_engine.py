"""OWNER: Member 5."""

from __future__ import annotations

import pytest

from app.schemas.profile import AssetClass, FinancialProfile, Goal, Holding
from app.schemas.scenario import (
    AllocationChangeParams,
    ContributionChangeParams,
    IncomeShockParams,
    MarketStressParams,
    ScenarioRequest,
    ScenarioType,
    SimulationSettings,
)
from app.simulation import assumptions, engine

SETTINGS = SimulationSettings(n_paths=500, seed=42)


def _request(profile, **kwargs) -> ScenarioRequest:
    return ScenarioRequest(profile=profile, horizon_months=60, settings=SETTINGS, **kwargs)


def _crash(profile, **kwargs):
    return _request(
        profile,
        scenario_type=ScenarioType.MARKET_STRESS,
        market_stress=MarketStressParams(shock_pct=-0.30),
        **kwargs,
    )


def test_baseline_returns_percentiles_and_path(profile):
    result = engine.run(_request(profile))
    assert len(result.median_path) == 61
    assert [p.p for p in result.terminal_percentiles] == [10, 25, 50, 75, 90]
    assert result.assumptions.seed == 42


def test_run_is_reproducible(profile):
    assert engine.run(_crash(profile)) == engine.run(_crash(profile))


def test_sip_pause_lowers_total_contributed(profile):
    paused = engine.run(
        _request(
            profile,
            scenario_type=ScenarioType.SIP_INTERRUPTION,
            contribution_change=ContributionChangeParams(pause_months=6),
        )
    )
    assert paused.total_contributed == 15_000 * 54


def test_new_contribution_amount_applies(profile):
    raised = engine.run(
        _request(
            profile,
            scenario_type=ScenarioType.CONTRIBUTION_CHANGE,
            contribution_change=ContributionChangeParams(new_monthly_contribution=20_000),
        )
    )
    assert raised.total_contributed == 20_000 * 60


def test_market_stress_lowers_median_vs_baseline(profile):
    comparison = engine.whatif(_crash(profile))
    assert comparison.baseline.scenario_type == ScenarioType.BASELINE
    assert next(iter(comparison.deltas.values())) < 0


def test_type_without_params_is_rejected(profile):
    with pytest.raises(ValueError, match="market_stress"):
        engine.run(_request(profile, scenario_type=ScenarioType.MARKET_STRESS))


def test_shock_outside_horizon_is_rejected(profile):
    with pytest.raises(ValueError, match="inside the horizon"):
        engine.run(
            _request(
                profile,
                scenario_type=ScenarioType.MARKET_STRESS,
                market_stress=MarketStressParams(shock_pct=-0.3, shock_at_month=60),
            )
        )


# ------------------------------------------------------------------ income shock


def test_income_shock_contributions_limited_to_what_is_left(profile):
    """Income 120k, expenses 70k, EMI 11k. At 50% income, 60k - 81k < 0: no SIP."""
    result = engine.run(
        _request(
            profile,
            scenario_type=ScenarioType.INCOME_SHOCK,
            income_shock=IncomeShockParams(income_multiplier=0.5, duration_months=6),
        )
    )
    assert result.total_contributed == 15_000 * 54


def test_mild_income_shock_keeps_contributions(profile):
    """At 90% income, 108k - 81k = 27k left, more than the 15k SIP: nothing changes."""
    result = engine.run(
        _request(
            profile,
            scenario_type=ScenarioType.INCOME_SHOCK,
            income_shock=IncomeShockParams(income_multiplier=0.9, duration_months=6),
        )
    )
    assert result.total_contributed == 15_000 * 60


def test_cash_runway_hand_computed(profile):
    """Cash 2.5L; gap at zero income = 70k expenses + 11k EMI = 81k/month."""
    result = engine.run(
        _request(
            profile,
            scenario_type=ScenarioType.INCOME_SHOCK,
            income_shock=IncomeShockParams(duration_months=6),
        )
    )
    assert result.cash_runway_months == pytest.approx(250_000 / 81_000)


# ------------------------------------------------------------ allocation change


def test_portfolio_return_vol_single_asset():
    mu, sigma = assumptions.portfolio_return_vol({AssetClass.EQUITY: 1.0})
    assert (mu, sigma) == pytest.approx(assumptions.ASSET_CLASS_ASSUMPTIONS[AssetClass.EQUITY])


def test_diversified_mix_has_lower_vol_than_weighted_average():
    w = {AssetClass.EQUITY: 0.6, AssetClass.DEBT: 0.4}
    _, sigma = assumptions.portfolio_return_vol(w)
    assert sigma < 0.6 * 0.18 + 0.4 * 0.04


def test_target_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        AllocationChangeParams(target_weights={AssetClass.EQUITY: 0.5})


def test_allocation_change_uses_derived_assumptions_on_both_sides(profile):
    request = _request(
        profile,
        scenario_type=ScenarioType.ALLOCATION_CHANGE,
        allocation_change=AllocationChangeParams(
            target_weights={AssetClass.EQUITY: 0.6, AssetClass.DEBT: 0.4}
        ),
    )
    comparison = engine.whatif(request)
    target_mu, _ = assumptions.portfolio_return_vol(request.allocation_change.target_weights)
    current_mu, _ = assumptions.portfolio_return_vol(assumptions.current_weights(profile))
    assert comparison.alternatives[0].assumptions.expected_annual_return == pytest.approx(target_mu)
    assert comparison.baseline.assumptions.expected_annual_return == pytest.approx(current_mu)
    assert assumptions.NOTE in comparison.alternatives[0].assumptions.notes


# ---------------------------------------------------------- goal failure analysis


def test_goal_outcome_is_attached(profile):
    result = engine.run(_request(profile))
    assert len(result.goal_outcomes) == 1
    outcome = result.goal_outcomes[0]
    assert 0.0 <= outcome.success_probability <= 1.0
    assert outcome.evaluated_at_month == 60


def test_shortfall_drivers_sum_to_signed_shortfall(profile):
    """Shapley efficiency: drivers add up to target - median, for any mix of factors."""
    request = _crash(
        profile,
        contribution_change=ContributionChangeParams(pause_months=6),
        income_shock=IncomeShockParams(duration_months=3, start_month=12),
    )
    result = engine.run(request)
    outcome = result.goal_outcomes[0]
    median_at_goal = result.median_path[outcome.evaluated_at_month]
    assert sum(outcome.shortfall_drivers.values()) == pytest.approx(
        outcome.target_amount - median_at_goal
    )
    assert set(outcome.shortfall_drivers) == {
        "baseline_plan",
        "market_shock",
        "contribution_change",
        "income_shock",
    }
    assert outcome.shortfall_drivers["market_shock"] > 0


def test_overlapping_factors_share_the_blame_equally(profile):
    """A pause and a zero-income shock over the same months do identical damage."""
    result = engine.run(
        _request(
            profile,
            scenario_type=ScenarioType.SIP_INTERRUPTION,
            contribution_change=ContributionChangeParams(pause_months=6),
            income_shock=IncomeShockParams(duration_months=6),
        )
    )
    drivers = result.goal_outcomes[0].shortfall_drivers
    assert drivers["contribution_change"] == pytest.approx(drivers["income_shock"])


def test_required_contribution_hits_target_at_median(profile):
    request = _request(profile)
    outcome = engine.run(request).goal_outcomes[0]
    required = outcome.required_monthly_contribution
    assert required > 0

    at_required = profile.model_copy(deep=True)
    at_required.cashflow.monthly_contribution = required
    check = engine.run(_request(at_required)).goal_outcomes[0]
    assert check.median_shortfall == pytest.approx(0.0, abs=500)


def test_required_contribution_is_zero_when_goal_already_met():
    profile = FinancialProfile(
        holdings=[Holding(symbol="X", quantity=1, current_price=100_000)],
        goals=[Goal(name="Small", target_amount=1_000, horizon_months=12)],
    )
    outcome = engine.run(ScenarioRequest(profile=profile, horizon_months=12, settings=SETTINGS))
    assert outcome.goal_outcomes[0].required_monthly_contribution == 0.0


def test_goal_evaluated_at_its_own_horizon(profile):
    profile.goals.append(Goal(name="Soon", target_amount=500_000, horizon_months=24))
    result = engine.run(_request(profile))
    by_name = {g.goal_name: g for g in result.goal_outcomes}
    assert by_name["Soon"].evaluated_at_month == 24


def test_goal_beyond_horizon_is_skipped_with_a_note(profile):
    profile.goals.append(Goal(name="Retirement", target_amount=9_000_000, horizon_months=240))
    result = engine.run(_request(profile))
    assert "Retirement" not in {g.goal_name for g in result.goal_outcomes}
    assert any("Retirement" in note for note in result.assumptions.notes)


# ---------------------------------------------------------------------- compare


def test_compare_rejects_mismatched_horizons(profile):
    other = _request(profile).model_copy(update={"horizon_months": 36})
    with pytest.raises(ValueError, match="horizon"):
        engine.compare([_request(profile), other])


def test_compare_rejects_mismatched_return_assumptions(profile):
    other = _request(profile).model_copy(update={"expected_annual_return": 0.15})
    with pytest.raises(ValueError, match="return"):
        engine.compare([_request(profile), other])
