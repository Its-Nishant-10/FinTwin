/**
 * The single place the frontend talks to the backend.
 * OWNER: Member 6 (Frontend/Evaluation)
 *
 * Do not call fetch() directly from components — add a function here so error
 * handling and the base URL stay in one place.
 */

import type {
  AgentResponse,
  DocumentExtraction,
  ExtractedField,
  FinancialProfile,
  HealthScore,
  PortfolioMetrics,
  ScenarioComparison,
  ScenarioRequest,
  ScenarioResult,
} from "./types";

export { formatINR } from "./format";

export const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** A failed API call, with FastAPI's `detail` already turned into readable text. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** FastAPI sends a string for HTTPException and a list of {loc, msg} for validation errors. */
function readDetail(body: string): string {
  try {
    const parsed: unknown = JSON.parse(body);
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      const detail = (parsed as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail
          .map((item) => {
            const entry = item as { loc?: unknown[]; msg?: string };
            const where = entry.loc?.filter((part) => part !== "body").join(".");
            return where ? `${where}: ${entry.msg}` : (entry.msg ?? "invalid input");
          })
          .join("; ");
      }
    }
  } catch {
    // not JSON — fall through to the raw text
  }
  return body.trim().slice(0, 300) || "no details returned";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // FormData needs the browser to set its own multipart boundary header.
  const isJson = typeof init.body === "string";
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      cache: "no-store",
      ...init,
      headers: { ...(isJson ? { "Content-Type": "application/json" } : {}), ...init.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(`Can't reach the FinTwin API at ${BASE_URL}. Is the backend running?`, 0);
  }

  if (!response.ok) {
    throw new ApiError(readDetail(await response.text()), response.status);
  }
  return response.json() as Promise<T>;
}

function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body), signal });
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  sampleProfile: () => request<FinancialProfile>("/profile/sample"),

  analyzePortfolio: (profile: FinancialProfile, signal?: AbortSignal) =>
    post<PortfolioMetrics>("/portfolio/analyze", profile, signal),

  healthScore: (profile: FinancialProfile, signal?: AbortSignal) =>
    post<HealthScore>("/portfolio/health-score", profile, signal),

  runScenario: (payload: ScenarioRequest, signal?: AbortSignal) =>
    post<ScenarioResult>("/scenario/run", payload, signal),

  /** One scenario plus an automatically built baseline under identical assumptions. */
  whatIf: (payload: ScenarioRequest, signal?: AbortSignal) =>
    post<ScenarioComparison>("/scenario/whatif", payload, signal),

  /** First request is the baseline; every other request is an alternative to it. */
  compareScenarios: (requests: ScenarioRequest[], signal?: AbortSignal) =>
    post<ScenarioComparison>("/scenario/compare", requests, signal),

  extractDocument: (file: File, signal?: AbortSignal) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentExtraction>("/documents/extract", {
      method: "POST",
      body: form,
      signal,
    });
  },

  /** Applies only the fields whose needs_confirmation is false. Does not save anything. */
  confirmExtraction: (profile: FinancialProfile, fields: ExtractedField[]) =>
    post<FinancialProfile>("/documents/confirm", { profile, fields }),

  ask: (question: string, profile: FinancialProfile, signal?: AbortSignal) =>
    post<AgentResponse>("/agent/ask", { question, profile }, signal),
};
