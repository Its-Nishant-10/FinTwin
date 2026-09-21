"""Allocation, concentration, correlation and risk metrics.

OWNER: Member 1 (Quant/Portfolio)

Pure functions over a `FinancialProfile` and, for the price-based metrics, a daily
price DataFrame: indexed by date, one column of adjusted closes per symbol (the
convention documented on `app.data.market.get_price_history`). No I/O, no randomness.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

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


# --------------------------------------------------------------------- assumptions

TRADING_DAYS_PER_YEAR = 252
# Fewer daily returns than this and a volatility or correlation is noise. The same floor
# applies to every price-based metric so they are all computed on comparable evidence.
MIN_RETURN_OBSERVATIONS = 60
# Annual risk-free rate. The API carries no risk-free input, so it is assumed to be zero.
RISK_FREE_RATE_ANNUAL = 0.0
# Minimum acceptable daily return for Sortino: any negative day counts as downside.
SORTINO_MAR_DAILY = 0.0
VAR_CONFIDENCE = 0.95
# Column in `price_history` holding the benchmark index (Nifty 50, Yahoo ticker). Beta is
# computed only when this column exists; a holding is never promoted to a benchmark.
BENCHMARK_SYMBOL = "^NSEI"
# Standard deviations below this are float noise around a constant series, not risk.
ZERO_VARIANCE_EPS = 1e-12


def _daily_returns(price_history: pd.DataFrame) -> pd.DataFrame:
    """Clean closes, then simple daily returns with no invented observations.

    Non-numeric, infinite and non-positive prices become NaN, the index is sorted and
    de-duplicated (last quote wins). Returns use `fill_method=None`, so a missing close
    costs the two returns that touch it instead of being carried forward into a fake
    flat day or stretched into a multi-day return.
    """
    prices = price_history.apply(pd.to_numeric, errors="coerce")
    prices = prices.replace([np.inf, -np.inf], np.nan)
    prices = prices.where(prices > 0)
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    return prices.pct_change(fill_method=None)


def _portfolio_returns(profile: FinancialProfile, price_history: pd.DataFrame) -> pd.Series | None:
    """Daily returns of the current holdings held at today's weights, or None.

    Weights come from `allocation(by="symbol")`, i.e. current market value. That is a
    constant-weight (daily rebalanced) approximation of the *current* portfolio, not a
    reconstruction of what the user actually owned in the past. Every weighted holding
    must have a price column: risk computed on a subset would silently understate the
    rest of the portfolio, so a missing column means "cannot compute" (None).
    """
    if price_history.empty:
        return None
    weights = {s.label: s.weight for s in allocation(profile, by="symbol") if s.weight > 0}
    if not weights or any(symbol not in price_history.columns for symbol in weights):
        return None

    returns = _daily_returns(price_history[list(weights)]).dropna()
    if returns.empty:
        return None
    return returns @ pd.Series(weights)


def _beta(portfolio: pd.Series, price_history: pd.DataFrame) -> float | None:
    """Cov(portfolio, benchmark) / Var(benchmark) over their overlapping days."""
    if BENCHMARK_SYMBOL not in price_history.columns:
        return None
    benchmark = _daily_returns(price_history[[BENCHMARK_SYMBOL]])[BENCHMARK_SYMBOL]
    joined = pd.concat([portfolio.rename("p"), benchmark.rename("b")], axis=1).dropna()
    if len(joined) < MIN_RETURN_OBSERVATIONS:
        return None
    benchmark_var = float(joined["b"].var(ddof=1))
    if not np.isfinite(benchmark_var) or benchmark_var < ZERO_VARIANCE_EPS**2:
        return None
    return float(joined["p"].cov(joined["b"]) / benchmark_var)


def risk_metrics(
    profile: FinancialProfile, price_history: pd.DataFrame | None = None
) -> RiskMetrics:
    """Volatility, drawdown, Sharpe, Sortino, VaR and beta of the current portfolio.

    All figures come from daily simple returns of the portfolio at today's weights
    (see `_portfolio_returns`). With no price history, an unpriced holding or fewer
    than MIN_RETURN_OBSERVATIONS returns, every metric is None. Individual metrics
    that are undefined (zero variance, no benchmark) are None on their own.

    - annual_volatility: sample std (ddof=1) of daily returns * sqrt(252).
    - max_drawdown: worst peak-to-trough fall of the wealth curve cumprod(1 + r),
      starting from 1.0. A negative decimal; 0.0 if wealth never falls below a peak.
    - sharpe_ratio: (mean daily return - daily risk-free) / std * sqrt(252). The
      risk-free rate is assumed to be 0 (RISK_FREE_RATE_ANNUAL) because the API has no
      such input. None if the std is zero.
    - sortino_ratio: (mean daily return - MAR) / downside deviation * sqrt(252), with
      MAR = 0 and downside deviation = sqrt(mean(min(r - MAR, 0)^2)) over all days.
      None if there is no downside day.
    - var_95: historical 1-day 95% VaR, -(5th percentile of daily returns, linear
      interpolation). Sign convention: a *positive* number is a loss, so 0.03 means
      "on 95% of days the loss was no worse than 3%". Negative means even the 5th
      percentile day was a gain.
    - beta: Cov(portfolio, benchmark) / Var(benchmark) on overlapping days, using the
      BENCHMARK_SYMBOL column of price_history. None when that column is absent.
    """
    if price_history is None:
        return RiskMetrics()
    returns = _portfolio_returns(profile, price_history)
    if returns is None or len(returns) < MIN_RETURN_OBSERVATIONS:
        return RiskMetrics()

    annualizer = np.sqrt(TRADING_DAYS_PER_YEAR)
    mean = float(returns.mean())
    std = float(returns.std(ddof=1))

    wealth = np.concatenate([[1.0], (1.0 + returns).cumprod().to_numpy()])
    max_drawdown = float((wealth / np.maximum.accumulate(wealth) - 1.0).min())

    daily_risk_free = (1.0 + RISK_FREE_RATE_ANNUAL) ** (1 / TRADING_DAYS_PER_YEAR) - 1.0
    sharpe = (mean - daily_risk_free) / std * annualizer if std >= ZERO_VARIANCE_EPS else None

    shortfall = np.minimum(returns.to_numpy() - SORTINO_MAR_DAILY, 0.0)
    downside_deviation = float(np.sqrt(np.mean(shortfall**2)))
    sortino = (
        (mean - SORTINO_MAR_DAILY) / downside_deviation * annualizer
        if downside_deviation >= ZERO_VARIANCE_EPS
        else None
    )

    return RiskMetrics(
        annual_volatility=std * annualizer,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        var_95=-float(np.percentile(returns.to_numpy(), (1 - VAR_CONFIDENCE) * 100)),
        beta=_beta(returns, price_history),
    )


def correlation_matrix(
    profile: FinancialProfile, price_history: pd.DataFrame | None = None
) -> dict[str, dict[str, float]]:
    """Pairwise correlation of daily returns between holdings.

    Every holding that has a price column is measured on the *same* days: those where
    all of them have a valid return (listwise deletion), which keeps the matrix
    consistent and positive semi-definite. Holdings with no price column, or a constant
    price (correlation undefined), are left out rather than given an invented value.

    Raises InsufficientDataError with no price history, no priced holding, or fewer than
    MIN_RETURN_OBSERVATIONS common return days. The result is symmetric with 1.0 on the
    diagonal.
    """
    if price_history is None or price_history.empty:
        raise InsufficientDataError("no price history to compute correlations from")
    symbols = list(dict.fromkeys(h.symbol for h in profile.holdings))
    symbols = [s for s in symbols if s in price_history.columns]
    if not symbols:
        raise InsufficientDataError("no holding has price history")

    returns = _daily_returns(price_history[symbols]).dropna()
    if len(returns) < MIN_RETURN_OBSERVATIONS:
        raise InsufficientDataError(
            f"{len(returns)} overlapping daily returns; need at least {MIN_RETURN_OBSERVATIONS}"
        )
    returns = returns.loc[:, returns.std(ddof=1) >= ZERO_VARIANCE_EPS]
    if returns.empty:
        raise InsufficientDataError("every holding's price is constant; correlation is undefined")

    corr = returns.corr().to_numpy()
    corr = np.clip((corr + corr.T) / 2, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    labels = list(returns.columns)
    return {
        row: {col: float(corr[i, j]) for j, col in enumerate(labels)}
        for i, row in enumerate(labels)
    }


def analyze(profile: FinancialProfile) -> PortfolioMetrics:
    """Assemble the full quant response. This is what /portfolio/analyze returns."""
    by_holding = allocation(profile, by="symbol")
    by_class = allocation(profile, by="asset_class")

    try:
        conc = concentration(profile)
    except InsufficientDataError:
        conc = None

    # No price history is wired into this endpoint yet, so both price-based results are
    # empty here rather than invented.
    try:
        correlations = correlation_matrix(profile)
    except InsufficientDataError:
        correlations = {}

    return PortfolioMetrics(
        total_value=profile.portfolio_value,
        by_asset_class=by_class,
        by_sector=allocation(profile, by="sector"),
        by_holding=by_holding,
        concentration=conc,
        risk=risk_metrics(profile),
        correlation_matrix=correlations,
        dominant_asset_class=(
            next(
                h.asset_class for h in profile.holdings if h.asset_class.value == by_class[0].label
            )
            if by_class
            else None
        ),
    )
