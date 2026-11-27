# Controlled native Linux runtime validation v2

All ten frozen v0.2 tasks completed one full gold/base pair through the actual
core `rhenium run` entry: **20 controls, 56 normally exited native game processes,
912 required outcomes**. Every gold passed; every base completed and was
rejected for behavior. There were no incomplete controls in this final batch.
Three separate initialized-load capability workflows also passed their original
six cases each, using six additional normally exited processes.

This validates the declared controlled, source-reviewed WSL2 execution scope.
It does **not** establish release/merge readiness: full repository checks still
have the failures and unavailable tools below. It is not an untrusted evaluation
host, a model study, three Linux rounds per candidate, or a portable deployment.

## Exact implementation and environment

- Branch `feat/balatro-linux-runtime`, base HEAD `e4f8326e388cae4fc4ee5066eff792a6ea7a3a72`; no new commit, push or PR.
- Existing Ubuntu 24.04 WSL2/WSLg, Linux x86_64, Python 3.12.3; native LÖVE 11.5,
  Lovely 0.9.0 and fixed SMODS 26.829.0. The licensed game archive from the pinned
  Windows Steam depot is loaded by native Linux LÖVE, not Wine or a game double.
- App 2379780, build 17459173, depot 2379781, manifest 3512319404653808464.
- Runtime `balatro/balatro-linux-17459173-controlled-v2`; immutable identity
  `sha256:33a9292ff56d88fea60070c659954d85b2dfabd2b45dcd47bc583c2b8f1c6e40`; fingerprint `e86485bd995e533dca9a32cabba96ee751a35e2185cb31c7d9e136d5e2852e28`.
- Session profile `visible-window800x600-null-audio-gs1-fast0-headless0-v2`. Serial, visible 800×600 window,
  gamespeed=1, FAST=0, HEADLESS=0. Process-local OpenAL null output. Mesa llvmpipe
  software rendering was observed; no driver repair or guaranteed FPS is claimed.
- Environment `1f4fac49547e187b9f48e68c3f77a61d7d162049c351e59fe761e4a07fc2f494`; harness `1417c682a810ea86bc072c65eeae8f6f0f0da32554b301130fd49e83f35351da`.
  Task and candidate identities are separate. Each pair shares the task and
  environment while retaining different sealed candidate bytes.
- Execution source freeze `0b869eab3b46f91f13d6bb274a52ffaa3bba9d949be53fc552d6c7fe6fe29ae3`. That execution capsule contains
  151 source/contract/manifest files. Every byte was rechecked after execution.

Only the operator-approved `send_raw` replacement changes third-party bytes, in
a new derived copy. The builder compares the complete original/derived trees
and executable modes, accepting exactly one changed file with the approved hash.
Original `.deps`, pins, controlled-v1 artifact and all old evidence remain intact.
The transport continues partial writes within a one-second budget; it neither
resends requests nor tolerates partial JSON. The 25-second RPC deadline is unchanged.

The first repaired-transport attempt then exposed an independent rendering
timing limit. Read-only frame/event measurements showed progressing animation
and repeated completion callbacks, with no second response ready at the deadline.
An ordinary 800×600 window, selected through the game's existing video callback
in each isolated process, completed the original flow. No state, lock, ready flag,
speed or assertion was changed. The unsuccessful 1280×720 pilot remains incomplete.
See [render diagnosis](RENDER-DIAGNOSIS-v1.md) and
[implementation/provenance](TRANSPORT-IMPLEMENTATION-v2.md).

The pre-freeze deck pilot was diagnostic gold only. The managed deck pair ran
inside the frozen ten-pair batch, rather than being represented as an earlier
separate managed pilot. This ordering difference is recorded and no cases or
required processes were omitted.

## Real engine results

| Task | Cases per control | Processes per control | Gold | Base |
| --- | ---: | ---: | --- | --- |
| growth-v2 | 18 | 1 | complete pass | complete behavior failure |
| reversible-hand-limit-v1 | 17 | 1 | complete pass | complete behavior failure |
| seeded-effect-stream-v1 | 27 | 4 | complete pass | complete behavior failure |
| bounded-generator-v2 | 75 | 5 | complete pass | complete behavior failure |
| deck-removal-consistency-v2 | 56 | 3 | complete pass | complete behavior failure |
| live-joker-adjacency-v2 | 20 | 2 | complete pass | complete behavior failure |
| isolated-card-wear-v2 | 19 | 1 | complete pass | complete behavior failure |
| durable-charge-v2 | 76 | 5 | complete pass | complete behavior failure |
| shop-price-coherence-v2 | 80 | 3 | complete pass | complete behavior failure |
| pack-choice-commit-v2 | 68 | 3 | complete pass | complete behavior failure |

