"use client";

/**
 * Allocation donut with a table twin.
 *
 * A donut is for part-to-whole at a glance, and any two slices can sit side by
 * side, so it carries at most three hues (the ones validated as safe for every
 * pairing, including colour-blind viewers). Everything past the top three folds
 * into one neutral "Other" slice; the table beside it still lists every entry.
 */

import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatCompactINR, formatINR, formatPct, humanize } from "@/lib/format";
import type { AllocationSlice, PortfolioMetrics } from "@/lib/types";

type View = "asset_class" | "sector" | "holding";

const VIEWS: { id: View; label: string }[] = [
  { id: "asset_class", label: "Asset class" },
  { id: "sector", label: "Sector" },
  { id: "holding", label: "Holding" },
];

const HUES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
const OTHER = "var(--series-neutral)";
const VISIBLE_ROWS = 8;

interface Row {
  label: string;
  value: number;
  weight: number;
  color: string;
  /** Which donut slice this row belongs to. */
  slice: number;
}

function rowsFor(view: View, metrics: PortfolioMetrics): AllocationSlice[] {
  const source =
    view === "asset_class"
      ? metrics.by_asset_class
      : view === "sector"
        ? metrics.by_sector
        : metrics.by_holding;
  return [...source].sort((a, b) => b.weight - a.weight);
}

function build(view: View, metrics: PortfolioMetrics): { rows: Row[]; donut: Row[] } {
  const rows: Row[] = rowsFor(view, metrics).map((item, index) => ({
    label: view === "asset_class" ? humanize(item.label) : item.label,
    value: item.value,
    weight: item.weight,
    color: index < HUES.length ? HUES[index] : OTHER,
    slice: Math.min(index, HUES.length),
  }));
  const top = rows.slice(0, HUES.length);
  const rest = rows.slice(HUES.length);
  const donut = rest.length
    ? [
        ...top,
        {
          label: `Other (${rest.length})`,
          value: rest.reduce((sum, row) => sum + row.value, 0),
          weight: rest.reduce((sum, row) => sum + row.weight, 0),
          color: OTHER,
          slice: HUES.length,
        },
      ]
    : top;
  return { rows, donut };
}

export function AllocationChart({ metrics }: { metrics: PortfolioMetrics }) {
  const [view, setView] = useState<View>("asset_class");
  const [active, setActive] = useState<number | null>(null);
  const [expanded, setExpanded] = useState(false);

  const { rows, donut } = build(view, metrics);
  const shownRows = expanded ? rows : rows.slice(0, VISIBLE_ROWS);

  if (rows.length === 0) {
    return <p className="empty">No holdings yet. Import a statement below to build the twin.</p>;
  }

  return (
    <div className="allocation">
      <div className="seg" role="group" aria-label="Group holdings by">
        {VIEWS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            aria-pressed={view === id}
            onClick={() => {
              setView(id);
              setActive(null);
              setExpanded(false);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="allocation__body">
        <div className="donut">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={donut}
                dataKey="value"
                nameKey="label"
                innerRadius="64%"
                outerRadius="94%"
                startAngle={90}
                endAngle={-270}
                stroke="var(--surface)"
                strokeWidth={2}
                isAnimationActive={false}
                onMouseEnter={(_, index) => setActive(index)}
                onMouseLeave={() => setActive(null)}
              >
                {donut.map((slice, index) => (
                  <Cell
                    key={slice.label}
                    fill={slice.color}
                    fillOpacity={active === null || active === index ? 1 : 0.35}
                  />
                ))}
              </Pie>
              <Tooltip
                content={(props) => {
                  const slice = props.payload?.[0]?.payload as Row | undefined;
                  if (!props.active || !slice) return null;
                  return (
                    <div className="chart-tooltip">
                      <div className="chart-tooltip__row">
                        <span className="key-swatch" style={{ background: slice.color }} />
                        <span className="chart-tooltip__value">{formatPct(slice.weight, 1)}</span>
                        <span className="chart-tooltip__name">{slice.label}</span>
                      </div>
                      <div className="chart-tooltip__foot">{formatINR(slice.value)}</div>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="donut__center">
            <span className="donut__value">{formatCompactINR(metrics.total_value)}</span>
            <span className="donut__label">Portfolio</span>
          </div>
        </div>

        <div className="table-wrap allocation__table">
          <table className="data-table">
            <caption className="sr-only">Portfolio by {VIEWS.find((v) => v.id === view)?.label}</caption>
            <thead>
              <tr>
                <th scope="col">{VIEWS.find((v) => v.id === view)?.label}</th>
                <th scope="col">Share</th>
                <th scope="col">Value</th>
              </tr>
            </thead>
            <tbody>
              {shownRows.map((row) => (
                <tr
                  key={row.label}
                  data-active={active === row.slice || undefined}
                  onMouseEnter={() => setActive(row.slice)}
                  onMouseLeave={() => setActive(null)}
                >
                  <th scope="row">
                    <span className="key-swatch" style={{ background: row.color }} />
                    {row.label}
                  </th>
                  <td>{formatPct(row.weight, 1)}</td>
                  <td>{formatINR(row.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > VISIBLE_ROWS && (
            <button type="button" className="btn btn--ghost" onClick={() => setExpanded(!expanded)}>
              {expanded ? "Show fewer" : `Show all ${rows.length}`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
