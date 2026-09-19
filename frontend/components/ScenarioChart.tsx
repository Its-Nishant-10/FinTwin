"use client";

/**
 * Baseline vs. alternative median paths. OWNER: Member 6.
 *
 * TODO(member-6): add a shaded p10-p90 band — showing only the median makes a
 * distribution look like a prediction, which is exactly what this project
 * argues against.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ScenarioResult } from "@/lib/types";

export function ScenarioChart({
  baseline,
  alternative,
}: {
  baseline: ScenarioResult;
  alternative?: ScenarioResult;
}) {
  const data = baseline.median_path.map((value, month) => ({
    month,
    baseline: Math.round(value),
    alternative: alternative ? Math.round(alternative.median_path[month]) : undefined,
  }));

  const compact = (value: number) =>
    new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(value);

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <CartesianGrid stroke="#243044" strokeDasharray="3 3" />
        <XAxis
          dataKey="month"
          stroke="#94a3b8"
          tickLine={false}
          label={{ value: "Month", position: "insideBottom", offset: -4, fill: "#94a3b8" }}
        />
        <YAxis stroke="#94a3b8" tickLine={false} tickFormatter={compact} width={56} />
        <Tooltip
          contentStyle={{ background: "#131a26", border: "1px solid #243044", borderRadius: 8 }}
          formatter={(value: number) => `₹${compact(value)}`}
        />
        <Line
          type="monotone"
          dataKey="baseline"
          name={baseline.label}
          stroke="#4ade80"
          strokeWidth={2}
          dot={false}
        />
        {alternative && (
          <Line
            type="monotone"
            dataKey="alternative"
            name={alternative.label}
            stroke="#f87171"
            strokeWidth={2}
            dot={false}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
