"""The tool registry the LLM chooses from — OWNER: Member 4.

Each tool binds a ToolName to real code owned by another member. The model
never sees or passes the user's profile: the orchestrator injects it, so the
model only chooses *what to ask*, never the data the answer is computed from.

Every tool returns {"summary": ..., "detail": ...}. The compact `summary` is
what the model reads and what Explanation.numbers carries; `detail` is the
full typed output for the UI (charts, tables).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent import extraction, research
from app.core.config import get_settings
from app.ml import volatility
from app.quant import analytics, health_score
from app.schemas.agent import ToolName
from app.schemas.profile import FinancialProfile
from app.schemas.scenario import (
    AllocationChangeParams,
    ContributionChangeParams,
    IncomeShockParams,
    MarketStressParams,
    ScenarioComparison,
    ScenarioRequest,
    ScenarioResult,
    ScenarioType,
    SimulationSettings,
)
from app.simulation import engine

ToolFn = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class Tool:
    name: ToolName
    description: str
    input_schema: dict[str, Any]
    fn: ToolFn


# --------------------------------------------------------------- scenario input

_ASSET_CLASSES = ["equity", "debt", "gold", "cash", "real_estate", "crypto", "other"]

SCENARIO_PROPERTIES: dict[str, Any] = {
    "horizon_months": {
        "type": "integer",
        "minimum": 1,
        "maximum": 600,
        "description": "Months to simulate. Omit to use the user's longest goal horizon.",
    },
    "shock_pct": {
        "type": "number",
        "minimum": -0.95,
        "maximum": 0,
        "description": "One-off market fall as a negative decimal: -0.30 means a 30% fall.",
    },
    "shock_at_month": {
        "type": "integer",
        "minimum": 0,
        "description": "Month of the fall. Default 0.",
    },
    "recovery_months": {
        "type": "integer",
        "minimum": 1,
        "description": "Only if the user describes a recovery: months to regain the lost level.",
    },
    "income_multiplier": {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "description": "Share of income kept during an income shock. 0 = income stops.",
    },
    "income_shock_months": {
        "type": "integer",
        "minimum": 1,
        "description": "Length of the income shock.",
    },
    "income_shock_start_month": {"type": "integer", "minimum": 0},
    "new_monthly_contribution": {
        "type": "number",
        "minimum": 0,
        "description": "New monthly SIP amount in rupees.",
    },
    "pause_months": {"type": "integer", "minimum": 1, "description": "Months the SIP is paused."},
    "pause_start_month": {"type": "integer", "minimum": 0},
    "target_weights": {
        "type": "object",
        "description": (
            "Hypothetical asset-class mix, weights summing to 1, "
            'e.g. {"equity": 0.6, "debt": 0.4}.'
        ),
        "properties": {
            asset: {"type": "number", "minimum": 0, "maximum": 1} for asset in _ASSET_CLASSES
        },
        "additionalProperties": False,
    },
}


def default_horizon(profile: FinancialProfile) -> int:
    """The user's longest goal, or five years if they have none."""
    return max((g.horizon_months for g in profile.goals), default=60)


def _settings() -> SimulationSettings:
    s = get_settings()
    return SimulationSettings(n_paths=s.simulation_default_paths, seed=s.simulation_seed)


