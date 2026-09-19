"""Scenario / Monte Carlo endpoints.  OWNER: Member 5 (Simulation)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import ScenarioComparison, ScenarioRequest, ScenarioResult
from app.simulation import engine

router = APIRouter(prefix="/scenario", tags=["scenario"])


@router.post("/run", response_model=ScenarioResult)
def run_scenario(request: ScenarioRequest) -> ScenarioResult:
    """Run one scenario and return a distribution of outcomes — never a point estimate."""
    return engine.run(request)


@router.post("/compare", response_model=ScenarioComparison)
def compare_scenarios(requests: list[ScenarioRequest]) -> ScenarioComparison:
    """First request is the baseline; the rest are alternatives under identical assumptions."""
    return engine.compare(requests)
