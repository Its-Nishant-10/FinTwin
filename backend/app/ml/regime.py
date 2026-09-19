"""Market regime detection — OWNER: Member 3.

Label periods as calm / stressed so the simulation engine can offer
regime-conditioned assumptions instead of one flat volatility number.
"""

from __future__ import annotations

from app.core.errors import NotImplementedYetError


def detect_regimes(returns, n_regimes: int = 2):
    """TODO(member-3): clustering or an HMM over rolling vol + drawdown features."""
    raise NotImplementedYetError("regime.detect_regimes")


def current_regime(symbol: str = "NIFTYBEES") -> dict:
    """TODO(member-3): {"regime": "calm"|"stressed", "confidence": 0-1, "since": date}."""
    raise NotImplementedYetError("regime.current_regime")
