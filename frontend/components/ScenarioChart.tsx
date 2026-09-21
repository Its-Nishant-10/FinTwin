"use client";

/**
 * Baseline vs. scenario, with the range of outcomes shaded around each median.
 * OWNER: Member 6.
 *
 * Showing only the median makes a distribution look like a prediction, which is
 * exactly what this project argues against — so the 10th–90th percentile band is
 * drawn behind every line. The baseline is the neutral reference; the scenario
 * takes the one accent colour (emphasis form). A table view carries every value
 * the chart shows.
 */

import { useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  bandOf,
  buildRows,
  monthTickLabel,
  monthTicks,
  tickStep,
  type ChartRow,
} from "@/lib/chart-data";
import { formatCompactINR, formatINR, formatMonths } from "@/lib/format";
import type { ScenarioResult } from "@/lib/types";

const BASELINE_COLOR = "var(--series-neutral)";
const SCENARIO_COLOR = "var(--series-1)";

export interface GoalMarker {
  name: string;
  target: number;
  month: number;
}

function EndLabel(text: string, lastIndex: number) {
  return function Label(props: { x?: number; y?: number; index?: number }) {
    if (props.index !== lastIndex || props.x == null || props.y == null) return <g />;
    return (
      <text x={props.x + 8} y={props.y} dominantBaseline="middle" className="chart-end-label">
        {text}
      </text>
    );
  };
}

function SeriesReadout({
  color,
  name,
  median,
  range,
}: {
  color: string;
  name: string;
  median: number;
  range?: [number, number];
}) {
  return (
    <div className="chart-tooltip__row">
      <span className="key-line" style={{ background: color }} />
      <span className="chart-tooltip__value">{formatINR(median)}</span>
      <span className="chart-tooltip__name">{name}</span>
      {range && (
        <span className="chart-tooltip__range">
          {formatCompactINR(range[0])} – {formatCompactINR(range[1])}
        </span>
      )}
    </div>
  );
}

