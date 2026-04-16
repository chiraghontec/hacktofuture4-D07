"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  type ApprovalResponse,
  type ChatStreamEvent,
  type IncidentReport,
  type IngestConfluenceResponse,
  type IngestIrisResponse,
  type TraceStep,
  type TranscriptResponse,
  getTranscript,
  ingestConfluence,
  ingestIris,
  streamChat,
  submitApproval,
} from "@/lib/chat-api";

const STRICT_LLM_PROVIDER = "groq";

function parsePageIds(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[\s,]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function errorToMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected request failure.";
}

function providerPolicyViolation(event: ChatStreamEvent): string | null {
  if (event.event_type !== "trace_step") {
    return null;
  }

  const stepName = String(event.step ?? "").toLowerCase();
  if (stepName === "reasoning" || stepName === "execution") {
    const provider = String(event.metadata?.provider ?? "").trim().toLowerCase();
    const model = String(event.metadata?.model ?? "").trim().toLowerCase();

    if (!provider) {
      return `Missing provider metadata on ${stepName} step. Expected ${STRICT_LLM_PROVIDER}.`;
    }

    if (provider === "deterministic" || model === "heuristic") {
      return `Invalid deterministic metadata detected on ${stepName} step.`;
    }

    if (provider !== STRICT_LLM_PROVIDER) {
      return `Unexpected provider '${provider}' on ${stepName} step. Expected ${STRICT_LLM_PROVIDER}.`;
    }
  }

  if (stepName === "retrieval") {
    const expansionProvider = String(event.metadata?.llm_query_expansion?.provider ?? "").trim().toLowerCase();
    if (expansionProvider && expansionProvider !== STRICT_LLM_PROVIDER) {
      return `Unexpected retrieval expansion provider '${expansionProvider}'. Expected ${STRICT_LLM_PROVIDER}.`;
    }
  }

  return null;
}

