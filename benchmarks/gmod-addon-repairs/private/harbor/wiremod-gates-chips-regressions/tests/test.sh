#!/bin/bash
# Stage the addon submission and collect GLuaTest results before public hooks can mutate them.
set -euo pipefail
mkdir -p /logs/verifier

EXPECTED=14
declare -a EXPECTED_CASES=(
  "sentinel: the addon, its gates and its chips are loaded"
  "A: a derivative gate drops back to zero once its input settles"
  "A: vector and angle derivative gates never report an infinite rate"
  "preserved: an ordinary gate still follows its inputs at once"
  "B: outputs added in front of existing ones keep a consistent order"
  "preserved: a chip's outputs carry the values it assigns"
  "C: unlimited mode lets a loop use the raised per-tick budget"
  "preserved: the normal per-tick budget still stops a runaway loop"
  "D: a timer still exists while its last run executes"
  "preserved: a finished timer is gone afterwards"
  "E: hologram functions return neutral values when there is no hologram"
  "preserved: an existing hologram reports its own properties"
  "F: calling a function by name as a statement works"
  "preserved: calling a function by name for its value works"
)
[ "${#EXPECTED_CASES[@]}" -eq "$EXPECTED" ]

ADDON=wire
GMOD_ROOT=/home/steam/gmodserver
SERVER_ROOT="$GMOD_ROOT/garrysmod"
OVERRIDE=/home/steam/garrysmod_override
RUNNER="$SERVER_ROOT/addons/gluatest/lua/gluatest/runner/runner.lua"
HARNESS_ROOT="$SERVER_ROOT/addons/gluatest/lua/gluatest"

# The addon is installed as a legacy filesystem addon next to GLuaTest; the private
# suite is the only test project on the Lua search path.
rm -rf "$OVERRIDE"
mkdir -p "$OVERRIDE/addons" "$OVERRIDE/lua/tests/gcb_suite"
cp -a "/app/$ADDON" "$OVERRIDE/addons/$ADDON"
cp /tests/suite.lua "$OVERRIDE/lua/tests/gcb_suite/suite.lua"

NONCE=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
HARNESS_SHA256=$(python3 /tests/trusted_collector.py patch "$RUNNER" "$NONCE")

# The pinned GLuaTest entrypoint appends "m" to TIMEOUT. Two minutes is longer
# than the suite's bounded async work and shorter than every outer evaluator limit.
export GAMEMODE=sandbox MAP=gm_construct TIMEOUT=2
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
