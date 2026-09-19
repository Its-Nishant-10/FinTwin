"""Allocation, concentration, correlation and risk metrics.

OWNER: Member 1 (Quant/Portfolio)

`allocation` and `concentration` below are implemented as a reference for the
shape the rest should take: pure functions, no I/O, exact numbers, tested.
The `TODO(member-1)` functions are yours.
"""

from __future__ import annotations

from collections import defaultdict

from app.core.errors import InsufficientDataError
from app.schemas import AllocationSlice, ConcentrationMetrics, PortfolioMetrics, RiskMetrics
from app.schemas.profile import FinancialProfile


def allocation(profile: FinancialProfile, by: str = "asset_class") -> list[AllocationSlice]:
    """Split portfolio value by asset_class, sector or symbol.

    Weights sum to 1.0 over a non-empty portfolio. Holdings with no sector are
    bucketed under "Unclassified" rather than dropped, so the weights still add up.
    """
    total = profile.portfolio_value
    if total <= 0:
        return []

    buckets: dict[str, float] = defaultdict(float)
    for holding in profile.holdings:
        if by == "asset_class":
            key = holding.asset_class.value
        elif by == "sector":
            key = holding.sector or "Unclassified"
        elif by == "symbol":
            key = holding.symbol
        else:
            raise ValueError(f"unknown grouping: {by!r}")
        buckets[key] += holding.market_value

    slices = [
        AllocationSlice(label=label, value=value, weight=value / total)
        for label, value in buckets.items()
    ]
    return sorted(slices, key=lambda s: s.weight, reverse=True)


def concentration(profile: FinancialProfile) -> ConcentrationMetrics:
    """Herfindahl-Hirschman Index over holding weights.

    HHI = sum(w_i^2). 1.0 means everything in one position; 1/n means equal weights.
    Effective holdings (1/HHI) is the intuitive version to show a user: "your
    20 holdings behave like 3".
    """
    slices = allocation(profile, by="symbol")
    if not slices:
        raise InsufficientDataError("no holdings to measure concentration on")

    weights = sorted((s.weight for s in slices), reverse=True)
    hhi = sum(w * w for w in weights)

    flags: list[str] = []
    limit = profile.risk.max_single_holding_pct
    if limit is not None and weights[0] > limit:
        flags.append(
            f"Top holding is {weights[0]:.0%} of the portfolio, above the "
            f"{limit:.0%} limit you set."
        )
    if hhi > 0.25:
        flags.append(f"Highly concentrated: effectively {1 / hhi:.1f} independent holdings.")

    return ConcentrationMetrics(
        hhi=hhi,
        effective_holdings=1 / hhi,
        top_holding_weight=weights[0],
        top_5_weight=sum(weights[:5]),
        flags=flags,
    )


def risk_metrics(profile: FinancialProfile, price_history=None) -> RiskMetrics:
    """Volatility, drawdown, Sharpe, Sortino, VaR, beta.

    TODO(member-1): needs price history from Member 2's market-data pipeline
    (app.data.market.get_price_history). Return None for any metric you cannot
    compute honestly — do not substitute zero.
    """
    return RiskMetrics()


def correlation_matrix(
    profile: FinancialProfile, price_history=None
) -> dict[str, dict[str, float]]:
    """Pairwise return correlation between holdings.

    TODO(member-1): pandas .pct_change().corr() over aligned daily closes.
    Needs >= 60 overlapping observations; raise InsufficientDataError otherwise.
    """
    return {}


def analyze(profile: FinancialProfile) -> PortfolioMetrics:
    """Assemble the full quant response. This is what /portfolio/analyze returns."""
    by_holding = allocation(profile, by="symbol")
    by_class = allocation(profile, by="asset_class")

    try:
        conc = concentration(profile)
    except InsufficientDataError:
        conc = None

    return PortfolioMetrics(
        total_value=profile.portfolio_value,
        by_asset_class=by_class,
        by_sector=allocation(profile, by="sector"),
        by_holding=by_holding,
        concentration=conc,
        risk=risk_metrics(profile),
        correlation_matrix=correlation_matrix(profile),
        dominant_asset_class=(
            next(
                h.asset_class
                for h in profile.holdings
                if h.asset_class.value == by_class[0].label
            )
            if by_class
            else None
        ),
    )
