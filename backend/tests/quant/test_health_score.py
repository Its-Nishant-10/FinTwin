"""OWNER: Member 1. Pins the "unknown is None, never 0" rule for unbuilt dimensions."""

from __future__ import annotations

import pytest

from app.agent import narrate, tools
from app.quant import health_score
from app.schemas.agent import ToolName, ToolResult
from app.schemas.profile import FinancialProfile


def test_liquidity_is_hand_computed(profile):
    # 250,000 cash / 70,000 monthly expenses = 3.571 months, against a 6-month target.
    score = health_score.compute(profile)
    assert score.liquidity == pytest.approx(3.5714 / 6 * 100, abs=0.01)
    assert score.drivers["cash_runway_months"] == pytest.approx(250_000 / 70_000)
    assert score.drivers["target_months"] == 6


def test_unbuilt_dimensions_are_none_not_zero(profile):
    score = health_score.compute(profile)
    assert score.debt_burden is None
    assert score.diversification is None
    assert score.goal_progress is None
    assert score.market_exposure is None


def test_overall_averages_only_scored_dimensions(profile):
    score = health_score.compute(profile)
    assert score.overall == pytest.approx(score.liquidity)


def test_liquidity_is_capped_at_100():
    rich = FinancialProfile(cash_balance=10_000_000)
    rich.cashflow.monthly_expenses = 50_000
    assert health_score.compute(rich).liquidity == 100.0


def test_health_tool_summary_keeps_nulls(profile):
    summary = tools.TOOLS[ToolName.COMPUTE_HEALTH_SCORE].fn(profile)["summary"]
    assert summary["debt_burden"] is None
    assert summary["liquidity"] == pytest.approx(59.5, abs=0.05)


def test_health_narration_names_what_is_not_scored(profile):
    output = tools.TOOLS[ToolName.COMPUTE_HEALTH_SCORE].fn(profile)
    text = narrate.narrate([ToolResult(tool=ToolName.COMPUTE_HEALTH_SCORE, output=output)])
    assert "1 of 5 dimensions" in text
    assert "Not scored yet: debt burden" in text
    assert "debt burden 0" not in text
