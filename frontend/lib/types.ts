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

// ------------------------------------------------------------------ portfolio

export interface AllocationSlice {
  label: string;
  value: number;
  weight: number;
}

export interface ConcentrationMetrics {
  hhi: number;
  effective_holdings: number;
  top_holding_weight: number;
  top_5_weight: number;
  flags: string[];
}

/** null means "not enough price history", never zero. */
export interface RiskMetrics {
  annual_volatility?: number | null;
  max_drawdown?: number | null;
  sharpe_ratio?: number | null;
  sortino_ratio?: number | null;
  var_95?: number | null;
  beta?: number | null;
}

export interface PortfolioMetrics {
  total_value: number;
  by_asset_class: AllocationSlice[];
  by_sector: AllocationSlice[];
  by_holding: AllocationSlice[];
  concentration?: ConcentrationMetrics | null;
  risk: RiskMetrics;
  correlation_matrix?: Record<string, Record<string, number>>;
  dominant_asset_class?: AssetClass | null;
}

/** A dimension that is null has not been scored yet; it is not a zero. */
export interface HealthScore {
  overall: number | null;
  liquidity: number | null;
  debt_burden: number | null;
  diversification: number | null;
  goal_progress: number | null;
  market_exposure: number | null;
  drivers: Record<string, number>;
}

// ------------------------------------------------------------------- scenario

export type ScenarioType =
  | "baseline"
  | "market_stress"
  | "income_shock"
  | "contribution_change"
  | "sip_interruption"
  | "allocation_change";

export interface SimulationSettings {
  n_paths?: number;
  seed?: number | null;
  percentiles?: number[];
  return_model?: "gbm" | "student_t";
  t_df?: number;
}

export interface ScenarioRequest {
  profile: FinancialProfile;
  scenario_type?: ScenarioType;
  horizon_months: number;
  expected_annual_return?: number;
  annual_volatility?: number;
  settings?: SimulationSettings;
  market_stress?: { shock_pct: number; shock_at_month?: number; recovery_months?: number | null };
  income_shock?: { income_multiplier?: number; duration_months: number; start_month?: number };
  contribution_change?: {
    new_monthly_contribution?: number | null;
    pause_months?: number;
    pause_start_month?: number;
  };
  allocation_change?: { target_weights: Partial<Record<AssetClass, number>> };
}

export interface Assumptions {
  horizon_months: number;
  expected_annual_return: number;
  annual_volatility: number;
  monthly_contribution: number;
  inflation?: number;
  n_paths: number;
  seed?: number | null;
  notes: string[];
}

export interface Percentile {
  p: number;
  value: number;
}

/** One percentile followed month by month — the edges of the range band. */
export interface PercentilePath {
  p: number;
  values: number[];
}

export interface GoalOutcome {
  goal_name: string;
  target_amount: number;
  success_probability: number;
  median_shortfall: number;
  evaluated_at_month?: number | null;
  /** Goal Failure Analysis: additive shares of (target - median outcome). */
  shortfall_drivers: Record<string, number>;
  required_monthly_contribution?: number | null;
}

export interface ScenarioResult {
  scenario_type: ScenarioType | string;
  label: string;
  assumptions: Assumptions;
  terminal_percentiles: Percentile[];
  median_path: number[];
  /** Optional so the UI degrades to median-only against an older backend. */
  percentile_paths?: PercentilePath[];
  total_contributed: number;
  goal_outcomes: GoalOutcome[];
  cash_runway_months?: number | null;
  explanation?: Explanation | null;
}

export interface ScenarioComparison {
  baseline: ScenarioResult;
  alternatives: ScenarioResult[];
  deltas: Record<string, number>;
}

// ---------------------------------------------------------------------- agent

export interface Evidence {
  claim: string;
  source: string;
  snippet?: string | null;
  confidence?: number | null;
}

export interface Explanation {
  summary: string;
  assumptions?: Assumptions | null;
  numbers: Record<string, unknown>;
  evidence: Evidence[];
  caveats: string[];
}

export interface ToolCall {
  tool: string;
  arguments: Record<string, unknown>;
  reasoning?: string | null;
}

export interface ToolResult {
  tool: string;
  ok: boolean;
  /** { summary, detail } — detail holds the full typed result for charts. */
  output: Record<string, unknown>;
  error?: string | null;
  latency_ms?: number | null;
}

export interface AgentResponse {
  answer: Explanation;
  tool_calls: ToolCall[];
  tool_results: ToolResult[];
  evidence: Evidence[];
  latency_ms?: number | null;
}

// ----------------------------------------------------------------- documents

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