def build_scenario_request(profile: FinancialProfile, args: dict[str, Any]) -> ScenarioRequest:
    """Flat tool arguments -> a validated ScenarioRequest. Raises on bad input."""
    unknown = set(args) - set(SCENARIO_PROPERTIES)
    if unknown:
        raise ValueError(f"unknown scenario arguments: {sorted(unknown)}")

    market = income = contribution = allocation = None
    if "shock_pct" in args:
        market = MarketStressParams(
            shock_pct=args["shock_pct"],
            shock_at_month=args.get("shock_at_month", 0),
            recovery_months=args.get("recovery_months"),
        )
    if "income_multiplier" in args or "income_shock_months" in args:
        income = IncomeShockParams(
            income_multiplier=args.get("income_multiplier", 0.0),
            duration_months=args.get("income_shock_months", 6),
            start_month=args.get("income_shock_start_month", 0),
        )
    if "new_monthly_contribution" in args or "pause_months" in args:
        contribution = ContributionChangeParams(
            new_monthly_contribution=args.get("new_monthly_contribution"),
            pause_months=args.get("pause_months", 0),
            pause_start_month=args.get("pause_start_month", 0),
        )
    if "target_weights" in args:
        allocation = AllocationChangeParams(target_weights=args["target_weights"])

    if allocation:
        kind = ScenarioType.ALLOCATION_CHANGE
    elif market:
        kind = ScenarioType.MARKET_STRESS
    elif income:
        kind = ScenarioType.INCOME_SHOCK
    elif contribution and contribution.pause_months:
        kind = ScenarioType.SIP_INTERRUPTION
    elif contribution:
        kind = ScenarioType.CONTRIBUTION_CHANGE
    else:
        kind = ScenarioType.BASELINE

    return ScenarioRequest(
        profile=profile,
        scenario_type=kind,
        horizon_months=args.get("horizon_months", default_horizon(profile)),
        settings=_settings(),
        market_stress=market,
        income_shock=income,
        contribution_change=contribution,
        allocation_change=allocation,
    )


# ------------------------------------------------------------- compact summaries


def _median(result: ScenarioResult) -> float:
    return next(p.value for p in result.terminal_percentiles if p.p == 50)


def _pct(result: ScenarioResult, p: float) -> float | None:
    return next((x.value for x in result.terminal_percentiles if x.p == p), None)


def _outcome_summary(result: ScenarioResult) -> dict[str, Any]:
    return {
        "median": round(_median(result)),
        "p10": round(_pct(result, 10) or 0),
        "p90": round(_pct(result, 90) or 0),
        "total_contributed": round(result.total_contributed),
    }


def summarize_comparison(comparison: ScenarioComparison) -> dict[str, Any]:
    """Everything the model needs to explain a what-if, and nothing it doesn't."""
    base = comparison.baseline
    alternatives = []
    for alt in comparison.alternatives:
        base_goals = {g.goal_name: g for g in base.goal_outcomes}
        goals = []
        for g in alt.goal_outcomes:
            b = base_goals.get(g.goal_name)
            goals.append(
                {
                    "goal": g.goal_name,
                    "target": round(g.target_amount),
                    "evaluated_at_month": g.evaluated_at_month,
                    "baseline_success_probability": round(b.success_probability, 2) if b else None,
                    "scenario_success_probability": round(g.success_probability, 2),
                    "scenario_median_shortfall": round(g.median_shortfall),
                    "shortfall_drivers": {k: round(v) for k, v in g.shortfall_drivers.items()},
                    "required_monthly_contribution": (
                        round(g.required_monthly_contribution)
                        if g.required_monthly_contribution is not None
                        else None
                    ),
                }
            )
        alternatives.append(
            {
                "scenario": alt.label,
                "outcome": _outcome_summary(alt),
                "change_in_median": round(_median(alt) - _median(base)),
                "current_monthly_contribution": round(alt.assumptions.monthly_contribution),
                "goals": goals,
                "cash_runway_months": (
                    round(alt.cash_runway_months, 1) if alt.cash_runway_months is not None else None
                ),
                "assumptions": {
                    "expected_annual_return": round(alt.assumptions.expected_annual_return, 4),
                    "annual_volatility": round(alt.assumptions.annual_volatility, 4),
                    "n_paths": alt.assumptions.n_paths,
                    "seed": alt.assumptions.seed,
                    "notes": alt.assumptions.notes,
                },
            }
        )
    return {
        "horizon_months": base.assumptions.horizon_months,
        "baseline": _outcome_summary(base),
        "alternatives": alternatives,
    }


# ------------------------------------------------------------------ tool bodies


