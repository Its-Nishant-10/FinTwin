"use client";

/**
 * The confirmation step for extracted values.
 *
 * Nothing extracted from a document reaches the profile until the user ticks it.
 * Every row starts unticked, values can be corrected first, and only ticked rows
 * are sent to /documents/confirm (which ignores the rest).
 */

import { useState } from "react";
import { api } from "@/lib/api";
import { formatINR, formatPct } from "@/lib/format";
import type { DocumentExtraction, ExtractedField, FinancialProfile } from "@/lib/types";
import { Notice, StatusBadge, type Tone } from "./ui";

const ASSET_CLASSES = ["equity", "debt", "gold", "cash", "real_estate", "crypto", "other"];

const SCALAR_LABELS: Record<string, string> = {
  "cashflow.monthly_income": "Monthly income",
  "cashflow.monthly_expenses": "Monthly expenses",
  "cashflow.monthly_contribution": "Monthly SIP",
  cash_balance: "Cash balance",
};

type Holding = Record<string, unknown> & { symbol: string };

const isHolding = (value: unknown): value is Holding =>
  typeof value === "object" &&
  value !== null &&
  typeof (value as { symbol?: unknown }).symbol === "string";

function confidence(value: number): { tone: Tone; label: string } {
  if (value >= 0.8) return { tone: "good", label: "High" };
  if (value >= 0.5) return { tone: "caution", label: "Medium" };
  return { tone: "critical", label: "Low" };
}

function fieldLabel(field: ExtractedField): string {
  if (field.field === "holding" && isHolding(field.value)) return `Holding: ${field.value.symbol}`;
  return SCALAR_LABELS[field.field] ?? field.field;
}

export function ExtractionReview({
  extraction,
  profile,
  onApplied,
  onDiscard,
}: {
  extraction: DocumentExtraction;
  profile: FinancialProfile;
  onApplied: (profile: FinancialProfile, applied: number) => void;
  onDiscard?: () => void;
}) {
  const [fields, setFields] = useState(extraction.fields);
  const [ticked, setTicked] = useState<boolean[]>(() => extraction.fields.map(() => false));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const count = ticked.filter(Boolean).length;

  const edit = (index: number, value: unknown) =>
    setFields((current) => current.map((f, i) => (i === index ? { ...f, value } : f)));
  const tick = (index: number, on: boolean) =>
    setTicked((current) => current.map((t, i) => (i === index ? on : t)));

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      const confirmed = fields.map((f, i) => ({ ...f, needs_confirmation: !ticked[i] }));
      const updated = await api.confirmExtraction(profile, confirmed);
      onApplied(updated, count);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Couldn't apply those values.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="review">
      <div className="review__head">
        <div>
          <strong>{extraction.filename}</strong>{" "}
          <StatusBadge tone="neutral">{extraction.doc_type.replace(/_/g, " ")}</StatusBadge>
        </div>
        <span className="review__hint">
          {fields.length} proposed {fields.length === 1 ? "value" : "values"} — tick the ones you
          confirm
        </span>
      </div>

      {extraction.warnings.map((warning) => (
        <Notice key={warning} tone="caution">
          {warning}
        </Notice>
      ))}

      {fields.length === 0 ? (
        <Notice tone="info">Nothing usable was found in this document.</Notice>
      ) : (
        <>
          <div className="review__actions">
            <button type="button" className="btn btn--ghost" onClick={() => setTicked(fields.map(() => true))}>
              Select all
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setTicked(fields.map((f) => f.confidence >= 0.8))}
            >
              Select high confidence only
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setTicked(fields.map(() => false))}>
              Clear
            </button>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <caption className="sr-only">Values proposed from {extraction.filename}</caption>
              <thead>
                <tr>
                  <th scope="col">Use</th>
                  <th scope="col">Field</th>
                  <th scope="col">Proposed value</th>
                  <th scope="col">Confidence</th>
                  <th scope="col">Source</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((field, index) => {
                  const level = confidence(field.confidence);
                  return (
                    <tr key={`${field.field}-${index}`} data-active={ticked[index] || undefined}>
                      <td>
                        <input
                          type="checkbox"
                          checked={ticked[index]}
                          onChange={(event) => tick(index, event.target.checked)}
                          aria-label={`Confirm ${fieldLabel(field)}`}
                        />
                      </td>
                      <th scope="row">{fieldLabel(field)}</th>
                      <td>
                        {isHolding(field.value) ? (
                          <HoldingEditor holding={field.value} onChange={(v) => edit(index, v)} />
                        ) : (
                          <input
                            className="input input--num"
                            type="number"
                            min={0}
                            step="any"
                            value={typeof field.value === "number" ? field.value : String(field.value ?? "")}
                            onChange={(event) =>
                              edit(index, event.target.value === "" ? "" : Number(event.target.value))
                            }
                            aria-label={`${fieldLabel(field)} in rupees`}
                          />
                        )}
                      </td>
                      <td>
                        <StatusBadge tone={level.tone}>
                          {level.label} · {formatPct(field.confidence)}
                        </StatusBadge>
                      </td>
                      <td>{field.source_page != null ? `Row/page ${field.source_page}` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {error && <Notice tone="critical">{error}</Notice>}

      <div className="review__foot">
        <button type="button" className="btn btn--primary" disabled={count === 0 || busy} onClick={apply}>
          {busy ? "Applying…" : `Apply ${count} confirmed ${count === 1 ? "value" : "values"}`}
        </button>
        {onDiscard && (
          <button type="button" className="btn btn--ghost" onClick={onDiscard} disabled={busy}>
            Discard
          </button>
        )}
        <span className="review__hint">Applied to this session only — nothing is saved.</span>
      </div>
    </div>
  );
}

function HoldingEditor({
  holding,
  onChange,
}: {
  holding: Holding;
  onChange: (holding: Holding) => void;
}) {
  const set = (key: string, value: unknown) => onChange({ ...holding, [key]: value });
  const quantity = Number(holding.quantity ?? 0);
  const price = Number(holding.current_price ?? 0);
  return (
    <div className="holding-editor">
      <label>
        <span>Qty</span>
        <input
          className="input input--num"
          type="number"
          min={0}
          step="any"
          value={quantity}
          onChange={(event) => set("quantity", Number(event.target.value))}
        />
      </label>
      <label>
        <span>Price ₹</span>
        <input
          className="input input--num"
          type="number"
          min={0}
          step="any"
          value={price}
          onChange={(event) => set("current_price", Number(event.target.value))}
        />
      </label>
      <label>
        <span>Class</span>
        <select
          className="input"
          value={String(holding.asset_class ?? "equity")}
          onChange={(event) => set("asset_class", event.target.value)}
        >
          {ASSET_CLASSES.map((asset) => (
            <option key={asset} value={asset}>
              {asset.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </label>
      <span className="holding-editor__value">= {formatINR(quantity * price)}</span>
    </div>
  );
}
