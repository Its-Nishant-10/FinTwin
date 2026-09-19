"""What-if machinery (Member 5).

A scenario is always: a baseline profile + a named perturbation + explicit
assumptions -> a distribution of outcomes. Never a single "predicted" number.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.common import Assumptions, Explanation, Money, Percentile
from app.schemas.profile import FinancialProfile


class ScenarioType(str, Enum):
    BASELINE = "baseline"
    MARKET_STRESS = "market_stress"
    INCOME_SHOCK = "income_shock"
    CONTRIBUTION_CHANGE = "contribution_change"
    SIP_INTERRUPTION = "sip_interruption"
    ALLOCATION_CHANGE = "allocation_change"


class MarketStressParams(BaseModel):
    """'What if markets fall 30%?'"""

    shock_pct: float = Field(..., le=0, description="Negative decimal, e.g. -0.30")
    shock_at_month: int = Field(default=0, ge=0)
    recovery_months: int | None = Field(
        default=None, description="None = no modeled recovery path"
    )


class IncomeShockParams(BaseModel):
    """'What if my income stops for six months?'"""

    income_multiplier: float = Field(default=0.0, ge=0, le=1)
    duration_months: int = Field(..., gt=0)
    start_month: int = Field(default=0, ge=0)


class ContributionChangeParams(BaseModel):
    """'What if I raise/lower/pause my SIP?'"""

    new_monthly_contribution: Money | None = Field(default=None, ge=0)
    pause_months: int = Field(default=0, ge=0)
    pause_start_month: int = Field(default=0, ge=0)


class SimulationSettings(BaseModel):
    n_paths: int = Field(default=10_000, gt=0, le=200_000)
    seed: int | None = Field(default=42, description="Pin it — the benchmark needs reproducibility")
    percentiles: list[float] = Field(default=[10, 25, 50, 75, 90])


class ScenarioRequest(BaseModel):
    profile: FinancialProfile
    scenario_type: ScenarioType = ScenarioType.BASELINE
    horizon_months: int = Field(..., gt=0)
    expected_annual_return: float = 0.12
    annual_volatility: float = 0.18
    settings: SimulationSettings = Field(default_factory=SimulationSettings)

    market_stress: MarketStressParams | None = None
    income_shock: IncomeShockParams | None = None
    contribution_change: ContributionChangeParams | None = None


class GoalOutcome(BaseModel):
    goal_name: str
    target_amount: Money
    success_probability: float = Field(..., ge=0, le=1)
    median_shortfall: Money = Field(default=0.0, description="0 if median run clears the target")
    # Goal Failure Analysis: how much of the modeled shortfall each factor explains.
    shortfall_drivers: dict[str, float] = Field(default_factory=dict)


class ScenarioResult(BaseModel):
    scenario_type: ScenarioType
    label: str = Field(..., description="Human-readable, e.g. 'Market -30% at month 0'")
    assumptions: Assumptions
    terminal_percentiles: list[Percentile] = Field(default_factory=list)
    median_path: list[Money] = Field(
        default_factory=list, description="Month-by-month median value, length = horizon_months + 1"
    )
    total_contributed: Money = 0.0
    goal_outcomes: list[GoalOutcome] = Field(default_factory=list)
    cash_runway_months: float | None = Field(
        default=None, description="Set by income-shock scenarios"
    )
    explanation: Explanation | None = None


class ScenarioComparison(BaseModel):
    """Baseline vs one or more alternatives, run under identical assumptions."""

    baseline: ScenarioResult
    alternatives: list[ScenarioResult] = Field(default_factory=list)
    deltas: dict[str, float] = Field(
        default_factory=dict, description="Alternative label -> change in median terminal value"
    )
