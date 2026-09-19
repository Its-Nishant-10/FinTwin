"""The Personal Financial Digital Twin — the user's current financial state.

This is the flagship data structure of the project. Everything else either
builds it (Member 2, Member 4), measures it (Members 1, 3) or simulates
alternative futures from it (Member 5).
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.common import Money


class AssetClass(str, Enum):
    EQUITY = "equity"
    DEBT = "debt"
    GOLD = "gold"
    CASH = "cash"
    REAL_ESTATE = "real_estate"
    CRYPTO = "crypto"
    OTHER = "other"


class Holding(BaseModel):
    """One position in the portfolio, normalized from whatever the user gave us."""

    symbol: str = Field(..., description="Ticker or scheme code, e.g. 'INFY', 'NIFTYBEES'")
    name: str | None = None
    asset_class: AssetClass = AssetClass.EQUITY
    sector: str | None = None
    quantity: float = Field(..., ge=0)
    avg_cost: Money = Field(default=0.0, ge=0)
    current_price: Money = Field(default=0.0, ge=0)

    @property
    def market_value(self) -> Money:
        return self.quantity * self.current_price


class Cashflow(BaseModel):
    """Monthly money in and out."""

    monthly_income: Money = Field(default=0.0, ge=0)
    monthly_expenses: Money = Field(default=0.0, ge=0)
    monthly_contribution: Money = Field(
        default=0.0, ge=0, description="SIP / recurring investment amount"
    )

    @property
    def monthly_surplus(self) -> Money:
        return self.monthly_income - self.monthly_expenses


class Liability(BaseModel):
    name: str
    outstanding: Money = Field(..., ge=0)
    monthly_emi: Money = Field(default=0.0, ge=0)
    annual_rate: float = Field(default=0.0, description="Decimal, e.g. 0.09 for 9%")


class Goal(BaseModel):
    name: str = Field(..., description="e.g. 'House down payment'")
    target_amount: Money = Field(..., gt=0)
    target_date: date | None = None
    horizon_months: int = Field(..., gt=0)
    priority: int = Field(default=1, ge=1, le=5)


class RiskConstraints(BaseModel):
    """What the user says they can tolerate. Used to flag, never to auto-trade."""

    risk_tolerance: str = Field(default="moderate", description="low | moderate | high")
    max_equity_pct: float | None = Field(default=None, ge=0, le=1)
    max_single_holding_pct: float | None = Field(default=None, ge=0, le=1)
    min_emergency_months: float = Field(default=6.0, ge=0)


class FinancialProfile(BaseModel):
    """The complete twin. Every scenario starts from one of these."""

    user_id: str = "demo-user"
    as_of: date | None = None

    cashflow: Cashflow = Field(default_factory=Cashflow)
    holdings: list[Holding] = Field(default_factory=list)
    cash_balance: Money = Field(default=0.0, ge=0)
    other_assets: Money = Field(default=0.0, ge=0)
    liabilities: list[Liability] = Field(default_factory=list)
    goals: list[Goal] = Field(default_factory=list)
    risk: RiskConstraints = Field(default_factory=RiskConstraints)

    @property
    def portfolio_value(self) -> Money:
        return sum(h.market_value for h in self.holdings)

    @property
    def total_liabilities(self) -> Money:
        return sum(liability.outstanding for liability in self.liabilities)

    @property
    def net_worth(self) -> Money:
        return (
            self.portfolio_value
            + self.cash_balance
            + self.other_assets
            - self.total_liabilities
        )
