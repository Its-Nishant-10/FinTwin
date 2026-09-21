/**
 * Concentration and risk, measured against the limits the user set themselves.
 *
 * The weights and metrics come from the quant engine; the limits come from the
 * profile's risk constraints. Nothing here is a recommendation — it flags, and
 * it says in words what the colour means.
 */

import { formatNumber, formatPct } from "@/lib/format";
import type { FinancialProfile, PortfolioMetrics, RiskMetrics } from "@/lib/types";
import { Meter, Notice, StatusBadge, type Tone } from "./ui";

function LimitMeter({
  title,
  detail,
  value,
  limit,
}: {
  title: string;
  detail: string;
  value: number;
  limit?: number | null;
}) {
  const hasLimit = limit != null;
  const over = hasLimit && value > limit;
  const near = hasLimit && !over && value >= 0.85 * limit;
  const tone: Tone = !hasLimit ? "neutral" : over ? "critical" : near ? "caution" : "good";
  const status = !hasLimit
    ? "No limit set"
    : over
      ? "Above your limit"
      : near
        ? "Close to your limit"
        : "Within your limit";

  return (
    <div className="limit">
      <div className="limit__head">
        <span className="limit__title">{title}</span>
        <StatusBadge tone={tone}>{status}</StatusBadge>
      </div>
      <Meter
        value={value * 100}
        tone={tone}
        marker={hasLimit ? limit * 100 : null}
        label={`${title}: ${formatPct(value)}${hasLimit ? `, your limit ${formatPct(limit)}` : ""}`}
      />
      <div className="limit__foot">
        {detail} <strong>{formatPct(value)}</strong>
        {hasLimit && <> · your limit {formatPct(limit)}</>}
      </div>
    </div>
  );
}

const RISK_ROWS: { key: keyof RiskMetrics; label: string; percent: boolean }[] = [
  { key: "annual_volatility", label: "Volatility (annual)", percent: true },
  { key: "max_drawdown", label: "Max drawdown", percent: true },
  { key: "var_95", label: "1-day VaR (95%)", percent: true },
  { key: "sharpe_ratio", label: "Sharpe ratio", percent: false },
  { key: "sortino_ratio", label: "Sortino ratio", percent: false },
  { key: "beta", label: "Beta", percent: false },
];

export function PortfolioRisk({
  metrics,
  profile,
}: {
  metrics: PortfolioMetrics;
  profile: FinancialProfile;
}) {
  const top = metrics.by_holding[0];
  const equity = metrics.by_asset_class.find((slice) => slice.label === "equity");
  const concentration = metrics.concentration;
  const anyRisk = RISK_ROWS.some(({ key }) => metrics.risk[key] != null);

  return (
    <div className="risk">
      <div className="risk__limits">
        {top && (
          <LimitMeter
            title="Largest holding"
            detail={`${top.label} is`}
            value={top.weight}
            limit={profile.risk.max_single_holding_pct}
          />
        )}
        <LimitMeter
          title="Equity share"
          detail="Equities make up"
          value={equity?.weight ?? 0}
          limit={profile.risk.max_equity_pct}
        />
        {concentration && (
          <p className="risk__note">
            Your {profile.holdings.length} holdings behave like about{" "}
            <strong>{formatNumber(concentration.effective_holdings)}</strong> equally sized ones; the
            top five make up {formatPct(concentration.top_5_weight)}.
          </p>
        )}
        {concentration?.flags.map((flag) => (
          <Notice key={flag} tone="caution">
            {flag}
          </Notice>
        ))}
      </div>

      <div className="risk__metrics">
        <h4 className="subhead">Risk metrics</h4>
        {anyRisk ? (
          <dl className="facts facts--stack">
            {RISK_ROWS.map(({ key, label, percent }) => {
              const value = metrics.risk[key];
              return (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>
                    {value == null ? "—" : percent ? formatPct(value, 1) : formatNumber(value)}
                  </dd>
                </div>
              );
            })}
          </dl>
        ) : (
          <Notice tone="info">
            Volatility, drawdown, Sharpe and the rest need market price history, which isn&apos;t
            connected yet. They show as unavailable rather than as zero.
          </Notice>
        )}
      </div>
    </div>
  );
}
