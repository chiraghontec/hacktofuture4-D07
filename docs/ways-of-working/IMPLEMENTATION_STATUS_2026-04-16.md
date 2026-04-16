# UniOps Implementation Status (2026-04-16)

This document captures the as-built state of UniOps as of 2026-04-16.

## 0) Current Project Status Snapshot

Legend:
- [x] Completed for now
- [~] In progress / partial
- [ ] Pending

Status:
- [x] Backend APIs and approval flow
- [~] Frontend integration completeness
- [x] SSE completion (live POST stream with heartbeat and terminal events)
- [x] Groq-first backend rollout across retrieval, reasoning, and execution swarms

## 1) What Is Implemented End-to-End

### Backend API
- Health endpoint:
  - `GET /health`
- Chat and trace endpoints:
  - `POST /api/chat` (live SSE execution stream)
  - `GET /api/chat/transcript/{trace_id}`
- Ingestion endpoints:
  - `POST /api/ingest/iris?case_id=<id>`
  - `POST /api/ingest/confluence` with body `{ "page_ids": ["..."] }`
- Approval endpoint:
  - `POST /api/approvals/{trace_id}`

### Core Runtime Flow
1. Query enters Controller Kernel.
2. Retrieval swarm performs keyword plus optional hybrid retrieval, with Groq-assisted query expansion when provider is enabled.
3. Reasoning swarm prioritizes evidence, computes confidence and reasoning breakdown metadata, and proposes structured action details.
4. Execution swarm performs Groq-based action normalization/risk rationale (when enabled), then classifies risk with native permission gate.
5. If high or uncertain risk, status is `pending_approval`.
6. Approval API applies `approve` or `reject` decision.
7. Transcript and audit artifacts are updated with final outcome.

### Memory and Audit
- Three-tier memory currently supports:
  - Static source loading from `data/{confluence,runbooks,incidents,github,slack}`
  - Runtime ingestion merge for IRIS and Confluence docs
  - Dedup pass and summary metadata
  - Transcript persistence with action details and approval status fields
  - Approval audit persistence under `backend/.uniops/approvals/`

### SSE Status
- SSE now runs as a live execution stream on `POST /api/chat`.
- Stream lifecycle events implemented: `trace_started`, `trace_step`, `trace_heartbeat`, `trace_complete`, and `trace_error`.
- Event envelopes include ordered sequencing and observability context: `event_id`, `trace_id`, `sequence`, and `status`.
- Step metadata now includes timing fields (`started_at`, `finished_at`, `duration_ms`) in addition to reasoning/execution metadata.

## 2) Key Files Added/Updated

### API routes
- `backend/app/api/routes/chat.py`
- `backend/app/api/routes/ingestion.py`
- `backend/app/api/routes/approvals.py`
- `backend/app/main.py`

### Core orchestration and memory
- `backend/src/agents/orchestrator.py`
- `backend/src/controller/controller.py`
- `backend/src/swarms/retrieval_swarm.py`
- `backend/src/swarms/reasoning_swarm.py`
- `backend/src/swarms/execution_swarm.py`
- `backend/src/memory/three_tier_memory.py`
- `backend/src/gates/permission_gate.py`
- `backend/src/vector_store/llamaindex_hybrid.py`
- `backend/src/adapters/llm_client.py`

### Integrations and tools
- `backend/src/adapters/iris_client.py`
- `backend/src/adapters/confluence_client.py`
- `backend/src/tools/executor.py`
- `backend/src/tools/registry.py`

### Contract
- `shared/contracts/chat.contract.json`

### Local DFIR-IRIS setup
- `Makefile` targets for IRIS lifecycle:
  - `iris-install`, `iris-up`, `iris-down`, `iris-logs`, `iris-admin-password`
- `scripts/iris/install_iris_web.sh`
- `docs/ways-of-working/LOCAL_DFIR_IRIS_SETUP_MACOS.md`
- `docs/ways-of-working/IRIS_INCIDENT_SETUP.md`

## 3) Current Contract Highlights

### Chat request modes
- `message_only`
- `incident_report_only`
- `message_and_incident_report`

Rule: when `incident_report` is present, backend derives canonical query context from that report.

### Chat response
- Live SSE event stream from `POST /api/chat`
- Terminal `trace_complete` event carries `answer`, `needs_approval`, `trace_id`, and dedup summary in metadata

### Provider error behavior
- `POST /api/chat` emits terminal `trace_error` SSE events for selected provider misconfiguration/runtime failure.

### Transcript metadata (implemented)
- `suggested_action`
- `action_details`
- `needs_approval`
- `execution_status`
- Optional after approval:
  - `approval`
  - `execution_result`
  - `final_status`

### Trace and stream metadata (implemented)
- `retrieval_method`, `query_tokens`, `llm_query_expansion`
- `confidence`, `confidence_breakdown`, `reasoning_steps`, `evidence_scores`
- `risk_level`, `requires_human_approval`, `execution_reasoning`, `risk_hint`

### Approval API response (implemented)
- `trace_id`
- `final_status` (`executed` or `rejected`)
- `approval` object
- `execution_result` object

### Confluence ingestion contract (implemented)
- Request body:
  - `page_ids: string[]` (deduplicated, non-empty)
- Response:
  - `ingested_count`
  - `failed_count`
  - `source`
  - `results[]` with per-page `page_id`, `status`, optional `title`, optional `error`

## 4) Test and Verification Evidence

### Confirmed passing in current environment
- `backend/.venv/Scripts/python -m pytest -q`
  - Result: `31 passed in 1.90s`

### Frontend validation
- `frontend npm run build`
  - Result: success (Next.js production build complete)

### Additional implemented test files
- `backend/tests/test_chat_iris_input.py`
- `backend/tests/test_chat_orchestration.py`
- `backend/tests/test_chat_stream.py`
- `backend/tests/test_ingestion.py`
- `backend/tests/test_memory_dedup.py`
- `backend/tests/test_reasoning_tuning.py`
- `backend/tests/test_retrieval_execution_groq.py`
- `backend/tests/test_e2e_ingest_chat_approve.py`

### Manual E2E verification script
- `scripts/e2e_confluence_flow.sh`
  - Sequence: ingest Confluence pages -> chat -> stream -> approval -> transcript
  - Required env: `CONFLUENCE_PAGE_IDS`

### Docs and schema availability
- Swagger UI active at `http://127.0.0.1:8000/docs`
- OpenAPI JSON active at `http://127.0.0.1:8000/openapi.json`

## 5) Frontend Status

### Implemented
- Next.js shell UI and design system scaffolding in `frontend/app/page.tsx` and `frontend/app/globals.css`
- Backend API utility in `frontend/lib/chat-api.ts`
- Trace panel rendering for confidence, confidence breakdown, reasoning steps, evidence scores, and source-level scores

### Pending for full UX completion
- Full approval modal wiring for `POST /api/approvals/{trace_id}`
- Ingestion action wiring for IRIS and Confluence from UI
- End-to-end trace and approval lifecycle rendering from UI state

## 6) Known Gaps (Next Work Items)

1. Implement live external adapters (GitHub/Slack/Jira) in teammate-owned workstream; current path remains mock execution.
2. Complete frontend approval and ingestion interaction flow hardening and UX polish.
3. Add stronger retry/error envelope strategy for external adapter calls and provider timeouts.
4. Add optional scheduled sync mode (currently manual ingestion trigger only).
5. Runtime-ingested documents are intentionally non-persistent for this slice and must be re-ingested after restart.
