"""The tool registry the LLM chooses from — OWNER: Member 4.

Each entry binds a ToolName to a real Python callable owned by another member.
Keep the descriptions written for the model: say when to use the tool, not how
it is implemented.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.quant import analytics, health_score
from app.schemas.agent import ToolName
from app.simulation import engine


def _analyze_portfolio(profile: dict, **_: Any) -> dict:
    from app.schemas.profile import FinancialProfile

    return analytics.analyze(FinancialProfile(**profile)).model_dump()


def _compute_health_score(profile: dict, **_: Any) -> dict:
    from app.schemas.profile import FinancialProfile

    return health_score.compute(FinancialProfile(**profile)).model_dump()


def _run_scenario(**kwargs: Any) -> dict:
    from app.schemas.scenario import ScenarioRequest

    return engine.run(ScenarioRequest(**kwargs)).model_dump()


#: tool name -> (callable, description shown to the LLM, JSON schema of arguments)
TOOL_REGISTRY: dict[ToolName, tuple[Callable[..., dict], str, dict]] = {
    ToolName.ANALYZE_PORTFOLIO: (
        _analyze_portfolio,
        "Break down the user's portfolio: allocation by asset class and sector, "
        "concentration, correlation and risk metrics. Use for 'what do I hold', "
        "'am I diversified', 'how risky is my portfolio'.",
        {"profile": "FinancialProfile"},
    ),
    ToolName.COMPUTE_HEALTH_SCORE: (
        _compute_health_score,
        "Score the user's overall financial health across liquidity, debt, "
        "diversification, goal progress and market exposure. Use for "
        "'how am I doing financially'.",
        {"profile": "FinancialProfile"},
    ),
    ToolName.RUN_SCENARIO: (
        _run_scenario,
        "Simulate a what-if: a market crash, an income shock, or a change/pause "
        "in monthly contributions. Returns a distribution of outcomes. Use for "
        "any question containing 'what if', 'what happens if', or a hypothetical.",
        {"profile": "FinancialProfile", "scenario_type": "str", "horizon_months": "int"},
    ),
    # TODO(member-4): register COMPARE_SCENARIOS, PROJECT_GOAL, EXTRACT_DOCUMENT,
    # RESEARCH_MARKET and FORECAST_VOLATILITY as their owners land them.
}


def to_llm_schema() -> list[dict]:
    """Render the registry as tool definitions for the LLM API.

    TODO(member-4): emit proper JSON Schema per tool rather than the placeholder
    argument map above.
    """
    return [
        {"name": name.value, "description": description, "input_schema": schema}
        for name, (_fn, description, schema) in TOOL_REGISTRY.items()
    ]
