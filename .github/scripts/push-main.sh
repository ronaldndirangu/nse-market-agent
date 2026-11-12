#!/usr/bin/env bash
# Rebase local commits onto the latest main and push, retrying when another workflow pushed first.
set -uo pipefail
for attempt in 1 2 3; do
  if ! git pull --rebase -q origin main; then
    git rebase --abort 2>/dev/null || true
    echo "::error::Local data commits conflict with origin/main; rerun this workflow."
    exit 1
  fi
  if git push -q origin HEAD:main; then
    exit 0
  fi
  echo "::warning::Push attempt $attempt failed; retrying."
  sleep $((attempt * 15))
done
echo "::error::Could not push to main after 3 attempts."
exit 1
