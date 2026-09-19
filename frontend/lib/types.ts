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
    evaluated_at_month?: number | null;
    /** Goal Failure Analysis: additive shares of (target - median outcome). */
    shortfall_drivers: Record<string, number>;
    required_monthly_contribution?: number | null;
  }[];
  cash_runway_months?: number | null;
}

export interface ScenarioComparison {
  baseline: ScenarioResult;
  alternatives: ScenarioResult[];
  deltas: Record<string, number>;
}

export interface Evidence {
  claim: string;
  source: string;
  snippet?: string | null;
  confidence?: number | null;
}

export interface AgentResponse {
  answer: {
    summary: string;
    assumptions?: Assumptions | null;
    numbers: Record<string, unknown>;
    evidence: Evidence[];
    caveats: string[];
  };
  tool_calls: { tool: string; arguments: Record<string, unknown>; reasoning?: string | null }[];
  tool_results: {
    tool: string;
    ok: boolean;
    /** { summary, detail } — detail holds the full typed result for charts. */
    output: Record<string, unknown>;
    error?: string | null;
  }[];
  evidence: Evidence[];
  latency_ms?: number | null;
}

export interface ExtractedField {
  field: string;
  value: unknown;
  confidence: number;
  source_page?: number | null;
  /** Flip to false when the user confirms the value. */
  needs_confirmation: boolean;
}

export interface DocumentExtraction {
  filename: string;
  doc_type: string;
  fields: ExtractedField[];
  proposed_profile?: FinancialProfile | null;
  warnings: string[];
}
