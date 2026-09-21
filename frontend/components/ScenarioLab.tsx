"use client";

/**
 * Scenario Lab: the demo script's what-ifs, run side by side against the current
 * plan. One filter row (horizon, market model) scopes everything beneath it.
 * While a re-run is in flight the previous result stays on screen, dimmed, so
 * the layout never jumps.
 */

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { formatMonths } from "@/lib/format";
import {
  buildLabRequests,
  horizonChoices,
  type LabOptions,
  type MarketModel,
} from "@/lib/scenarios";
import type { FinancialProfile, ScenarioComparison } from "@/lib/types";
import { ScenarioExplorer } from "./ScenarioExplorer";
import { Notice, Spinner } from "./ui";

export function ScenarioLab({
  profile,
  profileVersion,
  initial,
  initialOptions,
}: {
  profile: FinancialProfile;
  /** Bumped whenever the profile is replaced, so the lab knows to re-run. */
  profileVersion: number;
  initial: ScenarioComparison;
  initialOptions: LabOptions;
}) {
  const [options, setOptions] = useState(initialOptions);
  const [comparison, setComparison] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  const key = `${profileVersion}|${options.horizonMonths}|${options.model}|${retry}`;
  // The key of the data on screen. Starts as the first render's key, because the
  // server already ran that comparison.
  const loadedKey = useRef(key);

  useEffect(() => {
    if (loadedKey.current === key) {
      setBusy(false);
      return;
    }
    const controller = new AbortController();
    setBusy(true);
    setError(null);
    api
      .compareScenarios(buildLabRequests(profile, options), controller.signal)
      .then((next) => {
        loadedKey.current = key;
        setComparison(next);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "The simulation failed.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [key, profile, options]);

  return (
    <div className="lab">
      <div className="filters">
        <label className="field">
          <span>Horizon</span>
          <select
            value={options.horizonMonths}
            onChange={(event) =>
              setOptions({ ...options, horizonMonths: Number(event.target.value) })
            }
          >
            {horizonChoices(profile).map((months) => (
              <option key={months} value={months}>
                {formatMonths(months)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Market model</span>
          <select
            value={options.model}
            onChange={(event) => setOptions({ ...options, model: event.target.value as MarketModel })}
          >
            <option value="gbm">Normal returns</option>
            <option value="student_t">Fat-tailed returns</option>
          </select>
        </label>
        {busy && <Spinner label="Re-running simulation…" />}
      </div>

      {error && (
        <Notice
          tone="critical"
          action={
            <button type="button" className="btn btn--ghost" onClick={() => setRetry((n) => n + 1)}>
              Try again
            </button>
          }
        >
          {error}
        </Notice>
      )}

      <div className={busy ? "refetching is-busy" : "refetching"} aria-busy={busy}>
        <ScenarioExplorer comparison={comparison} />
      </div>
    </div>
  );
}
