#!/usr/bin/env bash
set -euo pipefail

# Prevent accidental cross-boundary edits in feature branches.
# Supports local execution and CI execution.
branch_name="${BRANCH_NAME:-$(git rev-parse --abbrev-ref HEAD)}"
base_ref="${BASE_REF:-origin/main}"

if ! git rev-parse --verify "$base_ref" >/dev/null 2>&1; then
  echo "Base ref '$base_ref' not found. Fetching remotes..."
  git fetch --all --prune >/dev/null 2>&1 || true
fi

changed_files="$(git diff --name-only "$base_ref"...HEAD || true)"

if [[ -z "$changed_files" ]]; then
  echo "No changed files detected between $base_ref and HEAD"
  exit 0
fi

print_illegal_and_exit() {
  local msg="$1"
  local illegal="$2"
  if [[ -n "$illegal" ]]; then
    echo "$msg"
    echo "$illegal"
    exit 1
  fi
}

contains_disallowed_files() {
  local allowed_regex="$1"
  echo "$changed_files" | grep -Ev "$allowed_regex" || true
}

if [[ "$branch_name" == feat/frontend-* ]]; then
  illegal="$(echo "$changed_files" | grep -E '^backend/|^infra/|^shared/contracts/' || true)"
  print_illegal_and_exit "Frontend branch contains backend/shared changes:" "$illegal"
fi

# Strict lane: backend architecture/intelligence owner
if [[ "$branch_name" == feat/backend-core-* ]]; then
  allowed='^(backend/src/controller/|backend/src/swarms/|backend/src/memory/|backend/src/gates/permission_gate.py$)'
  illegal="$(contains_disallowed_files "$allowed")"
  print_illegal_and_exit "Core backend lane contains out-of-lane changes:" "$illegal"
fi

# Strict lane: backend systems/production owner
if [[ "$branch_name" == feat/backend-systems-* ]]; then
  allowed='^(backend/app/|backend/src/tools/|backend/src/adapters/|backend/src/gates/(approval_queue.py|executor.py|__init__.py)$|backend/tests/|infra/|scripts/)'
  illegal="$(contains_disallowed_files "$allowed")"
  print_illegal_and_exit "Systems backend lane contains out-of-lane changes:" "$illegal"
fi

# Backward-compatible backend rule for older branch naming.
if [[ "$branch_name" == feat/backend-* && "$branch_name" != feat/backend-core-* && "$branch_name" != feat/backend-systems-* ]]; then
  illegal="$(echo "$changed_files" | grep -E '^frontend/|^shared/contracts/' || true)"
  print_illegal_and_exit "Backend branch contains frontend/shared changes:" "$illegal"
fi

echo "Boundary check passed for $branch_name"
