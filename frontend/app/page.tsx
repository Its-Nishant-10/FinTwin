/**
 * Dashboard entry. OWNER: Member 6 (Frontend/Evaluation)
 *
 * Loads the first view on the server so the page arrives with data; everything
 * interactive after that is the client-side Dashboard.
 */

import { Dashboard, type DashboardData } from "@/components/Dashboard";
import { api } from "@/lib/api";
import { buildLabRequests, defaultLabOptions } from "@/lib/scenarios";

// Always rendered per request: the page needs the live backend, which doesn't
// exist at build time.
export const dynamic = "force-dynamic";

async function loadDashboard(): Promise<
  { ok: true; data: DashboardData } | { ok: false; error: string }
> {
  try {
    const profile = await api.sampleProfile();
    const labOptions = defaultLabOptions(profile);
    const [metrics, health, lab] = await Promise.all([
      api.analyzePortfolio(profile),
      api.healthScore(profile),
      api.compareScenarios(buildLabRequests(profile, labOptions)),
    ]);
    return { ok: true, data: { profile, metrics, health, lab, labOptions } };
  } catch (cause) {
    return { ok: false, error: cause instanceof Error ? cause.message : String(cause) };
  }
}

export default async function Home() {
  const result = await loadDashboard();

  if (!result.ok) {
    return (
      <main>
        <h1>FinTwin</h1>
        <p className="tagline">Explainable AI personal finance intelligence &amp; simulation</p>
        <div className="card">
          <p className="status-down">The dashboard couldn&apos;t load.</p>
          <p>{result.error}</p>
          <p className="todo">
            Start the backend with <code>make backend</code>, then reload this page.
          </p>
        </div>
      </main>
    );
  }

  return <Dashboard initial={result.data} />;
}
