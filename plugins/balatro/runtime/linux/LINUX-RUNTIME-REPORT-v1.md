# Balatro Linux runtime: partial validation, blocked

Recorded on the controlled WSL2/WSLg host, 2026-10-31 local time. Branch
`feat/balatro-linux-runtime`, base HEAD
`e4f8326e388cae4fc4ee5066eff792a6ea7a3a72`. This is unreleased maintenance work;
no commit, push, PR, model experiment or new benchmark task was performed.

**Fixed-depot automated acquisition, managed artifact verification and native
engine smoke succeeded. Four of ten tasks have complete Linux gold/base pairs.
Full Linux validation is blocked, not complete.** The fixed Bot transport dropped
part of a large response in the next task. The gate is preserved. An explicit
[component-change proposal](COMPONENT-CHANGE-REQUEST-v1.md) is awaiting approval;
the proposed replacement has not run in a game or modified any fixed dependency.

## Acquisition and runtime boundary

The packaged Steam provider reused the approved independent official-client
login, through a container-loopback CEF endpoint with no published host port.
The actual core command `rhenium runtime prepare` acquired the exact app 2379780,
build 17459173, depot 2379781, manifest 3512319404653808464. The final preparation
took 48.972 seconds; read-only verify took 4.831 seconds. The provider recorded
one command, one matching completion and a normal client/container exit without
forced termination. Game SHA-256 is
`0d75fe164accf3312734d4b37ac98788dd15f0b8e4f9bb8b7f90c4e59de93f47`.

Preparation retains the approved isolated home, UID 1000, dropped capabilities,
no-new-privileges, seccomp exception, 3 GiB memory, 1 GiB shared memory, two CPUs,
512 PID limit and three scoped mounts. Credentials and licensed game files stay
in private operator state; no account identifier, password or session token was
extracted for the provider. Earlier failed/reconciled attempts remain separate.

Native LÖVE 11.5 runs the actual game archive, with Lovely 0.9.0 and unchanged
fixed SMODS/Bot sources. This is not Wine or a simulated engine. It does not claim
a Steam-supplied native Linux executable. Evaluation never acquires or updates.
The plugin owns Linux process/session adapters; core remains game-neutral.
The existing Python 3.12 Linux environment controls execution. The original
Python 3.13 Windows PoC and its frozen sources remain unchanged.

Each process has a new PID, nonce, HOME/XDG/save/mod directories and owned
loopback listener. Execution is serial and visible, gamespeed=1, FAST=0,
HEADLESS=0. Native and Windows existing-game guards, pre-load byte verification,
staged-input checks, normal quit, parent ownership and strict result classification
remain. Minimal environment propagation is not an untrusted-code sandbox.
Preparation/start/test/quit timings and directory sizes are recorded privately.

## Current managed engine controls

The current managed smoke is operation `00c08e165b5243d68cdc7aa7b5fade43`:
all six original cases, current artifact/environment/harness binding and normal
exit. It is not inferred from the existence of an old smoke file.

The following used the actual `rhenium run --profile full --security-mode honest`
entry, independently sealed/reviewed controls and frozen task assertions.
Every control starts fresh native processes; multiple scenarios within a control
are not described as independent control repetitions.

| Task | Gold | Base | Processes per completed control |
| --- | --- | --- | --- |
| growth-v2 | Full pass | Complete expected behavior rejection | 1 |
| reversible-hand-limit-v1 | Full pass | Complete expected behavior rejection | 1 |
| seeded-effect-stream-v1 | Full pass | Complete expected behavior rejection | 4 |
| bounded-generator-v2 | Full pass | Complete expected behavior rejection | 5 |
| deck-removal-consistency-v2 | Incomplete transport response; 1 of 3 processes | Unrun | — |
| live-joker-adjacency-v2 | Unrun | Unrun | — |
| isolated-card-wear-v2 | Unrun | Unrun | — |
| durable-charge-v2 | Unrun | Unrun | — |
| shop-price-coherence-v2 | Unrun | Unrun | — |
| pack-choice-commit-v2 | Unrun | Unrun | — |

Totals: eight complete control workflows, 22 native processes and 274 required
case outcomes in those workflows; one incomplete workflow and 11 unrun controls.
Only one round has run. Each complete process exited normally with unchanged
protected/staged bytes. Old Windows repetitions, variants and wrapper results
are not new Linux evidence. This work does not calibrate model difficulty.

## Confirmed transport failure

