# Branching Strategy (No-Conflict Fast Flow)

## Branch naming
- `feat/frontend-<task>`
- `feat/backend-core-<task>`
- `feat/backend-systems-<task>`
- `feat/backend-<task>` (legacy fallback)
- `chore/shared-<task>`

## Rules
1. No direct commits to `main`.
2. Engineer A only opens `feat/frontend-*` unless working on a shared lock.
3. Backend Engineer 1 (core intelligence) uses `feat/backend-core-*`.
4. Backend Engineer 2 (systems and production) uses `feat/backend-systems-*`.
5. `feat/backend-*` is legacy and only enforces broad backend/frontend boundaries.
6. Shared changes must be isolated in `chore/shared-*`.
7. Keep PRs small: target under 250 lines changed where possible.

## CI enforcement
- Workflow: `.github/workflows/ownership-boundary-check.yml`
- Script: `scripts/check-boundaries.sh`
- The check fails PRs when branch changes violate ownership lane rules.

## Merge cadence for 24h sprint
- Sync checkpoint every 2 hours:
  - Rebase active branch on `main`
  - Resolve conflicts immediately
  - Merge green PRs quickly

## Commit convention
- `feat(frontend): add reasoning trace panel shell`
- `feat(backend): add permission gate queue model`
- `chore(shared): update chat contract v0`