def _analyze_portfolio(profile: FinancialProfile) -> dict[str, Any]:
    metrics = analytics.analyze(profile)
    conc = metrics.concentration
    return {
        "summary": {
            "total_value": round(metrics.total_value),
            "by_asset_class": {s.label: round(s.weight, 3) for s in metrics.by_asset_class},
            "by_sector": {s.label: round(s.weight, 3) for s in metrics.by_sector},
            "top_holdings": {s.label: round(s.weight, 3) for s in metrics.by_holding[:5]},
            "effective_holdings": round(conc.effective_holdings, 2) if conc else None,
            "hhi": round(conc.hhi, 3) if conc else None,
            "flags": conc.flags if conc else [],
            "risk_metrics": {k: v for k, v in metrics.risk.model_dump().items() if v is not None},
        },
        "detail": metrics.model_dump(mode="json"),
    }


def _compute_health_score(profile: FinancialProfile) -> dict[str, Any]:
    score = health_score.compute(profile)
    dims = score.model_dump(exclude={"drivers"})
    return {
        "summary": {
            **{k: round(v, 1) for k, v in dims.items()},
            "drivers": {k: round(v, 2) for k, v in score.drivers.items()},
        },
        "detail": score.model_dump(mode="json"),
    }


def _run_scenario(profile: FinancialProfile, **args: Any) -> dict[str, Any]:
    comparison = engine.whatif(build_scenario_request(profile, args))
    return {
        "summary": summarize_comparison(comparison),
        "detail": comparison.model_dump(mode="json"),
    }


def _compare_scenarios(
    profile: FinancialProfile, scenarios: list[dict[str, Any]]
) -> dict[str, Any]:
    if not scenarios:
        raise ValueError("compare_scenarios needs at least one scenario")
    horizon = scenarios[0].get("horizon_months", default_horizon(profile))
    requests = [
        build_scenario_request(profile, {**s, "horizon_months": horizon}) for s in scenarios
    ]
    comparison = engine.compare([engine.baseline_for(requests[0]), *requests])
    return {
        "summary": summarize_comparison(comparison),
        "detail": comparison.model_dump(mode="json"),
    }


def _project_goal(profile: FinancialProfile, horizon_months: int | None = None) -> dict[str, Any]:
    if not profile.goals:
        raise ValueError("the profile has no goals to project")
    request = build_scenario_request(
        profile, {"horizon_months": horizon_months or default_horizon(profile)}
    )
    result = engine.run(request)
    return {
        "summary": {
            "horizon_months": request.horizon_months,
            "median": round(_median(result)),
            "goals": [
                {
                    "goal": g.goal_name,
                    "target": round(g.target_amount),
                    "evaluated_at_month": g.evaluated_at_month,
                    "success_probability": round(g.success_probability, 2),
                    "median_shortfall": round(g.median_shortfall),
                    "required_monthly_contribution": round(g.required_monthly_contribution or 0),
                }
                for g in result.goal_outcomes
            ],
            "current_monthly_contribution": round(profile.cashflow.monthly_contribution),
            "notes": result.assumptions.notes,
        },
        "detail": result.model_dump(mode="json"),
    }


def _extract_document(profile: FinancialProfile, text: str) -> dict[str, Any]:
    result = extraction.extract_text(text, filename="pasted-text")
    return {
        "summary": {
            "fields": [
                {"field": f.field, "value": f.value, "confidence": f.confidence}
                for f in result.fields
            ],
            "needs_user_confirmation": True,
            "warnings": result.warnings,
        },
        "detail": result.model_dump(mode="json"),
    }


def _research_market(profile: FinancialProfile, query: str) -> dict[str, Any]:
    evidence = research.research(query)
    return {
        "summary": {
            "results": [
                {"source": e.source, "text": e.snippet, "relevance": e.confidence} for e in evidence
            ],
            "note": None if evidence else "No sufficiently relevant passage in the knowledge base.",
        },
        "detail": [e.model_dump(mode="json") for e in evidence],
    }


def _forecast_volatility(
    profile: FinancialProfile, symbol: str, horizon_days: int = 21
) -> dict[str, Any]:
    forecast = volatility.forecast_volatility(symbol, horizon_days)
    return {"summary": forecast, "detail": forecast}


