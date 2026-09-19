"""Question -> tool selection -> execution -> explanation.  OWNER: Member 4.

    LLM path            Claude picks tools (possibly several turns), the tools
                        run here, Claude explains. Its prose is then checked
                        against the tool output (grounding.py); a draft citing
                        a number no tool produced is replaced by the template
                        explanation.
    Deterministic path  router.py picks the tool, narrate.py explains. Used when
                        no API key is set or the API call fails, so the demo
                        never hard-fails.

Either way the numbers the user sees come from tools, never from the model.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.agent import grounding, llm, narrate, router
from app.agent.tools import TOOLS, to_llm_schema
from app.core.config import get_settings
from app.core.errors import NotImplementedYetError
from app.core.logging import get_logger
from app.data.sample import load_sample_profile
from app.schemas.agent import AgentRequest, AgentResponse, ToolCall, ToolName, ToolResult
from app.schemas.common import Assumptions, Evidence, Explanation
from app.schemas.profile import FinancialProfile

log = get_logger(__name__)

SYSTEM_PROMPT = """\
You are the analysis assistant inside FinTwin, a research prototype that models a \
person's finances as a "digital twin" and simulates what-if scenarios. You are not \
a financial adviser and FinTwin does not give personalised investment advice.

How to work:
- Answer by calling tools. The tools already have the user's profile.
- Every number in your answer must be copied from a tool result, the profile summary \
or the user's question. You may reformat a number (rupees into ₹ lakh or crore with \
one decimal, a fraction such as 0.32 into 32%), but never calculate, estimate or \
combine numbers yourself. If you need a figure no tool returned, call a tool or leave \
it out. Your answer is checked against the tool results, and an answer with a number \
that isn't there will be discarded.
- Use run_scenario for a single what-if and compare_scenarios for several \
alternatives. "Markets fall 30%" is shock_pct -0.30; "for six months" is 6.
- If the user leaves out the size or length of an event, choose a reasonable value \
and say what you assumed.
- For stock tips, price predictions or anything the tools don't cover, say FinTwin \
doesn't provide that, and offer what it can do instead.

How to answer:
- Plain language for someone new to investing: three to six sentences, no headings, \
no tables.
- Rupees as ₹15,000 below a lakh, ₹16.7 lakh, ₹1.25 crore.
- Simulated results are modeled outcomes under assumptions, not predictions. Say so \
briefly and name the most important assumption.
- If a goal falls short, use shortfall_drivers to explain what causes the gap and \
required_monthly_contribution to say what would close it.
"""


# ----------------------------------------------------------------- tool running


def execute(call: ToolCall, profile: FinancialProfile) -> ToolResult:
    """Run one tool against the injected profile. Failures become ok=False, not exceptions."""
    tool = TOOLS.get(call.tool)
    started = time.perf_counter()
    if tool is None:
        return ToolResult(tool=call.tool, ok=False, error=f"{call.tool.value} is not registered")
    try:
        output = tool.fn(profile, **call.arguments)
        ok, error = True, None
    except NotImplementedYetError as exc:
        output, ok, error = {}, False, f"this part of FinTwin is not built yet ({exc})"
    except Exception as exc:  # surfaced as a failed tool, not a 500
        log.warning("tool %s failed: %s", call.tool.value, exc)
        output, ok, error = {}, False, str(exc) or type(exc).__name__
    return ToolResult(
        tool=call.tool,
        ok=ok,
        output=output,
        error=error,
        latency_ms=(time.perf_counter() - started) * 1000,
    )


def _summary(result: ToolResult) -> Any:
    return result.output.get("summary", result.output)


def profile_context(profile: FinancialProfile) -> dict[str, Any]:
    """The facts about the user the model is shown. Also part of the grounding set."""
    cf = profile.cashflow
    return {
        "portfolio_value": round(profile.portfolio_value),
        "holdings": len(profile.holdings),
        "cash_balance": round(profile.cash_balance),
        "monthly_income": round(cf.monthly_income),
        "monthly_expenses": round(cf.monthly_expenses),
        "monthly_sip": round(cf.monthly_contribution),
        "monthly_emis": round(sum(liability.monthly_emi for liability in profile.liabilities)),
        "goals": [
            {"name": g.name, "target": round(g.target_amount), "horizon_months": g.horizon_months}
            for g in profile.goals
        ],
    }


# ----------------------------------------------------------------- explanation


def _assumptions(results: list[ToolResult]) -> Assumptions | None:
    """Assumptions of the first simulation that ran, for the transparency panel."""
    for result in results:
        if not result.ok:
            continue
        detail = result.output.get("detail")
        if result.tool in (ToolName.RUN_SCENARIO, ToolName.COMPARE_SCENARIOS) and detail:
            scenario = (detail.get("alternatives") or [detail["baseline"]])[0]
            return Assumptions(**scenario["assumptions"])
        if result.tool == ToolName.PROJECT_GOAL and detail:
            return Assumptions(**detail["assumptions"])
    return None


def _evidence(results: list[ToolResult]) -> list[Evidence]:
    return [
        Evidence(**item)
        for result in results
        if result.ok and result.tool == ToolName.RESEARCH_MARKET
        for item in result.output.get("detail", [])
    ]


def _caveats(results: list[ToolResult]) -> list[str]:
    caveats = []
    if any(
        r.ok
        and r.tool in (ToolName.RUN_SCENARIO, ToolName.COMPARE_SCENARIOS, ToolName.PROJECT_GOAL)
        for r in results
    ):
        caveats.append(
            "Simulated results are modeled outcomes under the stated assumptions, not predictions."
        )
    if any(r.ok and r.tool == ToolName.EXTRACT_DOCUMENT for r in results):
        caveats.append("Extracted values must be confirmed before they are used.")
    return caveats


def build_explanation(summary: str, results: list[ToolResult], caveats: list[str]) -> Explanation:
    return Explanation(
        summary=summary,
        assumptions=_assumptions(results),
        numbers={r.tool.value: _summary(r) for r in results if r.ok},
        evidence=_evidence(results),
        caveats=[*caveats, *_caveats(results)],
    )


# ---------------------------------------------------------------------- LLM path


def _answer_with_llm(
    question: str, profile: FinancialProfile
) -> tuple[str, list[ToolCall], list[ToolResult]]:
    """Run the tool loop. Returns the model's final prose and what it ran."""
    context = json.dumps(profile_context(profile))
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": f"User profile summary: {context}\n\nQuestion: {question}"}
    ]
    calls: list[ToolCall] = []
    results: list[ToolResult] = []

    for _turn in range(get_settings().agent_max_turns):
        response = llm.create(system=SYSTEM_PROMPT, tools=to_llm_schema(), messages=messages)
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return llm.text_of(response), calls, results

        reasoning = llm.text_of(response) or None
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in tool_uses:
            try:
                call = ToolCall(
                    tool=ToolName(block.name), arguments=dict(block.input), reasoning=reasoning
                )
            except ValueError:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: unknown tool {block.name!r}",
                        "is_error": True,
                    }
                )
                continue
            result = execute(call, profile)
            calls.append(call)
            results.append(result)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(_summary(result))
                    if result.ok
                    else f"Error: {result.error}",
                    "is_error": not result.ok,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    raise llm.LLMUnavailable("the model did not finish within the turn limit")


