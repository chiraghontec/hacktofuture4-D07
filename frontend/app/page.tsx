"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  type ApprovalResponse,
  type IngestConfluenceResponse,
  type IngestIrisResponse,
  type TraceStep,
  type TranscriptResponse,
  getTranscript,
  ingestConfluence,
  ingestIris,
  postChat,
  streamTrace,
  submitApproval,
} from "@/lib/chat-api";

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

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!traceId) {
      return () => undefined;
    }

    eventSourceRef.current?.close();
    const source = streamTrace(traceId);
    eventSourceRef.current = source;
    setStreamStatus("connecting");

    const onTraceStep = (event: Event) => {
      const messageEvent = event as MessageEvent<string>;
      try {
        const parsed = JSON.parse(messageEvent.data) as TraceStep;
        setTraceSteps((previous) => [...previous, parsed]);
        setStreamStatus("streaming");
      } catch {
        setStreamStatus("parse_error");
      }
    };

    source.addEventListener("trace_step", onTraceStep as EventListener);
    source.onerror = () => {
      setStreamStatus("closed");
      source.close();
    };

    return () => {
      source.removeEventListener("trace_step", onTraceStep as EventListener);
      source.close();
    };
  }, [traceId]);

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
    if (!message.trim()) {
      setErrorMessage("Enter an incident prompt before starting the session.");
      return;
    }

    setErrorMessage(null);
    setChatLoading(true);
    setStreamStatus("idle");
    setTraceSteps([]);
    setTranscript(null);
    setApprovalResult(null);

    try {
      const result = await postChat({
        message: message.trim(),
        session_id: sessionId,
      });
      setAnswer(result.answer);
      setTraceId(result.trace_id);
      setNeedsApproval(result.needs_approval);
    } catch (error: unknown) {
      setErrorMessage(errorToMessage(error));
    } finally {
      setChatLoading(false);
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
            />
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
              <strong>Ready</strong>
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