# --------------------------------------------------------------------- registry

_NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

TOOLS: dict[ToolName, Tool] = {
    tool.name: tool
    for tool in [
        Tool(
            ToolName.ANALYZE_PORTFOLIO,
            "Break down the user's current portfolio: allocation by asset class, sector and "
            "holding, concentration (effective number of holdings) and any risk flags. Use for "
            "'what do I hold', 'am I diversified', 'am I too concentrated in X'.",
            _NO_ARGS,
            _analyze_portfolio,
        ),
        Tool(
            ToolName.COMPUTE_HEALTH_SCORE,
            "Score the user's overall financial health (0-100) across liquidity, debt burden, "
            "diversification, goal progress and market exposure, with the inputs behind each "
            "score. Use for 'how am I doing financially' or 'what should I worry about'.",
            _NO_ARGS,
            _compute_health_score,
        ),
        Tool(
            ToolName.RUN_SCENARIO,
            "Simulate ONE what-if against the user's current plan and return both, under "
            "identical assumptions: outcome ranges, change in the median, goal success "
            "probabilities, what drove any goal shortfall, and the SIP needed to close it. "
            "Combine arguments for combined events (e.g. a crash AND a SIP pause). Use for "
            "any hypothetical: 'what if markets fall 30%', 'what if I stop my SIP for 6 "
            "months', 'what if I lose my job', 'what if I move to 60/40'.",
            {"type": "object", "properties": SCENARIO_PROPERTIES, "additionalProperties": False},
            _run_scenario,
        ),
        Tool(
            ToolName.COMPARE_SCENARIOS,
            "Compare SEVERAL alternatives side by side against the current plan, e.g. 'SIP of "
            "15k vs 20k vs pausing for 6 months'. Each entry takes the same arguments as "
            "run_scenario. Use run_scenario instead when there is only one alternative.",
            {
                "type": "object",
                "properties": {
                    "scenarios": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "properties": SCENARIO_PROPERTIES,
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["scenarios"],
                "additionalProperties": False,
            },
            _compare_scenarios,
        ),
        Tool(
            ToolName.PROJECT_GOAL,
            "Project the user's current plan with no changes: chance of reaching each goal, "
            "expected shortfall, and the monthly SIP needed to reach it. Use for 'will I reach "
            "my goal', 'am I on track', 'how much should I invest per month'.",
            {
                "type": "object",
                "properties": {"horizon_months": SCENARIO_PROPERTIES["horizon_months"]},
                "additionalProperties": False,
            },
            _project_goal,
        ),
        Tool(
            ToolName.EXTRACT_DOCUMENT,
            "Extract holdings, balances and income from statement text the user pasted into "
            "the chat. Values are proposals that the user must confirm before they are used.",
            {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "The pasted text."}},
                "required": ["text"],
                "additionalProperties": False,
            },
            _extract_document,
        ),
        Tool(
            ToolName.RESEARCH_MARKET,
            "Look up background from FinTwin's sourced knowledge base: concepts (SIP, "
            "diversification, drawdowns, emergency funds, Monte Carlo) and historical market "
            "episodes. Use for 'what is', 'why', 'how does' questions, and to back up an "
            "explanation with a source. It does not cover live prices or individual stock tips.",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            _research_market,
        ),
        Tool(
            ToolName.FORECAST_VOLATILITY,
            "Forecast a symbol's volatility over the coming days, alongside a naive baseline "
            "and the model's historical error.",
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "horizon_days": {"type": "integer", "minimum": 1, "maximum": 252},
                },
                "required": ["symbol"],
                "additionalProperties": False,
            },
            _forecast_volatility,
        ),
    ]
}

# Kept for callers written against the scaffold's name.
TOOL_REGISTRY = TOOLS


def to_llm_schema() -> list[dict[str, Any]]:
    """Tool definitions in the shape the Messages API expects."""
    return [
        {"name": t.name.value, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS.values()
    ]
