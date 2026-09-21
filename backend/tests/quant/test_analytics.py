"""OWNER: Member 1. Every quant function needs a hand-checked number here."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.core.errors import InsufficientDataError
from app.quant import analytics
from app.schemas import RiskMetrics
from app.schemas.profile import AssetClass, FinancialProfile, Holding


def _two_holding_profile() -> FinancialProfile:
    """60/40 split by value, so the expected weights are obvious by hand."""
    return FinancialProfile(
        holdings=[
            Holding(symbol="A", asset_class=AssetClass.EQUITY, quantity=60, current_price=100),
            Holding(symbol="B", asset_class=AssetClass.DEBT, quantity=40, current_price=100),
        ]
    )


def test_allocation_weights_sum_to_one(profile):
    slices = analytics.allocation(profile, by="symbol")
    assert sum(s.weight for s in slices) == pytest.approx(1.0)


def test_allocation_by_symbol_exact_weights():
    slices = analytics.allocation(_two_holding_profile(), by="symbol")
    weights = {s.label: s.weight for s in slices}
    assert weights == pytest.approx({"A": 0.6, "B": 0.4})


def test_allocation_empty_portfolio_returns_empty():
    assert analytics.allocation(FinancialProfile()) == []


def test_concentration_hhi_hand_computed():
    # HHI = 0.6^2 + 0.4^2 = 0.52 -> effective holdings = 1/0.52 = 1.923
    conc = analytics.concentration(_two_holding_profile())
    assert conc.hhi == pytest.approx(0.52)
    assert conc.effective_holdings == pytest.approx(1 / 0.52)
    assert conc.top_holding_weight == pytest.approx(0.6)


def test_concentration_without_holdings_raises():
    with pytest.raises(InsufficientDataError):
        analytics.concentration(FinancialProfile())


def test_analyze_returns_total_value(profile):
    metrics = analytics.analyze(profile)
    assert metrics.total_value == pytest.approx(profile.portfolio_value)


# ---------------------------------------------------------------- price-based metrics

N_DAYS = 60  # daily returns in the fixtures: exactly the minimum the quant code accepts
TRADING_DAYS = 252


def _prices(returns: list[float], start: float = 100.0) -> pd.Series:
    """A close series whose pct_change() reproduces `returns` (first row is the start)."""
    closes = start * np.cumprod([1.0, *[1.0 + r for r in returns]])
    index = pd.bdate_range("2024-01-01", periods=len(closes))
    return pd.Series(closes, index=index)


def _history(**returns_by_symbol: list[float]) -> pd.DataFrame:
    return pd.DataFrame({symbol: _prices(r) for symbol, r in returns_by_symbol.items()})


def _alternating(up: float, down: float, n: int = N_DAYS) -> list[float]:
    return [up if i % 2 == 0 else down for i in range(n)]


def _single(symbol: str = "AAA") -> FinancialProfile:
    return FinancialProfile(
        holdings=[Holding(symbol=symbol, quantity=10, current_price=100)],
    )


def test_annual_volatility_hand_computed():
    # Returns alternate +1% / -1%: mean 0, sample variance = 60 * 0.01^2 / 59.
    risk = analytics.risk_metrics(_single(), _history(AAA=_alternating(0.01, -0.01)))
    expected = 0.01 * math.sqrt(60 / 59) * math.sqrt(TRADING_DAYS)
    assert risk.annual_volatility == pytest.approx(expected)


def test_volatility_weights_holdings_by_market_value():
    # 60/40 by value; B moves exactly against A, so the portfolio moves 0.6a - 0.4a = 0.2a.
    profile = _two_holding_profile()
    history = _history(A=_alternating(0.01, -0.01), B=_alternating(-0.01, 0.01))
    risk = analytics.risk_metrics(profile, history)
    expected = 0.2 * 0.01 * math.sqrt(60 / 59) * math.sqrt(TRADING_DAYS)
    assert risk.annual_volatility == pytest.approx(expected)


def test_max_drawdown_known_peak_and_decline():
    # Wealth: 1.00 -> 1.10 (peak) -> 0.88 -> flat. 0.88 / 1.10 - 1 = -0.20.
    risk = analytics.risk_metrics(_single(), _history(AAA=[0.10, -0.20] + [0.0] * 58))
    assert risk.max_drawdown == pytest.approx(-0.20)


def test_max_drawdown_counts_a_fall_from_the_starting_value():
    # The first day loses 10% before any higher peak exists: 0.90 / 1.00 - 1.
    risk = analytics.risk_metrics(_single(), _history(AAA=[-0.10] + [0.001] * 59))
    assert risk.max_drawdown == pytest.approx(-0.10)


def test_max_drawdown_is_zero_when_wealth_only_rises():
    risk = analytics.risk_metrics(_single(), _history(AAA=[0.01] * N_DAYS))
    assert risk.max_drawdown == 0.0


def test_sharpe_ratio_hand_computed_with_zero_risk_free_rate():
    # Half the days +2%, half -1%: mean 0.005, every deviation +-0.015,
    # sample std = 0.015 * sqrt(60/59)  ->  Sharpe = (1/3) * sqrt(252 * 59/60).
    risk = analytics.risk_metrics(_single(), _history(AAA=_alternating(0.02, -0.01)))
    assert risk.sharpe_ratio == pytest.approx(math.sqrt(TRADING_DAYS * 59 / 60) / 3)


def test_sortino_ratio_hand_computed_with_downside_only():
    # Downside deviation = sqrt(30 * 0.01^2 / 60) = sqrt(5e-5); Sortino = 0.005 / that * sqrt(252).
    risk = analytics.risk_metrics(_single(), _history(AAA=_alternating(0.02, -0.01)))
    assert risk.sortino_ratio == pytest.approx(0.005 / math.sqrt(5e-5) * math.sqrt(TRADING_DAYS))


def test_sortino_is_none_without_a_down_day():
    risk = analytics.risk_metrics(_single(), _history(AAA=_alternating(0.02, 0.01)))
    assert risk.sortino_ratio is None
    assert risk.sharpe_ratio is not None


def test_var_95_is_a_positive_loss_at_the_interpolated_5th_percentile():
    # Sorted returns are -0.060, -0.059, -0.058, -0.057, ... The 5th percentile sits at
    # index 0.05 * 59 = 2.95: -0.058 + 0.95 * 0.001 = -0.05705, reported as a 5.705% loss.
    shuffled = [(-0.060 + 0.001 * ((i * 7) % N_DAYS)) for i in range(N_DAYS)]
    risk = analytics.risk_metrics(_single(), _history(AAA=shuffled))
    assert risk.var_95 == pytest.approx(0.05705)
    assert risk.var_95 > 0


def test_var_95_is_negative_when_even_the_worst_days_gain():
    risk = analytics.risk_metrics(_single(), _history(AAA=[0.01 + 0.0001 * i for i in range(60)]))
    assert risk.var_95 < 0


def test_beta_against_known_benchmark():
    # Portfolio = 2 * benchmark + 0.1% every day: the constant does not change covariance.
    bench = _alternating(0.01, -0.01)
    history = _history(AAA=[2 * b + 0.001 for b in bench], **{analytics.BENCHMARK_SYMBOL: bench})
    assert analytics.risk_metrics(_single(), history).beta == pytest.approx(2.0)


def test_beta_is_none_without_a_benchmark_but_other_metrics_remain():
    risk = analytics.risk_metrics(_single(), _history(AAA=_alternating(0.02, -0.01)))
    assert risk.beta is None
    assert risk.annual_volatility is not None


def test_beta_never_falls_back_to_a_holding():
    history = _history(A=_alternating(0.01, -0.01), B=_alternating(0.02, -0.02))
    assert analytics.risk_metrics(_two_holding_profile(), history).beta is None


def test_beta_is_none_for_a_flat_benchmark():
    history = _history(
        AAA=_alternating(0.01, -0.01), **{analytics.BENCHMARK_SYMBOL: [0.0] * N_DAYS}
    )
    assert analytics.risk_metrics(_single(), history).beta is None


def test_zero_variance_returns_none_ratios_instead_of_infinity():
    risk = analytics.risk_metrics(_single(), _history(AAA=[0.0] * N_DAYS))
    assert risk.annual_volatility == 0.0
    assert risk.max_drawdown == 0.0
    assert risk.sharpe_ratio is None
    assert risk.sortino_ratio is None


def test_risk_metrics_without_price_history_are_all_none():
    assert analytics.risk_metrics(_single()) == RiskMetrics()
    assert analytics.risk_metrics(_single(), pd.DataFrame()) == RiskMetrics()


def test_risk_metrics_need_a_price_column_for_every_holding():
    history = _history(A=_alternating(0.01, -0.01))
    assert analytics.risk_metrics(_two_holding_profile(), history) == RiskMetrics()


def test_risk_metrics_need_sixty_returns():
    enough = _history(AAA=_alternating(0.01, -0.01, N_DAYS))
    too_few = _history(AAA=_alternating(0.01, -0.01, N_DAYS - 1))
    assert analytics.risk_metrics(_single(), enough).annual_volatility is not None
    assert analytics.risk_metrics(_single(), too_few) == RiskMetrics()


def test_missing_close_is_not_forward_filled():
    # 61 closes give exactly 60 returns; a NaN close removes the two returns touching it,
    # leaving 58. Forward-filling would have kept 60 by inventing a flat day.
    history = _history(AAA=_alternating(0.01, -0.01))
    history.iloc[30, 0] = np.nan
    assert analytics.risk_metrics(_single(), history) == RiskMetrics()


def test_non_positive_and_text_closes_are_treated_as_missing():
    for bad in (0.0, -5.0, "n/a"):
        history = _history(AAA=_alternating(0.01, -0.01)).astype(object)
        history.iloc[30, 0] = bad
        assert analytics.risk_metrics(_single(), history) == RiskMetrics()


def test_price_order_and_duplicate_dates_do_not_change_the_result():
    history = _history(AAA=_alternating(0.02, -0.01))
    scrambled = pd.concat([history.iloc[::-1], history.iloc[[5]]])
    assert analytics.risk_metrics(_single(), scrambled) == analytics.risk_metrics(
        _single(), history
    )


def test_risk_metrics_ignore_zero_value_holdings():
    profile = FinancialProfile(
        holdings=[
            Holding(symbol="AAA", quantity=10, current_price=100),
            Holding(symbol="GONE", quantity=0, current_price=50),
        ]
    )
    risk = analytics.risk_metrics(profile, _history(AAA=_alternating(0.01, -0.01)))
    assert risk.annual_volatility is not None


# ------------------------------------------------------------------------ correlation

_PATTERN_A = [0.01, 0.01, -0.01, -0.01]
_PATTERN_B = [0.01, 0.0, 0.0, -0.01]


def _tile(pattern: list[float], n: int = N_DAYS) -> list[float]:
    return [pattern[i % len(pattern)] for i in range(n)]


def _three_holdings() -> FinancialProfile:
    return FinancialProfile(
        holdings=[Holding(symbol=s, quantity=1, current_price=100) for s in ("AAA", "BBB", "CCC")]
    )


def _correlated_history() -> pd.DataFrame:
    return _history(
        AAA=_tile(_PATTERN_A),
        BBB=_tile(_PATTERN_B),
        CCC=[-r for r in _tile(_PATTERN_A)],
    )


def test_correlation_hand_computed_values():
    # Per 4-day period: sum(a*b) = 2, sum(a^2) = 4, sum(b^2) = 2 (x 1e-4), both zero-mean,
    # so corr(A, B) = 2 / sqrt(4 * 2) = 1/sqrt(2). C = -A, so corr(A, C) = -1.
    matrix = analytics.correlation_matrix(_three_holdings(), _correlated_history())
    assert matrix["AAA"]["BBB"] == pytest.approx(1 / math.sqrt(2))
    assert matrix["AAA"]["CCC"] == pytest.approx(-1.0)
    assert matrix["BBB"]["CCC"] == pytest.approx(-1 / math.sqrt(2))


def test_correlation_is_symmetric_with_unit_diagonal():
    matrix = analytics.correlation_matrix(_three_holdings(), _correlated_history())
    assert set(matrix) == {"AAA", "BBB", "CCC"}
    for a in matrix:
        assert matrix[a][a] == 1.0
        for b in matrix:
            assert matrix[a][b] == matrix[b][a]


def test_correlation_matches_the_documented_shape():
    profile = FinancialProfile(
        holdings=[Holding(symbol=s, quantity=1, current_price=100) for s in ("AAA", "BBB")]
    )
    history = _history(AAA=_tile(_PATTERN_A), BBB=_tile(_PATTERN_B))
    matrix = analytics.correlation_matrix(profile, history)
    r = 1 / math.sqrt(2)
    assert list(matrix) == ["AAA", "BBB"]
    assert matrix["AAA"] == pytest.approx({"AAA": 1.0, "BBB": r})
    assert matrix["BBB"] == pytest.approx({"AAA": r, "BBB": 1.0})


def test_correlation_accepts_exactly_sixty_and_rejects_fewer():
    profile = _three_holdings()
    just_enough = _correlated_history()
    assert analytics.correlation_matrix(profile, just_enough)
    with pytest.raises(InsufficientDataError):
        analytics.correlation_matrix(profile, just_enough.iloc[:-1])


def test_correlation_counts_only_overlapping_observations():
    # Each series has 60 returns but they overlap on only 30 days.
    profile = FinancialProfile(
        holdings=[Holding(symbol=s, quantity=1, current_price=100) for s in ("AAA", "BBB")]
    )
    history = _history(AAA=_tile(_PATTERN_A), BBB=_tile(_PATTERN_B))
    history.loc[history.index[:31], "BBB"] = np.nan
    with pytest.raises(InsufficientDataError):
        analytics.correlation_matrix(profile, history)


def test_correlation_without_price_history_raises():
    with pytest.raises(InsufficientDataError):
        analytics.correlation_matrix(_three_holdings())
    with pytest.raises(InsufficientDataError):
        analytics.correlation_matrix(_three_holdings(), pd.DataFrame())


def test_correlation_omits_symbols_without_price_data_or_variance():
    history = _history(AAA=_tile(_PATTERN_A), BBB=_tile(_PATTERN_B), CCC=[0.0] * N_DAYS)
    matrix = analytics.correlation_matrix(_three_holdings(), history[["AAA", "BBB", "CCC"]])
    assert set(matrix) == {"AAA", "BBB"}  # CCC has a constant price
    matrix = analytics.correlation_matrix(_three_holdings(), history[["AAA", "BBB"]])
    assert set(matrix) == {"AAA", "BBB"}  # CCC has no column at all


def test_correlation_is_independent_of_row_order():
    history = _correlated_history()
    assert analytics.correlation_matrix(
        _three_holdings(), history.iloc[::-1]
    ) == analytics.correlation_matrix(_three_holdings(), history)


def test_analyze_without_price_history_leaves_price_metrics_empty(profile):
    metrics = analytics.analyze(profile)
    assert metrics.risk == RiskMetrics()
    assert metrics.correlation_matrix == {}
