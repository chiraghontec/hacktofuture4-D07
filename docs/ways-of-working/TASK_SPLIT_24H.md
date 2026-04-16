# 24-Hour Execution Split (2 Engineers)

For backend-first execution with equal split by skill profile, use:
- docs/ways-of-working/BACKEND_SPLIT_24H.md

## Progress Snapshot (as of 2026-04-16)

Legend:
- [x] Completed for now
- [~] In progress / partial
- [ ] Pending

## Hour 0-2
- [x] Engineer A: Frontend setup, chat shell, trace panel layout
- [x] Engineer B: FastAPI setup, /health, /api/chat stub

## Hour 2-8
- [ ] Engineer A: SSE client, reasoning timeline UI, source citation cards
- [~] Engineer B: Controller + retrieval/reasoning/execution swarm stubs, SSE endpoint baseline only

## Hour 8-14
- [ ] Engineer A: Approval modal and action queue UI
- [x] Engineer B: Native permission gate and mock tool registry

## Hour 14-20
- [~] Engineer A: Polish UX, loading/error states, responsive layout
- [x] Engineer B: Memory layer, audit logs, ingestion glue

## Hour 20-24 (stabilization window)
- [~] Both: Bug fixing and demo prep only
- [~] No new architecture changes
- [~] Keep PR size small and merge every 60-90 minutes

## As-Built Delta (from IMPLEMENTATION_STATUS_2026-04-16)

- Backend now exposes:
	- `GET /health`
	- `POST /api/chat`
	- `GET /api/chat/transcript/{trace_id}`
	- `POST /api/chat` (live SSE stream)
	- `POST /api/ingest/iris?case_id=<id>`
	- `POST /api/ingest/confluence` with body `{"page_ids": ["..."]}`
	- `POST /api/approvals/{trace_id}`
- Shared contract has ingestion and approval schemas implemented.
- Shared contract now includes additive action and trace metadata fields for Groq-backed reasoning/execution transparency.
- Approval tests are passing in current backend environment (`tests/test_approvals.py`).
- Backend suite currently passes with Groq integration slices (`31 passed`).
- SSE is not done yet beyond baseline endpoint streaming.
- Main remaining product gaps are SSE completion and frontend completion for ingestion and HITL approval UX wiring.
