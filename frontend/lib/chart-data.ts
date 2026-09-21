/**
 * Shapes ScenarioResult data for the charts. Pure functions — no React.
 *
 * The band is always the outermost percentiles the backend returned on each
 * side of the median (p10 and p90 by default), so the label stays truthful if a
 * request asks for different percentiles.
 */

import type { ScenarioResult } from "./types";

export interface Band {
  low: number[];
  high: number[];
  lowP: number;
  highP: number;
}

export interface ChartRow {
  month: number;
  baseline: number;
  baselineBand?: [number, number];
  scenario?: number;
  scenarioBand?: [number, number];
}

export function bandOf(result: ScenarioResult): Band | null {
  const paths = result.percentile_paths ?? [];
  const below = paths.filter((path) => path.p < 50).sort((a, b) => a.p - b.p)[0];
  const above = paths.filter((path) => path.p > 50).sort((a, b) => b.p - a.p)[0];
  if (!below || !above) return null;
  return { low: below.values, high: above.values, lowP: below.p, highP: above.p };
}

export function terminalValue(result: ScenarioResult, percentile: number): number | undefined {
  return result.terminal_percentiles.find((point) => point.p === percentile)?.value;
}

const rounded = (value: number) => Math.round(value);

export function buildRows(baseline: ScenarioResult, scenario?: ScenarioResult): ChartRow[] {
  const baseBand = bandOf(baseline);
  const scenarioBand = scenario ? bandOf(scenario) : null;

  return baseline.median_path.map((value, month) => {
    const row: ChartRow = { month, baseline: rounded(value) };
    if (baseBand) row.baselineBand = [rounded(baseBand.low[month]), rounded(baseBand.high[month])];
    const scenarioValue = scenario?.median_path[month];
    if (scenarioValue !== undefined) {
      row.scenario = rounded(scenarioValue);
      if (scenarioBand) {
        row.scenarioBand = [rounded(scenarioBand.low[month]), rounded(scenarioBand.high[month])];
      }
    }
    return row;
  });
}

/** Tick spacing that keeps the x-axis readable from a two-year to a thirty-year horizon. */
export function tickStep(horizonMonths: number): number {
  if (horizonMonths <= 24) return 3;
  if (horizonMonths <= 72) return 12;
  if (horizonMonths <= 180) return 24;
  return 60;
}

export function monthTicks(horizonMonths: number): number[] {
  const step = tickStep(horizonMonths);
  const ticks: number[] = [];
  for (let month = 0; month <= horizonMonths; month += step) ticks.push(month);
  return ticks;
}

export function monthTickLabel(month: number, horizonMonths: number): string {
  if (month === 0) return "Now";
  return tickStep(horizonMonths) % 12 === 0 ? `${month / 12}y` : `${month}m`;
}
