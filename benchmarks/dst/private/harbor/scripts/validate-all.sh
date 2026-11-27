#!/usr/bin/env bash
# Run validate-task.sh for every Don't Starve Together Harbor task.
# Usage: scripts/validate-all.sh <results-dir>
set -uo pipefail

SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARBOR_ROOT="$(dirname "$SCRIPTS")"
OUT="${1:-${RHENIUM_DST_VALIDATION_DIR:-}}"
[ -n "$OUT" ] || {
  echo "results-dir or RHENIUM_DST_VALIDATION_DIR is required" >&2
  exit 1
}

failures=0
for task_toml in "$HARBOR_ROOT"/*/task.toml; do
  task="$(dirname "$task_toml")"
  bash "$SCRIPTS/validate-task.sh" "$task" "$OUT" || failures=$((failures + 1))
done
echo "== control failures: $failures"
[ "$failures" -eq 0 ]
