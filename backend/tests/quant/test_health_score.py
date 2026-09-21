"""OWNER: Member 1. Hand-checked scores, plus the "unknown is None, never 0" rule."""

from __future__ import annotations

import math

import pytest

from app.agent import narrate, tools
from app.core.errors import InsufficientDataError
from app.quant import analytics, health_score
from app.schemas.agent import ToolName, ToolResult
from app.schemas.profile import (
    AssetClass,
    Cashflow,
    FinancialProfile,
    Goal,
    Holding,
    Liability,
    RiskConstraints,
)

DIMENSIONS = ("liquidity", "debt_burden", "diversification", "goal_progress", "market_exposure")


def _cash_only_profile() -> FinancialProfile:
    """Only liquidity can be scored: no income, holdings, goals or equity limit."""
    return FinancialProfile(cash_balance=250_000, cashflow=Cashflow(monthly_expenses=70_000))


def _debt_profile(emi: float, income: float) -> FinancialProfile:
    return FinancialProfile(
        cashflow=Cashflow(monthly_income=income),
        liabilities=[Liability(name="Loan", outstanding=1_000_000, monthly_emi=emi)],
    )


def _holdings(*values: float, asset_class: AssetClass = AssetClass.EQUITY) -> list[Holding]:
    return [
        Holding(symbol=f"S{i}", asset_class=asset_class, quantity=1, current_price=v)
        for i, v in enumerate(values)
    ]


def _goal(target: float, priority: int = 1, name: str = "Goal") -> Goal:
    return Goal(name=name, target_amount=target, horizon_months=60, priority=priority)


def test_liquidity_is_hand_computed(profile):
    # 250,000 cash / 70,000 monthly expenses = 3.571 months, against a 6-month target.
    score = health_score.compute(profile)
    assert score.liquidity == pytest.approx(3.5714 / 6 * 100, abs=0.01)
    assert score.drivers["cash_runway_months"] == pytest.approx(250_000 / 70_000)
    assert score.drivers["target_months"] == 6


def test_dimensions_that_cannot_be_scored_are_none_not_zero():
    score = health_score.compute(_cash_only_profile())
    assert score.debt_burden is None
    assert score.diversification is None
    assert score.goal_progress is None
    assert score.market_exposure is None


def test_overall_averages_only_scored_dimensions():
    score = health_score.compute(_cash_only_profile())
    assert score.overall == pytest.approx(score.liquidity)


def test_overall_is_the_mean_of_all_five_for_the_sample_profile(profile):
    score = health_score.compute(profile)
    values = [getattr(score, d) for d in DIMENSIONS]
    assert None not in values
    assert score.overall == pytest.approx(sum(values) / 5)


def test_liquidity_is_capped_at_100():
    rich = FinancialProfile(cash_balance=10_000_000)
    rich.cashflow.monthly_expenses = 50_000
    assert health_score.compute(rich).liquidity == 100.0


def test_health_tool_summary_keeps_nulls():
    summary = tools.TOOLS[ToolName.COMPUTE_HEALTH_SCORE].fn(_cash_only_profile())["summary"]
    assert summary["debt_burden"] is None
    assert summary["liquidity"] == pytest.approx(59.5, abs=0.05)


def test_health_narration_names_what_is_not_scored():
    output = tools.TOOLS[ToolName.COMPUTE_HEALTH_SCORE].fn(_cash_only_profile())
    text = narrate.narrate([ToolResult(tool=ToolName.COMPUTE_HEALTH_SCORE, output=output)])
    assert "1 of 5 dimensions" in text
    assert "Not scored yet: debt burden" in text
    assert "debt burden 0" not in text


def test_health_narration_covers_all_five_for_the_sample_profile(profile):
    output = tools.TOOLS[ToolName.COMPUTE_HEALTH_SCORE].fn(profile)
    text = narrate.narrate([ToolResult(tool=ToolName.COMPUTE_HEALTH_SCORE, output=output)])
    assert "5 of 5 dimensions" in text
    assert "Not scored yet" not in text


# ------------------------------------------------------------------------ debt burden


def test_debt_burden_below_20_percent_scores_100():
    # 15,000 / 100,000 = 15%
    score, drivers = health_score.debt_burden_score(_debt_profile(15_000, 100_000))
    assert score == 100.0
    assert drivers == pytest.approx(
        {"total_monthly_emi": 15_000, "monthly_income": 100_000, "debt_burden_ratio": 0.15}
    )


def test_debt_burden_at_exactly_20_and_50_percent():
    assert health_score.debt_burden_score(_debt_profile(20_000, 100_000))[0] == pytest.approx(100)
    assert health_score.debt_burden_score(_debt_profile(50_000, 100_000))[0] == pytest.approx(0)


