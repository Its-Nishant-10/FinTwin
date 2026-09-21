"use client";

/**
 * A baseline plus its alternatives: comparison table, chart with the outcome
 * range, the selected goal's outcome and Goal Failure Analysis, and the
 * assumptions that produced all of it.
 *
 * Used by the Scenario Lab and by the chat, so a what-if looks the same wherever
 * it comes from. Every figure is read from the backend response.
 */

import { useState } from "react";
import { terminalValue } from "@/lib/chart-data";
import {
  formatCompactINR,
  formatINR,
  formatMonths,
  formatPct,
  formatSignedCompactINR,
  formatSignedPct,
} from "@/lib/format";
import type { GoalOutcome, ScenarioComparison, ScenarioResult } from "@/lib/types";
import { AssumptionsPanel } from "./Disclaimer";
import { ScenarioChart } from "./ScenarioChart";
import { ShortfallDrivers } from "./ShortfallDrivers";
import { Icon, StatTile } from "./ui";

/** Outermost terminal percentiles either side of the median, e.g. p10 and p90. */
function terminalRange(result: ScenarioResult): [number, number] | null {
  const below = result.terminal_percentiles.filter((point) => point.p < 50);
  const above = result.terminal_percentiles.filter((point) => point.p > 50);
  if (below.length === 0 || above.length === 0) return null;
  const low = below.reduce((a, b) => (a.p <= b.p ? a : b));
  const high = above.reduce((a, b) => (a.p >= b.p ? a : b));
  return [low.value, high.value];
}

function Delta({ value, base }: { value: number; base: number }) {
  if (Math.round(value) === 0) return <span className="delta">No change</span>;
  const tone = value > 0 ? "good" : "critical";
  return (
    <span className="delta" data-tone={tone}>
      <Icon name={value > 0 ? "up" : "down"} />
      {formatSignedCompactINR(value)}
      {base > 0 && <span className="delta__pct"> ({formatSignedPct(value / base)})</span>}
    </span>
  );
}

export function ScenarioExplorer({ comparison }: { comparison: ScenarioComparison }) {
  const { baseline, alternatives, deltas } = comparison;
  const [picked, setPicked] = useState(0);
  const [goalPicked, setGoalPicked] = useState(0);

  const selected = alternatives.length
    ? alternatives[Math.min(picked, alternatives.length - 1)]
    : undefined;
  const shown = selected ?? baseline;

  const goalNames = baseline.goal_outcomes.map((goal) => goal.goal_name);
  const goalName = goalNames[Math.min(goalPicked, goalNames.length - 1)];
  const goalIn = (result: ScenarioResult): GoalOutcome | undefined =>
    result.goal_outcomes.find((goal) => goal.goal_name === goalName);

  const shownGoal = goalIn(shown);
  const baselineGoal = goalIn(baseline);
  const baseMedian = terminalValue(baseline, 50) ?? 0;
  const horizon = baseline.assumptions.horizon_months;
  const currentSip = shown.assumptions.monthly_contribution;

  const rows = [baseline, ...alternatives];

  return (
    <div className="explorer">
      <div className="table-wrap">
        <table className="data-table data-table--rows">
          <caption className="sr-only">
            Scenario comparison after {formatMonths(horizon)}. Select a row to chart it.
          </caption>
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              <th scope="col">Median at {formatMonths(horizon)}</th>
              <th scope="col">Likely range</th>
              <th scope="col">vs. baseline</th>
              <th scope="col">{goalName ? `Chance: ${goalName}` : "Goal chance"}</th>
              <th scope="col">Median shortfall</th>
              <th scope="col">SIP for the goal</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((result, index) => {
              const isBaseline = index === 0;
              const median = terminalValue(result, 50) ?? 0;
              const range = terminalRange(result);
              const goal = goalIn(result);
              const change = isBaseline ? 0 : (deltas[result.label] ?? median - baseMedian);
              const active = result === shown;
              return (
                <tr key={`${result.label}-${index}`} data-active={active || undefined}>
                  <th scope="row">
                    {isBaseline ? (
                      <span className="row-label">
                        {result.label}
                        {alternatives.length > 0 && <span className="row-tag">reference</span>}
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="row-pick"
                        aria-pressed={active}
                        onClick={() => setPicked(index - 1)}
                      >
                        {result.label}
                      </button>
                    )}
                  </th>
                  <td>{formatCompactINR(median)}</td>
                  <td>{range ? `${formatCompactINR(range[0])} – ${formatCompactINR(range[1])}` : "—"}</td>
                  <td>{isBaseline ? "—" : <Delta value={change} base={baseMedian} />}</td>
                  <td>{goal ? formatPct(goal.success_probability) : "—"}</td>
                  <td>{goal ? (goal.median_shortfall > 0 ? formatCompactINR(goal.median_shortfall) : "None") : "—"}</td>
                  <td>
                    {goal?.required_monthly_contribution != null
                      ? `${formatINR(goal.required_monthly_contribution)}/mo`
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {goalNames.length > 1 && (
        <label className="field field--inline">
          <span>Goal</span>
          <select value={goalPicked} onChange={(event) => setGoalPicked(Number(event.target.value))}>
            {goalNames.map((name, index) => (
              <option key={name} value={index}>
                {name}
              </option>
            ))}
          </select>
        </label>
      )}

      <ScenarioChart
        baseline={baseline}
        alternative={selected}
        goal={
          shownGoal && shownGoal.evaluated_at_month != null
            ? {
                name: shownGoal.goal_name,
                target: shownGoal.target_amount,
                month: shownGoal.evaluated_at_month,
              }
            : undefined
        }
      />

      {shownGoal && (
        <div className="explorer__detail">
          <div className="explorer__col">
            <h4 className="subhead">{shownGoal.goal_name}</h4>
            <div className="tiles tiles--tight">
              <StatTile
                label="Chance of reaching it"
                value={formatPct(shownGoal.success_probability)}
                sub={
                  selected && baselineGoal
                    ? `${formatPct(baselineGoal.success_probability)} on your current plan`
                    : `Target ${formatCompactINR(shownGoal.target_amount)} by ${formatMonths(shownGoal.evaluated_at_month ?? horizon)}`
                }
              />
              <StatTile
                label="Median shortfall"
                value={shownGoal.median_shortfall > 0 ? formatCompactINR(shownGoal.median_shortfall) : "None"}
                sub={shownGoal.median_shortfall > 0 ? "median outcome vs. target" : "median outcome reaches the target"}
              />
              {shownGoal.required_monthly_contribution != null && (
                <StatTile
                  label="Steady SIP for the goal"
                  value={`${formatINR(shownGoal.required_monthly_contribution)}/mo`}
                  sub={`you invest ${formatINR(currentSip)} now`}
                />
              )}
              {shown.cash_runway_months != null && (
                <StatTile
                  label="Cash runway"
                  value={`${shown.cash_runway_months.toFixed(1)} months`}
                  sub="cash covers expenses and EMIs at the reduced income"
                />
              )}
            </div>
          </div>
          <div className="explorer__col">
            <h4 className="subhead">Why the goal {shownGoal.median_shortfall > 0 ? "falls short" : "is on track"}</h4>
            <ShortfallDrivers drivers={shownGoal.shortfall_drivers} />
          </div>
        </div>
      )}

      <AssumptionsPanel assumptions={shown.assumptions} />
    </div>
  );
}
