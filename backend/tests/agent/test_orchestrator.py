"""OWNER: Member 4."""

from __future__ import annotations

import pytest

from app.agent import grounding, llm, orchestrator
from app.schemas.agent import AgentRequest, ToolCall, ToolName
from tests.agent.fakes import ScriptedLLM, install, response, text_block, tool_use

# ---------------------------------------------------------- deterministic router


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What happens if markets fall 30%?", ToolName.RUN_SCENARIO),
        ("What if I stop my SIP for six months?", ToolName.RUN_SCENARIO),
        ("What if my income drops for six months?", ToolName.RUN_SCENARIO),
        ("How am I doing financially?", ToolName.COMPUTE_HEALTH_SCORE),
        ("Show me my allocation", ToolName.ANALYZE_PORTFOLIO),
        ("Am I too concentrated in IT stocks?", ToolName.ANALYZE_PORTFOLIO),
        ("Will I reach my goal?", ToolName.PROJECT_GOAL),
        ("What is rupee cost averaging?", ToolName.RESEARCH_MARKET),
        ("Compare SIP of 15k vs 20k", ToolName.COMPARE_SCENARIOS),
    ],
)
def test_tool_selection(question, expected):
    assert orchestrator.select_tools(question)[0].tool == expected


@pytest.mark.parametrize(
    ("question", "arguments"),
    [
        ("What happens if markets fall 30%?", {"shock_pct": -0.30}),
        (
            "What if the market crashes 40% and recovers in 2 years?",
            {"shock_pct": -0.40, "recovery_months": 24},
        ),
        ("What if I stop my SIP for six months?", {"pause_months": 6}),
        (
            "What if my income drops for six months?",
            {"income_multiplier": 0.0, "income_shock_months": 6},
        ),
        (
            "What if my salary is cut by 20% for a year?",
            {"income_multiplier": 0.8, "income_shock_months": 12},
        ),
        ("What if I increase my SIP to ₹20,000?", {"new_monthly_contribution": 20_000}),
        ("What if I increase my SIP by 5k?", {"new_monthly_contribution": 20_000}),
        ("What if I go 60/40 equity debt?", {"target_weights": {"equity": 0.6, "debt": 0.4}}),
    ],
)
def test_router_extracts_arguments(question, arguments, profile):
    call = orchestrator.select_tools(question, profile)[0]
    assert call.arguments == arguments


def test_router_says_what_it_assumed(profile):
    call = orchestrator.select_tools("What if I lose my job?", profile)[0]
    assert "assumed 6 months" in call.reasoning


def test_describe_tools_lists_every_tool():
    names = {t["name"] for t in orchestrator.describe_tools()}
    assert names == {t.value for t in ToolName}


# ------------------------------------------------------------ deterministic path


DEMO_QUESTIONS = [
    "What happens if the market falls 30%?",
    "What if I stop my SIP for six months?",
    "What if my income drops for six months?",
    "Will I reach my goal?",
    "Show me my allocation",
    "Compare SIP of 15k vs 20k",
    "What is rupee cost averaging?",
]


@pytest.mark.parametrize("question", DEMO_QUESTIONS)
def test_template_answers_are_fully_grounded(question, profile):
    """Every number the fallback path shows must trace to tool output."""
    result = orchestrator.answer(AgentRequest(question=question, profile=profile))
    assert all(r.ok for r in result.tool_results)
    grounded = grounding.grounded_values(
        list(result.answer.numbers.values()), orchestrator.profile_context(profile), question
    )
    assert grounding.unverified_numbers(result.answer.summary, grounded) == []


def test_scenario_answer_carries_assumptions_and_caveat(profile):
    result = orchestrator.answer(
        AgentRequest(question="What if markets fall 30%?", profile=profile)
    )
    assert result.answer.assumptions is not None
    assert result.answer.assumptions.seed is not None
    assert any("not predictions" in c for c in result.answer.caveats)


def test_research_answer_carries_evidence(profile):
    result = orchestrator.answer(
        AgentRequest(question="What is rupee cost averaging?", profile=profile)
    )
    assert result.evidence
    assert result.evidence[0].source.startswith("knowledge/sip.md")


