"""OWNER: Member 4. Keep these passing as the keyword router is replaced by the LLM."""

from __future__ import annotations

import pytest

from app.agent import orchestrator
from app.schemas.agent import ToolName


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What happens if markets fall 30%?", ToolName.RUN_SCENARIO),
        ("What if I stop my SIP for six months?", ToolName.RUN_SCENARIO),
        ("How am I doing financially?", ToolName.COMPUTE_HEALTH_SCORE),
        ("Show me my allocation", ToolName.ANALYZE_PORTFOLIO),
    ],
)
def test_tool_selection(question, expected):
    assert orchestrator.select_tools(question)[0].tool == expected


def test_describe_tools_lists_registry():
    tools = orchestrator.describe_tools()
    assert {t["name"] for t in tools} >= {"analyze_portfolio", "run_scenario"}
