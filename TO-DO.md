# UniOps Implementation Tracker

## Branch Lane Map
- Engineer 1 core branch: `feature/backend-orchestration-and-skills` (base branch)
- Engineer 2 systems branch: `feat/backend-systems-queue-flow`
- Shared contract branch: `chore/shared-actions-contract`
- Merged shared branches: `chore/shared-chat-contract-iris-incident-input`, `chore/shared-chat-contract-dedup-metadata`
- Merged backend branches: `feat/backend-systems-iris-report-query-pass-through`, `feat/backend-dedup-api-metadata`, `feat/backend-reasoning-source-priority-hints`, `feat/backend-dedup-determinism-tests`
- Merged integration branch: `feature/backend-final-demo-integration` -> `main`
- Open PR count: 0

## Engineer 1 Full Plan (Target 10 points)
- [x] P0 (3): Controller pipeline with swarm chaining.
- [x] P0 (3): Retrieval + reasoning output schema and citation handoff.
- [x] P1 (2): Permission policy rules for HITL decisions.
- [x] P1 (2): Memory summary and Kairos-lite dedup pass API.
- Current completion: 10/10 points.
- Remaining completion: 0/10 points.

## Backlog
- [x] Engineer 1: Add `run_dedup_pass()` in `backend/src/memory/three_tier_memory.py` for transcript/doc dedup.
- [x] Engineer 1: Expose dedup summary metadata in memory summary API shape.
- [x] Engineer 1: Add focused tests for dedup behavior and deterministic idempotency (`backend/tests/test_memory_dedup.py`).
- [x] Engineer 1: Tune reasoning quality hints for source prioritization (non-breaking).

## In Progress
- [ ] Core MVP golden flow implementation: IRIS + Confluence end-to-end integration on `main` baseline.
- [ ] HITL completion path: pending approval -> approve/reject -> executed/rejected audit trace.
- [ ] Live demo runbook finalization: standardize validated IDs (`Confluence: 65868,65898`, `IRIS case_id: 1`) across scripted and frontend flows.

## Done
- [x] Established branch split strategy and pushed baseline/core changes to `main`.
- [x] Pushed backend orchestration and skill assets to feature branch.
- [x] Slice 1: Contract updates for stream/transcript endpoints.
- [x] Slice 1: Backend live SSE trace endpoint (`POST /api/chat`).
- [x] Slice 1: Backend transcript read endpoint (`GET /api/chat/transcript/{trace_id}`).
- [x] Slice 1: Frontend hooks for chat and trace streaming.
- [x] Slice 1: Frontend page integration for answer + live trace.
- [x] Slice 1: Backend tests for stream and transcript behavior.
- [x] Systems-slice changes moved off this branch to `feat/backend-systems-queue-flow`.
- [x] Shared contract actions changes moved to `chore/shared-actions-contract`.
- [x] IRIS dual-input contract added (message + incident_report with precedence rule).
- [x] IRIS runtime path added in backend chat route with validation and canonical incident context mapping.
- [x] Kairos dedup pass implemented for documents/transcripts.
- [x] Dedup summary metadata exposed in chat response and transcript payload.
- [x] Reasoning quality tuning shipped (source reranking, dedup-aware confidence, tuned action selection).
- [x] Dedicated deterministic/idempotency dedup tests added.
- [x] Active feature branches merged into `feature/backend-final-demo-integration` and verified end-to-end.
- [x] PR #1 merged to `main` (`feat: add backend orchestration core and local skill assets`).
- [x] PR #4 retargeted to `main` and merged (`merge: final integrated backend feature set + PRD demo verification`).
- [x] PR #2 and PR #3 closed as superseded by merged integration work.
- [x] Frontend on `main` restored to main-baseline implementation after merge sequencing.
- [x] API-only Confluence batch ingestion shipped (`POST /api/ingest/confluence` with body `page_ids`) with partial-failure reporting.
- [x] Automated API-only E2E flow test added (`backend/tests/test_e2e_ingest_chat_approve.py`) for ingest -> chat -> stream -> approve -> transcript lifecycle.
- [x] Manual E2E verification script added (`scripts/e2e_confluence_flow.sh`) for live backend runs.
- [x] Phase 2 frontend demo wiring shipped (`frontend/app/page.tsx`, `frontend/lib/chat-api.ts`): ingestion controls, chat submit, SSE trace rendering, approval actions, transcript refresh.
- [x] Credential setup completed for live connectors: `.env` now has working Confluence and IRIS integration keys (IRIS key sourced from local `iris-web` DB admin user record).

