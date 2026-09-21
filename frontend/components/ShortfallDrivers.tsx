/**
 * Goal Failure Analysis: what widens or narrows the gap to a goal.
 *
 * The backend guarantees the values are additive — they sum to
 * (target − median outcome) — so the bars can be read as a breakdown of one
 * number. Positive (warm) widens the shortfall, negative (cool) narrows it.
 * Every bar also says so in words; colour is never the only signal.
 */

import { formatCompactINR } from "@/lib/format";

const LABELS: Record<string, string> = {
  baseline_plan: "Your current plan on its own",
  market_shock: "The market fall",
  contribution_change: "The change to your SIP",
  income_shock: "The income shock",
  allocation_change: "The new allocation",
};

const label = (key: string) => LABELS[key] ?? key.replace(/_/g, " ");

function describe(key: string, value: number): string {
  const amount = formatCompactINR(Math.abs(value));
  if (key === "baseline_plan") {
    return value > 0 ? `leaves a gap of ${amount}` : `clears the target by ${amount}`;
  }
  return value > 0 ? `widens the gap by ${amount}` : `closes ${amount} of the gap`;
}

export function ShortfallDrivers({ drivers }: { drivers: Record<string, number> }) {
  const rows = Object.entries(drivers)
    .filter(([, value]) => Math.abs(value) >= 1)
    .sort(([a, x], [b, y]) => {
      if (a === "baseline_plan") return -1;
      if (b === "baseline_plan") return 1;
      return Math.abs(y) - Math.abs(x);
    });
  if (rows.length === 0) return null;

  const scale = Math.max(...rows.map(([, value]) => Math.abs(value)));
  const gap = rows.reduce((sum, [, value]) => sum + value, 0);

  return (
    <div className="drivers">
      <div className="drivers__axis" aria-hidden="true">
        <span />
        <span className="drivers__axis-labels">
          <span>← closes the gap</span>
          <span>widens the gap →</span>
        </span>
      </div>
      <ul className="drivers__list">
        {rows.map(([key, value]) => (
          <li key={key} className="driver">
            <span className="driver__label">
              <span className="driver__name">{label(key)}</span>
              <span className="driver__text">{describe(key, value)}</span>
            </span>
            <span className="driver__track" aria-hidden="true">
              <span
                className="driver__bar"
                data-side={value > 0 ? "widen" : "narrow"}
                style={{ width: `${(Math.abs(value) / scale) * 50}%` }}
              />
            </span>
          </li>
        ))}
      </ul>
      <p className="drivers__total">
        {gap > 0
          ? `Together: the median outcome falls ${formatCompactINR(gap)} short of the target.`
          : `Together: the median outcome clears the target by ${formatCompactINR(-gap)}.`}
      </p>
    </div>
  );
}
