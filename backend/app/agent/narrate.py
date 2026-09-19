"""Template explanations — OWNER: Member 4.

Plain-language answers assembled directly from tool summaries. Used when the
LLM is unavailable, and as the replacement whenever the LLM's draft cites a
number no tool produced. Every figure here is copied from tool output, so these
explanations are grounded by construction (a test checks that).
"""

from __future__ import annotations

from typing import Any

from app.agent.grounding import format_inr, format_pct
from app.schemas.agent import ToolName, ToolResult

_DRIVER_LABELS = {
    "baseline_plan": "your current plan on its own",
    "market_shock": "the market fall",
    "contribution_change": "the change to your SIP",
    "income_shock": "the income shock",
    "allocation_change": "the new allocation",
}


def _signed_inr(value: float) -> str:
    return ("+" if value >= 0 else "-") + format_inr(abs(value))


def _drivers_sentence(goal: dict[str, Any]) -> str:
    parts = []
    for key, value in sorted(goal["shortfall_drivers"].items(), key=lambda kv: -abs(kv[1])):
        if abs(value) < 1:
            continue
        label = _DRIVER_LABELS.get(key, key.replace("_", " "))
        if key == "baseline_plan":
            parts.append(
                f"{label} leaves a gap of {format_inr(value)}"
                if value > 0
                else f"{label} would clear the target by {format_inr(-value)}"
            )
        else:
            parts.append(
                f"{label} costs {format_inr(value)}"
                if value > 0
                else f"{label} adds {format_inr(-value)}"
            )
    return "Breaking that down: " + "; ".join(parts) + "." if parts else ""


def _scenario(summary: dict[str, Any]) -> str:
    base = summary["baseline"]
    h = summary["horizon_months"]
    sentences = []
    for alt in summary["alternatives"]:
        out = alt["outcome"]
        sentences.append(
            f"{alt['scenario']}: after {h} months the median modeled portfolio is "
            f"{format_inr(out['median'])}, against {format_inr(base['median'])} if nothing "
            f"changes ({_signed_inr(alt['change_in_median'])})."
        )
        sentences.append(
            f"In this scenario, 8 in 10 simulated outcomes land between {format_inr(out['p10'])} "
            f"and {format_inr(out['p90'])}."
        )
        for goal in alt["goals"]:
            scenario_chance = format_pct(goal["scenario_success_probability"])
            baseline_chance = format_pct(goal["baseline_success_probability"])
            sentences.append(
                f"The chance of reaching '{goal['goal']}' ({format_inr(goal['target'])} by month "
                f"{goal['evaluated_at_month']}) is {scenario_chance}, compared with "
                f"{baseline_chance} on your current plan."
            )
            shortfall = goal["scenario_median_shortfall"]
            if shortfall > 0:
                sentences.append(
                    f"The median outcome falls {format_inr(shortfall)} short. "
                    + _drivers_sentence(goal)
                )
                required = goal.get("required_monthly_contribution")
                current = alt.get("current_monthly_contribution")
                if required and current is not None and required > current:
                    sentences.append(
                        f"A steady SIP of about {format_inr(required)} a month, instead of "
                        f"{format_inr(current)}, would bring the median outcome up to the target "
                        "under the same market conditions."
                    )
        if alt.get("cash_runway_months") is not None:
            sentences.append(
                f"At the reduced income, your cash covers about {alt['cash_runway_months']:g} "
                "months of expenses and EMIs."
            )
    return " ".join(s for s in sentences if s)


def _comparison(summary: dict[str, Any]) -> str:
    base = summary["baseline"]
    sentences = [
        f"After {summary['horizon_months']} months your current plan has a median modeled "
        f"portfolio of {format_inr(base['median'])}."
    ]
    for alt in summary["alternatives"]:
        line = (
            f"{alt['scenario']}: {format_inr(alt['outcome']['median'])} "
            f"({_signed_inr(alt['change_in_median'])})"
        )
        goal = alt["goals"][0] if alt["goals"] else None
        if goal:
            line += (
                f", with a {format_pct(goal['scenario_success_probability'])} chance of "
                f"reaching '{goal['goal']}'"
            )
        sentences.append(line + ".")
    return " ".join(sentences)


def _project_goal(summary: dict[str, Any]) -> str:
    sentences = [
        f"On your current plan of {format_inr(summary['current_monthly_contribution'])} a month, "
        f"the median modeled portfolio after {summary['horizon_months']} months is "
        f"{format_inr(summary['median'])}."
    ]
    for goal in summary["goals"]:
        sentences.append(
            f"The chance of reaching '{goal['goal']}' ({format_inr(goal['target'])} by month "
            f"{goal['evaluated_at_month']}) is {format_pct(goal['success_probability'])}."
        )
        if goal["median_shortfall"] > 0:
            required = format_inr(goal["required_monthly_contribution"])
            sentences.append(
                f"The median outcome falls {format_inr(goal['median_shortfall'])} short; a SIP of "
                f"about {required} a month would bring the median up to the target."
            )
        else:
            sentences.append("The median outcome reaches the target.")
    return " ".join(sentences)


def _portfolio(summary: dict[str, Any]) -> str:
    mix = ", ".join(f"{label} {format_pct(w)}" for label, w in summary["by_asset_class"].items())
    sentences = [
        f"Your portfolio is worth {format_inr(summary['total_value'])}. By asset class: {mix}."
    ]
    if summary.get("by_sector"):
        top_sector, weight = next(iter(summary["by_sector"].items()))
        sentences.append(f"The largest sector is {top_sector} at {format_pct(weight)}.")
    if summary.get("effective_holdings"):
        sentences.append(
            f"It behaves like about {summary['effective_holdings']:g} equally sized holdings."
        )
    sentences.extend(summary.get("flags", []))
    return " ".join(sentences)


def _health(summary: dict[str, Any]) -> str:
    dims = ["liquidity", "debt_burden", "diversification", "goal_progress", "market_exposure"]
    scores = ", ".join(f"{d.replace('_', ' ')} {summary[d]:g}" for d in dims)
    return f"Overall financial health score: {summary['overall']:g} out of 100 ({scores})."


def _research(summary: dict[str, Any]) -> str:
    results = summary.get("results", [])
    if not results:
        return "FinTwin's knowledge base has nothing sufficiently relevant to that question."
    top = results[0]
    return f"From FinTwin's knowledge base: {top['text']} (source: {top['source']})"


def _extraction(summary: dict[str, Any]) -> str:
    fields = summary.get("fields", [])
    if not fields:
        return "I could not find any figures to extract from that text."
    return (
        f"I found {len(fields)} value(s) in the text. They are proposals only: please "
        "confirm each one before it is added to your profile."
    )


_NARRATORS = {
    ToolName.RUN_SCENARIO: _scenario,
    ToolName.COMPARE_SCENARIOS: _comparison,
    ToolName.PROJECT_GOAL: _project_goal,
    ToolName.ANALYZE_PORTFOLIO: _portfolio,
    ToolName.COMPUTE_HEALTH_SCORE: _health,
    ToolName.RESEARCH_MARKET: _research,
    ToolName.EXTRACT_DOCUMENT: _extraction,
}


def narrate(results: list[ToolResult]) -> str:
    parts = []
    for result in results:
        if not result.ok:
            parts.append(f"I couldn't run {result.tool.value}: {result.error}")
            continue
        narrator = _NARRATORS.get(result.tool)
        summary = result.output.get("summary", result.output)
        parts.append(narrator(summary) if narrator else f"{result.tool.value} returned: {summary}")
    return " ".join(parts) or "I couldn't find a tool that answers that question."
