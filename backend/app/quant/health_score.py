"""Financial Health Scorecard — OWNER: Member 1.

Five dimensions, each a formula over the profile. The `drivers` dict carries the
raw inputs so the UI can show "why" beside every score. An LLM must never
produce these numbers.
"""

from __future__ import annotations

from app.schemas.portfolio import HealthScore
from app.schemas.profile import FinancialProfile


def liquidity_score(profile: FinancialProfile) -> tuple[float, dict[str, float]]:
    """Months of expenses covered by cash, against the user's emergency-fund target."""
    expenses = profile.cashflow.monthly_expenses
    months = profile.cash_balance / expenses if expenses > 0 else 0.0
    target = profile.risk.min_emergency_months or 6.0
    score = min(100.0, (months / target) * 100) if target > 0 else 100.0
    return score, {"cash_runway_months": months, "target_months": target}


def debt_burden_score(profile: FinancialProfile) -> tuple[float | None, dict[str, float]]:
    """TODO(member-1): EMI-to-income ratio. <20% -> 100, >50% -> 0, linear between.

    Return None until this is implemented — not 0.0, which would read as the worst score.
    """
    return None, {}


def diversification_score(profile: FinancialProfile) -> tuple[float | None, dict[str, float]]:
    """TODO(member-1): derive from analytics.concentration() — effective_holdings and HHI."""
    return None, {}


def goal_progress_score(profile: FinancialProfile) -> tuple[float | None, dict[str, float]]:
    """TODO(member-1): current corpus vs. required corpus, weighted by goal priority."""
    return None, {}


def market_exposure_score(profile: FinancialProfile) -> tuple[float | None, dict[str, float]]:
    """TODO(member-1): equity weight vs. the user's stated max_equity_pct and horizon."""
    return None, {}


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
