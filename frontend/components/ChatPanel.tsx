"use client";

/**
 * What-if chat. The model picks tools and writes the explanation; the numbers,
 * charts and tables beside it come straight from the tools' own output.
 *
 * The "How FinTwin answered" panel is the evidence view: which tools ran, with
 * what arguments, what they returned, and what sources backed the explanation.
 */

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { formatLatency } from "@/lib/format";
import { CHAT_SUGGESTIONS } from "@/lib/scenarios";
import {
  extractionFrom,
  healthFrom,
  portfolioFrom,
  scenarioFrom,
  toolLabel,
} from "@/lib/tool-results";
import type { AgentResponse, FinancialProfile, ToolResult } from "@/lib/types";
import { AllocationChart } from "./AllocationChart";
import { AssumptionsPanel } from "./Disclaimer";
import { ExtractionReview } from "./ExtractionReview";
import { HealthScorecard } from "./HealthScorecard";
import { PortfolioRisk } from "./PortfolioRisk";
import { ScenarioExplorer } from "./ScenarioExplorer";
import { Notice, Spinner, StatusBadge } from "./ui";

type MessageBody =
  | { role: "user"; text: string }
  | { role: "assistant"; response: AgentResponse }
  | { role: "error"; text: string };

type Message = MessageBody & { id: number };

function ToolVisual({
  result,
  profile,
  onApplied,
}: {
  result: ToolResult;
  profile: FinancialProfile;
  onApplied: (profile: FinancialProfile, applied: number) => void;
}) {
  const scenario = scenarioFrom(result);
  if (scenario) return <ScenarioExplorer comparison={scenario} />;

  const portfolio = portfolioFrom(result);
  if (portfolio) {
    return (
      <>
        <AllocationChart metrics={portfolio} />
        <PortfolioRisk metrics={portfolio} profile={profile} />
      </>
    );
  }

  const health = healthFrom(result);
  if (health) return <HealthScorecard health={health} />;

  const extraction = extractionFrom(result);
  if (extraction) {
    return (
      <ExtractionReview extraction={extraction} profile={profile} onApplied={onApplied} />
    );
  }
  return null;
}

