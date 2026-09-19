"""Quant engine endpoints.  OWNER: Member 1 (Quant/Portfolio)."""

from __future__ import annotations

from fastapi import APIRouter

from app.quant import analytics, health_score
from app.schemas import FinancialProfile, PortfolioMetrics
from app.schemas.portfolio import HealthScore

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/analyze", response_model=PortfolioMetrics)
def analyze_portfolio(profile: FinancialProfile) -> PortfolioMetrics:
    """Allocation, concentration, correlation and risk metrics for one twin."""
    return analytics.analyze(profile)


@router.post("/health-score", response_model=HealthScore)
def compute_health_score(profile: FinancialProfile) -> HealthScore:
    """Financial Health Scorecard. Every sub-score traces to `drivers`."""
    return health_score.compute(profile)
