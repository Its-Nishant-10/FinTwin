/**
 * TypeScript mirrors of backend/app/schemas/*.py.
 *
 * These MUST stay in sync with the Python models. If a schema changes, update
 * this file in the same PR.
 *
 * TODO(member-6): generate these from the OpenAPI spec instead of hand-writing
 * them — `npx openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts`.
 */

export type AssetClass =
  | "equity" | "debt" | "gold" | "cash" | "real_estate" | "crypto" | "other";

export interface Holding {
  symbol: string;
  name?: string | null;
  asset_class: AssetClass;
  sector?: string | null;
  quantity: number;
  avg_cost: number;
  current_price: number;
}

export interface Cashflow {
  monthly_income: number;
  monthly_expenses: number;
  monthly_contribution: number;
}

export interface Liability {
  name: string;
  outstanding: number;
  monthly_emi: number;
  annual_rate: number;
}

export interface Goal {
  name: string;
  target_amount: number;
  target_date?: string | null;
  horizon_months: number;
  priority: number;
}

export interface RiskConstraints {
  risk_tolerance: string;
  max_equity_pct?: number | null;
  max_single_holding_pct?: number | null;
  min_emergency_months: number;
}

export interface FinancialProfile {
  user_id: string;
  as_of?: string | null;
  cashflow: Cashflow;
  holdings: Holding[];
  cash_balance: number;
  other_assets: number;
  liabilities: Liability[];
  goals: Goal[];
  risk: RiskConstraints;
}

export interface AllocationSlice {
  label: string;
  value: number;
  weight: number;
}

export interface PortfolioMetrics {
  total_value: number;
  by_asset_class: AllocationSlice[];
  by_sector: AllocationSlice[];
  by_holding: AllocationSlice[];
  concentration?: {
    hhi: number;
    effective_holdings: number;
    top_holding_weight: number;
    top_5_weight: number;
    flags: string[];
  } | null;
  risk: Record<string, number | null>;
}

export interface Assumptions {
  horizon_months: number;
  expected_annual_return: number;
  annual_volatility: number;
  monthly_contribution: number;
  n_paths: number;
  seed?: number | null;
  notes: string[];
}

export interface ScenarioResult {
  scenario_type: string;
  label: string;
  assumptions: Assumptions;
  terminal_percentiles: { p: number; value: number }[];
  median_path: number[];
  total_contributed: number;
  goal_outcomes: {
    goal_name: string;
    target_amount: number;
    success_probability: number;
    median_shortfall: number;
  }[];
  cash_runway_months?: number | null;
}

export interface AgentResponse {
  answer: {
    summary: string;
    numbers: Record<string, unknown>;
    caveats: string[];
  };
  tool_calls: { tool: string; reasoning?: string | null }[];
  tool_results: { tool: string; ok: boolean; error?: string | null }[];
  latency_ms?: number | null;
}
