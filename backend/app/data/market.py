"""Market-data ingestion — OWNER: Member 2.

Every other module gets prices through here. Cache aggressively: the demo must
work without network access on presentation day.
"""

from __future__ import annotations

from datetime import date

from app.core.errors import NotImplementedYetError


def get_price_history(symbols: list[str], start: date, end: date):
    """Daily adjusted closes as a DataFrame indexed by date, one column per symbol.

    TODO(member-2): yfinance/provider fetch + on-disk cache under data/cache/.
    Members 1 and 3 are blocked on this — ship a cached CSV fallback early.
    """
    raise NotImplementedYetError("market.get_price_history")


def get_latest_prices(symbols: list[str]) -> dict[str, float]:
    """TODO(member-2): last close per symbol, used to mark holdings to market."""
    raise NotImplementedYetError("market.get_latest_prices")
