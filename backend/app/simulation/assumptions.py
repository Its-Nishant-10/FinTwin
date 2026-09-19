"""Capital-market assumptions — OWNER: Member 5.

Long-run expected return and volatility per asset class, plus the correlations
between them. Used only where the engine has to *derive* return and volatility
from an allocation (allocation-change scenarios), so that the current and the
hypothetical portfolio are judged by the same yardstick.

These are illustrative, round-number assumptions for a research prototype, in
nominal INR terms. They are not forecasts and are not calibrated to any data
set. Every result built on them says so in its Assumptions.notes. Replace them
with estimates from Member 2's price history once that pipeline exists.
"""

from __future__ import annotations

import numpy as np

from app.core.errors import InsufficientDataError
from app.schemas.profile import AssetClass, FinancialProfile

#: asset class -> (expected annual return, annual volatility)
ASSET_CLASS_ASSUMPTIONS: dict[AssetClass, tuple[float, float]] = {
    AssetClass.EQUITY: (0.12, 0.18),
    AssetClass.DEBT: (0.07, 0.04),
    AssetClass.GOLD: (0.08, 0.15),
    AssetClass.CASH: (0.04, 0.01),
    AssetClass.REAL_ESTATE: (0.09, 0.12),
    AssetClass.CRYPTO: (0.15, 0.70),
    AssetClass.OTHER: (0.08, 0.15),
}

_ORDER = list(AssetClass)

# Symmetric correlation matrix in _ORDER:
#   equity, debt, gold, cash, real_estate, crypto, other
_CORRELATION = np.array(
    [
        [1.00, 0.10, -0.05, 0.00, 0.40, 0.30, 0.50],
        [0.10, 1.00, 0.10, 0.20, 0.10, 0.00, 0.20],
        [-0.05, 0.10, 1.00, 0.00, 0.05, 0.10, 0.10],
        [0.00, 0.20, 0.00, 1.00, 0.00, 0.00, 0.00],
        [0.40, 0.10, 0.05, 0.00, 1.00, 0.10, 0.30],
        [0.30, 0.00, 0.10, 0.00, 0.10, 1.00, 0.20],
        [0.50, 0.20, 0.10, 0.00, 0.30, 0.20, 1.00],
    ]
)

NOTE = (
    "Return and volatility derived from illustrative long-run asset-class "
    "assumptions (app/simulation/assumptions.py), not from market data."
)


def current_weights(profile: FinancialProfile) -> dict[AssetClass, float]:
    """The portfolio's present asset-class mix, by market value."""
    total = profile.portfolio_value
    if total <= 0:
        raise InsufficientDataError("no holdings, so there is no current allocation to compare")
    weights: dict[AssetClass, float] = {}
    for holding in profile.holdings:
        weights[holding.asset_class] = weights.get(holding.asset_class, 0.0) + (
            holding.market_value / total
        )
    return weights


def portfolio_return_vol(weights: dict[AssetClass, float]) -> tuple[float, float]:
    """Expected annual return (weighted mean) and volatility (sqrt of w' Σ w)."""
    w = np.array([weights.get(asset, 0.0) for asset in _ORDER])
    mu = np.array([ASSET_CLASS_ASSUMPTIONS[asset][0] for asset in _ORDER])
    sigma = np.array([ASSET_CLASS_ASSUMPTIONS[asset][1] for asset in _ORDER])
    covariance = _CORRELATION * np.outer(sigma, sigma)
    return float(w @ mu), float(np.sqrt(w @ covariance @ w))
