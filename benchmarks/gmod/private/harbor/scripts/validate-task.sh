#!/usr/bin/env bash
# Local two-way validation for one task, mirroring Harbor's separate-verifier
# flow without needing the Harbor CLI:
#
#   nop run     starter workspace only        -> must score reward 0
#   oracle run  solution/solve.sh applied     -> must score reward 1, with the
#                                                real Dedicated Server having run
#
# The verifier image is built from the task's tests/ directory on top of the
# locally prepared gcb-gmod-addons-verifier runtime, and runs without network.
# Results are written outside the benchmark pack.
#
# Usage: scripts/validate-task.sh <task-dir> <results-dir>
set -uo pipefail

TASK="$(cd "${1:?usage: validate-task.sh <task-dir> <results-dir>}" && pwd)"
OUT_ROOT="${2:-${RHENIUM_GMOD_VALIDATION_DIR:-}}"
[ -n "$OUT_ROOT" ] || {
  echo "results-dir or RHENIUM_GMOD_VALIDATION_DIR is required" >&2
  exit 1
}
TASK_ID="$(basename "$TASK")"
OUT="$(mkdir -p "$OUT_ROOT" && cd "$OUT_ROOT" && pwd)/$TASK_ID"
case "$OUT" in
  "$(cd "$TASK/../../.." && pwd)"/*)
    echo "results-dir must be outside the benchmark pack" >&2
    exit 1
    ;;
esac
IMAGE="gcb-gmod-harbor-validate-$TASK_ID:local"

echo "== building verifier image for $TASK_ID"
docker build --quiet --tag "$IMAGE" "$TASK/tests" >/dev/null || {
  echo "verifier image build failed; prepare gcb-gmod-addons-verifier first" >&2
  exit 1
}

run_side() { # <side>
  local side="$1"
  rm -rf "${OUT:?}/$side"
  mkdir -p "$OUT/$side/addon" "$OUT/$side/logs"
  cp -a "$TASK/environment/addon/." "$OUT/$side/addon/"
  if [ "$side" = "oracle" ]; then
    docker run --rm --network=none \
      -v "$TASK/solution:/solution:ro" \
      -v "$OUT/$side/addon:/app/addon" \
      "$IMAGE" bash /solution/solve.sh > "$OUT/$side/solve.log" 2>&1 || {
      echo "$side: solve.sh failed" >&2
      return
    }
  fi
  docker run --rm --network=none \
    -v "$OUT/$side/addon:/app/addon:ro" \
    -v "$OUT/$side/logs:/logs" \
    "$IMAGE" bash /tests/test.sh > "$OUT/$side/run.log" 2>&1
  echo "$side: reward=$(cat "$OUT/$side/logs/verifier/reward.txt" 2>/dev/null || echo missing)"
}

run_side nop
run_side oracle

# Logs are written by root inside the container; hand them back to the caller.
docker run --rm --network=none -v "$OUT:/out" "$IMAGE" \
  chown -R "$(id -u):$(id -g)" /out >/dev/null 2>&1 || true
docker image rm "$IMAGE" >/dev/null 2>&1 || true

nop=$(cat "$OUT/nop/logs/verifier/reward.txt" 2>/dev/null || echo missing)
oracle=$(cat "$OUT/oracle/logs/verifier/reward.txt" 2>/dev/null || echo missing)
server=$(grep -c '"real_gmod_server_ran": true' "$OUT/oracle/logs/verifier/result.json" 2>/dev/null || true)
echo "== summary: nop=$nop (want 0) oracle=$oracle (want 1) oracle_real_server_ran=${server:-0} (want 1)"

[ "$nop" = "0" ] && [ "$oracle" = "1" ] && [ "${server:-0}" = "1" ]
