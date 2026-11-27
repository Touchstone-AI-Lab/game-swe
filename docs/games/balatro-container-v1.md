# Balatro Linux container profile

The 0.3.0 plugin adds a game-owned Linux container profile for the ten unchanged
Balatro v0.2 tasks. All ten full gold/base pairs completed through the core CLI:
20 controls, 56 normally exited real game processes and 912 required outcomes.
Every gold passed and every base failed for its intended behavior. Historical
Windows and WSL evidence keeps its original version and fingerprints.

The complete original matrix also passed its intended outcomes: **68 controls,
197 normally exited real game processes and 3461 required outcomes**. Ten golds
and four independent correct alternatives passed; ten bases and 44 mutants
completed and failed as required. See the [validation report](../../plugins/balatro/runtime/linux/LINUX-CONTAINER-REPORT-v1.md)
and [sanitized evidence](../../plugins/balatro/runtime/linux/validation-linux-container-v1.json).

Container-v1 requires a native Linux x86_64 Docker host and rejects Microsoft/WSL
kernels. It does not add a Windows worker or macOS support. Lab uses its local
Docker daemon; other hosts and remote-daemon execution have not been validated.

The runtime key is `balatro/balatro-linux-17459173-container-v1`. Explicit runtime
preparation consumes the Steam-acquired, checksum-pinned build 17459173. It builds
an owned Ubuntu image from a digest-pinned base and hash-pinned existing Python
dependencies, prepares the original LÖVE/Lovely/Steamodded components and the
previously approved Bot transport derivation, then runs all six original smoke
assertions. Licensed game bytes remain in private runtime caches and are mounted
read-only; they are not copied into the dependency image or a wheel.
Native Linux LÖVE loads the licensed game archive from the fixed Windows Steam
depot.

Evaluation starts the exact prepared image ID with an owned rendered X display,
normal graphics enabled, gamespeed=1, FAST=0, HEADLESS=0 and the existing 800×600
window profile. This is a virtual display; it does not promise an interactive host
desktop. No host port, Docker socket, provider home, credential environment or
host package installation is needed. Evaluation has no external network and does
not authenticate, acquire source, install dependencies or build an image.

The owned container has an 8 GiB memory limit, a 16-CPU ceiling and a 256-process
limit. The controlled Lab host has 104 logical CPUs and uses Mesa llvmpipe software
rendering. A four-CPU pilot timed out during a complex play; that incomplete
control and its halt are retained separately. The original 25-second RPC bounds
and 1800-second native controller deadline remain unchanged. The outer container
and host deadlines allow the native deadline and cleanup to finish.

This remains source-reviewed **honest** execution. It is not the provider-neutral
untrusted/disposable evaluation-host contract. New executable submission bytes
require actual source review and a matching explicit review seal before scoring.
The inner evaluator, task assertions, case requirements, normal-exit checks and
frozen assets are reused unchanged. Container PID namespaces are recorded
separately from local process IDs and nonces.

## Version and migration

Plugin 0.3.0 is a minor-version decision for the new default Linux execution
profile. Task catalog 0.2.0, task identities, numbering and grading semantics do
not change. The default managed bindings now select the new Linux-only runtime;
the 0.2.2 native Windows entry is historical and must not be represented as
validated under these new bindings. Existing Windows operators should retain
their 0.2.2 source/pack pairing. No Windows worker or automatic WSL installation
is introduced.

Existing runtime artifacts, bindings, reviews and historical evidence are never
silently migrated. Prepare the new runtime explicitly; old WSL and Windows
artifacts are preserved. A changed image, native tree, source recipe, host kernel,
smoke or source-review seal makes full evaluation unavailable.

```sh
rhenium runtime doctor balatro/balatro-linux-17459173-container-v1
rhenium runtime prepare balatro/balatro-linux-17459173-container-v1
rhenium runtime verify balatro/balatro-linux-17459173-container-v1
```

