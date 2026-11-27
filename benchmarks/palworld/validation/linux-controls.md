# Native Linux catalog 2.0.0 controls

Date: 2026-10-26. This is benchmark authoring and runtime maintenance, not a
model attempt. No model outcome or difficulty calibration is inferred.

## Decision and scope

Both retired tasks are **construct** tasks. Native Linux runs of their reference
mods crashed at the Palbox container-update and Actor damage hook respectively,
before any server assertion result. Each full result was incomplete, score 60,
with zero engine cases. The hooks and assertions were not bypassed.

Catalog 2.0.0 replaces those two identities with two new construct tasks:

- `base-containment-mincut` (SG-157): exact directed cut with locks and hard
  implications; minimize energy, changed labels, then the lexical label vector.
  Support 48 nodes and 256 arcs without partition enumeration.
- `guild-draft-canonical-order` (SG-158): exact ordering under hard precedence
  and weighted conflicting preferences; minimize preference penalty, maximum
  displacement, total displacement, then lexical order. Support 16 items without
  factorial enumeration. A single best prefix under the bottleneck objective
  is insufficient.

Both require strict validation, revision precedence, atomic failures, detached
state, recomputation of saved certificates and a real dedicated-server service
with hook cleanup. Each has eight behavioral cases and four engine cases.
Independent exhaustive small-instance oracles cover generated histories and
input permutations. Maximum-size controls retain the existing sandbox limits.
Ten discriminating mutations cover objective weighting, arc direction/cost,
history, canonical reconstruction, bottleneck/total movement and forged recovery.
All ten are rejected. Suggested 960-minute durations are author estimates.

The other eight catalog entries and authored assets match baseline `8b6e9a43`.
The canonical retained-entry SHA-256 is
`2f72c8931601f125988cd474eeb81f86997bd869f0ac890f5b3bc4180bb4ae67`.
Historical retired assets remain in the repository but are not registered.
New task identities inherit no results from the retired tasks.
Retained study task versions stay at 1.2.0; the new maps use 2.0.0.

## Real-engine environment

The controlled host is Red, Linux x86_64. Engine processes run as UID 1001 in
separate disposable Docker overlays, with network disabled, no capabilities,
no new privileges, 8 CPUs and 16 GiB per container. Pack/source inputs are
read-only. Generated submissions, logs and saves are outside the benchmark pack.
Other host services were not stopped or reconfigured.

- Palworld Steam App 2394010, build **25247047**, game **v1.0.5.102999**,
  Unreal **5.1.1**; anonymous acquisition was an explicit preparation step.
- Native Linux UE4SS source
  `BlackBookOfficial/RE-UE4SS-Linux@2397c7b1ce2841fd6526b8d8110cd008c90a6316`.
- Native loader SHA-256
  `6f1dacc9e117becf1485d903b6847fee8e31bc2871c82563fe048e333e1dda06`.
- Immutable local image ID
  `sha256:55acf9a22ae86cfc2a522e87f2d3e2a9330865fe04c44a23e783da094bcf30ba`.
- Unmodified Palworld plugin **0.6.1**, `PalworldEvaluator.evaluate` with
  `profile="full"`; no scorer or resource-limit change.

The runtime's shared world helper has a compatibility patch. It waits for the
first game-thread callback and selects a real reflected UWorld instead of the
port's crashing `GameInstance:GetWorld()` call. Real native Kismet authority,
hook registration/release and server Lua remain in use. No engine result is
stubbed. The launcher checks seven file hashes before each server launch.
A separate disposable overlay appended a comment to `UE4SS-settings.ini`;
`run-native` exited 1 at its hash check, before executing the game.
Source instructions, patch, MIT notice and exact pins are under
[`plugins/palworld/runtime/linux/`](../../../plugins/palworld/runtime/linux/README.md).
The runtime is manual, local and non-redistributable; no managed builder or
automatic Linux discovery is claimed.

## Results

The machine-readable [control record](linux-controls.json) contains 30 distinct
control IDs, per-control results and SHA-256 hashes of every current exam,
behavior suite, server suite and reference file. All ten current tasks were
rerun against catalog 2.0.0 in three independent runtime installations.

- **Gold:** 10/10 passed, score 100, `complete=true`, and 4/4 real engine cases
  observed per task. That is 40/40 gold engine assertions.
- **Empty NOP:** 10/10 failed, score 0, `complete=false`; no engine assertion is
  claimed for a submission missing its entry point and service.
- **Service absent:** 10/10 failed with `complete=true`; all four real engine
  cases were observed per task, and only the real-world/API sentinel passed.
  Each score was 15. This distinguishes engine availability from service success.
- Every run restored `mods.txt` and left zero `rhenium_*` mod directories.
  All three control containers exited with status 0 after checking the controls.

Portable Lua and simulated-service reference/empty controls are tested
separately. They are not counted as engine evidence. Fresh Harbor scheduler
oracle/nop Docker jobs were not run for the two new packages. Historical Harbor
1.x results are not relabeled as 2.0.0 results.

## Limits

The native port and helper patch are experimental and were measured on one
Linux x86_64 host and one game build. New task callbacks register and release a
real PlayerController hook; a player connection and possession delivery were
not exercised. Trusted service inputs do not imply real inventory manipulation.
Other builds, Linux architectures, long-running stability and the two new tasks
on native Windows are unvalidated.

A separate Windows-server-under-Wine smoke probe passed. Full Wine task
controls were not run; the catalog's Linux evidence above uses native ELF
binaries only. Earlier Windows records remain historical evidence for their
recorded task versions.

## Repository checks and delivery

Ruff, Mypy, the relevant study inventory/map checks, portable
reference/empty and mutation tests, shell syntax and ShellCheck passed. Frontend
lint, tests and production build passed with the bundled Node 24.19.0; lint
reported eight existing warnings. `web/dist/.keep` was preserved after build.
`git diff --check` passed. The prescribed `devenv shell` commands could not run
because devenv is unavailable; checks used the locked Python 3.12 workspace
virtual environment and the bundled Node runtime instead.

The repository-wide pytest run collected 2,075 tests and ended with eight
failures in unchanged code/assets:

- Two Slay the Spire frozen-manifest tests, for `stslib-block-ledger-r1` and
  `stslib-icon-layout-r1`: checked-in PNG bytes differ from their recorded
  manifests. Working-tree PNG bytes were confirmed identical to baseline
  `8b6e9a43`. Neither the assets nor expected hashes were changed here.
- Three `tests/test_util_hash_tree.py` cases: the adversarial fixture needs
  case-sensitive `A` and `a` entries, which collide on this macOS filesystem.
- Mindustry `test_prepare_builds_from_acquired_source`, RimWorld
  `test_runtime_command_is_sandboxed_and_uses_only_snapshot_assemblies`, and
  Terraria `test_prepare_builds_task_image_from_recorded_source`: the local
  Docker CLI is absent. No host installer was run to change that condition.

Other games' unavailable local-engine/container checks were skipped. The local
Palworld real-engine probe was also skipped; the separate native Linux controls
above provide the actual game evidence. The two newly added runtime-inventory
and launcher/patch pin tests were run separately after collection and passed.
The helper patch was also applied to the original loader asset and reproduced
the pinned helper SHA-256 exactly.

The branch is kept separate from main while the eight unrelated repository-wide
failures remain unresolved.
