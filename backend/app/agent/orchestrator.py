"""Question -> tool selection -> execution -> explanation.  OWNER: Member 4.

Ships with a keyword router so the pipeline is testable before the LLM is wired
in. Replace `select_tools` with real tool-calling; keep `answer`'s shape intact
because the frontend and the benchmark both depend on it.
"""

from __future__ import annotations

import time

from app.agent.tools import TOOL_REGISTRY, to_llm_schema
from app.core.logging import get_logger
from app.schemas.agent import AgentRequest, AgentResponse, ToolCall, ToolName, ToolResult
from app.schemas.common import Explanation

log = get_logger(__name__)


def select_tools(question: str) -> list[ToolCall]:
    """Decide which tools answer this question.

    TODO(member-4): replace with LLM tool-calling against to_llm_schema().
    The keyword rules below are a placeholder AND the fallback for when the API
    key is missing — keep a deterministic path so the demo never hard-fails.
    """
    q = question.lower()
    scenario_words = ("what if", "what happens if", "crash", "falls", "stop my sip", "pause")
    if any(k in q for k in scenario_words):
        return [ToolCall(tool=ToolName.RUN_SCENARIO, reasoning="hypothetical / scenario question")]
    if any(k in q for k in ("health", "how am i doing", "score")):
        return [ToolCall(tool=ToolName.COMPUTE_HEALTH_SCORE, reasoning="overall health question")]
    return [ToolCall(tool=ToolName.ANALYZE_PORTFOLIO, reasoning="default portfolio question")]


def execute(call: ToolCall) -> ToolResult:
    entry = TOOL_REGISTRY.get(call.tool)
    if entry is None:
        return ToolResult(tool=call.tool, ok=False, error=f"{call.tool.value} not registered")

    fn, _description, _schema = entry
    started = time.perf_counter()
    try:
        output = fn(**call.arguments)
        return ToolResult(
            tool=call.tool, ok=True, output=output,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:  # surfaced to the user as a failed tool, not a 500
        log.exception("tool %s failed", call.tool.value)
        return ToolResult(
            tool=call.tool, ok=False, error=str(exc),
            latency_ms=(time.perf_counter() - started) * 1000,
        )


def explain(question: str, results: list[ToolResult]) -> Explanation:
    """Turn tool output into plain language.

    TODO(member-4): send question + tool output to the LLM with a system prompt
    that forbids inventing numbers. Copy every figure through from `results`
    into Explanation.numbers so the UI can cross-check what was said.
    """
    ok = [r for r in results if r.ok]
    return Explanation(
        summary=(
            f"Ran {len(ok)} tool(s) for: {question!r}. "
            "LLM explanation not wired up yet — see app/agent/orchestrator.py:explain."
        ),
        numbers={r.tool.value: r.output for r in ok},
        caveats=["Placeholder explanation. Numbers are real tool output."],
    )


def answer(request: AgentRequest) -> AgentResponse:
    started = time.perf_counter()

    calls = select_tools(request.question)
    if request.profile is not None:
        for call in calls:
            call.arguments.setdefault("profile", request.profile.model_dump())

    results = [execute(call) for call in calls]
    return AgentResponse(
        answer=explain(request.question, results),
        tool_calls=calls,
        tool_results=results,
        latency_ms=(time.perf_counter() - started) * 1000,
    )


def describe_tools() -> list[dict[str, str]]:
    return [{"name": t["name"], "description": t["description"]} for t in to_llm_schema()]
