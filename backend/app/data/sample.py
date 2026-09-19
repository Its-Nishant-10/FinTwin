"""The demo twin, hard-coded so every module has something to run against on day 1.

Numbers come straight from the worked example in the proposal:
3,00,000 invested, 15,000/month, 20,00,000 target in 5 years.
"""

from __future__ import annotations

from datetime import date

from app.schemas.profile import (
    AssetClass,
    Cashflow,
    FinancialProfile,
    Goal,
    Holding,
    Liability,
    RiskConstraints,
)


def load_sample_profile() -> FinancialProfile:
    return FinancialProfile(
        user_id="demo-user",
        as_of=date(2026, 1, 1),
        cashflow=Cashflow(
            monthly_income=120_000,
            monthly_expenses=70_000,
            monthly_contribution=15_000,
        ),
        holdings=[
            Holding(
                symbol="NIFTYBEES", name="Nippon Nifty 50 ETF", asset_class=AssetClass.EQUITY,
                sector="Index", quantity=400, avg_cost=240, current_price=280,
            ),
            Holding(
                symbol="INFY", name="Infosys", asset_class=AssetClass.EQUITY,
                sector="IT", quantity=60, avg_cost=1_450, current_price=1_600,
            ),
            Holding(
                symbol="HDFCBANK", name="HDFC Bank", asset_class=AssetClass.EQUITY,
                sector="Financials", quantity=40, avg_cost=1_500, current_price=1_700,
            ),
            Holding(
                symbol="LIQUIDBEES", name="Nippon Liquid ETF", asset_class=AssetClass.DEBT,
                sector="Debt", quantity=150, avg_cost=1_000, current_price=1_000,
            ),
        ],
        cash_balance=250_000,
        other_assets=0,
        liabilities=[
            Liability(name="Car loan", outstanding=320_000, monthly_emi=11_000, annual_rate=0.09),
        ],
        goals=[
            Goal(name="Down payment", target_amount=2_000_000, horizon_months=60, priority=1),
        ],
        risk=RiskConstraints(
            risk_tolerance="moderate",
            max_equity_pct=0.75,
            max_single_holding_pct=0.25,
            min_emergency_months=6,
        ),
    )
