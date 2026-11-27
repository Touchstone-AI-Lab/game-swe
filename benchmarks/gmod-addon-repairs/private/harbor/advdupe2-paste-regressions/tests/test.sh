#!/bin/bash
# Stage the addon submission and collect GLuaTest results before public hooks can mutate them.
set -euo pipefail
mkdir -p /logs/verifier

EXPECTED=11
declare -a EXPECTED_CASES=(
  "sentinel: the addon and its duplicator are loaded"
  "preserved: a copied prop pastes at the requested place, frozen"
  "A: a prop saved at a larger scale pastes with a matching physics size"
  "B: a piece that fails to paste leaves nothing behind"
  "C: props a player pasted are released by unfreeze-all"
  "D: a pasted rope counts against the rope limit"
  "D: the rope limit is enforced when pasting"
  "preserved: a pasted weld still counts as a constraint"
  "E: file names lose the spaces around separators and dots"
  "preserved: file names keep their other characters readable"
  "preserved: an encoded dupe decodes to the same contraption"
)
[ "${#EXPECTED_CASES[@]}" -eq "$EXPECTED" ]

ADDON=advdupe2
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
