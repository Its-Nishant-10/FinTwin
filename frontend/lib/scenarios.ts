/**
 * The Scenario Lab's fixed set of what-ifs, taken from the demo script.
 *
 * All of them share one horizon, one market assumption and one simulation
 * setting, because /scenario/compare only accepts alternatives that differ from
 * the baseline in the perturbation alone. Allocation changes are left to the
 * chat: their return and volatility are derived per side, so they can't share a
 * hand-typed baseline here.
 */

import type { FinancialProfile, ScenarioRequest } from "./types";

export type MarketModel = "gbm" | "student_t";

export interface LabOptions {
  horizonMonths: number;
  model: MarketModel;
}

/** Same defaults the backend applies; sent explicitly so every request agrees. */
const EXPECTED_ANNUAL_RETURN = 0.12;
const ANNUAL_VOLATILITY = 0.18;
const SIP_INCREASE = 5_000;

const HORIZON_CHOICES = [24, 36, 60, 84, 120, 180];

/** The user's longest goal, or five years — the same rule the agent uses. */
export function defaultHorizon(profile: FinancialProfile): number {
  return Math.max(60, ...profile.goals.map((goal) => goal.horizon_months));
}

export function horizonChoices(profile: FinancialProfile): number[] {
  return [...new Set([...HORIZON_CHOICES, defaultHorizon(profile)])].sort((a, b) => a - b);
}

export function defaultLabOptions(profile: FinancialProfile): LabOptions {
  return { horizonMonths: defaultHorizon(profile), model: "gbm" };
}

/** Baseline first, then each alternative — the order /scenario/compare expects. */
export function buildLabRequests(
  profile: FinancialProfile,
  { horizonMonths, model }: LabOptions,
): ScenarioRequest[] {
  const shared = {
    profile,
    horizon_months: horizonMonths,
    expected_annual_return: EXPECTED_ANNUAL_RETURN,
    annual_volatility: ANNUAL_VOLATILITY,
    settings: { return_model: model },
  };
  const sip = profile.cashflow.monthly_contribution;

  return [
    { ...shared, scenario_type: "baseline" },
    {
      ...shared,
      scenario_type: "market_stress",
      market_stress: { shock_pct: -0.3, shock_at_month: 0 },
    },
    {
      ...shared,
      scenario_type: "market_stress",
      market_stress: { shock_pct: -0.3, shock_at_month: 0, recovery_months: 12 },
    },
    {
      ...shared,
      scenario_type: "sip_interruption",
      contribution_change: { pause_months: 6 },
    },
    {
      ...shared,
      scenario_type: "contribution_change",
      contribution_change: { new_monthly_contribution: sip + SIP_INCREASE },
    },
    {
      ...shared,
      scenario_type: "income_shock",
      income_shock: { income_multiplier: 0, duration_months: 6 },
    },
  ];
}

export const CHAT_SUGGESTIONS = [
  "What happens if the market falls 30%?",
  "What if I stop my SIP for six months?",
  "What if my income drops for six months?",
  "Am I on track for my goal?",
  "What if I move to 60% equity and 40% debt?",
  "How am I doing financially?",
];
