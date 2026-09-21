/**
 * Assumption Transparency Panel + scope note.
 *
 * Per the proposal, a simulated number is never shown without the assumptions
 * that produced it. Keep this on every page that displays a projection.
 */

import { formatINR, formatMonths, formatNumber, formatPct } from "@/lib/format";
import type { Assumptions } from "@/lib/types";

export function AssumptionsPanel({
  assumptions,
  title = "Assumptions behind these numbers",
}: {
  assumptions: Assumptions;
  title?: string;
}) {
  const facts: [string, string][] = [
    ["Horizon", formatMonths(assumptions.horizon_months)],
    ["Expected annual return", formatPct(assumptions.expected_annual_return, 1)],
    ["Annual volatility", formatPct(assumptions.annual_volatility, 1)],
    ["Current monthly SIP", formatINR(assumptions.monthly_contribution)],
    ["Simulated paths", formatNumber(assumptions.n_paths)],
    ["Random seed", assumptions.seed == null ? "Not fixed" : String(assumptions.seed)],
    [
      "Inflation",
      assumptions.inflation ? formatPct(assumptions.inflation, 1) : "Not modeled",
    ],
  ];

  return (
    <section className="assumptions" aria-label={title}>
      <h4 className="assumptions__title">{title}</h4>
      <dl className="facts">
        {facts.map(([term, description]) => (
          <div key={term}>
            <dt>{term}</dt>
            <dd>{description}</dd>
          </div>
        ))}
      </dl>
      {assumptions.notes.length > 0 && (
        <ul className="assumptions__notes">
          {assumptions.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function Disclaimer({ assumptions }: { assumptions?: Assumptions }) {
  return (
    <div className="disclaimer">
      {assumptions && <AssumptionsPanel assumptions={assumptions} />}
      <p>
        FinTwin is a research prototype for financial analysis and simulation. Results are
        modeled outcomes under stated assumptions, not predictions, and this is not
        personalized investment advice.
      </p>
    </div>
  );
}
