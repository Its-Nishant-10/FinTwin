"use client";

/**
 * The dashboard shell. Owns the one piece of shared state: the current profile
 * (the twin) and the numbers derived from it. When an import is confirmed, or
 * the demo profile is restored, everything downstream is re-derived from the
 * backend before the new profile is shown, so the page never mixes old numbers
 * with a new twin.
 */

import { useState } from "react";
import { api } from "@/lib/api";
import type { LabOptions } from "@/lib/scenarios";
import type {
  FinancialProfile,
  HealthScore,
  PortfolioMetrics,
  ScenarioComparison,
} from "@/lib/types";
import { AllocationChart } from "./AllocationChart";
import { ChatPanel } from "./ChatPanel";
import { Disclaimer } from "./Disclaimer";
import { DocumentUpload } from "./DocumentUpload";
import { HealthScorecard } from "./HealthScorecard";
import { PortfolioRisk } from "./PortfolioRisk";
import { ScenarioLab } from "./ScenarioLab";
import { TwinSummary } from "./TwinSummary";
import { Notice, Spinner, StatusBadge } from "./ui";

export interface DashboardData {
  profile: FinancialProfile;
  metrics: PortfolioMetrics;
  health: HealthScore;
  lab: ScenarioComparison;
  labOptions: LabOptions;
}

interface Twin {
  profile: FinancialProfile;
  metrics: PortfolioMetrics;
  health: HealthScore;
  /** Bumped on every replacement so the lab knows to re-run. */
  version: number;
  imported: boolean;
}

const SECTIONS = [
  { id: "twin", label: "Twin" },
  { id: "portfolio", label: "Portfolio" },
  { id: "scenarios", label: "Scenarios" },
  { id: "ask", label: "Ask" },
  { id: "import", label: "Import" },
];

export function Dashboard({ initial }: { initial: DashboardData }) {
  const [twin, setTwin] = useState<Twin>({
    profile: initial.profile,
    metrics: initial.metrics,
    health: initial.health,
    version: 0,
    imported: false,
  });
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function replaceProfile(next: FinancialProfile, imported: boolean, message: string) {
    setRefreshing(true);
    setError(null);
    setNotice(null);
    try {
      const [metrics, health] = await Promise.all([
        api.analyzePortfolio(next),
        api.healthScore(next),
      ]);
      setTwin((current) => ({
        profile: next,
        metrics,
        health,
        version: current.version + 1,
        imported,
      }));
      setNotice(message);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? `Couldn't update the twin: ${cause.message}`
          : "Couldn't update the twin.",
      );
    } finally {
      setRefreshing(false);
    }
  }

  const onApplied = (profile: FinancialProfile, applied: number) =>
    replaceProfile(
      profile,
      true,
      `Applied ${applied} confirmed ${applied === 1 ? "value" : "values"}. The allocation, health score and scenarios below now use your updated twin.`,
    );

  async function restoreDemo() {
    try {
      await replaceProfile(await api.sampleProfile(), false, "Back on the demo profile.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Couldn't load the demo profile.");
    }
  }

  const { profile, metrics, health } = twin;

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="masthead">
        <div>
          <h1>FinTwin</h1>
          <p className="tagline">Explainable AI personal finance intelligence &amp; simulation</p>
        </div>
        <div className="masthead__status">
          <StatusBadge tone={twin.imported ? "caution" : "good"}>
            {twin.imported ? "Imported values applied" : "Demo profile"}
          </StatusBadge>
          {twin.imported && (
            <button type="button" className="btn btn--ghost" onClick={restoreDemo} disabled={refreshing}>
              Back to demo profile
            </button>
          )}
        </div>
      </header>

      <nav className="sectionnav" aria-label="Sections">
        {SECTIONS.map(({ id, label }) => (
          <a key={id} href={`#${id}`}>
            {label}
          </a>
        ))}
      </nav>

      <main id="main" className={refreshing ? "refetching is-busy" : "refetching"} aria-busy={refreshing}>
        {refreshing && <Spinner label="Updating your twin…" />}
        {error && <Notice tone="critical">{error}</Notice>}
        {notice && <Notice tone="good">{notice}</Notice>}

        <section id="twin" aria-labelledby="twin-title">
          <h2 id="twin-title">Your digital twin</h2>
          <TwinSummary profile={profile} health={health} />
        </section>

        <section id="portfolio" aria-labelledby="portfolio-title">
          <h2 id="portfolio-title">Portfolio and health</h2>
          <div className="grid-2">
            <div className="card">
              <h3>Allocation</h3>
              <AllocationChart metrics={metrics} />
            </div>
            <div className="card">
              <h3>Financial health</h3>
              <HealthScorecard health={health} />
            </div>
          </div>
          <div className="card">
            <h3>Concentration and risk</h3>
            <PortfolioRisk metrics={metrics} profile={profile} />
          </div>
        </section>

        <section id="scenarios" aria-labelledby="scenarios-title">
          <h2 id="scenarios-title">Scenario lab</h2>
          <p className="lede">
            Each what-if is simulated thousands of times against your current plan. Pick a row to
            see its range of outcomes, and what is driving any gap to your goal.
          </p>
          <div className="card">
            <ScenarioLab
              profile={profile}
              profileVersion={twin.version}
              initial={initial.lab}
              initialOptions={initial.labOptions}
            />
          </div>
        </section>

        <section id="ask" aria-labelledby="ask-title">
          <h2 id="ask-title">Ask FinTwin</h2>
          <div className="card">
            <ChatPanel profile={profile} onApplied={onApplied} />
          </div>
        </section>

        <section id="import" aria-labelledby="import-title">
          <h2 id="import-title">Import a statement</h2>
          <p className="lede">
            Values found in a document are only proposals. Nothing reaches your twin until you
            confirm it.
          </p>
          <div className="card">
            <DocumentUpload profile={profile} onApplied={onApplied} />
          </div>
        </section>

        <Disclaimer />
      </main>
    </>
  );
}
