# Branching Strategy (No-Conflict Fast Flow)

## Branch naming
- `feat/frontend-<task>`
- `feat/backend-<task>`
- `chore/shared-<task>`

## Rules
1. No direct commits to `main`.
2. Engineer A only opens `feat/frontend-*` unless working on a shared lock.
3. Engineer B only opens `feat/backend-*` unless working on a shared lock.
4. Shared changes must be isolated in `chore/shared-*`.
5. Keep PRs small: target under 250 lines changed where possible.

## Merge cadence for 24h sprint
- Sync checkpoint every 2 hours:
  - Rebase active branch on `main`
  - Resolve conflicts immediately
  - Merge green PRs quickly

## Commit convention
- `feat(frontend): add reasoning trace panel shell`
- `feat(backend): add permission gate queue model`
- `chore(shared): update chat contract v0`
