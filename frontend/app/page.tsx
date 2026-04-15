"use client";

import { FormEvent, useState } from "react";

import { useApprovalQueue } from "../lib/useApprovalQueue";
import { useChat } from "../lib/useChat";
import { useTraceStream } from "../lib/useTraceStream";

export default function HomePage() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [needsApproval, setNeedsApproval] = useState(false);

  const { sendMessage, loading, error } = useChat();
  const {
    actions,
    loading: queueLoading,
    error: queueError,
    mutatingActionId,
    reloadPending,
    approveAction,
    rejectAction,
  } = useApprovalQueue();
  const { steps, isStreaming, streamError } = useTraceStream(traceId);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!message.trim()) {
      return;
    }

    const result = await sendMessage(message.trim());
    if (!result) {
      return;
    }

    setAnswer(result.answer);
    setTraceId(result.trace_id);
    setNeedsApproval(result.needs_approval);
    setMessage("");
    await reloadPending();
  };

  return (
    <main className="page">
      <section className="card">
        <h1>UniOps Live Trace</h1>
        <p className="subtitle">Ask an operational question and inspect controller trace steps in real time.</p>

        <form className="chat-form" onSubmit={onSubmit}>
          <label htmlFor="chat-message">Message</label>
          <div className="chat-controls">
            <input
              id="chat-message"
              type="text"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Explain Redis latency from last week"
              disabled={loading}
            />
            <button type="submit" disabled={loading || !message.trim()}>
              {loading ? "Sending..." : "Send"}
            </button>
          </div>
        </form>

        {error ? <p className="error">{error}</p> : null}
        {streamError ? <p className="error">{streamError}</p> : null}
        {queueError ? <p className="error">{queueError}</p> : null}

        {answer ? (
          <div className="answer-panel">
            <h2>Answer</h2>
            <p>{answer}</p>
            <div className={needsApproval ? "approval approval-pending" : "approval approval-safe"}>
              {needsApproval ? "Approval required for follow-up action." : "No approval required."}
            </div>
            {traceId ? <p className="trace-id">Trace ID: {traceId}</p> : null}
          </div>
        ) : null}

        <div className="trace-panel">
          <div className="trace-header">
            <h2>Live Trace</h2>
            <span>{isStreaming ? "Streaming" : "Idle"}</span>
          </div>

          {steps.length === 0 ? (
            <p className="trace-empty">No trace steps yet.</p>
          ) : (
            <ul className="trace-list">
              {steps.map((step, index) => (
                <li key={`${step.step}-${index}`}>
                  <div className="trace-meta">
                    <strong>{step.step}</strong>
                    <span>{step.agent}</span>
                  </div>
                  <p>{step.observation}</p>
                  {step.sources.length > 0 ? (
                    <ul className="source-list">
                      {step.sources.map((source) => (
                        <li key={`${source.path}-${source.title}`}>
                          <span>{source.title}</span>
                          <small>{source.path}</small>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="queue-panel">
          <div className="queue-header">
            <h2>Pending Approvals</h2>
            <button type="button" onClick={() => void reloadPending()} disabled={queueLoading}>
              {queueLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {actions.length === 0 ? (
            <p className="queue-empty">No pending actions.</p>
          ) : (
            <ul className="queue-list">
              {actions.map((action) => {
                const busy = mutatingActionId === action.id;
                return (
                  <li key={action.id}>
                    <div className="queue-meta">
                      <strong>{action.action}</strong>
                      <span>{action.risk_level}</span>
                    </div>
                    <p>{action.reason}</p>
                    <p className="queue-trace">Trace: {action.trace_id}</p>
                    <div className="queue-controls">
                      <button type="button" disabled={busy} onClick={() => void approveAction(action.id)}>
                        {busy ? "Working..." : "Approve"}
                      </button>
                      <button type="button" disabled={busy} onClick={() => void rejectAction(action.id)}>
                        Reject
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}
