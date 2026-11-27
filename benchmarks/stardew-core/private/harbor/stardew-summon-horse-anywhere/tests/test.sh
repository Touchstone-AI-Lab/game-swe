#!/bin/bash
# Harbor verifier: build the agent's mod tree, compile the private suite into the
# GCB harness, boot the real game headless (SMAPI + xvfb/llvmpipe), and gate the
# reward exclusively on the harness's JSON verdict.
#
# Inherited rule from the DarkRP suite: exit codes gate NOTHING. Reward is 1 only if
# the verdict file exists, parses, passed == EXPECTED, failed == 0, and fatal is null.
set -uo pipefail
mkdir -p /logs/verifier

EXPECTED=3
SUITE=/tests/SuiteSummon.cs
MOD_PROJECT=/app/mod/SummonAnywhere/SummonAnywhere.csproj
MOD_DEPLOY_NAME=SummonAnywhere
GAME_PATH="${GAME_PATH:-/opt/stardew}"
RESULT=/logs/verifier/result.json

# --- 1. Build the submission (static layer: it must compile). -------------------
# NuGet was warmed at image build; --no-restore keeps this offline. ModBuildConfig
# deploys the built mod into $GAME_PATH/Mods automatically.
if ! dotnet build "$MOD_PROJECT" -c Release --no-restore \
      -p:GamePath="$GAME_PATH" \
      > /logs/verifier/build-submission.log 2>&1; then
  echo "submission build failed (see build-submission.log)"
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi
# Deploy the built mod ourselves: the skeleton is a plain csproj, not ModBuildConfig.
rm -rf "$GAME_PATH/Mods/$MOD_DEPLOY_NAME"
mkdir -p "$GAME_PATH/Mods/$MOD_DEPLOY_NAME"
if ! cp /app/mod/SummonAnywhere/bin/Release/SummonAnywhere.dll \
       /app/mod/SummonAnywhere/manifest.json \
       "$GAME_PATH/Mods/$MOD_DEPLOY_NAME/" 2>/dev/null; then
  echo "build succeeded but SummonAnywhere.dll / manifest.json were not produced"
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

# --- 2. Compile the harness with this task's private suite. ---------------------
STAGE=$(mktemp -d)
cp -a /opt/gcb/harness/GcbHarness "$STAGE/GcbHarness"
cp "$SUITE" "$STAGE/GcbHarness/TaskSuite.cs"
if ! dotnet build "$STAGE/GcbHarness/GcbHarness.csproj" -c Release --no-restore \
      -p:GamePath="$GAME_PATH" \
      > /logs/verifier/build-harness.log 2>&1; then
  echo "harness build failed (verifier bug, not the submission)"
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi
mkdir -p "$GAME_PATH/Mods/GcbHarness"
cp "$STAGE/GcbHarness/bin/Release/GcbHarness.dll" \
   "$STAGE/GcbHarness/manifest.json" \
   "$GAME_PATH/Mods/GcbHarness/"

# --- 3. Per-task mod config, if any. --------------------------------------------
if [ -f /tests/mod-config.json ]; then
  cp /tests/mod-config.json "$GAME_PATH/Mods/$MOD_DEPLOY_NAME/config.json"
fi

# --- 4. Boot the game headless and run the suite. -------------------------------
export GCB_MODE=run-suite GCB_RESULT_PATH="$RESULT"
GCB_SAVE_NAME="$(cat /opt/gcb/save-name.txt)"
export GCB_SAVE_NAME
timeout "${GCB_BOOT_TIMEOUT:-600}" \
  xvfb-run -a -s '-screen 0 1280x720x24 +extension GLX' \
  "$GAME_PATH/StardewValley" > /logs/verifier/game.log 2>&1
status=$?
echo "game_exit=$status"
cp "$HOME/.config/StardewValley/ErrorLogs/SMAPI-latest.txt" /logs/verifier/smapi.log 2>/dev/null || true

# --- 5. Reward gate: the JSON verdict is the only authority. --------------------
python3 - "$RESULT" "$EXPECTED" <<'EOF'
import json, sys
path, expected = sys.argv[1], int(sys.argv[2])
reward = 0
try:
    with open(path) as f:
        v = json.load(f)
    ok = (v.get("fatal") is None
          and v.get("passed") == expected
          and v.get("failed") == 0)
    reward = 1 if ok else 0
    print(f"passed={v.get('passed')} failed={v.get('failed')} fatal={v.get('fatal')} expected={expected}")
    for case in v.get("cases", []):
        print(f"  [{'PASS' if case.get('Passed') else 'FAIL'}] {case.get('Name')}"
              + (f" -- {case.get('Error')}" if case.get('Error') else ""))
except Exception as ex:  # missing/corrupt verdict -> harness never finished -> 0
    print(f"no usable verdict: {ex}")
with open("/logs/verifier/reward.txt", "w") as f:
    f.write(f"{reward}\n")
EOF
exit 0
