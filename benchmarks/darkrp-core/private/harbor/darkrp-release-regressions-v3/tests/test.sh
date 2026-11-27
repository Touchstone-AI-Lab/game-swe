#!/bin/bash
# Stage the submission and collect GLuaTest results before public hooks can mutate them.
set -euo pipefail
mkdir -p /logs/verifier

EXPECTED=10
declare -a EXPECTED_CASES=(
  "The gamemode is loaded"
  "A: the arrested-player query API exists"
  "A: the arrested-player query API is self-consistent"
  "B: spawned ammo survives a missing physics object"
  "B: spawned weapon survives a missing physics object"
  "D: destroying a question by an unknown id does not error"
  "E: creating a job hands back the team number"
  "F: a shipment created with mixed case is found by its lower-case name"
  "F: a shipment created in lower case is found by a mixed-case name"
  "G: unrestricting a weapon with no argument tells the admin"
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