export default function Home() {
  const navItems = ["Overview", "Trace", "Approvals", "Runbooks"];
  const [sessionId] = useState<string>(() => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return `sess-${Date.now()}`;
  });

  const [message, setMessage] = useState<string>(
    "Create rollback PR and notify Slack and Jira for redis latency incident",
  );
  const [confluencePageIds, setConfluencePageIds] = useState<string>("65868,65898");
  const [irisCaseId, setIrisCaseId] = useState<string>("1");
  const [useIrisContextForChat, setUseIrisContextForChat] = useState<boolean>(false);
  const [approverId, setApproverId] = useState<string>("demo-approver");
  const [approvalComment, setApprovalComment] = useState<string>("Approved from frontend demo flow.");

  const [traceId, setTraceId] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string>("");
  const [needsApproval, setNeedsApproval] = useState<boolean>(false);
  const [streamStatus, setStreamStatus] = useState<string>("idle");
  const [traceSteps, setTraceSteps] = useState<TraceStep[]>([]);
  const [transcript, setTranscript] = useState<TranscriptResponse | null>(null);
  const [confluenceResult, setConfluenceResult] = useState<IngestConfluenceResponse | null>(null);
  const [irisResult, setIrisResult] = useState<IngestIrisResponse | null>(null);
  const [approvalResult, setApprovalResult] = useState<ApprovalResponse | null>(null);

  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [confluenceLoading, setConfluenceLoading] = useState<boolean>(false);
  const [irisLoading, setIrisLoading] = useState<boolean>(false);
  const [approvalLoading, setApprovalLoading] = useState<boolean>(false);
  const [transcriptLoading, setTranscriptLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const streamAbortRef = useRef<AbortController | null>(null);
  const seenEventIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
    };
  }, []);

  function stepFromStreamEvent(event: ChatStreamEvent): TraceStep {
    const metadata = {
      ...(event.metadata ?? {}),
      stream_sequence: event.sequence,
    };
    return {
      step: event.step ?? "unknown",
      agent: event.agent ?? "unknown_agent",
      observation: event.observation ?? "",
      sources: event.sources ?? [],
      metadata,
      timestamp: event.timestamp,
    };
  }

  function formatTimestamp(value?: string): string {
    if (!value) {
      return "n/a";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return parsed.toLocaleString();
  }

  async function refreshTranscript(activeTraceId: string): Promise<void> {
    setTranscriptLoading(true);
    try {
      const result = await getTranscript(activeTraceId);
      setTranscript(result);
      setTraceSteps(result.steps);
      if (result.final_status) {
        setNeedsApproval(false);
      }
    } finally {
      setTranscriptLoading(false);
    }
  }

  async function handleConfluenceIngest(): Promise<void> {
    const pageIds = parsePageIds(confluencePageIds);
    if (pageIds.length === 0) {
      setErrorMessage("Provide at least one Confluence page ID.");
      return;
    }

    setErrorMessage(null);
    setConfluenceLoading(true);
    try {
      const result = await ingestConfluence(pageIds);
      setConfluenceResult(result);
    } catch (error: unknown) {
      setErrorMessage(errorToMessage(error));
    } finally {
      setConfluenceLoading(false);
    }
  }

  async function handleIrisIngest(): Promise<void> {
    const caseId = irisCaseId.trim();
    if (!caseId) {
      setErrorMessage("Provide an IRIS case ID before ingesting.");
      return;
    }

    setErrorMessage(null);
    setIrisLoading(true);
    try {
      const result = await ingestIris(caseId);
      setIrisResult(result);
    } catch (error: unknown) {
      setErrorMessage(errorToMessage(error));
    } finally {
      setIrisLoading(false);
    }
  }

  async function handleChatSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const hasIrisContext = useIrisContextForChat && Boolean(irisResult?.incident_report);
    if (!hasIrisContext && !message.trim()) {
      setErrorMessage("Enter an incident prompt before starting the session.");
      return;
    }
    if (useIrisContextForChat && !irisResult?.incident_report) {
      setErrorMessage("Ingest an IRIS case first before using incident_report chat mode.");
      return;
    }

    setErrorMessage(null);
    setChatLoading(true);
    setStreamStatus("idle");
    setTraceSteps([]);
    setTranscript(null);
    setApprovalResult(null);
    setTraceId(null);
    setAnswer("");

    streamAbortRef.current?.abort();
    const abortController = new AbortController();
    streamAbortRef.current = abortController;
    seenEventIdsRef.current = new Set();

    let terminalErrorMessage: string | null = null;

    try {
      let completedTraceId: string | null = null;

      setStreamStatus("connecting");
      const payload: {
        message?: string;
        session_id: string;
        incident_report?: IncidentReport;
      } = {
        session_id: sessionId,
      };

      if (!hasIrisContext) {
        payload.message = message.trim();
      }

      if (hasIrisContext && irisResult?.incident_report) {
        payload.incident_report = irisResult.incident_report;
      }

      await streamChat(
        payload,
        {
          signal: abortController.signal,
          onEvent: (streamEvent) => {
            if (seenEventIdsRef.current.has(streamEvent.event_id)) {
              return;
            }
            seenEventIdsRef.current.add(streamEvent.event_id);

            if (streamEvent.trace_id && streamEvent.trace_id !== "trace-pending") {
              setTraceId(streamEvent.trace_id);
            }

            if (streamEvent.event_type === "trace_started") {
              setStreamStatus("streaming");
              return;
            }

            if (streamEvent.event_type === "trace_heartbeat") {
              setStreamStatus("heartbeat");
              return;
            }

            if (streamEvent.event_type === "trace_step") {
              const providerViolation = providerPolicyViolation(streamEvent);
              if (providerViolation) {
                terminalErrorMessage = providerViolation;
                setStreamStatus("error");
                abortController.abort();
                return;
              }

              setStreamStatus("streaming");
              setTraceSteps((previous) => [...previous, stepFromStreamEvent(streamEvent)]);
              return;
            }

            if (streamEvent.event_type === "trace_complete") {
              completedTraceId = streamEvent.trace_id;
              setAnswer(streamEvent.answer ?? "");
              setNeedsApproval(Boolean(streamEvent.needs_approval));
              setStreamStatus("complete");
              return;
            }

            if (streamEvent.event_type === "trace_error") {
              terminalErrorMessage = streamEvent.error ?? "Streaming failed.";
              setStreamStatus("error");
            }
          },
        },
      );

      if (terminalErrorMessage) {
        setErrorMessage(terminalErrorMessage);
      }

      if (completedTraceId) {
        await refreshTranscript(completedTraceId);
      }
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") {
        if (terminalErrorMessage) {
          setErrorMessage(terminalErrorMessage);
          setStreamStatus("error");
        } else {
          setStreamStatus("aborted");
        }
        return;
      }
      setErrorMessage(errorToMessage(error));
      setStreamStatus("error");
    } finally {
      setChatLoading(false);
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null;
      }
    }
  }

  async function handleApproval(decision: "approve" | "reject"): Promise<void> {
    if (!traceId) {
      setErrorMessage("Start a chat trace before submitting approval.");
      return;
    }

    setErrorMessage(null);
    setApprovalLoading(true);
    try {
      const result = await submitApproval(traceId, {
        decision,
        approver_id: approverId.trim() || "demo-approver",
        comment: approvalComment.trim() || undefined,
      });
      setApprovalResult(result);
      setNeedsApproval(false);
      await refreshTranscript(traceId);
    } catch (error: unknown) {
      setErrorMessage(errorToMessage(error));
    } finally {
      setApprovalLoading(false);
    }
  }

  async function handleTranscriptRefresh(): Promise<void> {
    if (!traceId) {
      setErrorMessage("No active trace yet. Start with a chat request.");
      return;
    }

    setErrorMessage(null);
    try {
      await refreshTranscript(traceId);
    } catch (error: unknown) {
      setErrorMessage(errorToMessage(error));
    }
  }

  return (
    <div className="app-shell">
      <header className="top-nav">
        <div className="brand-wrap">
          <h1 className="brand-name title-highlight">UniOps</h1>
        </div>
        <nav className="nav-links" aria-label="Primary">
          {navItems.map((item) => (
            <button key={item} type="button" className="nav-link">
              {item}
            </button>
          ))}
        </nav>
      </header>

      <main className="dashboard-grid">
        <section className="panel hero-panel">
          <p className="kicker">Ops Copilot Workspace</p>
          <h2 className="hero-title">
            Observe, reason, and act with <span className="title-highlight">human control</span>
          </h2>
          <p className="hero-copy">
            Run the full demo from this page: ingest Confluence and IRIS context, generate trace-guided reasoning,
            and complete the human approval path with persisted transcript evidence.
          </p>
          <p className="response-meta">Chat now runs as live POST SSE stream against /api/chat.</p>
          <p className="response-meta">Strict provider mode: reasoning and execution must report provider={STRICT_LLM_PROVIDER}.</p>

          <form className="chat-form" onSubmit={handleChatSubmit}>
            <label className="chat-label" htmlFor="chat-message">
              Incident Prompt
            </label>
            <textarea
              id="chat-message"
              className="message-input"
              rows={4}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              disabled={useIrisContextForChat && Boolean(irisResult?.incident_report)}
            />
            <label className="chat-label" htmlFor="use-iris-context">
              <input
                id="use-iris-context"
                type="checkbox"
                checked={useIrisContextForChat}
                onChange={(event) => setUseIrisContextForChat(event.target.checked)}
              />
              Use latest IRIS incident report as chat context
            </label>
            {useIrisContextForChat && !irisResult?.incident_report && (
              <p className="response-meta">Ingest an IRIS case first to include incident_report in the chat request.</p>
            )}
            {useIrisContextForChat && irisResult?.incident_report && (
              <p className="response-meta">Incident report mode is active. Prompt text is optional and not sent.</p>
            )}
            <div className="hero-actions">
              <button type="submit" className="btn btn-primary" disabled={chatLoading}>
                {chatLoading ? "Running Session..." : "Start Incident Session"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={handleTranscriptRefresh}
                disabled={!traceId || transcriptLoading}
              >
                {transcriptLoading ? "Refreshing..." : "View Trace Timeline"}
              </button>
            </div>
          </form>

          {errorMessage && <p className="error-callout">{errorMessage}</p>}

          {answer && (
            <div className="response-card">
              <p className="response-text">{answer}</p>
              <p className="response-meta">
                Trace: {traceId ?? "n/a"} | Session: {sessionId}
              </p>
            </div>
          )}
        </section>

        <section className="panel status-panel">
          <h3>System Snapshot</h3>
          <ul className="status-list">
            <li>
              <span>Chat Endpoint</span>
              <strong>Groq-only</strong>
            </li>
            <li>
              <span>Trace Stream</span>
              <strong>{streamStatus}</strong>
            </li>
            <li>
              <span>Approval Queue</span>
              <strong>{needsApproval ? "Pending" : transcript?.final_status ?? "Idle"}</strong>
            </li>
            <li>
              <span>Confluence Ingest</span>
              <strong>
                {confluenceResult
                  ? `${confluenceResult.ingested_count} ok / ${confluenceResult.failed_count} failed`
                  : "Not run"}
              </strong>
            </li>
            <li>
              <span>IRIS Ingest</span>
              <strong>{irisResult ? `Case ${irisResult.case_id}` : "Not run"}</strong>
            </li>
          </ul>
        </section>

        <section className="panel trace-panel">
          <h3>Trace Preview</h3>
          <p>Live stream of trace_step events (retrieval, reasoning, execution) with transcript refresh support.</p>
          {traceSteps.length === 0 ? (
            <div className="trace-lines" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          ) : (
            <ul className="trace-events">
              {traceSteps.map((step, index) => (
                <li key={`${step.step}-${step.agent}-${index}`}>
                  <strong>{step.step}</strong> ({step.agent})<br />
                  {step.observation}
                  <br />
                  <small>
                    Seq: {step.metadata?.stream_sequence ?? "n/a"} | Timestamp: {formatTimestamp(step.timestamp)}
                  </small>
                  {typeof step.metadata?.duration_ms === "number" && (
                    <>
                      <br />
                      <small>Duration: {step.metadata.duration_ms.toFixed(2)}ms</small>
                    </>
                  )}
                  {(step.metadata?.provider || step.metadata?.model) && (
                    <>
                      <br />
                      <small>
                        Provider: {step.metadata?.provider ?? "n/a"} | Model: {step.metadata?.model ?? "n/a"}
                      </small>
                    </>
                  )}
                  {step.metadata?.llm_query_expansion && (
                    <>
                      <br />
                      <small>
                        Query Expansion: {step.metadata.llm_query_expansion.used ? "used" : "not used"}
                        {Array.isArray(step.metadata.llm_query_expansion.expanded_query_tokens)
                          ? ` (${step.metadata.llm_query_expansion.expanded_query_tokens.join(", ")})`
                          : ""}
                      </small>
                    </>
                  )}
                  {typeof step.metadata?.confidence === "number" && (
                    <>
                      <br />
                      <small>Confidence: {step.metadata.confidence.toFixed(3)}</small>
                    </>
                  )}
                  {typeof step.metadata?.confidence_breakdown?.final_confidence === "number" && (
                    <>
                      <br />
                      <small>
                        Confidence Breakdown: base {step.metadata.confidence_breakdown.base_confidence?.toFixed(3) ?? "n/a"},
                        quality {step.metadata.confidence_breakdown.quality_bonus?.toFixed(3) ?? "n/a"},
                        penalty {step.metadata.confidence_breakdown.duplicate_penalty?.toFixed(3) ?? "n/a"},
                        final {step.metadata.confidence_breakdown.final_confidence.toFixed(3)}
                      </small>
                    </>
                  )}
                  {Array.isArray(step.metadata?.reasoning_steps) && step.metadata.reasoning_steps.length > 0 && (
                    <>
                      <br />
                      <small>Reasoning Steps: {step.metadata.reasoning_steps.join(" | ")}</small>
                    </>
                  )}
                  {Array.isArray(step.metadata?.evidence_scores) && step.metadata.evidence_scores.length > 0 && (
                    <>
                      <br />
                      <small>
                        Evidence Scores: {step.metadata.evidence_scores
                          .map((score) => `${score.title} (${score.priority_score.toFixed(3)})`)
                          .join(", ")}
                      </small>
                    </>
                  )}
                  {step.sources.length > 0 && (
                    <>
                      <br />
                      <small>
                        Sources: {step.sources
                          .map((source) =>
                            `${source.title}${typeof source.score === "number" ? ` (score ${source.score})` : ""}`,
                          )
                          .join(", ")}
                      </small>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
          {traceId && <p className="trace-status">Active trace: {traceId}</p>}
        </section>

        <section className="panel runbook-panel">
          <h3>Integration Controls</h3>
          <div className="chat-form">
            <label className="chat-label" htmlFor="confluence-pages">
              Confluence Page IDs (comma or space separated)
            </label>
            <input
              id="confluence-pages"
              className="message-input"
              value={confluencePageIds}
              onChange={(event) => setConfluencePageIds(event.target.value)}
            />
            <button type="button" className="btn btn-ghost" onClick={handleConfluenceIngest} disabled={confluenceLoading}>
              {confluenceLoading ? "Ingesting Confluence..." : "Ingest Confluence Runbooks"}
            </button>

            <label className="chat-label" htmlFor="iris-case-id">
              IRIS Case ID
            </label>
            <input
              id="iris-case-id"
              className="message-input"
              value={irisCaseId}
              onChange={(event) => setIrisCaseId(event.target.value)}
            />
            <button type="button" className="btn btn-ghost" onClick={handleIrisIngest} disabled={irisLoading}>
              {irisLoading ? "Ingesting IRIS..." : "Ingest IRIS Incident"}
            </button>

            <label className="chat-label" htmlFor="approver-id">
              Approver ID
            </label>
            <input
              id="approver-id"
              className="message-input"
              value={approverId}
              onChange={(event) => setApproverId(event.target.value)}
            />

            <label className="chat-label" htmlFor="approval-comment">
              Approval Comment
            </label>
            <textarea
              id="approval-comment"
              className="message-input"
              rows={2}
              value={approvalComment}
              onChange={(event) => setApprovalComment(event.target.value)}
            />

            <div className="hero-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleApproval("approve")}
                disabled={!traceId || !needsApproval || approvalLoading}
              >
                {approvalLoading ? "Submitting..." : "Approve Action"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void handleApproval("reject")}
                disabled={!traceId || !needsApproval || approvalLoading}
              >
                Reject Action
              </button>
            </div>
          </div>

          {approvalResult && (
            <div className="response-card">
              <p className="response-text">
                Approval submitted: {approvalResult.approval.decision} ({approvalResult.final_status})
              </p>
            </div>
          )}

          {transcript && (
            <div className="response-card">
              <p className="response-text">
                Transcript final status: {transcript.final_status ?? "n/a"}
              </p>
              <p className="response-meta">
                Suggested action: {transcript.suggested_action ?? "n/a"}
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
