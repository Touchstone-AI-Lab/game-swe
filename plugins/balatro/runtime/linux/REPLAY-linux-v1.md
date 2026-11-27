# Replay scope: controlled-v1, halted partial batch

Use the source hashes in [the manifest](runtime-manifest-linux-v1.json). The
current state is halted after a confirmed transport truncation. Do not delete
`linux-halt.json`, edit old pins/artifacts, retry an unresolved action or run the
proposed component change to bypass this gate. This document records commands;
it does not grant new authentication, component or host permissions.

The measured host has WSL Ubuntu, Python 3.12, approved WSLg display, existing
fixed dependencies, a licensed independently authenticated Steam client and the
private authored pack snapshot. None is bundled here. Keep a foreground WSL
owner during long-running native operations. Do not install or upgrade from
these instructions. Commands below use Bash **inside WSL**, not PowerShell.

## Environment for read-only verification

```bash
cd /mnt/c/Touchstone/Balatro-PoC/staging/swe-game-balatro-linux
export PATH=/home/psy/balatro-linux-v1/venv/bin:/usr/bin:/bin
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export RHENIUM_ROOT="$PWD"
export RHENIUM_STATE_DIR=/home/psy/balatro-linux-v1/state
export RHENIUM_BENCHMARK_PATH=/home/psy/balatro-linux-v1/state/packs/authored-v02-snapshot-v2
export PYTHONPATH="$PWD/src:$PWD/plugins/balatro/src:$PWD/providers/steam/src"
rhenium runtime verify balatro/balatro-linux-17459173-controlled-v1
```

The verify route is read-only and requires no Steam login or CEF endpoint. Its
original receipt is `controlled-managed-verify-v1` under local `.test-state`.
If bytes or recipe differ, stop; do not rewrite its expected hash.

## Historical acquisition and smoke commands

The approved provider preparation used the following operator-only environment
variable containing a **path**, never a token. Its profile points to private
existing login state. Do not print that file or copy it into a submission.

```bash
export RHENIUM_STEAM_OFFICIAL_PROFILE=/home/psy/balatro-linux-v1/state/providers/steam/controlled-official-v1/profile.json
rhenium runtime prepare balatro/balatro-linux-17459173-controlled-v1 --account linux-official-v1
unset RHENIUM_STEAM_OFFICIAL_PROFILE
```

The original fresh preparation and source hashes are preserved in
`.test-state/linux-runtime-v1/controlled-managed-prepare-v1`. Running `prepare`
against an existing cache is not evidence of another fresh acquisition. Do not
remove the cache to manufacture a rerun; any new artifact gets a new version.

The original current-source smoke used:

```bash
python -m rhenium_balatro.linux_operator smoke \
  --pack "$RHENIUM_BENCHMARK_PATH" \
  --state "$RHENIUM_STATE_DIR/packs/balatro/core" \
  --cache "$RHENIUM_STATE_DIR/cache/plugins/balatro/core" \
  --artifact "$PWD/.test-state/linux-runtime-v1/controlled-managed-prepare-v1/stdout.txt" \
  --windows-powershell /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
```

It refuses an existing binding or halt. This command must **not** be rerun in
the current halted state. A future approved runtime requires its own reviewed
operator binding/state, current-host smoke and source record.

## Historical maintenance controls

The exact versioned driver materializes/seals each reviewed gold/base and calls
the real core CLI. It stops on unexpected behavior, infrastructure failure or
incomplete execution. It never classifies by candidate label. The two recorded
batches selected growth first, then the other nine tasks:

```bash
python plugins/balatro/runtime/linux/validate_controls_v1.py \
  --repo "$PWD" --pack "$RHENIUM_BENCHMARK_PATH" --state "$RHENIUM_STATE_DIR" \
  --round 1 --tasks growth-v2

python plugins/balatro/runtime/linux/validate_controls_v1.py \
  --repo "$PWD" --pack "$RHENIUM_BENCHMARK_PATH" --state "$RHENIUM_STATE_DIR" \
  --round 1 --tasks reversible-hand-limit-v1 seeded-effect-stream-v1 \
  bounded-generator-v2 deck-removal-consistency-v2 live-joker-adjacency-v2 \
  isolated-card-wear-v2 durable-charge-v2 shop-price-coherence-v2 pack-choice-commit-v2
```

These are maintenance-only commands, not anonymous model-attempt instructions.
They are blocked now. The stock `scripts/score-exam` wrapper requires Nix/devenv
and has not been validated on this host. Do not substitute a wrapper shim or
claim these direct core-CLI results as anonymous-wrapper proof.

## Checks and evidence preservation

Targeted tests can run without launching a game:

```bash
python -m pytest plugins/balatro/tests providers/steam/tests plugins/contract/tests
bash -n providers/steam/src/rhenium_steam/interactive-launch-v1.sh
git diff --check
```

The contract tests require their exact tracked HEAD fixtures; do not replace
them with invented expected output. Full checks and their failures/unavailable
tools are listed in [the report](LINUX-RUNTIME-REPORT-v1.md). Proposed transport
Lua tests exercise doubles only and do not authorize component/game execution.

Every new operation creates a unique evidence directory. Preserve old failure,
halt, source capsule, private checkpoint and receipt hashes. Never export raw
logs, game content, saves, profile files or private assertions to public attempts.