export function ScenarioChart({
  baseline,
  alternative,
  goal,
}: {
  baseline: ScenarioResult;
  alternative?: ScenarioResult;
  goal?: GoalMarker;
}) {
  const [view, setView] = useState<"chart" | "table">("chart");

  const rows = buildRows(baseline, alternative);
  const horizon = baseline.median_path.length - 1;
  const band = bandOf(baseline);
  const scenarioBand = alternative ? bandOf(alternative) : null;
  const rangeName = band ? `${band.lowP}th–${band.highP}th percentile` : null;

  const last = rows[rows.length - 1];
  const yMax = Math.max(
    ...rows.map((row) => Math.max(row.baseline, row.baselineBand?.[1] ?? 0, row.scenarioBand?.[1] ?? 0)),
    goal?.target ?? 0,
  );
  // Two end labels that would sit on top of each other: keep the scenario's, the
  // baseline's value is still in the legend, tooltip and table.
  const labelsCollide =
    last.scenario !== undefined && Math.abs(last.scenario - last.baseline) / yMax < 0.07;

  const summary =
    `Median portfolio value after ${formatMonths(horizon)}: baseline ${formatINR(last.baseline)}` +
    (last.scenario !== undefined ? `, ${alternative?.label} ${formatINR(last.scenario)}` : "") +
    (rangeName ? `. Shaded areas show the ${rangeName} range of simulated outcomes.` : ".");

  return (
    <figure className="figure">
      <div className="figure__head">
        <ul className="legend" aria-label="Chart legend">
          <li className="legend__item">
            <span className="key-line" style={{ background: BASELINE_COLOR }} />
            <span className="key-band" style={{ background: BASELINE_COLOR }} />
            {baseline.label}
          </li>
          {alternative && (
            <li className="legend__item">
              <span className="key-line" style={{ background: SCENARIO_COLOR }} />
              <span className="key-band" style={{ background: SCENARIO_COLOR }} />
              {alternative.label}
            </li>
          )}
        </ul>
        <div className="seg" role="group" aria-label="Chart or table">
          <button type="button" aria-pressed={view === "chart"} onClick={() => setView("chart")}>
            Chart
          </button>
          <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}>
            Table
          </button>
        </div>
      </div>

      {view === "chart" ? (
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart
            data={rows}
            margin={{ top: 12, right: 76, bottom: 4, left: 0 }}
            accessibilityLayer
          >
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="month"
              type="number"
              domain={[0, horizon]}
              ticks={monthTicks(horizon)}
              tickFormatter={(month: number) => monthTickLabel(month, horizon)}
              tickLine={false}
              axisLine={{ stroke: "var(--axis)" }}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
            />
            <YAxis
              domain={[0, "auto"]}
              tickFormatter={formatCompactINR}
              tickLine={false}
              axisLine={false}
              width={64}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
            />
            <Tooltip
              cursor={{ stroke: "var(--ink-3)", strokeWidth: 1 }}
              content={(props) => {
                const row = props.payload?.[0]?.payload as ChartRow | undefined;
                if (!props.active || !row) return null;
                return (
                  <div className="chart-tooltip">
                    <div className="chart-tooltip__title">
                      {row.month === 0 ? "Today" : `Month ${row.month} · ${formatMonths(row.month)}`}
                    </div>
                    <SeriesReadout
                      color={BASELINE_COLOR}
                      name={baseline.label}
                      median={row.baseline}
                      range={row.baselineBand}
                    />
                    {alternative && row.scenario !== undefined && (
                      <SeriesReadout
                        color={SCENARIO_COLOR}
                        name={alternative.label}
                        median={row.scenario}
                        range={row.scenarioBand}
                      />
                    )}
                    {rangeName && <div className="chart-tooltip__foot">Range: {rangeName}</div>}
                  </div>
                );
              }}
            />
            {band && (
              <Area
                dataKey="baselineBand"
                stroke={BASELINE_COLOR}
                strokeWidth={1}
                strokeOpacity={0.35}
                fill={BASELINE_COLOR}
                fillOpacity={0.1}
                isAnimationActive={false}
                activeDot={false}
                legendType="none"
              />
            )}
            {scenarioBand && (
              <Area
                dataKey="scenarioBand"
                stroke={SCENARIO_COLOR}
                strokeWidth={1}
                strokeOpacity={0.4}
                fill={SCENARIO_COLOR}
                fillOpacity={0.12}
                isAnimationActive={false}
                activeDot={false}
                legendType="none"
              />
            )}
            {goal && (
              <ReferenceLine
                y={goal.target}
                ifOverflow="extendDomain"
                stroke="var(--ink-2)"
                strokeDasharray="4 4"
                label={{
                  value: `Goal ${formatCompactINR(goal.target)}`,
                  position: "insideTopLeft",
                  fill: "var(--muted)",
                  fontSize: 12,
                }}
              />
            )}
            <Line
              type="monotone"
              dataKey="baseline"
              name={baseline.label}
              stroke={BASELINE_COLOR}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
              isAnimationActive={false}
              label={labelsCollide ? undefined : EndLabel(formatCompactINR(last.baseline), horizon)}
            />
            {alternative && (
              <Line
                type="monotone"
                dataKey="scenario"
                name={alternative.label}
                stroke={SCENARIO_COLOR}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
                isAnimationActive={false}
                label={EndLabel(formatCompactINR(last.scenario ?? 0), horizon)}
              />
            )}
            {goal && goal.month <= horizon && (
              <ReferenceDot
                x={goal.month}
                y={goal.target}
                r={5}
                fill="var(--surface)"
                stroke="var(--ink)"
                strokeWidth={2}
                ifOverflow="extendDomain"
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        <ChartTable rows={rows} horizon={horizon} baseline={baseline} alternative={alternative} />
      )}

      <figcaption className="figure__caption">
        <span className="sr-only">{summary} </span>
        {rangeName
          ? `Lines are the median simulated outcome. Shaded bands cover the ${rangeName} range, so about 8 in 10 simulated outcomes fall inside — a range of possibilities, not a forecast.`
          : "Lines are the median simulated outcome. This backend did not return a percentile range."}
        {goal && ` The dot marks the goal “${goal.name}” at month ${goal.month}.`}
      </figcaption>
    </figure>
  );
}

function ChartTable({
  rows,
  horizon,
  baseline,
  alternative,
}: {
  rows: ChartRow[];
  horizon: number;
  baseline: ScenarioResult;
  alternative?: ScenarioResult;
}) {
  const step = tickStep(horizon);
  const shown = rows.filter((row) => row.month % step === 0 || row.month === horizon);
  const hasBand = rows[0]?.baselineBand !== undefined;
  const hasScenarioBand = rows[0]?.scenarioBand !== undefined;

  return (
    <div className="table-wrap">
      <table className="data-table">
        <caption className="sr-only">Simulated portfolio value by month</caption>
        <thead>
          <tr>
            <th scope="col">Month</th>
            {hasBand && <th scope="col">{baseline.label}: low</th>}
            <th scope="col">{baseline.label}: median</th>
            {hasBand && <th scope="col">{baseline.label}: high</th>}
            {alternative && hasScenarioBand && <th scope="col">{alternative.label}: low</th>}
            {alternative && <th scope="col">{alternative.label}: median</th>}
            {alternative && hasScenarioBand && <th scope="col">{alternative.label}: high</th>}
          </tr>
        </thead>
        <tbody>
          {shown.map((row) => (
            <tr key={row.month}>
              <th scope="row">{row.month === 0 ? "Today" : formatMonths(row.month)}</th>
              {hasBand && <td>{formatINR(row.baselineBand?.[0] ?? 0)}</td>}
              <td>{formatINR(row.baseline)}</td>
              {hasBand && <td>{formatINR(row.baselineBand?.[1] ?? 0)}</td>}
              {alternative && hasScenarioBand && <td>{formatINR(row.scenarioBand?.[0] ?? 0)}</td>}
              {alternative && <td>{row.scenario === undefined ? "—" : formatINR(row.scenario)}</td>}
              {alternative && hasScenarioBand && <td>{formatINR(row.scenarioBand?.[1] ?? 0)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
