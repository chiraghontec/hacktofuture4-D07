# Ownership Map (2-Engineer Setup)

Goal: prevent merge conflicts by assigning strict ownership boundaries.

## Engineer A (Frontend + UX)
- Owns `frontend/**`
- Owns chat UX, reasoning trace UI, approval modal, loading/error states
- Can update `shared/contracts/**` only through contract PR process

## Engineer B (Backend + Agents)
- Owns `backend/**`
- Owns FastAPI routes, controller kernel, swarms, permission gate, memory
- Can update `shared/contracts/**` only through contract PR process

## Shared Zone (High-risk for conflicts)
- `shared/contracts/**`
- `infra/**`
- `README.md`
- `docs/ways-of-working/**`

Rule for shared zone: only one engineer edits at a time on a short-lived branch.

## Daily Lock Strategy (24h hackathon)
- Every 2 hours, announce lock ownership in chat.
- Lock expires after 20 minutes if no commit is pushed.
- Never keep a shared file lock while coding unrelated tasks.