## Risks
- SSE consumers can see parse errors if event payload shape changes unexpectedly.
- Browser CORS can block frontend-to-backend calls if origin config is too strict.
- Read-after-write race is possible if transcript fetch occurs before file write completion.
- Local Python 3.14 environments may fail to build backend dependencies (`pydantic-core`/PyO3) without compatibility handling.

## Decisions
- Tight Slice 1 first: TO-DO + SSE trace + transcript read + frontend live trace.
- Queue work is isolated to systems branch (`feat/backend-systems-queue-flow`).
- Shared actions contract is isolated to `chore/shared-actions-contract`.
- Keep `POST /api/chat` backward compatible while extending payload shape additively.
- Incident input model supports both free-text and IRIS incident reports; `incident_report` takes precedence when present.
- Dedup metadata is additive and non-breaking in both chat response and transcript payload.

## Current Implementation Approach (Active)
- Core MVP feature selected from PRD: single golden flow for "Explain Redis latency incident" using Confluence runbook context + IRIS incident context + live trace + human approval before external action.
- Integration targets: Atlassian Confluence Cloud and ServiceNow-style IRIS APIs (real connectors, not local-only stubs).
- Auth model: environment secret based credentials for external API access.
- Delivery bar: one complete golden flow end-to-end (not all four PRD flows in this sprint slice).
- Base branch strategy: implement from `main` state to avoid drift from older feature branch snapshots.
- Branch lane execution plan:
	- `chore/shared-*`: contract/schema updates first.
	- `feat/backend-systems-*`: ingestion routes, approval route, external API adapters.
	- `feat/backend-core-*`: controller/retrieval/execution approval state transitions and trace/audit persistence.
	- `feat/frontend-*`: chat + trace + incident input + approval modal wiring.
- Backend build scope for this slice:
	- Extend chat request to support dual input (`message` + `incident_report`) with precedence validation.
	- Add `/api/ingest/confluence` and `/api/ingest/iris` for source sync.
	- Add approval decision endpoint for trace-bound actions (`approve` / `reject`).
	- Replace pending-only execution stop with full decision transition and recorded execution outcome.
- Frontend build scope for this slice:
	- Replace static shell with functional chat workflow.
	- Show live SSE trace steps with cited sources.
	- Add incident input path and approval modal submission UX.
	- Display post-approval action result and updated trace.
- Verification gates for completion:
	- Boundary checks per branch lane (`scripts/check-boundaries.sh`).
	- Backend tests for dual-input chat, ingestion, approval transitions, and stream/transcript regression.
	- Frontend build + runtime smoke.
	- Golden flow API sequence: ingest -> chat -> stream -> approve/reject -> transcript confirms final state.

