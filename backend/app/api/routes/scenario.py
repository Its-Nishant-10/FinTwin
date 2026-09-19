"""Scenario / Monte Carlo endpoints.  OWNER: Member 5 (Simulation)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, HTTPException

from app.core.errors import InsufficientDataError, NotImplementedYetError
from app.schemas import ScenarioComparison, ScenarioRequest, ScenarioResult
from app.simulation import engine

router = APIRouter(prefix="/scenario", tags=["scenario"])

T = TypeVar("T")


def _call(fn: Callable[[], T]) -> T:
    """Turn the engine's domain errors into HTTP errors instead of 500s."""
    try:
        return fn()
    except (ValueError, InsufficientDataError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedYetError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.post("/run", response_model=ScenarioResult)
def run_scenario(request: ScenarioRequest) -> ScenarioResult:
    """Run one scenario and return a distribution of outcomes — never a point estimate."""
    return _call(lambda: engine.run(request))


@router.post("/whatif", response_model=ScenarioComparison)
def whatif(request: ScenarioRequest) -> ScenarioComparison:
    """Run one scenario next to an automatically built baseline under identical assumptions."""
    return _call(lambda: engine.whatif(request))


@router.post("/compare", response_model=ScenarioComparison)
def compare_scenarios(requests: list[ScenarioRequest]) -> ScenarioComparison:
    """First request is the baseline; the rest are alternatives under identical assumptions."""
    return _call(lambda: engine.compare(requests))
