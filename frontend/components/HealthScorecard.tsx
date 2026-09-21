/**
 * Financial Health Scorecard.
 *
 * A dimension the backend hasn't built comes back as null and is shown as "not
 * scored yet" — never as a zero, which would read as the worst possible result.
 * The overall score averages only what has been scored, and says how many that is.
 */

import { formatNumber, humanize } from "@/lib/format";
import type { HealthScore } from "@/lib/types";
import { Meter, Notice, StatusBadge, type Tone } from "./ui";

type Dimension = Exclude<keyof HealthScore, "overall" | "drivers">;

const DIMENSIONS: { key: Dimension; label: string; measures: string }[] = [
  { key: "liquidity", label: "Liquidity", measures: "Cash against your emergency-fund target" },
  { key: "debt_burden", label: "Debt burden", measures: "EMIs relative to your income" },
  { key: "diversification", label: "Diversification", measures: "How spread out your holdings are" },
  { key: "goal_progress", label: "Goal progress", measures: "What you have against what your goals need" },
  { key: "market_exposure", label: "Market exposure", measures: "Equity share against your own limit" },
];

/** Presentation bands only; the scores themselves are computed by the backend. */
function band(score: number): { tone: Tone; label: string } {
  if (score >= 70) return { tone: "good", label: "Strong" };
  if (score >= 40) return { tone: "caution", label: "Fair" };
  return { tone: "critical", label: "Weak" };
}

/** cash_runway_months -> "Cash runway", 3.57 -> "3.6 months". */
function driver(key: string, value: number): [string, string] {
  const months = key.endsWith("_months");
  const name = humanize(months ? key.slice(0, -"_months".length) : key);
  return [name, months ? `${formatNumber(value)} months` : formatNumber(value)];
}

export function HealthScorecard({ health }: { health: HealthScore }) {
  const scored = DIMENSIONS.filter(({ key }) => health[key] != null).length;
  const overall = health.overall;
  const overallBand = overall == null ? null : band(overall);
  const drivers = Object.entries(health.drivers);

  return (
    <div className="health">
      <div className="health__overall">
        <div>
          <div className="stat-label">Overall</div>
          <div className="health__score">
            {overall == null ? "—" : Math.round(overall)}
            <span className="health__of"> / 100</span>
          </div>
        </div>
        <div className="health__overall-side">
          {overallBand && <StatusBadge tone={overallBand.tone}>{overallBand.label}</StatusBadge>}
          <span className="health__basis">
            Based on {scored} of {DIMENSIONS.length} areas
          </span>
        </div>
      </div>

      {scored < DIMENSIONS.length && (
        <Notice tone="info">
          {DIMENSIONS.length - scored} of {DIMENSIONS.length} areas aren&apos;t scored yet, so the
          overall score covers only the areas below that are.
        </Notice>
      )}

      <ul className="health__list">
        {DIMENSIONS.map(({ key, label, measures }) => {
          const score = health[key];
          const result = score == null ? null : band(score);
          return (
            <li key={key} className="dimension">
              <div className="dimension__head">
                <span className="dimension__name">{label}</span>
                {score == null ? (
                  <StatusBadge tone="neutral">Not scored yet</StatusBadge>
                ) : (
                  <span className="dimension__score">
                    <strong>{Math.round(score)}</strong>
                    {result && <StatusBadge tone={result.tone}>{result.label}</StatusBadge>}
                  </span>
                )}
              </div>
              <Meter
                value={score ?? 0}
                tone={result?.tone ?? "neutral"}
                label={score == null ? `${label}: not scored yet` : `${label}: ${Math.round(score)} out of 100`}
              />
              <div className="dimension__measures">{measures}</div>
            </li>
          );
        })}
      </ul>

      {drivers.length > 0 && (
        <details className="health__drivers">
          <summary>What moved these scores</summary>
          <dl className="facts facts--stack">
            {drivers.map(([key, value]) => {
              const [name, text] = driver(key, value);
              return (
                <div key={key}>
                  <dt>{name}</dt>
                  <dd>{text}</dd>
                </div>
              );
            })}
          </dl>
        </details>
      )}
    </div>
  );
}
