"use client";

/**
 * Statement import: upload a file or paste text, review what was found, confirm
 * what to use. The confirmation step lives in ExtractionReview.
 */

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentExtraction, FinancialProfile } from "@/lib/types";
import { ExtractionReview } from "./ExtractionReview";
import { Notice, Spinner } from "./ui";

const MAX_BYTES = 10 * 1024 * 1024;

// Plain lines the pattern extractor understands, so the flow can be tried without a file.
const EXAMPLE = `Monthly income: 125000
Monthly expenses: 72000
SIP amount: 20000
Closing balance: 310000
INFY 60 @ 1600
HDFCBANK 40 @ 1700`;

export function DocumentUpload({
  profile,
  onApplied,
}: {
  profile: FinancialProfile;
  onApplied: (profile: FinancialProfile, applied: number) => void;
}) {
  const [mode, setMode] = useState<"file" | "text">("file");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<{ id: number; data: DocumentExtraction } | null>(null);
  const [dragging, setDragging] = useState(false);
  const counter = useRef(0);

  async function extract(file: File) {
    if (file.size > MAX_BYTES) {
      setError("That file is larger than 10 MB.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = await api.extractDocument(file);
      setExtraction({ id: ++counter.current, data });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Couldn't read that document.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="import">
      <div className="seg" role="group" aria-label="Import method">
        <button type="button" aria-pressed={mode === "file"} onClick={() => setMode("file")}>
          Upload a file
        </button>
        <button type="button" aria-pressed={mode === "text"} onClick={() => setMode("text")}>
          Paste text
        </button>
      </div>

      {mode === "file" ? (
        <label
          className="dropzone"
          data-dragging={dragging || undefined}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const file = event.dataTransfer.files[0];
            if (file) void extract(file);
          }}
        >
          <input
            type="file"
            accept=".pdf,.csv,.txt,text/csv,text/plain,application/pdf"
            disabled={busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void extract(file);
              event.target.value = "";
            }}
          />
          <span className="dropzone__title">Drop a statement here, or choose a file</span>
          <span className="dropzone__hint">
            CSV holdings export, or a text-based PDF (up to 10 MB). Scanned PDFs need OCR, which
            isn&apos;t supported yet.
          </span>
        </label>
      ) : (
        <div className="paste">
          <label className="field field--block">
            <span>Statement text</span>
            <textarea
              rows={6}
              value={text}
              placeholder={EXAMPLE}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          <div className="review__actions">
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy || text.trim() === ""}
              onClick={() => void extract(new File([text], "pasted-text.txt", { type: "text/plain" }))}
            >
              Find values
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setText(EXAMPLE)}>
              Use an example
            </button>
          </div>
        </div>
      )}

      {busy && <Spinner label="Reading the document…" />}
      {error && <Notice tone="critical">{error}</Notice>}

      {extraction && (
        <ExtractionReview
          key={extraction.id}
          extraction={extraction.data}
          profile={profile}
          onApplied={(updated, applied) => {
            setExtraction(null);
            onApplied(updated, applied);
          }}
          onDiscard={() => setExtraction(null)}
        />
      )}
    </div>
  );
}
