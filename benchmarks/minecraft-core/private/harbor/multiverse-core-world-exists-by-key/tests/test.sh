#!/usr/bin/env bash
set -uo pipefail

LOG_ROOT="${LOGS_DIR:-/logs}/verifier"
mkdir -p "$LOG_ROOT"
export GCB_LOGS="$LOG_ROOT"

python3 /tests/verify.py 2>&1 | tee "$LOG_ROOT/verifier.log"
status=${PIPESTATUS[0]}

# verify.py writes the reward itself; a crash before that point fails closed.
if [ ! -s "$LOG_ROOT/reward.txt" ]; then
  echo 0 > "$LOG_ROOT/reward.txt"
fi
echo "verifier_exit=$status reward=$(cat "$LOG_ROOT/reward.txt")"
exit 0
