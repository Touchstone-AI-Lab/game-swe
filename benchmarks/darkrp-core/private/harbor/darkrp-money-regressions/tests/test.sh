#!/bin/bash
# Stage the submission and collect GLuaTest results before public hooks can mutate them.
set -euo pipefail
mkdir -p /logs/verifier

EXPECTED=9
declare -a EXPECTED_CASES=(
  "sentinel: the gamemode and its money API are loaded"
  "control: a whole amount larger than the wallet is not affordable"
  "A: an amount just above the wallet is not affordable"
  "B: the wallet notification reports the balance before the change"
  "C: a very large money bag still holds a positive amount"
  "D: money a player dropped is recognised as money"
  "E: a wallet is unharmed by an amount that is not a number"
  "F: a limit of zero lets a player keep placing the thing"
  "G: paying another player moves the money to that player"
)
[ "${#EXPECTED_CASES[@]}" -eq "$EXPECTED" ]

GMOD_ROOT=/home/steam/gmodserver
SERVER_ROOT="$GMOD_ROOT/garrysmod"
OVERRIDE=/home/steam/garrysmod_override
RUNNER="$SERVER_ROOT/addons/gluatest/lua/gluatest/runner/runner.lua"
HARNESS_ROOT="$SERVER_ROOT/addons/gluatest/lua/gluatest"

rm -rf "$OVERRIDE"
mkdir -p "$OVERRIDE/gamemodes" "$OVERRIDE/lua/tests/gcb_suite"
cp -a /app/darkrp "$OVERRIDE/gamemodes/darkrp"
cp /tests/suite.lua "$OVERRIDE/lua/tests/gcb_suite/suite.lua"

NONCE=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
HARNESS_SHA256=$(python3 /tests/trusted_collector.py patch "$RUNNER" "$NONCE")

# The pinned GLuaTest entrypoint appends "m" to TIMEOUT. Two minutes is longer
# than the suite's bounded async work and shorter than every outer evaluator limit.
export GAMEMODE=darkrp MAP=gm_construct TIMEOUT=2
set +e
"$GMOD_ROOT/entrypoint.sh" > /logs/verifier/server.log 2>&1
status=$?
set -e

declare -a collector_cases=()
for name in "${EXPECTED_CASES[@]}"; do
  collector_cases+=(--case "$name")
done
python3 /tests/trusted_collector.py collect \
  --server-log /logs/verifier/server.log \
  --clean-exit "$SERVER_ROOT/data/gluatest_clean_exit.txt" \
  --debug-log "$GMOD_ROOT/debug.log" \
  --harness-root "$HARNESS_ROOT" \
  --harness-sha256 "$HARNESS_SHA256" \
  --status "$status" \
  --nonce "$NONCE" \
  --result /logs/verifier/result.json \
  --reward /logs/verifier/reward.txt \
  "${collector_cases[@]}"
exit 0
