/**
 * Narrowing for the untyped `output.detail` of an agent tool result.
 *
 * Every tool returns { summary, detail }; `detail` is the full typed payload the
 * UI draws charts from. It arrives as unknown JSON, so each accessor checks the
 * minimum shape it relies on and returns null otherwise — a malformed or failed
 * tool result must never crash the chat.
 */

import type {
  DocumentExtraction,
  Evidence,
  HealthScore,
  PortfolioMetrics,
  ScenarioComparison,
  ScenarioResult,
  ToolResult,
} from "./types";

type Rec = Record<string, unknown>;

const isRecord = (value: unknown): value is Rec =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function detailOf(result: ToolResult): unknown {
  return result.ok ? result.output.detail : undefined;
}

function isScenarioResult(value: unknown): value is ScenarioResult {
  return (
    isRecord(value) &&
    Array.isArray(value.median_path) &&
    Array.isArray(value.terminal_percentiles) &&
    isRecord(value.assumptions)
  );
}

/** run_scenario / compare_scenarios return a comparison; project_goal a single result. */
export function scenarioFrom(result: ToolResult): ScenarioComparison | null {
  const detail = detailOf(result);
  if (isRecord(detail) && isScenarioResult(detail.baseline) && Array.isArray(detail.alternatives)) {
    return {
      baseline: detail.baseline,
      alternatives: detail.alternatives.filter(isScenarioResult),
      deltas: isRecord(detail.deltas) ? (detail.deltas as Record<string, number>) : {},
    };
  }
  if (isScenarioResult(detail)) return { baseline: detail, alternatives: [], deltas: {} };
  return null;
}

export function portfolioFrom(result: ToolResult): PortfolioMetrics | null {
  const detail = detailOf(result);
  return isRecord(detail) && Array.isArray(detail.by_asset_class)
    ? (detail as unknown as PortfolioMetrics)
    : null;
}

export function healthFrom(result: ToolResult): HealthScore | null {
  const detail = detailOf(result);
  return isRecord(detail) && "overall" in detail && isRecord(detail.drivers)
    ? (detail as unknown as HealthScore)
    : null;
}

export function extractionFrom(result: ToolResult): DocumentExtraction | null {
  const detail = detailOf(result);
  return isRecord(detail) && Array.isArray(detail.fields)
    ? (detail as unknown as DocumentExtraction)
    : null;
}

export function passagesFrom(result: ToolResult): Evidence[] {
  const detail = detailOf(result);
  return Array.isArray(detail) ? (detail.filter(isRecord) as unknown as Evidence[]) : [];
}

const TOOL_LABELS: Record<string, string> = {
  analyze_portfolio: "Portfolio analysis",
  compute_health_score: "Health score",
  run_scenario: "Scenario simulation",
  compare_scenarios: "Scenario comparison",
  project_goal: "Goal projection",
  extract_document: "Document extraction",
  research_market: "Knowledge-base lookup",
  forecast_volatility: "Volatility forecast",
};

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool.replace(/_/g, " ");
}
