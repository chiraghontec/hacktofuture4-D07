export default function Home() {
  const navItems = ["Overview", "Trace", "Approvals", "Runbooks"];

  return (
    <div className="app-shell">
      <header className="top-nav">
        <div className="brand-wrap">
          <h1 className="brand-name title-highlight">
            UniOps
          </h1>
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
            UniOps unifies runbooks, incident notes, and change history into one auditable
            flow. This shell is ready for chat wiring and live trace streaming.
          </p>
          <div className="hero-actions">
            <button type="button" className="btn btn-primary">
              Start Incident Session
            </button>
            <button type="button" className="btn btn-ghost">
              View Trace Timeline
            </button>
          </div>
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
              <strong>Stub (501)</strong>
            </li>
            <li>
              <span>Approval Queue</span>
              <strong>UI Pending</strong>
            </li>
          </ul>
        </section>

        <section className="panel trace-panel">
          <h3>Trace Preview</h3>
          <p>Waiting for live SSE events. Backend contract is already aligned for `trace_step`.</p>
          <div className="trace-lines" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
        </section>

        <section className="panel runbook-panel">
          <h3>Runbook Quick Actions</h3>
          <div className="chip-row">
            <span className="chip">High CPU Service X</span>
            <span className="chip">Redis Latency</span>
            <span className="chip">Rollback Deploy</span>
          </div>
          <p>
            Action execution remains human-gated. This panel will connect to approval modal
            and tool actions in the next phase.
          </p>
        </section>
      </main>
    </div>
  );
}
