"""OWNER: Member 4."""

from __future__ import annotations

import pytest

from app.agent import tools
from app.schemas.agent import ToolName
from app.schemas.scenario import ScenarioType


def test_every_tool_name_is_registered():
    assert set(tools.TOOLS) == set(ToolName)


def test_llm_schemas_are_closed_objects():
    for definition in tools.to_llm_schema():
        schema = definition["input_schema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "profile" not in schema["properties"]


@pytest.mark.parametrize(
    ("args", "expected_type"),
    [
        ({}, ScenarioType.BASELINE),
        ({"shock_pct": -0.3}, ScenarioType.MARKET_STRESS),
        ({"income_shock_months": 6}, ScenarioType.INCOME_SHOCK),
        ({"pause_months": 6}, ScenarioType.SIP_INTERRUPTION),
        ({"new_monthly_contribution": 20_000}, ScenarioType.CONTRIBUTION_CHANGE),
        ({"target_weights": {"equity": 0.6, "debt": 0.4}}, ScenarioType.ALLOCATION_CHANGE),
    ],
)
def test_build_scenario_request_types(profile, args, expected_type):
    request = tools.build_scenario_request(profile, args)
    assert request.scenario_type == expected_type
    assert request.horizon_months == 60  # the demo profile's goal horizon


def test_build_scenario_request_rejects_unknown_arguments(profile):
    with pytest.raises(ValueError, match="unknown"):
        tools.build_scenario_request(profile, {"shock": -0.3})


def test_run_scenario_summary_has_baseline_and_alternative(profile):
    output = tools.TOOLS[ToolName.RUN_SCENARIO].fn(profile, shock_pct=-0.3)
    summary = output["summary"]
    assert summary["alternatives"][0]["change_in_median"] < 0
    assert summary["alternatives"][0]["goals"][0]["shortfall_drivers"]["market_shock"] > 0


def test_compare_scenarios_uses_one_shared_baseline(profile):
    output = tools.TOOLS[ToolName.COMPARE_SCENARIOS].fn(
        profile, scenarios=[{"new_monthly_contribution": 20_000}, {"pause_months": 6}]
    )
    assert len(output["summary"]["alternatives"]) == 2


def test_project_goal_needs_goals(profile):
    profile.goals = []
    with pytest.raises(ValueError, match="no goals"):
        tools.TOOLS[ToolName.PROJECT_GOAL].fn(profile)
