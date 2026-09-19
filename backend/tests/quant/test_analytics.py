"""OWNER: Member 1. Every quant function needs a hand-checked number here."""

from __future__ import annotations

import pytest

from app.core.errors import InsufficientDataError
from app.quant import analytics
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
