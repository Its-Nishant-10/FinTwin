"""Scenario orchestration — OWNER: Member 5.

A scenario is a baseline twin plus zero or more *perturbations*:

    market_shock         a one-off fall, optionally with a recovery path
    contribution_change  a new SIP amount and/or a pause
    income_shock         income cut for a while; contributions come out of what is left
    allocation_change    a different asset-class mix

`scenario_type` labels the request; the perturbations that actually apply are
the ones whose parameters are present. That lets one request combine, say, a
crash and a SIP pause, and it is what makes Goal Failure Analysis possible:
switch each perturbation on and off, holding the random market fixed, and
measure what each one costs.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import factorial

import numpy as np

from app.schemas.common import Assumptions, Percentile, PercentilePath
from app.schemas.profile import Goal
from app.schemas.scenario import (
    GoalOutcome,
    ScenarioComparison,
    ScenarioRequest,
    ScenarioResult,
    ScenarioType,
)
from app.simulation import assumptions as cma
from app.simulation import montecarlo

MARKET = "market_shock"
CONTRIBUTION = "contribution_change"
INCOME = "income_shock"
ALLOCATION = "allocation_change"
BASELINE_PLAN = "baseline_plan"

# Which parameter block each scenario_type needs.
_REQUIRED_PARAMS = {
    ScenarioType.MARKET_STRESS: "market_stress",
    ScenarioType.INCOME_SHOCK: "income_shock",
    ScenarioType.CONTRIBUTION_CHANGE: "contribution_change",
    ScenarioType.SIP_INTERRUPTION: "contribution_change",
    ScenarioType.ALLOCATION_CHANGE: "allocation_change",
}


@dataclass(frozen=True)
class _Spec:
    """Everything simulate_paths needs, after perturbations are applied."""

    schedule: np.ndarray
    mu: float
    sigma: float
    shock_pct: float = 0.0
    shock_at_month: int = 0
    recovery_months: int | None = None


# ---------------------------------------------------------------- building specs


def validate(request: ScenarioRequest) -> None:
    """Reject requests whose type and parameters disagree. Raises ValueError."""
    needed = _REQUIRED_PARAMS.get(request.scenario_type)
    if needed and getattr(request, needed) is None:
        raise ValueError(f"scenario_type={request.scenario_type.value!r} needs {needed!r}")

    h = request.horizon_months
    if request.market_stress and request.market_stress.shock_at_month >= h:
        raise ValueError("market_stress.shock_at_month must fall inside the horizon")
    if request.income_shock and request.income_shock.start_month >= h:
        raise ValueError("income_shock.start_month must fall inside the horizon")
    change = request.contribution_change
    if change and change.pause_months and change.pause_start_month >= h:
        raise ValueError("contribution_change.pause_start_month must fall inside the horizon")


def active_factors(request: ScenarioRequest) -> list[str]:
    """Perturbations present on this request, in a fixed order."""
    present = {
        MARKET: request.market_stress is not None,
        CONTRIBUTION: request.contribution_change is not None,
        INCOME: request.income_shock is not None,
        ALLOCATION: request.allocation_change is not None,
    }
    return [name for name, on in present.items() if on]


def _base_return_vol(request: ScenarioRequest, factors: frozenset[str]) -> tuple[float, float]:
    """Return/vol for this spec.

    If the request involves an allocation change, both sides of the comparison
    use capital-market assumptions — current weights without the factor, target
    weights with it — so neither side gets the hand-typed 12%/18% default.
    """
    if request.allocation_change is None:
        return request.expected_annual_return, request.annual_volatility
    if ALLOCATION in factors:
        weights = request.allocation_change.target_weights
    else:
        weights = cma.current_weights(request.profile)
    return cma.portfolio_return_vol(weights)


def _schedule(request: ScenarioRequest, factors: frozenset[str]) -> np.ndarray:
    profile = request.profile
    schedule = np.full(request.horizon_months, profile.cashflow.monthly_contribution, dtype=float)

    change = request.contribution_change
    if CONTRIBUTION in factors and change is not None:
        if change.new_monthly_contribution is not None:
            schedule[:] = change.new_monthly_contribution
        if change.pause_months > 0:
            start = change.pause_start_month
            schedule[start : start + change.pause_months] = 0.0

    shock = request.income_shock
    if INCOME in factors and shock is not None:
        # Contributions come out of whatever income is left after expenses and
        # EMIs, and never exceed what was planned. At zero income they stop.
        cf = profile.cashflow
        emis = sum(liability.monthly_emi for liability in profile.liabilities)
        available = cf.monthly_income * shock.income_multiplier - cf.monthly_expenses - emis
        start, end = shock.start_month, shock.start_month + shock.duration_months
        schedule[start:end] = np.clip(schedule[start:end], 0.0, max(0.0, available))

    return schedule


def _spec(request: ScenarioRequest, factors: frozenset[str]) -> _Spec:
    mu, sigma = _base_return_vol(request, factors)
    stress = request.market_stress if MARKET in factors else None
    return _Spec(
        schedule=_schedule(request, factors),
        mu=mu,
        sigma=sigma,
        shock_pct=stress.shock_pct if stress else 0.0,
        shock_at_month=stress.shock_at_month if stress else 0,
        recovery_months=stress.recovery_months if stress else None,
    )


def _simulate(request: ScenarioRequest, spec: _Spec, schedule: np.ndarray | None = None):
    settings = request.settings
    return montecarlo.simulate_paths(
        initial_value=request.profile.portfolio_value,
        monthly_contribution=0.0,
        horizon_months=request.horizon_months,
        expected_annual_return=spec.mu,
        annual_volatility=spec.sigma,
        n_paths=settings.n_paths,
        seed=settings.seed,
        contribution_schedule=spec.schedule if schedule is None else schedule,
        shock_pct=spec.shock_pct,
        shock_at_month=spec.shock_at_month,
        recovery_months=spec.recovery_months,
        return_model=settings.return_model,
        t_df=settings.t_df,
    )


# ---------------------------------------------------------- goal failure analysis


def _shapley(factors: list[str], value: dict[frozenset[str], float]) -> dict[str, float]:
    """Each factor's Shapley share of the drop value(∅) - value(all factors).

    Shapley values are the only attribution that is additive (shares sum to the
    total) and order-independent when factors interact — and they do here: a
    SIP pause costs more after a crash than before one.
    """
    n = len(factors)
    shares: dict[str, float] = {}
    for factor in factors:
        others = [f for f in factors if f != factor]
        share = 0.0
        for size in range(n):
            weight = factorial(size) * factorial(n - size - 1) / factorial(n)
            for subset in combinations(others, size):
                without = frozenset(subset)
                share += weight * (value[without] - value[without | {factor}])
        shares[factor] = share
    return shares


def _required_contribution(
    request: ScenarioRequest, factors: frozenset[str], target: float, month: int
) -> float:
    """Flat monthly SIP at which the median value at `month` reaches `target`.

    Market-side perturbations (crash, allocation) stay on; contribution-side
    ones are replaced by the flat SIP being solved for. For a fixed random path
    the outcome is affine in the contribution, value = a + c·b with b >= 0, so
    two simulations give (a, b) for every path and the median can then be
    solved by bisection without simulating again.
    """
    market_side = _spec(request, factors & {MARKET, ALLOCATION})
    h = request.horizon_months
    a = _simulate(request, market_side, np.zeros(h))[:, month]
    b = _simulate(request, market_side, np.ones(h))[:, month] - a

    def median_at(c: float) -> float:
        return float(np.median(a + c * b))

    if median_at(0.0) >= target:
        return 0.0
    high = max(target / month, 1.0)
    for _ in range(60):
        if median_at(high) >= target:
            break
        high *= 2
    low = 0.0
    for _ in range(60):
        mid = (low + high) / 2
        low, high = (mid, high) if median_at(mid) < target else (low, mid)
    return high


def _goal_outcomes(
    request: ScenarioRequest,
    paths: np.ndarray,
    factors: list[str],
    goals: list[Goal],
) -> list[GoalOutcome]:
    if not goals:
        return []

    # Median path for every on/off combination of the active factors. Same seed,
    # so every combination sees the same random market.
    median_paths: dict[frozenset[str], np.ndarray] = {}
    for size in range(len(factors) + 1):
        for subset in combinations(factors, size):
            key = frozenset(subset)
            sim = paths if len(key) == len(factors) else _simulate(request, _spec(request, key))
            median_paths[key] = np.median(sim, axis=0)

    outcomes = []
    for goal in goals:
        month = goal.horizon_months
        at_month = {key: float(path[month]) for key, path in median_paths.items()}
        median_value = at_month[frozenset(factors)]

        drivers = {BASELINE_PLAN: goal.target_amount - at_month[frozenset()]}
        drivers.update(_shapley(factors, at_month))

        outcomes.append(
            GoalOutcome(
                goal_name=goal.name,
                target_amount=goal.target_amount,
                success_probability=montecarlo.success_probability(
                    paths, goal.target_amount, month
                ),
                median_shortfall=max(0.0, goal.target_amount - median_value),
                evaluated_at_month=month,
                shortfall_drivers=drivers,
                required_monthly_contribution=_required_contribution(
                    request, frozenset(factors), goal.target_amount, month
                ),
            )
        )
    return outcomes


# ------------------------------------------------------------------ public API


def _label(request: ScenarioRequest) -> str:
    parts = []
    if request.market_stress:
        stress = request.market_stress
        part = f"Market {stress.shock_pct:.0%} at month {stress.shock_at_month}"
        if stress.recovery_months:
            part += f", recovering over {stress.recovery_months} months"
        parts.append(part)
    if request.contribution_change:
        change = request.contribution_change
        if change.new_monthly_contribution is not None:
            parts.append(f"SIP changed to ₹{change.new_monthly_contribution:,.0f}")
        if change.pause_months:
            parts.append(f"SIP paused for {change.pause_months} months")
    if request.income_shock:
        shock = request.income_shock
        parts.append(f"Income at {shock.income_multiplier:.0%} for {shock.duration_months} months")
    if request.allocation_change:
        mix = ", ".join(
            f"{w:.0%} {asset.value}"
            for asset, w in sorted(
                request.allocation_change.target_weights.items(), key=lambda kv: -kv[1]
            )
            if w > 0
        )
        parts.append(f"Allocation {mix}")
    return " + ".join(parts) or "Baseline"


def _cash_runway_months(request: ScenarioRequest) -> float | None:
    """How long cash covers expenses once income is reduced. None = never runs out."""
    if request.income_shock is None:
        return None
    cf = request.profile.cashflow
    reduced_income = cf.monthly_income * request.income_shock.income_multiplier
    emis = sum(liability.monthly_emi for liability in request.profile.liabilities)
    monthly_gap = (cf.monthly_expenses + emis) - reduced_income
    if monthly_gap <= 0:
        return None
    return request.profile.cash_balance / monthly_gap


def _notes(request: ScenarioRequest, skipped_goals: list[Goal]) -> list[str]:
    notes = [
        "Modeled outcomes under stated assumptions — not a prediction.",
        "Monthly log-normal returns with contributions at the start of each month."
        if request.settings.return_model == "gbm"
        else f"Fat-tailed (Student-t, {request.settings.t_df:g} df) monthly returns, "
        "truncated at 6 standard deviations.",
    ]
    if request.market_stress and not request.market_stress.recovery_months:
        notes.append("The market shock is a permanent level loss; no recovery is modeled.")
    if request.allocation_change:
        notes.append(cma.NOTE)
    if request.income_shock:
        notes.append(
            "During the income shock, contributions are limited to income left after "
            "expenses and EMIs."
        )
    for goal in skipped_goals:
        notes.append(
            f"Goal '{goal.name}' ({goal.horizon_months} months) lies beyond the "
            f"{request.horizon_months}-month horizon and was not evaluated."
        )
    return notes


def run(request: ScenarioRequest) -> ScenarioResult:
    """Run one scenario and return its outcome distribution."""
    validate(request)
    factors = active_factors(request)
    spec = _spec(request, frozenset(factors))
    paths = _simulate(request, spec)

    goals = [g for g in request.profile.goals if g.horizon_months <= request.horizon_months]
    skipped = [g for g in request.profile.goals if g.horizon_months > request.horizon_months]
    percentiles = montecarlo.summarize(paths, request.settings.percentiles)
    bands = montecarlo.path_percentiles(paths, request.settings.percentiles)

    return ScenarioResult(
        scenario_type=request.scenario_type,
        label=_label(request),
        assumptions=Assumptions(
            horizon_months=request.horizon_months,
            expected_annual_return=spec.mu,
            annual_volatility=spec.sigma,
            monthly_contribution=request.profile.cashflow.monthly_contribution,
            n_paths=request.settings.n_paths,
            seed=request.settings.seed,
            notes=_notes(request, skipped),
        ),
        terminal_percentiles=[Percentile(p=p, value=v) for p, v in sorted(percentiles.items())],
        median_path=np.median(paths, axis=0).tolist(),
        percentile_paths=[PercentilePath(p=p, values=v.tolist()) for p, v in sorted(bands.items())],
        total_contributed=float(spec.schedule.sum()),
        goal_outcomes=_goal_outcomes(request, paths, factors, goals),
        cash_runway_months=_cash_runway_months(request),
    )


def baseline_for(request: ScenarioRequest) -> ScenarioRequest:
    """The same request with every perturbation removed, under identical assumptions."""
    mu, sigma = _base_return_vol(request, frozenset())
    return request.model_copy(
        update={
            "scenario_type": ScenarioType.BASELINE,
            "expected_annual_return": mu,
            "annual_volatility": sigma,
            "market_stress": None,
            "income_shock": None,
            "contribution_change": None,
            "allocation_change": None,
        }
    )


def _median_terminal(result: ScenarioResult) -> float:
    return next((p.value for p in result.terminal_percentiles if p.p == 50), 0.0)


def compare(requests: list[ScenarioRequest]) -> ScenarioComparison:
    """Baseline first, alternatives after — all under the same assumptions.

    Raises ValueError if an alternative changes the horizon, the simulation
    settings, or (outside allocation scenarios, which derive their own) the
    return and volatility assumptions: a comparison is only meaningful when the
    perturbation is the one thing that differs.
    """
    if not requests:
        raise ValueError("compare() needs at least a baseline request")

    base = requests[0]
    for alt in requests[1:]:
        if alt.horizon_months != base.horizon_months:
            raise ValueError("all scenarios in a comparison must share horizon_months")
        if alt.settings != base.settings:
            raise ValueError("all scenarios in a comparison must share simulation settings")
        derived = alt.allocation_change is not None or base.allocation_change is not None
        same_market = (alt.expected_annual_return, alt.annual_volatility) == (
            base.expected_annual_return,
            base.annual_volatility,
        )
        if not derived and not same_market:
            raise ValueError("all scenarios in a comparison must share return/volatility")

    baseline = run(base)
    alternatives = [run(r) for r in requests[1:]]
    base_median = _median_terminal(baseline)
    return ScenarioComparison(
        baseline=baseline,
        alternatives=alternatives,
        deltas={alt.label: _median_terminal(alt) - base_median for alt in alternatives},
    )


def whatif(request: ScenarioRequest) -> ScenarioComparison:
    """One scenario, compared against its own automatically built baseline."""
    validate(request)
    return compare([baseline_for(request), request])
