# Replay: controlled-v2 with visible window profile v2

This is a maintenance workflow for the licensed, source-reviewed WSL2 host. It
does not grant authentication, component, host-setting or container permissions.
Use the final hashes in `runtime-manifest-linux-v2.json` and the measured outcomes
in `validation-linux-runtime-v2.json`. Earlier v1 receipts keep their original
meaning. Preserve both the original transport halt and the first v2 timing halt.

Commands below are Bash inside WSL Ubuntu. The existing Python 3.12 environment,
fixed dependencies, licensed provider cache, independent official Steam login,
native authored pack and WSLg are prerequisites; they are not bundled. Keep a
foreground WSL owner. Do not install packages or weaken process protection to
replay. Native game execution is serial and visible, gamespeed=1, FAST=0 and
HEADLESS=0, with process-local null audio and an ordinary 800×600 window.

## Verify prepared content

```bash
cd /mnt/c/Touchstone/Balatro-PoC/staging/swe-game-balatro-linux
export PATH=/home/psy/balatro-linux-v1/venv/bin:/usr/bin:/bin
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export RHENIUM_ROOT="$PWD"
export RHENIUM_STATE_DIR=/home/psy/balatro-linux-v1/state
export RHENIUM_BENCHMARK_PATH="$RHENIUM_STATE_DIR/packs/authored-v02-snapshot-v3"
export PYTHONPATH="$PWD/src:$PWD/plugins/balatro/src:$PWD/providers/steam/src"
rhenium runtime verify balatro/balatro-linux-17459173-controlled-v2
```

Verification is read-only. It checks the immutable artifact and approved derived
transport bytes; it does not invoke Steam. Stop on a mismatch. Do not repin or
overwrite a receipt to accept it. The binding is under
`packs/balatro/core/linux-controlled-v2-window-v2` in operator state and requires
its matching normal six-case smoke.

## Acquisition and initial binding record

The recorded preparation command was:

```bash
export RHENIUM_STEAM_OFFICIAL_PROFILE="$RHENIUM_STATE_DIR/providers/steam/controlled-official-v1/profile.json"
rhenium runtime prepare balatro/balatro-linux-17459173-controlled-v2 --account linux-official-v1
unset RHENIUM_STEAM_OFFICIAL_PROFILE
```

The profile is private. Never print it or copy it into a submission. The first
v2 acquisition did not exit normally and remains incomplete. The successful
prepare consumed an explicitly reverified cache from an earlier complete,
normally exited official acquisition. See `TRANSPORT-IMPLEMENTATION-v2.md` and
the provider's `CONTROLLED-CONSOLE.md`. Reusing an existing artifact is not a
new fresh-acquisition experiment. Do not delete caches to manufacture one.

The final source binding was created by:

```bash
python -m rhenium_balatro.linux_operator smoke \
  --pack "$RHENIUM_BENCHMARK_PATH" \
  --state "$RHENIUM_STATE_DIR/packs/balatro/core/linux-controlled-v2-window-v2" \
  --cache "$RHENIUM_STATE_DIR/cache/plugins/balatro/core" \
  --artifact "$PWD/.test-state/linux-runtime-v2/managed-prepare-v2-recovery-v1/stdout.json" \
  --windows-powershell /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
```

This command deliberately refuses an existing binding or halt. It documents the
initial binding, not an instruction to overwrite it. A changed implementation
needs a separately versioned binding and new smoke. The current final binding
can be reused for new sealed, reviewed submissions with the same verified inputs.

## Full maintenance controls

```bash
python plugins/balatro/runtime/linux/validate_controls_v1.py \
  --repo "$PWD" --pack "$RHENIUM_BENCHMARK_PATH" \
  --state "$RHENIUM_STATE_DIR" --round 1
```

The source-hashed driver creates a unique batch directory, materializes and seals
each reviewed control, and invokes the actual core `rhenium run` CLI with the
full profile. It stops on unexpected outcomes or incomplete execution. Each base
must complete its required cases and fail for behavior; a timeout cannot count.
The current driver writes under `platform-controls-v2-window-v2` in state.
The final measured batch is one independent gold/base suite per task, not three
Linux repetitions or a model experiment. Additional mutations were not rerun.

These are operator maintenance commands, not anonymous exam instructions. The
stock `scripts/score-exam` Nix/devenv wrapper is unvalidated on this host. No shim
or direct-run substitution is claimed as evidence for that wrapper.

## Initialized-load capability repeats

Execute the following command serially three times; the probe creates a fresh
operation directory each time:

```bash
python plugins/balatro/runtime/linux/probe_save_v1.py \
  --prepared "$PWD/.test-state/linux-runtime-v2/managed-prepare-v2-recovery-v1/stdout.json" \
  --pack "$RHENIUM_BENCHMARK_PATH" \
  --state "$RHENIUM_STATE_DIR/save-validation-window-v2" \
  --windows-powershell /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
  --controlled-runtime
```

All six original cases remain required. Each repeat uses real discard/play/save,
normal quit, a new PID/nonce/save directory, complete independent seeded startup,
one load request with its full response, restored fields and subsequent real
play. The original checkpoint must remain byte-identical. No candidate is part
of this capability probe. Blank-MENU direct loading remains outside the claim.

## Transport and code checks

The fixed native LuaSocket test loads libraries, not the game. Use a new output
filename on every run; the tool refuses to overwrite one:

```bash
python plugins/balatro/runtime/linux/socket_loopback_v1.py \
  --artifact "$RHENIUM_STATE_DIR/cache/runtimes/balatro/balatro-linux-17459173-controlled-v2/derived-tree-v2" \
  --output "$RHENIUM_STATE_DIR/socket-replay-$(date -u +%Y%m%dT%H%M%SZ).json"

python -m pytest -o addopts= -q -p no:cacheprovider \
  plugins/balatro/tests providers/steam/tests \
  tests/test_plugin_architecture.py tests/test_auth_runtime.py
git diff --check
```

The related pytest command is scoped. It does not replace the full required
repository gates, whose failures and unavailable tools are listed in the report.
Wheel inspection and extracted-wheel read-only binding verification have their
own receipts; they must not be called an installed-wheel full engine rerun.

Every new result retains source, environment, harness, task and candidate
identities. Public summaries contain hashes and outcomes only. Keep raw logs,
private assertions, game files, client state, checkpoints and credentials out of
public packages and source control. No commit, push or PR is part of this work.
