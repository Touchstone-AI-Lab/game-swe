# Balatro benchmark support

| Field | Value |
| --- | --- |
| Maintainer | Sangyu Pan |
| Status | **Experimental** |
| Plugin / pack | `balatro` / `balatro/core`, frozen v0.2 tasks |
| Runtime | `balatro/balatro-linux-17459173-controlled-v2` |
| Measured host | Ubuntu 24.04 on WSL2/WSLg, Linux x86_64, Python 3.12 |
| Execution | Visible, serial, gamespeed=1, FAST=0, HEADLESS=0; 800×600 window and process-local OpenAL null output |
| Security mode | Source-reviewed `honest`; no untrusted evaluation host |
| Difficulty | Authored 3 Easy / 4 Medium / 3 Hard; model difficulty uncalibrated |

This unreleased worktree adds managed fixed-depot acquisition and a native Linux
evaluator. The existing independent official Steam login is reused through an
explicitly approved provider backend. Core stays game-neutral. The exact measured
coverage, failures and unrun checks are in the
[Linux validation report](../../plugins/balatro/runtime/linux/LINUX-RUNTIME-REPORT-v2.md);
the [replay guide](../../plugins/balatro/runtime/linux/REPLAY-linux-v2.md) identifies
the source version and operator prerequisites.

All ten tasks completed one full Linux gold/base pair through the actual core
CLI: 20 complete controls, 56 normally exited processes and 912 required outcomes.
Three separate initialized-load probes passed all six original cases each.
The approved versioned transport repair and owned window profile are bound to
these results. Extracted-wheel read-only artifact/smoke verification also passed.
The later [repository checks v3](../../plugins/balatro/runtime/linux/REPOSITORY-CHECKS-REPORT-v3.md)
pass full Ruff/Mypy/pytest and frontend/shell checks, with documented conditional
skips and warnings. The v2 engine evidence remains separate; neither local batch
claims release approval, remote CI success or untrusted-host readiness.

## Runtime and acquisition

The fixed Steam source is app **2379780**, build **17459173**, depot **2379781**,
manifest **3512319404653808464**. `rhenium runtime prepare` obtains it through the
Steam provider, verifies the declared game SHA-256, and constructs the managed
artifact. Read-only `runtime verify` checks its byte manifest and recipe. Evaluation
does not authenticate, download, install, update or rebuild.

The real game archive in the acquired `Balatro.exe` runs under native Linux
LÖVE **11.5**, with Lovely **0.9.0**, unchanged fixed Steamodded, and the explicitly
approved Bot `send_raw` derivation. Every other Bot byte is unchanged. This is
neither Wine nor a reimplemented engine, and it does not imply
that Steam distributes a native Linux Balatro executable. Bot's release label is
1.5.2 while its paired Lua manifest reports 1.5.1; byte identities are authoritative.
Licensed content remains in private operator caches and is absent from wheels,
task packages and source control.

The [controlled Steam backend](../../providers/steam/CONTROLLED-CONSOLE.md) requires
an existing signed-in independent client, an approved immutable container image,
a private operator profile and container-loopback CEF control. It publishes no
host port and does not extract a password, account identifier or helper token.
This is a tested acquisition route on the prepared host, not automatic cross-host
client installation or login bootstrap. The original unbound capability-probe
runtime is retained as a separate artifact and is not an evaluation runtime.

## Scoring and integrity

The evaluator consumes the runtime artifact supplied by core, seals the starter
allowlist and requires reviewed source bytes. A current-host smoke must match the
artifact, environment, harness and private asset descriptor. Its original cases
and normal cleanup are rechecked; a historical `passed` flag is insufficient.
Environment, harness, task and candidate fingerprints are independent.

The plugin reuses the frozen Session, RPC, scenarios and every required assertion.
Each game gets new save/mod directories, PID and nonce. Existing Linux and Windows
game-process guards remain. Components and staged inputs are checked before load
and after exit; controller/game ownership and parent-death termination constrain
cleanup. Missing responses, incomplete cases and forced exits cannot pass.
Only predeclared structured business rejections can be normal task outcomes.

The controller uses Python **3.12** and plugin-owned compatibility adapters. The
original Windows PoC Python **3.13** environment and dependency pins are unchanged;
game-specific code is not imported into core. Generated submissions, saves, logs,
review records and bindings belong only in operator state/cache locations.

## Validated lifecycle boundary

Save restoration uses a new process, complete independent seeded initialization,
one load request with its original complete response, restored-field checks and
subsequent real play. Checkpoint hashes and normal process exit remain required.
Blank-MENU direct loading was not repaired. Unconfirmed non-idempotent actions are
not resent, and a similar gamestate after timeout is not a successful response.

The default audio route caused slow game updates on this host. Bounded diagnostics
and a clean comparison support the process-local OpenAL null profile; no host
audio setting, game speed, timeout, engine component or completion predicate was
changed. The [diagnosis](../../plugins/balatro/runtime/linux/ENGINE-DIAGNOSIS-v1.md)
retains the incomplete attempts and the narrower remaining uncertainty.

A later software-rendering timing limit required an ordinary visible 800×600
window in each isolated process. The original game video callback applies it;
actual dimensions and profile bytes are verified. No state, lock, completion
condition, game speed or RPC deadline is changed. The
[rendering diagnosis](../../plugins/balatro/runtime/linux/RENDER-DIAGNOSIS-v1.md)
retains unsuccessful controls. The sole third-party byte change is the approved
[versioned partial-write transport repair](../../plugins/balatro/runtime/linux/TRANSPORT-IMPLEMENTATION-v2.md).

## Remaining boundaries and history

Native execution is not a hostile-code sandbox, network isolation or a disposable
evaluation host. Exact-byte review does not replace those controls. Formal
`untrusted` execution, Harbor, other hosts, macOS and model calibration are not
claimed. The stock shell scorer requires Nix/devenv; the measured maintenance
entry is identified explicitly in the validation report.

The worktree retains distribution version 0.2.2 to preserve preparatory recipe
identities; it is not a new release under that version. A future release needs its
own version/migration decision and final-identity validation.

The [Windows 0.2.2 record](balatro-branch-v2.md), original PoC and earlier probes
keep their own fingerprints. Their repetitions, mutations and wrapper results
are not relabeled as Linux evidence. The frozen public materials, private controls
and provenance are described in the [pack guide](../../benchmarks/balatro/CURRENT.md).
No new task, model experiment, commit, push or PR is part of this runtime work.
