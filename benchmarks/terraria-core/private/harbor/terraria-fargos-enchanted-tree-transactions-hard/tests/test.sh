#!/usr/bin/env bash
set -uo pipefail

export GCB_SUBMISSION="${GCB_SUBMISSION:-/workspace/fargos-mutant}"
mkdir -p /logs/verifier
python3 /tests/verify.py 2>&1 | tee /logs/verifier/verifier.log
status=${PIPESTATUS[0]}
if [[ "$status" -eq 0 ]]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
echo "verifier_exit=$status reward=$(cat /logs/verifier/reward.txt)"
exit 0
