/**
 * The digital twin at a glance: one hero figure, then the facts behind it.
 */

import { formatCompactINR, formatINR, formatNumber, formatPct } from "@/lib/format";
import { twinTotals } from "@/lib/twin";
import type { FinancialProfile, HealthScore } from "@/lib/types";
import { StatTile } from "./ui";

export function TwinSummary({
  profile,
  health,
}: {
  profile: FinancialProfile;
  health: HealthScore;
}) {
  const totals = twinTotals(profile);
  const { cashflow } = profile;
  const runway = health.drivers.cash_runway_months;
  const goal = [...profile.goals].sort((a, b) => a.priority - b.priority)[0];
  const sipShare = totals.monthlySurplus > 0 ? cashflow.monthly_contribution / totals.monthlySurplus : null;

  return (
    <div className="twin">
      <StatTile
        hero
        label="Net worth"
        value={formatINR(totals.netWorth)}
        sub="Portfolio + cash + other assets − liabilities"
      />
      <div className="tiles">
        <StatTile
          label="Portfolio value"
          value={formatCompactINR(totals.portfolioValue)}
          sub={`${profile.holdings.length} holdings`}
        />
        <StatTile
          label="Cash"
          value={formatCompactINR(profile.cash_balance)}
          sub={
            runway == null
              ? undefined
              : `About ${formatNumber(runway)} months of expenses (target ${profile.risk.min_emergency_months})`
          }
        />
        <StatTile
          label="Liabilities"
          value={formatCompactINR(totals.totalLiabilities)}
          sub={`EMIs ${formatINR(totals.monthlyEmis)} a month`}
        />
        <StatTile
          label="Monthly surplus"
          value={formatINR(totals.monthlySurplus)}
          sub={`SIP ${formatINR(cashflow.monthly_contribution)}${sipShare == null ? "" : ` (${formatPct(sipShare)} of it)`}`}
        />
        {goal && (
          <StatTile
            label="Top goal"
            value={formatCompactINR(goal.target_amount)}
            sub={`${goal.name} in ${Math.round(goal.horizon_months / 12)} years`}
          />
        )}
      </div>
    </div>
  );
}
