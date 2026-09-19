"""Outputs of the quant engine (Member 1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Money
from app.schemas.profile import AssetClass


class AllocationSlice(BaseModel):
    label: str = Field(..., description="Asset class, sector or symbol")
    value: Money
    weight: float = Field(..., ge=0, le=1)


class ConcentrationMetrics(BaseModel):
    """How much of the portfolio rides on too few things."""

    hhi: float = Field(..., ge=0, le=1, description="Herfindahl-Hirschman Index of weights")
    effective_holdings: float = Field(..., gt=0, description="1 / HHI")
    top_holding_weight: float = Field(..., ge=0, le=1)
    top_5_weight: float = Field(..., ge=0, le=1)
    flags: list[str] = Field(default_factory=list)


class RiskMetrics(BaseModel):
    """Annualized unless stated otherwise. None means 'not enough price history'."""

    annual_volatility: float | None = None
    max_drawdown: float | None = Field(default=None, description="Negative decimal, e.g. -0.32")
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    var_95: float | None = Field(default=None, description="1-day 95% Value at Risk, decimal")
    beta: float | None = None


class PortfolioMetrics(BaseModel):
    """The full quant-engine response for one profile."""

    total_value: Money
    by_asset_class: list[AllocationSlice] = Field(default_factory=list)
    by_sector: list[AllocationSlice] = Field(default_factory=list)
    by_holding: list[AllocationSlice] = Field(default_factory=list)
    concentration: ConcentrationMetrics | None = None
    risk: RiskMetrics = Field(default_factory=RiskMetrics)
    correlation_matrix: dict[str, dict[str, float]] = Field(default_factory=dict)
    dominant_asset_class: AssetClass | None = None


class HealthScore(BaseModel):
    """Financial Health Scorecard — every sub-score must trace to real inputs.

    Do not produce these with an LLM. Each dimension is a formula over the
    profile, and `drivers` names the numbers that moved it.
    """

    overall: float = Field(..., ge=0, le=100)
    liquidity: float = Field(..., ge=0, le=100)
    debt_burden: float = Field(..., ge=0, le=100)
    diversification: float = Field(..., ge=0, le=100)
    goal_progress: float = Field(..., ge=0, le=100)
    market_exposure: float = Field(..., ge=0, le=100)
    drivers: dict[str, float] = Field(
        default_factory=dict, description="Raw inputs behind each score"
    )
