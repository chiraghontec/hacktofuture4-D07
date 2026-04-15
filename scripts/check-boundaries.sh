#!/usr/bin/env bash
set -euo pipefail

# Prevent accidental cross-boundary edits in feature branches.
branch_name="$(git rev-parse --abbrev-ref HEAD)"
changed_files="$(git diff --name-only origin/main...HEAD || true)"

if [[ "$branch_name" == feat/frontend-* ]]; then
  illegal="$(echo "$changed_files" | grep -E '^backend/|^infra/|^shared/contracts/' || true)"
  if [[ -n "$illegal" ]]; then
    echo "Frontend branch contains backend/shared changes:"
    echo "$illegal"
    exit 1
  fi
fi

if [[ "$branch_name" == feat/backend-* ]]; then
  illegal="$(echo "$changed_files" | grep -E '^frontend/|^shared/contracts/' || true)"
  if [[ -n "$illegal" ]]; then
    echo "Backend branch contains frontend/shared changes:"
    echo "$illegal"
    exit 1
  fi
fi

echo "Boundary check passed for $branch_name"
