/**
 * Totals shown on the digital-twin summary.
 *
 * These mirror FinancialProfile.portfolio_value / net_worth on the backend.
 * Pydantic doesn't serialise @property values, so the API doesn't send them.
 * They are sums of figures the user entered, not analysis; anything that needs
 * judgement (allocation, risk, scores, simulation) still comes from the backend.
 */

import type { FinancialProfile } from "./types";

export interface TwinTotals {
  portfolioValue: number;
  totalLiabilities: number;
  monthlyEmis: number;
  netWorth: number;
  monthlySurplus: number;
}

export function twinTotals(profile: FinancialProfile): TwinTotals {
  const portfolioValue = profile.holdings.reduce(
    (sum, holding) => sum + holding.quantity * holding.current_price,
    0,
  );
  const totalLiabilities = profile.liabilities.reduce((sum, item) => sum + item.outstanding, 0);
  const monthlyEmis = profile.liabilities.reduce((sum, item) => sum + item.monthly_emi, 0);
  return {
    portfolioValue,
    totalLiabilities,
    monthlyEmis,
    netWorth: portfolioValue + profile.cash_balance + profile.other_assets - totalLiabilities,
    monthlySurplus: profile.cashflow.monthly_income - profile.cashflow.monthly_expenses,
  };
}
