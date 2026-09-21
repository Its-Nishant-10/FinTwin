"""Financial Health Scorecard — OWNER: Member 1.

Five dimensions, each a formula over the profile. The `drivers` dict carries the
raw inputs so the UI can show "why" beside every score. An LLM must never
produce these numbers.
"""

from __future__ import annotations

from app.core.errors import InsufficientDataError
from app.quant.analytics import allocation, concentration
from app.schemas.portfolio import HealthScore
from app.schemas.profile import AssetClass, FinancialProfile

SCORE_MIN = 0.0
SCORE_MAX = 100.0
# EMI / income at or below this scores 100; at or above DEBT_RATIO_WORST scores 0.
DEBT_RATIO_FULL_MARKS = 0.20
DEBT_RATIO_WORST = 0.50
# Effective holdings (1 / HHI) at which diversification is scored 100. A transparent
# convention, not a market truth: 10 equally sized positions.
TARGET_EFFECTIVE_HOLDINGS = 10.0
# Goal.priority runs 1..5 and the UI treats 1 as the most important goal, so a goal's
# weight is (MAX_PRIORITY + 1 - priority): priority 1 weighs 5, priority 5 weighs 1.
MAX_PRIORITY = 5


def _clamp(score: float) -> float:
    return max(SCORE_MIN, min(SCORE_MAX, score))


def liquidity_score(profile: FinancialProfile) -> tuple[float, dict[str, float]]:
    """Months of expenses covered by cash, against the user's emergency-fund target."""
    expenses = profile.cashflow.monthly_expenses
    months = profile.cash_balance / expenses if expenses > 0 else 0.0
    target = profile.risk.min_emergency_months or 6.0
    score = min(100.0, (months / target) * 100) if target > 0 else 100.0
    return score, {"cash_runway_months": months, "target_months": target}


def debt_burden_score(profile: FinancialProfile) -> tuple[float | None, dict[str, float]]:
    """Total monthly EMI / monthly income, scored 100 at <=20% and 0 at >=50%.

    Between the two thresholds the score falls linearly:
    100 * (0.50 - ratio) / (0.50 - 0.20). With no income the ratio is undefined
    (and a zero income usually means "not entered"), so the score is None rather than
    a misleading 0 or 100. The raw inputs are still reported in the drivers.
    """
    emi = sum(liability.monthly_emi for liability in profile.liabilities)
    income = profile.cashflow.monthly_income
    drivers = {"total_monthly_emi": emi, "monthly_income": income}
    if income <= 0:
        return None, drivers

    ratio = emi / income
    drivers["debt_burden_ratio"] = ratio
    score = SCORE_MAX * (DEBT_RATIO_WORST - ratio) / (DEBT_RATIO_WORST - DEBT_RATIO_FULL_MARKS)
    return _clamp(score), drivers


def diversification_score(profile: FinancialProfile) -> tuple[float | None, dict[str, float]]:
    """How many independent-looking holdings the portfolio behaves like, from concentration().

    Score = 100 * (effective_holdings - 1) / (10 - 1), capped to 0..100, where
    effective_holdings = 1 / HHI. One holding (or all value in one) scores 0; ten equal
    positions or more score 100. Empty portfolios are not scored (None).
    """
    try:
        conc = concentration(profile)
    except InsufficientDataError:
        return None, {}

    score = SCORE_MAX * (conc.effective_holdings - 1) / (TARGET_EFFECTIVE_HOLDINGS - 1)
    return _clamp(score), {
        "hhi": conc.hhi,
        "effective_holdings": conc.effective_holdings,
        "top_holding_weight": conc.top_holding_weight,
        "holding_count": float(len(profile.holdings)),
    }


def goal_progress_score(profile: FinancialProfile) -> tuple[float | None, dict[str, float]]:
    """Current portfolio value against each goal's target, weighted by priority.

    Assumption: no required-corpus formula is defined for this scorecard, so a goal's
    progress is min(1, portfolio_value / target_amount) * 100. Horizon, future
    contributions and expected returns are deliberately ignored (that is the simulation
    engine's job), and each goal is compared with the whole corpus rather than a share
    of it. The score is the mean of goal progress weighted by (6 - priority). None when
    there are no goals.
    """
    if not profile.goals:
        return None, {}

    corpus = profile.portfolio_value
    weighted_progress = 0.0
    total_weight = 0
    drivers: dict[str, float] = {"current_corpus": corpus, "goal_count": float(len(profile.goals))}
    for i, goal in enumerate(profile.goals, start=1):
        progress = _clamp(corpus / goal.target_amount * SCORE_MAX)
        weight = MAX_PRIORITY + 1 - goal.priority
        weighted_progress += weight * progress
        total_weight += weight
        drivers[f"goal_{i}_target_amount"] = goal.target_amount
        drivers[f"goal_{i}_priority"] = float(goal.priority)
        drivers[f"goal_{i}_progress"] = progress
    return _clamp(weighted_progress / total_weight), drivers


def market_exposure_score(profile: FinancialProfile) -> tuple[float | None, dict[str, float]]:
    """Equity share of the portfolio against the user's own max_equity_pct.

    Equity at or under the limit scores 100. Above it the score falls linearly to 0 as
    the equity share reaches 100%: 100 * (1 - (equity - limit) / (1 - limit)). A
    flag against the user's stated limit, not advice: nothing is rebalanced. Returns
    None for an empty portfolio or when the user has set no limit; no horizon or risk
    tolerance assumption is substituted.
    """
    limit = profile.risk.max_equity_pct
    slices = allocation(profile, by="asset_class")
    if not slices or limit is None:
        return None, {}

    equity = next((s.weight for s in slices if s.label == AssetClass.EQUITY.value), 0.0)
    drivers = {
        "equity_weight": equity,
        "max_equity_pct": limit,
        "portfolio_value": profile.portfolio_value,
    }
    if equity <= limit:
        return SCORE_MAX, drivers
    return _clamp(SCORE_MAX * (1 - (equity - limit) / (1 - limit))), drivers


def compute(profile: FinancialProfile) -> HealthScore:
    liquidity, d1 = liquidity_score(profile)
    debt, d2 = debt_burden_score(profile)
    diversification, d3 = diversification_score(profile)
    goals, d4 = goal_progress_score(profile)
    exposure, d5 = market_exposure_score(profile)

    # Average only what has been scored: an unimplemented dimension must not drag
    # the overall score down as if it were a zero.
    scored = [s for s in (liquidity, debt, diversification, goals, exposure) if s is not None]
    return HealthScore(
        overall=sum(scored) / len(scored) if scored else None,
        liquidity=liquidity,
        debt_burden=debt,
        diversification=diversification,
        goal_progress=goals,
        market_exposure=exposure,
        drivers={**d1, **d2, **d3, **d4, **d5},
    )
