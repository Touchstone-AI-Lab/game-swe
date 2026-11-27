#!/bin/bash
# Stage the submission and collect GLuaTest results before public hooks can mutate them.
set -euo pipefail
mkdir -p /logs/verifier

EXPECTED=12
declare -a EXPECTED_CASES=(
  "sentinel: the gamemode and its player-record API are loaded"
  "control: an ordinary balance is written down"
  "control: an ordinary name is written down"
  "A: a new player's cash and pay are not written into each other"
  "B: a balance of nothing is written down like any other"
  "C: money given to an absent player reaches the record read back"
  "D: a name change announces the name that was in use before it"
  "E: a name too short to identify anyone is refused"
  "F: a name nobody is using is reported as free"
  "G: an amount that is not a real number is refused, not rounded"
  "H: a name is looked up as written, not as a pattern"
  "I: looking someone up by nothing at all finds nobody"
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
