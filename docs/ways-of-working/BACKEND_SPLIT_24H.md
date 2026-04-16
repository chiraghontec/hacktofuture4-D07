# Backend Split for 2 Engineers (Skill-Aligned and Equal)

Goal: split backend execution into two equal ownership tracks with minimal overlap.

Branch mapping enforced by CI:
- Engineer 1: `feat/backend-core-<task>`
- Engineer 2: `feat/backend-systems-<task>`
- Shared/contract edits: `chore/shared-<task>`

## Engineer 1 (You: deep technical understanding, agent architecture)
Primary fit: core intelligence and safety semantics.

Ownership track:
- Controller kernel and orchestration flow
- Retrieval, reasoning, and execution swarm logic
- Three-tier memory behavior and Kairos dedup logic
- Permission policy logic and approval decision semantics
- Contract decisions for reasoning trace and tool-action payloads

Files owned first:
- backend/src/controller/**
- backend/src/swarms/**
- backend/src/memory/**
- backend/src/gates/permission_gate.py (decision logic)
- shared/contracts/chat.contract.json (only via shared branch)

## Engineer 2 (Teammate: systems, production, deployment)
Primary fit: reliability, runtime, integrations, and delivery.

Ownership track:
- FastAPI routes and API lifecycle
- SSE stream endpoint and connection stability
- Approval queue persistence path and action execution wiring
- Tool registry adapters (GitHub/Slack/Jira mocks)
- Audit logging, health checks, failure handling
- Docker, runtime env, local deployment workflow, Milvus operations

Files owned first:
- backend/app/**
- backend/src/tools/**
- backend/src/gates/** (queue and API-side integration)
- backend/tests/**
- infra/**
- scripts/**

## Equal Workload Definition
Use feature points to keep load balanced (target 50/50):
- P0 feature = 3 points
- P1 feature = 2 points
- P2 feature = 1 point

Both engineers should carry 8 to 10 points in first 18 hours.

## Feature Allocation (POC-Compliant)
Engineer 1:
1. [x] Controller pipeline with swarm chaining (P0, 3)
2. [x] Retrieval + reasoning output schema and citation model (P0, 3)
3. [x] Permission decision policy rules for HITL (P1, 2)
4. [x] Memory summary and dedup pass API for Kairos-lite (P1, 2)
Total: 10

Engineer 2:
1. [x] FastAPI chat + stream endpoints and response contracts (P0, 3)
2. [ ] SSE event delivery, reconnect-safe behavior, timeout handling (P0, 3)
3. [x] Approval queue execution path + mock tool invocation hooks (P1, 2)
4. [~] Structured audit logs + health checks + docker runtime hardening (P1, 2)
Total: 10

Progress note (2026-04-16):
- Implemented backend endpoints now include chat, transcript, stream, ingestion, and approval APIs.
- Contract updates for ingestion and approval are complete in `shared/contracts/chat.contract.json`.
- Groq-first integration slice completed across retrieval, reasoning, and execution swarms.
- Trace payloads now expose richer metadata (`confidence_breakdown`, `reasoning_steps`, `evidence_scores`, structured action details).
- Backend regression baseline currently: `31 passed` in backend test suite.
- SSE is not done yet beyond baseline endpoint streaming; reconnect-safe semantics, heartbeat, and timeout handling remain pending.
- Remaining backend hardening is mainly reliability behavior (SSE reliability, retries/timeouts, and final runtime polish).

## Integration Contract Between Both
- Engineer 1 outputs trace events in canonical shape.
- Engineer 2 streams those events over SSE without shape mutation.
- Any schema change goes through shared contract PR first.

## 24-Hour Backend Timeline
Hour 0-2:
- [x] Engineer 1: controller flow skeleton + swarm interfaces
- [x] Engineer 2: API skeleton + health + chat route baseline

Hour 2-8:
- [x] Engineer 1: retrieval and reasoning composition + source citation model
- [ ] Engineer 2: SSE stream endpoint reliability and API error envelopes

Hour 8-14:
- [x] Engineer 1: permission policy rules + memory hooks
- [x] Engineer 2: approval queue API + tool registry wiring

Hour 14-20:
- [x] Engineer 1: Kairos-lite dedup and reasoning quality improvements
- [~] Engineer 2: audit logging, reliability checks, docker and Milvus validation

Hour 20-24:
- [~] Both: bug fixing, smoke tests, demo hardening, no schema-breaking changes

## Conflict Prevention Rules for Backend Pair
1. Engineer 1 should not edit backend/app except interface signatures.
2. Engineer 2 should not edit backend/src/swarms logic except integration adapters.
3. Shared files are lock-based for 20 minutes max:
- backend/src/gates/permission_gate.py
- shared/contracts/chat.contract.json
4. Merge backend branches every 90 minutes.