The plugin-owned `python -m rhenium_balatro.container_operator` exposes `inspect`
and `review`; its `--help` lists the explicit pack/state/cache/artifact/submission
arguments. Inspection computes a seal without authorizing execution. `review`
requires `--source-reviewed` and the matching `--reviewed-sha` after inspecting
the actual executable source. A source review does not change the submission.
The separate real-engine admission probe verified rejection before review with
zero game processes, then a complete 18-assertion pass after explicit review of
the same new-byte submission. It is separate from the 68 original controls.

## Study attempts

The ten tasks are registered in the private study inventory, and E0 admitted all of
them on 62 real-engine controls: ten starters, ten references, 23 target-negative,
nine compat-negative and ten alternative controls. Six alternatives were written from
the public contract without reading the gold control, then reviewed and sealed like
any new bytes. Six tasks have no compatibility-specific negative, so only four qualify
for the joint compatibility analysis.

A study lists `balatro` in `deferred_evaluation`, because generated bytes cannot run
until they are reviewed. Generation leaves each attempt pending. The operator reads
each frozen submission in full, records its seal, evaluates it with `rhenium run` and
scores the output with `rhenium-study e1 import-evaluations`.

`rhenium-study e1 review-balatro` can record the seal instead of the reading. It seals a
submission only when its static policy finds no file, process, network or dynamic-code
capability and no reference to the observer, the guard or the harness, and it leaves
every other submission for the operator. The policy is a guard for honest submissions,
not a sandbox, and it cannot judge whether code special-cases a scoring scene. Its seals,
like the operator's, belong to one artifact, so after a halt the command seals the
unevaluated attempts again on the new artifact. The
[study README](../../tools/study/README.md) lists its rules.

The runtime lock does not wait. A second evaluation or a review that starts while
another holds it fails at once, so these steps run strictly one after another.

An incomplete evaluation is not always an environment fault. A scenario that cannot
reach a later step, because the submission did not produce what that step needs, stops
with `test_gap` and is published as `environment_failure`. Read the private
`engine-result.json` of the operation before attributing it.

An incomplete evaluation also leaves the halt marker in place, and that artifact then
refuses further evaluations and reviews. No command recovers from this.
`rhenium runtime verify` does not read the marker, so the runtime still reports ready
and `rhenium runtime prepare` returns the same artifact. `rhenium runtime prune` deletes
every preparation of the runtime, their private evidence and the source cache.

## NixOS acquisition boundary

Lab uses an operator-local `RHENIUM_STEAM_HELPER` wrapper to run the unchanged
released 0.1.0 Linux helper in an existing dependency container. Its SHA-256
matches the packaged manifest. The actual provider still acquires the exact
Steam depot automatically; the wrapper does not replace acquisition with copied
operator files or a fabricated receipt. This is local override evidence, not
direct generic-helper support on stock NixOS. No host packages or Docker daemon
configuration are changed. The first direct-helper failure and the first
source-permission image failure remain in private preparation evidence.

## Maintenance replay

After explicit preparation, save `rhenium runtime verify` output outside the
repository. The maintenance driver accepts only the original exact-hash controls:

```sh
rhenium runtime verify balatro/balatro-linux-17459173-container-v1 > "$PRIVATE/verify.json"
python plugins/balatro/runtime/linux/validate_container_v1.py \
  --repo "$PWD" --pack "$PWD/benchmarks/balatro" \
  --state "$RHENIUM_STATE_DIR" --artifact "$PRIVATE/verify.json" \
  --output "$PRIVATE/controls" --group all
```

`PRIVATE` must be a fresh operator-owned directory outside the repository;
`RHENIUM_STATE_DIR` selects the Hub state used for preparation. `--group pairs`
runs the twenty gold/base controls; `--group remaining` runs the other forty-eight
original controls. Each evaluation uses the actual core CLI with the `full`
profile and stops the batch at the first unexpected or incomplete outcome.
Receipts retain the image, artifact, source seal, namespace, case completeness and
normal-exit evidence. No source review is inferred for new model submissions.
