/**
 * Assumption Transparency Panel + scope note.
 *
 * Per the proposal, a simulated number is never shown without the assumptions
 * that produced it. Keep this on every page that displays a projection.
 */

import type { Assumptions } from "@/lib/types";

export function Disclaimer({ assumptions }: { assumptions?: Assumptions }) {
  return (
    <div className="disclaimer" style={{ marginTop: 32 }}>
      {assumptions && (
        <p style={{ marginTop: 0 }}>
          <strong>Assumptions:</strong> {assumptions.horizon_months} months ·{" "}
          {(assumptions.expected_annual_return * 100).toFixed(0)}% expected annual return ·{" "}
          {(assumptions.annual_volatility * 100).toFixed(0)}% volatility ·{" "}
          {assumptions.n_paths.toLocaleString("en-IN")} simulated paths · seed{" "}
          {assumptions.seed ?? "unset"}
        </p>
      )}
      <p style={{ marginBottom: 0 }}>
        FinTwin is a research prototype for financial analysis and simulation. Results are
        modeled outcomes under stated assumptions, not predictions, and this is not
        personalized investment advice.
      </p>
    </div>
  );
}
