/**
 * The single place the frontend talks to the backend.
 * OWNER: Member 6 (Frontend/Evaluation)
 *
 * Do not call fetch() directly from components — add a function here so error
 * handling and the base URL stay in one place.
 */

import type {
  AgentResponse,
  FinancialProfile,
  PortfolioMetrics,
  ScenarioResult,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${response.status}): ${detail}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  sampleProfile: () => request<FinancialProfile>("/profile/sample"),

  analyzePortfolio: (profile: FinancialProfile) =>
    request<PortfolioMetrics>("/portfolio/analyze", {
      method: "POST",
      body: JSON.stringify(profile),
    }),

  runScenario: (payload: Record<string, unknown>) =>
    request<ScenarioResult>("/scenario/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  ask: (question: string, profile: FinancialProfile) =>
    request<AgentResponse>("/agent/ask", {
      method: "POST",
      body: JSON.stringify({ question, profile }),
    }),
};

/** Indian-format currency, used everywhere a rupee amount is shown. */
export function formatINR(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}