def test_debt_burden_above_50_percent_scores_0():
    score, drivers = health_score.debt_burden_score(_debt_profile(60_000, 100_000))
    assert score == 0.0
    assert drivers["debt_burden_ratio"] == pytest.approx(0.6)


def test_debt_burden_between_20_and_50_percent_interpolates_linearly():
    # 35% is halfway between 20% and 50%; 26% is 80% of the way from 50% down to 20%.
    assert health_score.debt_burden_score(_debt_profile(35_000, 100_000))[0] == pytest.approx(50)
    assert health_score.debt_burden_score(_debt_profile(26_000, 100_000))[0] == pytest.approx(80)


def test_debt_burden_sums_every_liability():
    profile = _debt_profile(10_000, 100_000)
    profile.liabilities.append(Liability(name="Card", outstanding=50_000, monthly_emi=25_000))
    score, drivers = health_score.debt_burden_score(profile)
    assert drivers["total_monthly_emi"] == 35_000
    assert score == pytest.approx(50)


def test_debt_burden_without_liabilities_scores_100():
    profile = FinancialProfile(cashflow=Cashflow(monthly_income=100_000))
    assert health_score.debt_burden_score(profile)[0] == 100.0


def test_debt_burden_with_zero_income_is_none_and_keeps_raw_inputs():
    score, drivers = health_score.debt_burden_score(_debt_profile(11_000, 0))
    assert score is None
    assert drivers == {"total_monthly_emi": 11_000, "monthly_income": 0}
    assert health_score.debt_burden_score(FinancialProfile())[0] is None


def test_debt_burden_of_sample_profile(profile):
    score, drivers = health_score.debt_burden_score(profile)
    assert drivers["debt_burden_ratio"] == pytest.approx(11_000 / 120_000)
    assert score == 100.0


# ------------------------------------------------------------------- diversification


def test_diversification_concentrated_portfolio_scores_0():
    score, drivers = health_score.diversification_score(FinancialProfile(holdings=_holdings(1_000)))
    assert score == 0.0
    assert drivers["hhi"] == pytest.approx(1.0)
    assert drivers["effective_holdings"] == pytest.approx(1.0)


def test_diversification_two_holdings_hand_computed():
    # 60/40 -> HHI 0.52 -> effective holdings 1/0.52 -> 100 * (1/0.52 - 1) / 9.
    score, drivers = health_score.diversification_score(
        FinancialProfile(holdings=_holdings(60, 40))
    )
    assert score == pytest.approx(100 * (1 / 0.52 - 1) / 9)
    assert drivers == pytest.approx(
        {
            "hhi": 0.52,
            "effective_holdings": 1 / 0.52,
            "top_holding_weight": 0.6,
            "holding_count": 2,
        }
    )


def test_diversification_ten_equal_holdings_score_100():
    score, drivers = health_score.diversification_score(
        FinancialProfile(holdings=_holdings(*[100] * 10))
    )
    assert score == pytest.approx(100)
    assert drivers["effective_holdings"] == pytest.approx(10)


def test_diversification_is_capped_at_100():
    score, _ = health_score.diversification_score(FinancialProfile(holdings=_holdings(*[1] * 40)))
    assert score == 100.0


def test_diversification_of_empty_portfolio_is_none():
    assert health_score.diversification_score(FinancialProfile()) == (None, {})
    zero_value = FinancialProfile(holdings=_holdings(0))
    assert health_score.diversification_score(zero_value) == (None, {})


def test_diversification_still_reuses_concentration_error():
    with pytest.raises(InsufficientDataError):
        analytics.concentration(FinancialProfile())


# ----------------------------------------------------------------------- goal progress


def test_goal_progress_single_goal():
    # corpus 500,000 against a 2,000,000 target = 25%.
    profile = FinancialProfile(holdings=_holdings(500_000), goals=[_goal(2_000_000)])
    score, drivers = health_score.goal_progress_score(profile)
    assert score == pytest.approx(25)
    assert drivers == pytest.approx(
        {
            "current_corpus": 500_000,
            "goal_count": 1,
            "goal_1_target_amount": 2_000_000,
            "goal_1_priority": 1,
            "goal_1_progress": 25,
        }
    )


def test_goal_progress_multiple_goals_weighted_by_priority():
    # Corpus 1,000,000. Goal 1: target 2,000,000 -> 50%, priority 1 -> weight 5.
    # Goal 2: target 10,000,000 -> 10%, priority 4 -> weight 2.
    # (5 * 50 + 2 * 10) / 7 = 270 / 7.
    profile = FinancialProfile(
        holdings=_holdings(1_000_000),
        goals=[_goal(2_000_000, priority=1), _goal(10_000_000, priority=4)],
    )
    score, drivers = health_score.goal_progress_score(profile)
    assert score == pytest.approx(270 / 7)
    assert drivers["goal_1_progress"] == pytest.approx(50)
    assert drivers["goal_2_progress"] == pytest.approx(10)
    assert drivers["goal_count"] == 2


