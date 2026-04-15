# Integration Rules

## API contract first
- Backend and frontend integration only through files in `shared/contracts/`.
- Do not break contract fields without bumping version in contract file.

## Contract update protocol
1. Create `chore/shared-*` branch.
2. Update contract file in `shared/contracts/`.
3. Both engineers review quickly.
4. Merge contract PR before dependent implementation PRs.

## Freeze windows
- Last 2 hours of hackathon:
  - No major refactors
  - Bug fixes only
  - No contract-breaking changes

## Fast smoke checks before merging
- Frontend: app builds and route loads
- Backend: `/health` responds with 200
- Contract: both sides still parse request/response payload