function EvidencePanel({ response, open }: { response: AgentResponse; open: boolean }) {
  const { answer, tool_calls: calls, tool_results: results } = response;
  const sources = [...answer.evidence, ...response.evidence].filter(
    (item, index, all) => all.findIndex((other) => other.claim === item.claim && other.source === item.source) === index,
  );

  return (
    <details className="trace" open={open}>
      <summary>
        How FinTwin answered
        <span className="trace__meta">
          {calls.length} {calls.length === 1 ? "tool" : "tools"}
          {response.latency_ms != null && ` · ${formatLatency(response.latency_ms)}`}
        </span>
      </summary>

      {calls.length === 0 ? (
        <p className="trace__empty">No tool matched this question, so nothing was computed.</p>
      ) : (
        <ol className="trace__steps">
          {calls.map((call, index) => {
            const result = results[index];
            return (
              <li key={`${call.tool}-${index}`}>
                <div className="trace__step-head">
                  <strong>{toolLabel(call.tool)}</strong>
                  <code>{call.tool}</code>
                  {result &&
                    (result.ok ? (
                      <StatusBadge tone="good">Ran</StatusBadge>
                    ) : (
                      <StatusBadge tone="critical">Failed</StatusBadge>
                    ))}
                  {result?.latency_ms != null && (
                    <span className="trace__latency">{formatLatency(result.latency_ms)}</span>
                  )}
                </div>
                {Object.keys(call.arguments).length > 0 && (
                  <div className="chips">
                    {Object.entries(call.arguments).map(([key, value]) => (
                      <span key={key} className="chip">
                        {key} = {typeof value === "object" ? JSON.stringify(value) : String(value)}
                      </span>
                    ))}
                  </div>
                )}
                {call.reasoning && <p className="trace__reason">{call.reasoning}</p>}
                {result && !result.ok && <p className="trace__error">{result.error}</p>}
              </li>
            );
          })}
        </ol>
      )}

      <p className="trace__note">
        Every figure in the answer above comes from these tool results. The language model chooses
        the tools and writes the explanation; it does not calculate.
      </p>

      {sources.length > 0 && (
        <div className="trace__sources">
          <h5>Sources</h5>
          <ul>
            {sources.map((item) => (
              <li key={`${item.source}-${item.claim}`}>
                <span className="source__name">{item.source}</span>
                <span>{item.snippet ?? item.claim}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="trace__raw">
        <summary>Computed figures (raw tool output)</summary>
        <pre>{JSON.stringify(answer.numbers, null, 2)}</pre>
      </details>
    </details>
  );
}

export function ChatPanel({
  profile,
  onApplied,
}: {
  profile: FinancialProfile;
  onApplied: (profile: FinancialProfile, applied: number) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const nextId = useRef(1);
  const controller = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => controller.current?.abort(), []);

  useEffect(() => {
    if (messages.length === 0) return;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    endRef.current?.scrollIntoView({ block: "nearest", behavior: calm ? "auto" : "smooth" });
  }, [messages.length]);

  const push = (body: MessageBody) =>
    setMessages((current) => [...current, { ...body, id: nextId.current++ }]);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    push({ role: "user", text: trimmed });
    setQuestion("");
    setPending(true);
    controller.current = new AbortController();
    try {
      push({
        role: "assistant",
        response: await api.ask(trimmed, profile, controller.current.signal),
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      push({
        role: "error",
        text: cause instanceof Error ? cause.message : "Something went wrong asking that.",
      });
    } finally {
      setPending(false);
    }
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant")?.id;

  return (
    <div className="chat">
      {messages.length === 0 && (
        <div className="chat__intro">
          <p>
            Ask a what-if in plain language. FinTwin picks the right calculation, runs it on your
            twin, and explains the result — with the assumptions and the evidence alongside.
          </p>
          <div className="chips chips--buttons">
            {CHAT_SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="chip chip--button"
                onClick={() => void ask(suggestion)}
                disabled={pending}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      <ol className="chat__log">
        {messages.map((message) => (
          <li key={message.id} className="message" data-role={message.role}>
            {message.role === "user" && <p className="message__text">{message.text}</p>}

            {message.role === "error" && <Notice tone="critical">{message.text}</Notice>}

            {message.role === "assistant" && (
              <div className="answer">
                <p className="message__text">{message.response.answer.summary}</p>

                {message.response.tool_results.map((result, index) => (
                  <ToolVisual
                    key={`${result.tool}-${index}`}
                    result={result}
                    profile={profile}
                    onApplied={onApplied}
                  />
                ))}

                {message.response.answer.assumptions &&
                  !message.response.tool_results.some((r) => scenarioFrom(r)) && (
                    <AssumptionsPanel assumptions={message.response.answer.assumptions} />
                  )}

                {message.response.answer.caveats.map((caveat) => (
                  <Notice key={caveat} tone="info">
                    {caveat}
                  </Notice>
                ))}

                <EvidencePanel response={message.response} open={message.id === lastAssistant} />
              </div>
            )}
          </li>
        ))}
      </ol>
      <div ref={endRef} />

      <div className="sr-only" role="status" aria-live="polite">
        {pending ? "FinTwin is working on your question." : messages.length > 0 ? "Answer ready." : ""}
      </div>
      {pending && <Spinner label="Running the numbers…" />}

      <form
        className="chat__form"
        onSubmit={(event) => {
          event.preventDefault();
          void ask(question);
        }}
      >
        <label className="sr-only" htmlFor="chat-question">
          Ask a what-if question
        </label>
        <input
          id="chat-question"
          className="input chat__input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="e.g. What if I stop my SIP for six months?"
          autoComplete="off"
        />
        <button type="submit" className="btn btn--primary" disabled={pending || question.trim() === ""}>
          Ask
        </button>
      </form>

      {messages.length > 0 && (
        <div className="chips chips--buttons chat__more">
          {CHAT_SUGGESTIONS.slice(0, 4).map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="chip chip--button"
              onClick={() => void ask(suggestion)}
              disabled={pending}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
