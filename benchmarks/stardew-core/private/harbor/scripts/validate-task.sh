#!/bin/bash
# Local two-way validation for one task, mirroring Harbor's verifier flow:
#
#   base run    unmodified tree  -> must score reward 0, with the sentinel case
#                                   passing (else the harness itself is broken)
#   oracle run  solution applied -> must score reward 1
#
# Usage: scripts/validate-task.sh <task-dir> <image-tag> [results-dir]
set -uo pipefail

TASK="$(cd "${1:?usage: validate-task.sh <task-dir> <image>}" && pwd)"
IMAGE="${2:?image tag required}"
OUT="${3:-${RHENIUM_STARDEW_VALIDATION_DIR:-}}"
[ -n "$OUT" ] || {
  echo "results-dir or RHENIUM_STARDEW_VALIDATION_DIR is required" >&2
  exit 1
}
OUT="$(mkdir -p "$OUT" && cd "$OUT" && pwd)/$(basename "$TASK")"
NAME="sglang-omni-jaxan-gcbval"

run_side() { # <side> <extra setup command>
  local side="$1" setup="$2"
  mkdir -p "$OUT/$side"
  docker run --rm --name "$NAME-$side" \
    -v "$TASK/tests:/tests:ro" \
    -v "$TASK/solution:/solution:ro" \
    -v "$OUT/$side:/logs" \
    "$IMAGE" bash -c "$setup bash /tests/test.sh" \
    > "$OUT/$side/run.log" 2>&1
  local reward
  reward=$(cat "$OUT/$side/verifier/reward.txt" 2>/dev/null || echo "missing")
  echo "$side: reward=$reward"
}

echo "== validating $(basename "$TASK") with $IMAGE"
run_side base ""
run_side oracle "bash /solution/solve.sh && "

# Logs are written by root inside the container; hand them back to the invoking
# user so plain rsync/rm on the host keep working.
docker run --rm --name "$NAME-chown" -v "$OUT:/logs" "$IMAGE" \
  chown -R "$(id -u):$(id -g)" /logs >/dev/null 2>&1 || true

base=$(cat "$OUT/base/verifier/reward.txt" 2>/dev/null || echo missing)
oracle=$(cat "$OUT/oracle/verifier/reward.txt" 2>/dev/null || echo missing)
echo "== summary: base=$base (want 0) oracle=$oracle (want 1)"
echo "== case detail (base):";   grep -E '^\s+\[' "$OUT/base/run.log"   || tail -5 "$OUT/base/run.log"
echo "== case detail (oracle):"; grep -E '^\s+\[' "$OUT/oracle/run.log" || tail -5 "$OUT/oracle/run.log"

[ "$base" = "0" ] && [ "$oracle" = "1" ]
