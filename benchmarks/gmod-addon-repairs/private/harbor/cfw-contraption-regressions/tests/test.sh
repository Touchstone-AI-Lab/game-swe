#!/bin/bash
# Stage the addon submission and collect GLuaTest results before public hooks can mutate them.
set -euo pipefail
mkdir -p /logs/verifier

EXPECTED=10
declare -a EXPECTED_CASES=(
  "sentinel: the framework is loaded and tracking entities"
  "A: a parented group's total mass follows a member's new mass"
  "preserved: a welded contraption's total mass follows a member's new mass"
  "B: a parent that only vetoes children can refuse one"
  "preserved: a parent with both hooks can refuse or accept children"
  "C: something parented to a player stays out of contraptions"
  "C: something parented to an NPC stays out of contraptions"
  "C: something parented to a nextbot stays out of contraptions"
  "D: joining two bones of one ragdoll creates no contraption"
  "preserved: welding two props makes one contraption until the weld goes"
)
[ "${#EXPECTED_CASES[@]}" -eq "$EXPECTED" ]

ADDON=cfw
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