## Verification Log
- 2026-04-16: Started Slice 1 implementation.
- 2026-04-16: Backend tests passed (`pytest -q`): 6 passed.
- 2026-04-16: Frontend production build passed (`npm run build`).
- 2026-04-16: Slice 1 marked complete; queue work remains in Backlog for Slice 2.
- 2026-04-16: Stream test suite cleaned and rerun (`pytest -q`): 7 passed.
- 2026-04-16: Branch split completed; systems and shared changes removed from Engineer 1 branch.
- 2026-04-16: IRIS runtime validation passed on local backend (`GET /health` 200, `POST /api/chat` message-only 200, incident_report-only 200, dual-input 200, invalid payload 422, transcript fetch 200 with 3 steps, stream fetch returned 3 data events).
- 2026-04-16: IRIS automated validation passed (`python -m pytest -q tests/test_chat_iris_input.py`: 4 passed; `python -m pytest -q`: 11 passed; `BASE_REF=origin/feature/backend-orchestration-and-skills bash scripts/check-boundaries.sh`: passed).
- 2026-04-16: PR evidence recorded: #2 `chore(shared): add IRIS incident_report dual-input chat contract` (https://github.com/chiraghontec/hacktofuture4-D07/pull/2) and #3 `feat(backend): support IRIS incident report as chat input context` (https://github.com/chiraghontec/hacktofuture4-D07/pull/3).
- 2026-04-16: Dedup pass + metadata implementation completed and pushed (`feat/backend-dedup-api-metadata`, commit `399c8b3`; `python -m pytest -q`: 11 passed; runtime payload shows `dedup_summary` in both `POST /api/chat` and `GET /api/chat/transcript/{trace_id}`).
- 2026-04-16: Dedup metadata contract update completed and pushed (`chore/shared-chat-contract-dedup-metadata`, commit `17d2f33`; JSON validation via `jq empty shared/contracts/chat.contract.json`).
- 2026-04-16: Reasoning quality tuning completed and pushed (`feat/backend-reasoning-source-priority-hints`, commit `ea8d5d4`; `python -m pytest -q`: 14 passed; `BASE_REF=origin/feature/backend-orchestration-and-skills bash scripts/check-boundaries.sh`: passed).
- 2026-04-16: Dedicated deterministic/idempotency dedup tests completed and pushed (`feat/backend-dedup-determinism-tests`, commit `b944e52`; `python -m pytest -q tests/test_memory_dedup.py`: 2 passed; full suite `python -m pytest -q`: 13 passed).
- 2026-04-16: Active feature branches merged into integration branch `feature/backend-final-demo-integration`; full backend suite passed (`python -m pytest -q`: 16 passed) and frontend build passed (`npm run build`).
- 2026-04-16: Final PRD-aligned browser demo flows validated on merged integration branch (4/4 flows passed with rendered answers, expected approval behavior, and trace steps `retrieval -> reasoning -> execution`; transcript endpoint returned `dedup_summary`; SSE stream emitted 3 events per flow).
- 2026-04-16: Integration PR opened: #4 `merge: final integrated backend feature set + PRD demo verification` (https://github.com/chiraghontec/hacktofuture4-D07/pull/4).
- 2026-04-16: PR #1 merged to `main` (merge commit `8884e63`; https://github.com/chiraghontec/hacktofuture4-D07/pull/1).
- 2026-04-16: PR #4 retargeted to `main` and merged (merge commit `326a4e5`; https://github.com/chiraghontec/hacktofuture4-D07/pull/4).
- 2026-04-16: PR #2 and PR #3 closed as superseded after integration merge (https://github.com/chiraghontec/hacktofuture4-D07/pull/2, https://github.com/chiraghontec/hacktofuture4-D07/pull/3).
- 2026-04-16: Frontend baseline correction applied on `main` to keep main-branch frontend implementation (`fix(frontend): keep main frontend baseline`, commit `89d25bc`); frontend production build passed (`npm run build`).
- 2026-04-16: Active implementation approach logged for next build slice: contract-first IRIS + Confluence golden flow with HITL approval completion path and branch-lane execution plan.
- 2026-04-16: Phase 1 implementation started for DFIR-IRIS local setup. Added `make iris-install|iris-up|iris-down|iris-logs|iris-admin-password`, installer script (`scripts/iris/install_iris_web.sh`), and local runbook (`docs/ways-of-working/LOCAL_DFIR_IRIS_SETUP_MACOS.md`).
- 2026-04-16: Official `dfir-iris/iris-web` installed locally to `.vendor/iris-web` at tag `v2.4.27`; generated local `.env` with randomized DB/admin/secret values and `SERVER_NAME=localhost`.
- 2026-04-16: Runtime start attempt blocked in this environment because Docker CLI is unavailable (`docker: command not found`). Added `require-docker` precheck in `Makefile` for clear operator feedback.
- 2026-04-16: Phase 2 ingestion implementation started: added IRIS and Confluence adapter clients (`backend/src/adapters/*.py`), ingestion API routes (`POST /api/ingest/iris`, `POST /api/ingest/confluence`), runtime document ingestion in memory, and `backend/tests/test_ingestion.py`.
- 2026-04-16: Backend dependency installation for tests is blocked on Python 3.14 compatibility (`pydantic-core/jiter` build failure). Validation requires Python 3.12 environment.
- 2026-04-16: Phase 3 approval workflow implementation started: added approval endpoint (`POST /api/approvals/{trace_id}`), mock tool executor, transcript approval audit persistence, and router registration.
- 2026-04-16: Shared contract updated for ingestion and approval endpoints plus transcript approval metadata (`shared/contracts/chat.contract.json`); JSON validation passed (`python3 -m json.tool`).
- 2026-04-16: Syntax validation passed for approval workflow files (`python3 -m py_compile ...`). Automated tests remain blocked in current `.venv` because `pytest` and compatible dependencies are unavailable with Python 3.14 pin set.
- 2026-04-16: Confluence ingestion contract upgraded to batch request shape (`POST /api/ingest/confluence` body `{ "page_ids": [...] }`) and per-page result reporting in `shared/contracts/chat.contract.json`; JSON validation passed (`python3 -m json.tool shared/contracts/chat.contract.json`).
- 2026-04-16: Backend batch ingestion implementation + regression fixes completed (`backend/app/api/routes/ingestion.py`, `backend/app/api/routes/chat.py` SSE streaming via `StreamingResponse`), focused tests passed (`10 passed`) and full backend suite passed (`22 passed`) using `backend/.venv`.
- 2026-04-16: API-only golden flow validation assets completed: `backend/tests/test_e2e_ingest_chat_approve.py` and executable script `scripts/e2e_confluence_flow.sh`.
- 2026-04-16: Demo run executed now: backend started successfully from `backend/.venv` (`uvicorn app.main:app --host 0.0.0.0 --port 8000`), automated E2E demo passed (`.venv/bin/python -m pytest -q tests/test_e2e_ingest_chat_approve.py`: `1 passed`).
- 2026-04-16: Live scripted demo run executed (`CONFLUENCE_PAGE_IDS=12345,67890 ./scripts/e2e_confluence_flow.sh`): full trace/approval path completed (`final_status=executed`, 3 SSE events), while Confluence fetch step returned `CONFLUENCE_BASE_URL is not configured` (runtime env configuration pending).
- 2026-04-16: Backend startup updated to auto-load root `.env` (`backend/app/main.py` using `python-dotenv` when available); regression tests passed (`.venv/bin/python -m pytest -q tests/test_ingestion.py tests/test_chat_stream.py tests/test_approvals.py`: `9 passed`).
- 2026-04-16: Phase 2 frontend verification passed (`npm run lint`, `npm run build`) and browser demo validated at `http://localhost:3000`: chat produced trace, SSE rendered retrieval/reasoning/execution, approval action produced `executed` final status and transcript card updated.
- 2026-04-16: Live Confluence connector now reads env values, but sample IDs `12345,67890` returned upstream 404 from Confluence API; requires valid page IDs for successful live ingest evidence.
- 2026-04-16: Confluence credential validity confirmed by page discovery probe (`GET /rest/api/content?limit=5` 200); validated page IDs captured (`65868`, `65898`) and scripted demo run passed with `ingested_count=2`.
- 2026-04-16: IRIS auth issue resolved from 401 to valid auth by replacing placeholder password with actual admin API key token (retrieved from local `iris_db` user record); IRIS list endpoint probe returned case `1` (`#1 - Initial Demo`) and ingestion succeeded (`POST /api/ingest/iris?case_id=1` => 200).
- 2026-04-16: Frontend live-demo verification completed at `http://localhost:3000` with validated defaults (`Confluence page IDs: 65868,65898`, `IRIS case ID: 1`): Confluence ingest status `2 ok / 0 failed`, IRIS ingest status `Case 1`, approval flow executed, transcript final status `executed`.