Deck gold operation `3b8a5fb356624612be39faf8dc92c318` stopped at a read-only
observation with `ProtocolError: Invalid JSON response`. A separate bounded
diagnostic reproduced HTTP 200 with Content-Length 154,032 but only 109,458 bytes
received: 44,574 bytes were missing. The fixed server logged a send timeout.
The diagnostic recorded lengths/counters/hashes, preserved calls/returns/errors,
did not alter gameplay, and did not repeat an unresolved non-idempotent action.

Fixed `core/server.lua` uses nonblocking sockets, calls `send` once, discards
the partial index and closes after the response attempt. Once closed, a longer
client timeout cannot recover discarded bytes. The frozen raw runner labels
this broad class `test_gap`; the platform correctly marks it incomplete/environment
failure. It is neither a gold behavior failure nor an acceptable business error.
Both incomplete processes exited normally. No case, parser or timeout was relaxed.

The proposed `send_raw` change resumes partial writes within a one-second write
budget, preserving original bytes and RPC semantics. Eight LuaJIT double-based
tests passed; these are not game evidence. Original `.deps`, pins, old artifacts
and `linux-halt.json` are intact. Execution cannot proceed on this proposal
without the requested component approval and a separately versioned artifact.

## Earlier capability evidence

Default audio initially limited frame updates to about 5 FPS. A bounded diagnosis
measured sound modulation consuming 26.801 of 27.376 seconds of Game.update work.
Process-local OpenAL null output restored about 60 FPS and a clean real-play smoke.
No system audio setting, game speed, completion condition or RPC timeout changed.
The exact cause inside the default backend remains unknown; see the retained
[engine diagnosis](ENGINE-DIAGNOSIS-v1.md).

The earlier frozen six-case save probe passed save/normal quit/new process/full
seeded initialization/single complete load/restored fields/subsequent real play,
with unchanged checkpoint hashes. That is a capability pilot on its recorded
source. Three final-code repetitions have not run. Blank-MENU direct load was
not fixed, and no old save result is promoted to final managed task evidence.

## Checks and packaging

- Current production adapters passed targeted Ruff/Mypy and 16 implementation/
  compatibility tests. Additional observer/process tests passed. Related full
  pytest originally recorded 196 passes, seven Windows-only skips and one missing
  contract-fixture failure. Both contract tests passed after materializing the
  exact HEAD fixture bytes; both the original failure and recheck remain recorded.
- Full Ruff was attempted: after fixing only new maintenance-helper formatting,
  36 findings remain in six frozen historical copies. Full Mypy stopped at duplicate
  `probe` modules in frozen copies. Full pytest could not collect because the
  installed workspace lacks `rhenium_authoring`. These checks did not pass.
- The packaged Steam shell launcher passed `bash -n`. ShellCheck, Nix/devenv and
  the web toolchain/dependencies are unavailable in this WSL environment; those
  required checks and remote CI remain unrun. No tool/dependency was installed to
  conceal that limitation. Git whitespace validation is recorded separately.
- Two wheels were built and inspected: all 33 Balatro and nine Steam source files
  matched, with required resources and no game/credential/state assets. Read-only
  wheel reuse of the current editable artifact failed because self-authored
  resource executable flags differ. See [the packaging finding](PACKAGING-NOTE-v1.md).
  Installed-wheel game execution and release readiness are not claimed.
- The protection audit verified original protected data, 16 controller files,
  350 private task files and six fixed dependency groups. No old checksum or
  baseline was changed. The later receipt and final source manifest retain hashes.

## Evidence and remaining work

[Generated validation](validation-linux-runtime-v1.json) derives control status
from actual result/classification files, not task labels or manually assigned
completion. [Source/runtime manifest](runtime-manifest-linux-v1.json) binds this
snapshot. [Replay instructions](REPLAY-linux-v1.md) distinguish read-only checks,
past commands and blocked future execution. Private source capsules and receipts
remain under `.test-state/linux-runtime-v1` and isolated Linux operator state;
no raw log, checkpoint, licensed game or authentication profile is published here.

Required before claiming full Linux readiness: approved versioned transport
repair and real-socket verification; stable wheel/source recipe handling; fresh
artifact/smoke evidence; deck gold/base and every remaining full pair; final-code
save repetitions and relevant regressions; anonymous stock-wrapper validation;
resolution or explicit disposition of repository checks and release versioning.
No mutations, alternative-correct controls, cross-host/Linux-container engine
matrix, formal untrusted host, Harbor or model calibration ran in this batch.
