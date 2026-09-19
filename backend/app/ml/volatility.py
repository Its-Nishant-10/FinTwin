"""Volatility modelling — OWNER: Member 3.

The honest baseline is rolling realized volatility. A learned model only earns
its place in the report if it beats that baseline on held-out data — and the
comparison goes in the benchmark either way.
"""

from __future__ import annotations

from app.core.errors import NotImplementedYetError


def realized_volatility(returns, window: int = 21) -> float:
    """Annualized rolling standard deviation. The baseline everything is judged against.

    TODO(member-3): returns.rolling(window).std() * sqrt(252), take the last value.
    """
    raise NotImplementedYetError("volatility.realized_volatility")


def forecast_volatility(symbol: str, horizon_days: int = 21) -> dict:
    """Predicted volatility + the baseline it is being compared against.

    TODO(member-3): return {"forecast": x, "baseline": y, "model": name, "mae": z}
    so the agent can quote the error alongside the number.
    """
    raise NotImplementedYetError("volatility.forecast_volatility")