All 56 PIDs and nonces were distinct. All processes used fresh save/mod paths,
normal exit code 0, unchanged staged inputs and the same observed visible video
profile. Temporary profiling mods were absent; original frozen task observers
were retained. No missing response, crash or forced cleanup counted as success.
The final six-case smoke passed against these exact inputs before the batch.

The batch took 3755.839 seconds. Summed game-process timings:
preparation 234.787, startup 492.760,
testing 2690.063, exit 56.189 seconds.
Recorded run directories total 573,795,976 bytes. These are
measured values for this host, not an optimization or throughput claim.

The three separate save probes each used real discard/play/save, normal quit,
new PID/nonce/save directory, complete independent LOADPREP seeded startup,
one load with its full successful response, matching restored fields and real
continued play. Original checkpoint hashes stayed unchanged. These are capability
flows without task candidates. They do not repair blank-MENU direct load or add
another durable-charge task.

A separate final-source deck-base framing diagnostic completed all 56 cases and
three processes with expected behavior failure. It recorded
229 complete HTTP responses, maximum
194,197 bytes, with no short read, dropped row or observer
error. It is excluded from the 20 final controls. Native fixed-library LuaSocket
checks independently passed small, partial-write large and bounded nonreading
peer cases; no game is loaded by those socket tests.

## Acquisition and preserved failures

The first v2 preparation completed the fixed download but the official client
required forced termination (exit 143). It remains incomplete. No failed receipt
was promoted. An explicit provider cache-reuse action verified the earlier
normally exited acquisition `19ba5da56c0647f4819e5e47e15faef6`, its exact source
bytes and retained failure receipts. Subsequent actual `runtime prepare` consumed
that proven provider cache, completed in 10.718 seconds and passed read-only verify.
Reuse launched no client and issued no new download command.

The original truncation halt and first v2 timing halt were preserved. Additional
incomplete read-only diagnostics and the 1280×720 failure remain recorded. One
early diagnostic driver called nonexistent `stop`; parent-death cleanup ended
its owned child, and that run is explicitly a harness error, not a normal exit.
No new account, permission, system setting, login or dependency upgrade was used
to finish this stage.

## Code, packaging and repository checks

Related pytest: **229 passed, 7 skipped**, plus one Starlette/httpx deprecation
warning. Skips are native Windows Job Object/environment/readiness tests on Linux.
Scoped Ruff and Mypy passed for the 14 changed Linux/provider implementation
files. Six shell entry points passed `bash -n`; the named
`benchmarks/stardew-core/private/harbor/scripts/validate-task.sh` path is
absent and was not checked. Frozen task/controller checks,
the six original dependency groups and protected directories passed the final
read-only audit; no personal data was copied or restored.

Affected wheels were built in a new ignored directory from existing tools:

- `rhenium_balatro_plugin-0.2.2-py3-none-any.whl`: 44 entries, SHA-256 `a5ed1cedbd6e3f17c3f58bc0476d907c7d8613b228d22102ebe7c30aa12482e9`.
- `rhenium_steam-0.1.0-py3-none-any.whl`: 14 entries, SHA-256 `69269cbbe840da118d8970266058d8c11f70ecd1392c80e5d0c8bd54a230a2ad`.

Every packaged source/resource byte matched, required package data were present,
and no game/loader binary, save, runtime cache or credential asset was included.
Extracted wheels, without installing/upgrading packages, successfully reverified
the current managed artifact and matching smoke binding. This fixes the earlier
editable-versus-wheel resource-mode identity mismatch for v2. Full engine suites
were run from frozen source, not from an installed wheel.

Full required gates are **not all passing**: Ruff reports 36 findings in six
retained frozen source files; Mypy stops at duplicate modules in frozen capability
fixtures; full pytest collection fails because `rhenium_authoring` is absent.
Those files, expected hashes and rules were not weakened to obtain green checks.
Nix/devenv, Node/npm and ShellCheck are unavailable in this existing WSL
environment; frontend lint/test/build, stock exam wrapper and remote CI were not
run. No tools were installed to hide those limitations.

Final-source Windows native engine regressions, additional mutation/alternate
correct controls, three full Linux rounds per candidate, installed-wheel full
engine runs, other Linux/macOS hosts and an untrusted evaluation host remain
unrun. Old Windows repetitions and old Linux partial batches retain their original
fingerprints and are not relabeled as this version. Model calibration remains
unperformed. Distribution versions are retained for this unreleased worktree;
a release needs its own version/migration decision and final-identity validation.

## Evidence and replay

The machine-readable [validation summary](validation-linux-runtime-v2.json),
[source/runtime manifest](runtime-manifest-linux-v2.json) and
[replay commands](REPLAY-linux-v2.md) bind the measured results. Private operation
receipts, checkpoints and raw logs remain under independent operator state and
`.test-state/linux-runtime-v2`; they are not distributable task assets.
The live support guide links this report while historical v1 reports and hashes
remain unchanged. No task semantics, project rules, original game, daily Mods,
personal data, Cloud settings or original PoC environment were modified.