def select_tools_llm(question: str, profile: FinancialProfile) -> list[ToolCall]:
    """The LLM's first-turn tool choice, without running anything. For the benchmark."""
    context = json.dumps(profile_context(profile))
    response = llm.create(
        system=SYSTEM_PROMPT,
        tools=to_llm_schema(),
        messages=[
            {"role": "user", "content": f"User profile summary: {context}\n\nQuestion: {question}"}
        ],
    )
    calls = []
    for block in response.content:
        if block.type == "tool_use":
            try:
                calls.append(ToolCall(tool=ToolName(block.name), arguments=dict(block.input)))
            except ValueError:
                log.warning("model chose unknown tool %r", block.name)
    return calls


# -------------------------------------------------------------------- public API


def select_tools(question: str, profile: FinancialProfile | None = None) -> list[ToolCall]:
    """Deterministic tool choice (keyword router). See router.py."""
    return router.select_tools(question, profile)


def answer(request: AgentRequest) -> AgentResponse:
    started = time.perf_counter()
    caveats: list[str] = []

    profile = request.profile
    if profile is None:
        profile = load_sample_profile()
        caveats.append("No profile was sent, so this answer uses the demo profile.")

    if llm.available():
        try:
            text, calls, results = _answer_with_llm(request.question, profile)
        except llm.LLMUnavailable as exc:
            log.warning("LLM path failed (%s); using the deterministic router", exc)
            caveats.append(
                f"The language model was unavailable ({exc}); this answer uses templates."
            )
        else:
            grounded = grounding.grounded_values(
                [_summary(r) for r in results if r.ok],
                profile_context(profile),
                request.question,
            )
            unverified = grounding.unverified_numbers(text, grounded)
            if unverified:
                log.warning("discarding LLM draft with ungrounded numbers: %s", unverified)
                caveats.append(
                    "The language model's draft cited figures that no tool produced "
                    f"({', '.join(unverified)}), so it was replaced with a template explanation."
                )
                text = narrate.narrate(results)
            return AgentResponse(
                answer=build_explanation(text, results, caveats),
                tool_calls=calls,
                tool_results=results,
                evidence=_evidence(results),
                latency_ms=(time.perf_counter() - started) * 1000,
            )

    calls = select_tools(request.question, profile)
    results = [execute(call, profile) for call in calls]
    return AgentResponse(
        answer=build_explanation(narrate.narrate(results), results, caveats),
        tool_calls=calls,
        tool_results=results,
        evidence=_evidence(results),
        latency_ms=(time.perf_counter() - started) * 1000,
    )


def describe_tools() -> list[dict[str, str]]:
    return [{"name": t["name"], "description": t["description"]} for t in to_llm_schema()]
