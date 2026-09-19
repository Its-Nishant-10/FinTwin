/**
 * Dashboard shell. OWNER: Member 6 (Frontend/Evaluation)
 *
 * This renders real data from the backend so everyone can see their work land.
 * The sections marked TODO are the ones still to build.
 */

import { api, formatINR } from "@/lib/api";
import { ScenarioChart } from "@/components/ScenarioChart";
import { Disclaimer } from "@/components/Disclaimer";
import type { FinancialProfile, PortfolioMetrics, ScenarioResult } from "@/lib/types";

async function loadDashboard(): Promise<{
  profile: FinancialProfile;
  metrics: PortfolioMetrics;
  baseline: ScenarioResult;
  crash: ScenarioResult;
} | null> {
  try {
    const profile = await api.sampleProfile();
    const [metrics, baseline, crash] = await Promise.all([
      api.analyzePortfolio(profile),
      api.runScenario({ profile, scenario_type: "baseline", horizon_months: 60 }),
      api.runScenario({
        profile,
        scenario_type: "market_stress",
        horizon_months: 60,
        market_stress: { shock_pct: -0.3, shock_at_month: 0 },
      }),
    ]);
    return { profile, metrics, baseline, crash };
  } catch {
    return null;
  }
}

export default async function Home() {
  const data = await loadDashboard();

  if (!data) {
    return (
      <main>
        <h1>FinTwin</h1>
        <p className="tagline">Explainable AI personal finance intelligence &amp; simulation</p>
        <div className="card">
          <p className="status-down">Backend not reachable.</p>
          <p className="todo">
            Start it with <code>make backend</code>, then reload this page.
          </p>
        </div>
      </main>
    );
  }

  const { profile, metrics, baseline, crash } = data;
  const median = (r: ScenarioResult) =>
    r.terminal_percentiles.find((p) => p.p === 50)?.value ?? 0;

  return (
    <main>
      <h1>FinTwin</h1>
      <p className="tagline">Explainable AI personal finance intelligence &amp; simulation</p>

      <h2>Your digital twin</h2>
      <div className="grid">
        <div className="card">
          <div className="stat-label">Portfolio value</div>
          <div className="stat-value">{formatINR(metrics.total_value)}</div>
        </div>
        <div className="card">
          <div className="stat-label">Monthly contribution</div>
          <div className="stat-value">{formatINR(profile.cashflow.monthly_contribution)}</div>
        </div>
        <div className="card">
          <div className="stat-label">Effective holdings</div>
          <div className="stat-value">
            {metrics.concentration ? metrics.concentration.effective_holdings.toFixed(1) : "—"}
          </div>
        </div>
      </div>

      <h2>What if markets fall 30%?</h2>
      <div className="card">
        <ScenarioChart baseline={baseline} alternative={crash} />
        <div className="grid" style={{ marginTop: 20 }}>
          <div>
            <div className="stat-label">Baseline median (5y)</div>
            <div className="stat-value">{formatINR(median(baseline))}</div>
          </div>
          <div>
            <div className="stat-label">After a 30% crash</div>
            <div className="stat-value">{formatINR(median(crash))}</div>
          </div>
          <div>
            <div className="stat-label">Goal success probability</div>
            <div className="stat-value">
              {crash.goal_outcomes[0]
                ? `${(crash.goal_outcomes[0].success_probability * 100).toFixed(0)}%`
                : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* TODO(member-6): allocation donut, health scorecard, what-if chat panel,
          scenario comparison table, assumption transparency panel. */}
      <h2>Still to build</h2>
      <div className="card todo">
        Allocation breakdown · Health scorecard · What-if chat · Scenario comparison ·
        Assumption transparency panel · Document upload &amp; confirmation
      </div>

      <Disclaimer assumptions={baseline.assumptions} />
    </main>
  );
}
