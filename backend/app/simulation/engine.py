"""Scenario orchestration — OWNER: Member 5.

`run` handles BASELINE and MARKET_STRESS end to end so the demo has a working
vertical slice from day 1. The remaining scenario types are marked TODO and
follow the same pattern: build a contribution schedule, call simulate_paths,
summarize.
"""

from __future__ import annotations

import numpy as np

from app.core.errors import NotImplementedYetError
from app.schemas.common import Assumptions, Percentile
from app.schemas.scenario import (
    GoalOutcome,
    ScenarioComparison,
    ScenarioRequest,
    ScenarioResult,
    ScenarioType,
)
from app.simulation import montecarlo


def _contribution_schedule(request: ScenarioRequest) -> np.ndarray:
    """Month-by-month contribution, after applying any scenario that changes it."""
    base = request.profile.cashflow.monthly_contribution
    schedule = np.full(request.horizon_months, base, dtype=float)

    change = request.contribution_change
    if change is not None:
        if change.new_monthly_contribution is not None:
            schedule[:] = change.new_monthly_contribution
        if change.pause_months > 0:
            start = change.pause_start_month
            schedule[start : start + change.pause_months] = 0.0

    shock = request.income_shock
    if shock is not None:
        # Income drops -> contributions are the first thing to go.
        start, end = shock.start_month, shock.start_month + shock.duration_months
        schedule[start:end] = schedule[start:end] * shock.income_multiplier

    return schedule


def _label(request: ScenarioRequest) -> str:
    if request.scenario_type == ScenarioType.MARKET_STRESS and request.market_stress:
        stress = request.market_stress
        return f"Market {stress.shock_pct:.0%} at month {stress.shock_at_month}"
    if request.scenario_type == ScenarioType.INCOME_SHOCK and request.income_shock:
        shock = request.income_shock
        return (
            f"Income at {shock.income_multiplier:.0%} "
            f"for {shock.duration_months} months"
        )
    if request.scenario_type == ScenarioType.SIP_INTERRUPTION and request.contribution_change:
        return f"SIP paused for {request.contribution_change.pause_months} months"
    return "Baseline"


def _cash_runway_months(request: ScenarioRequest) -> float | None:
    """How long cash covers expenses once income is reduced."""
    if request.scenario_type != ScenarioType.INCOME_SHOCK or request.income_shock is None:
        return None
    cf = request.profile.cashflow
    reduced_income = cf.monthly_income * request.income_shock.income_multiplier
    emis = sum(liability.monthly_emi for liability in request.profile.liabilities)
    monthly_gap = (cf.monthly_expenses + emis) - reduced_income
    if monthly_gap <= 0:
        return float("inf")
    return request.profile.cash_balance / monthly_gap


def run(request: ScenarioRequest) -> ScenarioResult:
    """Run one scenario and return its outcome distribution."""
    if request.scenario_type == ScenarioType.ALLOCATION_CHANGE:
        # TODO(member-5): re-derive expected return/vol from the hypothetical
        # allocation (needs Member 1's correlation matrix), then simulate.
        raise NotImplementedYetError("engine.run: ALLOCATION_CHANGE")

    schedule = _contribution_schedule(request)
    stress = request.market_stress

    paths = montecarlo.simulate_paths(
        initial_value=request.profile.portfolio_value,
        monthly_contribution=request.profile.cashflow.monthly_contribution,
        horizon_months=request.horizon_months,
        expected_annual_return=request.expected_annual_return,
        annual_volatility=request.annual_volatility,
        n_paths=request.settings.n_paths,
        seed=request.settings.seed,
        contribution_schedule=schedule,
        shock_pct=stress.shock_pct if stress else 0.0,
        shock_at_month=stress.shock_at_month if stress else 0,
    )

    percentiles = montecarlo.summarize(paths, request.settings.percentiles)
    median_path = np.median(paths, axis=0).tolist()

    goal_outcomes = [
        GoalOutcome(
            goal_name=goal.name,
            target_amount=goal.target_amount,
            success_probability=montecarlo.success_probability(paths, goal.target_amount),
            median_shortfall=max(0.0, goal.target_amount - median_path[-1]),
            # TODO(member-5): Goal Failure Analysis — attribute the shortfall
            # across contribution level, market path, starting corpus and pauses.
            shortfall_drivers={},
        )
        for goal in request.profile.goals
    ]

    return ScenarioResult(
        scenario_type=request.scenario_type,
        label=_label(request),
        assumptions=Assumptions(
            horizon_months=request.horizon_months,
            expected_annual_return=request.expected_annual_return,
            annual_volatility=request.annual_volatility,
            monthly_contribution=request.profile.cashflow.monthly_contribution,
            n_paths=request.settings.n_paths,
            seed=request.settings.seed,
            notes=[
                "Geometric Brownian Motion with monthly contributions.",
                "Modeled outcomes under stated assumptions — not a prediction.",
            ],
        ),
        terminal_percentiles=[Percentile(p=p, value=v) for p, v in sorted(percentiles.items())],
        median_path=median_path,
        total_contributed=float(schedule.sum()),
        goal_outcomes=goal_outcomes,
        cash_runway_months=_cash_runway_months(request),
    )


def compare(requests: list[ScenarioRequest]) -> ScenarioComparison:
    """Baseline first, alternatives after — all under the same assumptions."""
    if not requests:
        raise ValueError("compare() needs at least a baseline request")

    baseline = run(requests[0])
    alternatives = [run(r) for r in requests[1:]]

    def median_terminal(result: ScenarioResult) -> float:
        return next((p.value for p in result.terminal_percentiles if p.p == 50), 0.0)

    base_median = median_terminal(baseline)
    return ScenarioComparison(
        baseline=baseline,
        alternatives=alternatives,
        deltas={alt.label: median_terminal(alt) - base_median for alt in alternatives},
    )