def test_goal_progress_is_capped_per_goal():
    # The met goal counts as 100, not 250, so it cannot hide the unmet one: (100 + 20) / 2.
    profile = FinancialProfile(
        holdings=_holdings(500_000), goals=[_goal(200_000), _goal(2_500_000)]
    )
    score, drivers = health_score.goal_progress_score(profile)
    assert drivers["goal_1_progress"] == 100.0
    assert score == pytest.approx(60)


def test_goal_progress_with_no_goals_is_none():
    assert health_score.goal_progress_score(FinancialProfile(holdings=_holdings(1_000))) == (
        None,
        {},
    )


def test_goal_progress_with_an_empty_portfolio_is_zero_not_none():
    # The corpus is known to be 0, so the goal really is 0% funded.
    score, drivers = health_score.goal_progress_score(FinancialProfile(goals=[_goal(1_000)]))
    assert score == 0.0
    assert drivers["current_corpus"] == 0


def test_goal_progress_of_sample_profile(profile):
    # 400*280 + 60*1600 + 40*1700 + 150*1000 = 426,000 against 2,000,000.
    assert health_score.goal_progress_score(profile)[0] == pytest.approx(21.3)


# --------------------------------------------------------------------- market exposure


def _exposure_profile(equity: float, debt: float, limit: float | None) -> FinancialProfile:
    return FinancialProfile(
        holdings=[
            *_holdings(equity, asset_class=AssetClass.EQUITY),
            Holding(symbol="D", asset_class=AssetClass.DEBT, quantity=1, current_price=debt),
        ],
        risk=RiskConstraints(max_equity_pct=limit),
    )


def test_market_exposure_under_the_limit_scores_100():
    score, drivers = health_score.market_exposure_score(_exposure_profile(60, 40, 0.75))
    assert score == 100.0
    assert drivers == pytest.approx(
        {"equity_weight": 0.6, "max_equity_pct": 0.75, "portfolio_value": 100}
    )


def test_market_exposure_exactly_at_the_limit_scores_100():
    assert health_score.market_exposure_score(_exposure_profile(75, 25, 0.75))[0] == 100.0


def test_market_exposure_above_the_limit_falls_linearly_to_zero_at_full_equity():
    # 90% equity vs a 60% limit: excess 0.30 of the 0.40 headroom -> 100 * (1 - 0.75) = 25.
    score, drivers = health_score.market_exposure_score(_exposure_profile(90, 10, 0.60))
    assert score == pytest.approx(25)
    assert drivers["equity_weight"] == pytest.approx(0.9)
    fully_equity = FinancialProfile(
        holdings=_holdings(100), risk=RiskConstraints(max_equity_pct=0.60)
    )
    assert health_score.market_exposure_score(fully_equity)[0] == pytest.approx(0)


def test_market_exposure_with_no_equity_scores_100():
    profile = FinancialProfile(
        holdings=_holdings(100, asset_class=AssetClass.DEBT),
        risk=RiskConstraints(max_equity_pct=0.5),
    )
    score, drivers = health_score.market_exposure_score(profile)
    assert score == 100.0
    assert drivers["equity_weight"] == 0.0


def test_market_exposure_without_a_configured_limit_is_none():
    assert health_score.market_exposure_score(_exposure_profile(60, 40, None)) == (None, {})


def test_market_exposure_of_an_empty_portfolio_is_none():
    empty = FinancialProfile(risk=RiskConstraints(max_equity_pct=0.5))
    assert health_score.market_exposure_score(empty) == (None, {})


def test_market_exposure_of_sample_profile(profile):
    # Equity 276,000 / 426,000 = 64.8%, inside the 75% limit.
    score, drivers = health_score.market_exposure_score(profile)
    assert score == 100.0
    assert drivers["equity_weight"] == pytest.approx(276_000 / 426_000)


def test_zero_equity_limit_with_equity_scores_0():
    assert health_score.market_exposure_score(_exposure_profile(50, 50, 0.0))[0] == pytest.approx(
        50
    )


# ------------------------------------------------------------------------------ bounds


def test_every_score_stays_between_0_and_100(profile):
    profiles = [
        profile,
        FinancialProfile(),
        _cash_only_profile(),
        _debt_profile(500_000, 100_000),
        _exposure_profile(99, 1, 0.1),
        FinancialProfile(holdings=_holdings(1), goals=[_goal(1_000_000_000, priority=5)]),
        FinancialProfile(holdings=_holdings(*[1] * 100), goals=[_goal(1)]),
    ]
    for candidate in profiles:
        result = health_score.compute(candidate)
        for name in (*DIMENSIONS, "overall"):
            value = getattr(result, name)
            assert value is None or 0 <= value <= 100, (name, value)
        assert all(math.isfinite(v) for v in result.drivers.values())