def test_missing_profile_uses_demo_and_says_so():
    result = orchestrator.answer(AgentRequest(question="Show me my allocation"))
    assert any("demo profile" in c for c in result.answer.caveats)


def test_unbuilt_tool_fails_softly(profile):
    result = orchestrator.answer(
        AgentRequest(question="Forecast volatility for INFY", profile=profile)
    )
    assert not result.tool_results[0].ok
    assert "not built yet" in result.answer.summary


def test_execute_reports_bad_arguments_as_failed_tool(profile):
    call = ToolCall(tool=ToolName.RUN_SCENARIO, arguments={"shock_pct": 0.5})
    result = orchestrator.execute(call, profile)
    assert not result.ok and result.error


# --------------------------------------------------------------------- LLM path


def test_llm_loop_runs_tools_and_keeps_grounded_prose(monkeypatch, profile):
    scripted = install(
        monkeypatch,
        ScriptedLLM(
            response(
                text_block("Running the crash scenario."),
                tool_use("run_scenario", {"shock_pct": -0.3}),
            ),
            response(text_block("A 30% fall lowers your median outcome; see the numbers.")),
        ),
    )
    result = orchestrator.answer(
        AgentRequest(question="What if markets fall 30%?", profile=profile)
    )

    assert [c.tool for c in result.tool_calls] == [ToolName.RUN_SCENARIO]
    assert result.tool_calls[0].reasoning == "Running the crash scenario."
    assert result.answer.summary == "A 30% fall lowers your median outcome; see the numbers."
    # Second request carries the tool result back, marked as a success.
    tool_result = scripted.requests[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["is_error"] is False
    # The model is never handed the raw profile inside tool arguments.
    assert "profile" not in result.tool_calls[0].arguments


def test_llm_prose_with_invented_number_is_replaced(monkeypatch, profile):
    install(
        monkeypatch,
        ScriptedLLM(
            response(tool_use("project_goal", {})),
            response(text_block("You will have ₹31.4 lakh, easily beating your goal.")),
        ),
    )
    result = orchestrator.answer(AgentRequest(question="Will I reach my goal?", profile=profile))
    assert "31.4" not in result.answer.summary
    assert result.answer.summary.startswith("On your current plan")
    assert any("₹31.4 lakh" in c for c in result.answer.caveats)


def test_llm_tool_error_is_sent_back_to_the_model(monkeypatch, profile):
    scripted = install(
        monkeypatch,
        ScriptedLLM(
            response(tool_use("run_scenario", {"shock_pct": 0.5})),
            response(text_block("That scenario was invalid.")),
        ),
    )
    orchestrator.answer(AgentRequest(question="What if markets rise 50%?", profile=profile))
    tool_result = scripted.requests[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True


def test_llm_failure_falls_back_to_router(monkeypatch, profile):
    def boom(**_):
        raise llm.LLMUnavailable("rate limited")

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "create", boom)
    result = orchestrator.answer(
        AgentRequest(question="What if markets fall 30%?", profile=profile)
    )
    assert result.tool_calls[0].tool == ToolName.RUN_SCENARIO
    assert any("rate limited" in c for c in result.answer.caveats)


def test_llm_that_never_stops_calling_tools_falls_back(monkeypatch, profile):
    endless = [response(tool_use("analyze_portfolio", {}, block_id=f"t{i}")) for i in range(20)]
    install(monkeypatch, ScriptedLLM(*endless))
    result = orchestrator.answer(AgentRequest(question="Show me my allocation", profile=profile))
    assert any("turn limit" in c for c in result.answer.caveats)


def test_select_tools_llm_reads_first_turn(monkeypatch, profile):
    install(monkeypatch, ScriptedLLM(response(tool_use("compute_health_score", {}))))
    calls = orchestrator.select_tools_llm("How am I doing?", profile)
    assert [c.tool for c in calls] == [ToolName.COMPUTE_HEALTH_SCORE]
