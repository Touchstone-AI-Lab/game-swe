# RimWorld support

| Field | Value |
| --- | --- |
| Maintainer | Zhengshen He |
| Status | `In Development` |
| Plugin distribution | `rhenium-rimworld` |
| Plugin / game ID | `rimworld` |
| Pack | `rimworld/core` |
| Catalog | `rimworld-core` 0.5.0; ten source-authored repair tasks, all validated two-way on the real game; legacy private protocol v2 plus per-task v3 |
| Game build | RimWorld 1.6.4871, Steam build `23969874`, Linux depot `294103` manifest `3402513235443928324` |
| Game engine | Unity 2022.3.35f1 with the depot-provided Mono runtime |
| Build toolchain | .NET SDK 8.0.422 targeting .NET Framework 4.7.2 |
| Mod dependency | Harmony 2.4.2 / Harmony Mod 2.4.2.0 |
| Source Mods | R⁴ plus eight audited repositories in registered tasks; task-local records distinguish exact snapshots, 1.6 reconstructions and mixed MIT/MPL Adaptive Storage dependencies; the retired Zombieland task keeps its source slice in the pack |
| Submission language | C#/.NET |
| Game runtime platform | Linux x86_64 container; real-engine runs on one Linux x86_64 Docker host (2026-09-24, 2026-10-29, 2026-10-30) |
| Runner platforms | Linux x86_64 only; macOS and Windows are not declared |

This milestone follows Rhenium 0.6's plugin and managed-runtime contracts without
adding RimWorld knowledge to the game-neutral core. Its fixed scope and
implementation plan are accepted and active development has started, so it is `In
Development`. On 2026-09-24 nine of the ten tasks completed full reference and
starter runs in the pinned real game through the Hub on one Linux x86_64 Docker
host, after the verifier repairs listed under
[Engine validation](#engine-validation-2026-09-24): every reference scored 100 three
times with identical case outcomes, and every unchanged starter completed and failed
only its target cases. Catalog 0.4.0 adds the research-tab task, which passed the
same two-way validation on that host on 2026-10-29; see
[Research-tab task](#research-tab-task-catalog-040). Catalog 0.4.1 repairs the
Adaptive Storage verifier's rectangle self-check, after which that task passed the
same two-way validation and its negative controls on that host on 2026-10-30; see
[Adaptive Storage acceptance](#adaptive-storage-acceptance-revision-6). No real-game run was made on macOS,
Windows or WSL2,
and the status stays
`In Development` pending maintainer review.

Catalog 0.5.0 retires `zombieland-dynamic-needs-capacities` (SG-128) without a
replacement because it was saturated and no longer discriminated. Its exam, Harbor
tree, source slice and study controls stay in the pack as history, and the validation
records below still describe it where it was measured. The prepared runtime records
images and build evidence for every catalog task, so an artifact prepared before 0.5.0
fails `runtime verify`; prepare the runtime again.

## Source selection and license boundary

The dated [task-authoring candidate audit](rimworld-authoring-candidates.md)
records selection and rejection evidence. Catalog 0.3.0 promoted nine additional
source-authored tasks from that queue. Promotion records source and license bytes;
it is not compile, container, control, or real-engine evidence.

The original task uses [R⁴](https://github.com/CheaterEater-RM/RRRR), fixed at tag
`v1.48` and commit `7fbf158f4b988a6f806cc609282175143a3a41a6`. Its root
license is MIT, but the license file explicitly excludes included textures that
contain RimWorld art and other separately licensed textures. The pack therefore
contains only the two C# files needed by the task, the upstream MIT license and
benchmark-authored text/build files. It contains no upstream texture, preview,
sound, precompiled DLL or Workshop payload.

R⁴ was selected because the target material-basis behavior is deterministic after
RimWorld has loaded its definitions and can be checked without UI automation, map
generation, network access or DLC. Camera+ was not selected because its meaningful
behavior is predominantly camera/input/rendering based. Allow Tool was not selected
because the audited candidate did not establish a repository-wide SPDX license and
adds HugsLib plus a much larger UI/compatibility surface. Harmony and HugsLib are
dependencies to understand, not task subjects.

The repository/tag/commit relationship above comes from the supplied authoring
snapshot and was not independently refetched during this Phase A-B pass. The
preserved source and license bytes are hashed; any decision that depends on the
complete upstream Git graph still requires fresh read-only provenance evidence.

## Runtime and acquisition boundary

RimWorld is proprietary and is never distributed in this repository or the plugin
wheel. The managed runtime source fixes Steam App `294100`, Linux depot `294103`,
and manifest `3402513235443928324`. Runtime preparation must validate the expected
native executable, Unity player, managed assemblies, Core metadata and the first
`Version.txt` token `1.6.4871`. The full revision and file hashes remain to be
recorded after an authorized acquisition; they are not inferred from another
platform.

An operator who owns RimWorld prepares the runtime explicitly:

```sh
rhenium auth login steam
rhenium runtime prepare rimworld/rimworld-1.6.4871-linux-x64
```

Interactive Steam login is an operator action and uses provider-owned state. Steam
credentials, session state and Workshop caches never enter the runtime image,
benchmark pack, attempt or logs. Evaluation consumes only the immutable local image
IDs recorded by preparation and runs with Docker networking disabled. It never
logs in, downloads, restores packages or rebuilds a missing runtime.

The verifier repairs of 2026-09-24 changed adapter inputs, so the prepared images
no longer verified. On the validation host the operator's Steam account could no
longer acquire app 294100 ("not available from this account"), so `rhenium runtime
prepare` failed at acquisition. The images were rebuilt instead from the provider
cache that the same pinned depot manifest produced on 2026-09-18, by running the body
of `RimWorldRuntimeBuilder.prepare` (its source validation, build-context staging and
role-image builds, parallel across tasks) followed by the builder's `verify`, and the
resulting artifact was stored as ready. No file of that cache was changed; a host that re-acquires the
manifest should re-run `rhenium runtime prepare`.

On 2026-10-29 the same host ran the normal path again for catalog 0.4.0.
`rhenium runtime prepare rimworld/rimworld-1.6.4871-linux-x64 --account <alias>`,
with a Steam session that owns app 294100, acquired the pinned manifest and built
and verified role images for all eleven tasks. Preparing with a session that does
not own the game fails at acquisition and leaves the runtime record `failed`; pass
the entitled session's alias.

Preparation stages only reviewed runtime paths plus the task Dockerfile and test
inputs into a task-owned destination. It validates the declared expected-file
types and any declared SHA-256 values, then hashes the actual staged source and
build inputs. It creates distinct immutable builder and evaluator image roles with
role and ownership labels. Package restore and dependency acquisition occur only
during the explicit preparation action. `doctor()` and `verify()` are read-only:
they check the Linux x86_64 Docker daemon identity and the immutable image IDs,
labels, pack-input evidence and artifact fingerprint, but do not launch RimWorld
and never report engine-launch validation.

RimWorld does not claim an officially supported headless mode. The proposed full
runner starts the native Linux x86_64 client under Xvfb with its depot-provided
Unity/Mono runtime and a private verifier mod that exits after definition-level
assertions. `-batchmode` and `-nographics` are deliberately absent until the exact
manifest proves them reliable. Missing runtime, compilation failure, launch failure,
timeout, missing/duplicate results or incomplete case execution all fail closed.

For evaluation, the plugin snapshots only the task's required C# sources with
no-follow file opens and rejects traversal, symlinks, special files, hard links,
binary inputs and private-harness markers. Candidate-supplied project files,
targets and DLLs are not compiled. A networkless non-root builder uses the fixed
prepared toolchain with `--no-restore`; only the re-read and hashed candidate and
adapter assemblies reach the separate evaluator image. The evaluator runs with a
read-only root filesystem, dropped capabilities, `no-new-privileges`, bounded
resources and logs, internal Xvfb, and no Docker socket, host X11, Steam session or
user-directory mount.

The game adapter emits observations only. The original 38-case private protocol v2 uses one
owner-only `tests/assertions.json` as the maintained case, fixture, expected-result,
and weighting declaration. Runtime preparation generates a dispatch without
expected values; neither the manifest nor expected results enter a
candidate-readable image or evaluation mount. A plugin-owned external supervisor
strictly parses them, rejects duplicate or unknown JSON fields, type errors,
non-finite numbers, stale evaluation identity, missing/duplicate/extra cases,
multiple terminal markers, abnormal exits, and contradictory counts or reward.
It alone computes the final result. Protocol v3 has distinct private, observer,
and supervisor identities and permits a task-specific assertion count; catalog
loading binds each manifest protocol and exact count to its task. Task starter
root, package ID, assembly, Mod metadata, rubric, authored-source hash, adapter
evidence, and immutable role images are independently bound. Detailed case messages and integrity evidence
stay in an owner-only state directory. For a complete verdict the operator result
also lists each case ID with a pass/fail boolean under `runtime.caseOutcomes` (no
messages or observed values); anonymous attempt results drop that field, so they
expose only generic categories. A normal completed behavior failure is complete but failed;
build, fixture, runtime or evidence-integrity failures are incomplete. A failed build's public
log line names the side that did not compile, from MSBuild's own project attribution: the
submission (`RimWorld submission build failed: ...`) when only the submission project has
errors, the verifier harness when that project has any, and neither otherwise. The study
adjudicates only the first as a failed attempt; compiler output stays private.

The candidate and verifier adapter still share RimWorld's CLR. An arbitrary
malicious .NET submission can therefore attempt to interfere with the adapter or
its observations. The nonce, external supervisor, source screening and assembly
hashes are defense in depth, not a proof of tamper resistance. Claims against that
threat require a separately reviewed isolation design.

## Profiles and catalog 0.5.0 tasks

| Profile | Behavior | Complete eligible |
| --- | --- | --- |
| `core` | Validate the public source shape and provenance boundary | No |
| `full` | Compile the submission, start the pinned real game under Xvfb, and run every named assertion | Yes |

Catalog 0.5.0 contains the unchanged R4 material-basis task plus nine
source-authored tasks: R4 small-bench ingredient consumption, Project RimFactory
cell-local cultivator conditions, Adaptive Storage saved slot limits, Combat
Readiness Check colony wealth, Customize Weapon ability lifecycle, Total Control
vanilla gear generation, Bill Autopilot repeat-mode ownership, Playwright non-bulk
trade accounting and, new in 0.4.0, Research: Organized research-tab state. Catalog
0.4.0 also had Zombieland dynamic needs/capacities, which 0.5.0 retired. Automatic Outfit
Manager was rejected because neither selected commit contains a LICENSE or NOTICE;
Project RimFactory replaced it. Pick Up And Haul was rejected after its target
proved not to implement the requested capacity-bounded queue semantics; Combat
Readiness Check replaced it using the documented faithful 1.6 reconstruction.

Each task's `validation/controls.json` keeps the authoring plan and, since
2026-09-24, the observed compile, container, oracle (reference), base (unchanged
starter) and no-op (independently materialized starter) outcomes; see
[Engine validation](#engine-validation-2026-09-24). Adaptive Storage's record also
keeps its earlier failed and compile-only revisions as history; its engine outcome
is from 2026-10-30 (revision 6).

The original task, **Restore R⁴'s material basis for uncraftable gear**, starts from
R⁴ 1.47's material utility and asks the model to restore the v1.48 behavior. The
public contract covers precedence among a real adjusted cost, an authored extension
and a deterministic market-value/technology fallback, plus use by the existing
repair and clean paths. The public contract names the shared resolver signature that
the private harness calls; no unannounced private helper or code layout is required.
Assertions run only after real RimWorld definitions have loaded and do not constrain
formatting or exact log text.

Its exact scope is `ResolveMaterialBasis`, `GetRepairCycleCost`, and
`GetCleanCost`. It does not score recycling randomness, map placement, eligibility,
`DoRecycleProducts`, or `SpawnPartialReclaim`, and a pass is not evidence that all
R⁴ v1.48 behavior was restored. The protocol covers all 38 named cases, including
float32 nearest-even boundaries and independent repair/clean setting formulas.

The authoring plan expected the v1.48 oracle to pass 38/38 and the unmodified v1.47
starter to pass 7 and fail 31. The real-game runs of 2026-09-24 observed exactly
that: the reference passes all 38 cases, and the starter completes with the two
gates, the three craft-preservation cases and the two repair-guard cases passing
and the other 31 failing. The negative controls (authored overrides must not beat a
real crafting cost; Undefined technology is Industrial) behave as declared; see
`private/study-controls/r4-uncraftable-material-basis/NOTES.md`.

## Toolchain pins and open validation

- .NET SDK `8.0.422-bookworm-slim` image digest
  `sha256:63ebabdcde24cc8134304a6f50719cf1e22bb4e9f7148ac4ef967c7680187356`;
- target framework `net472` with
  `Microsoft.NETFramework.ReferenceAssemblies.net472` 1.0.3;
- compile-time reference API `Krafs.Rimworld.Ref` 1.6.4871; the licensed depot
  assemblies are used only by the actual game process;
- Harmony library 2.4.2 and RimWorld Harmony Mod 2.4.2.0; the release archive is
  fixed by URL and SHA-256 in the evaluator Dockerfile;
- Unity `2022.3.35f1`, but always executed from the licensed depot rather than a
  system Unity or Mono installation.

The pinned manifest was acquired on the validation host on 2026-09-18; the game
reports itself as `RimWorld 1.6.4871 rev600` on Unity `2022.3.35f1` and launches
offline under the pinned images (`--network=none`, Xvfb, no Steam client). The
2026-09-24 runs recorded a full oracle pass and complete base/no-op target failures
for nine tasks on that one Linux x86_64 Docker host. Critical-file hashes are still
not declared in `runtimes.json`. macOS, Windows/WSL2, DLC combinations and a second
host remain unverified. Adaptive Storage's engine result is from 2026-10-30, after
the revision 6 verifier repair.

## Catalog 0.3.3 authoring review

[Revision 3](rimworld-authoring-revision-3.md) records the nine v3 fixture changes.
[Revision 4](rimworld-authoring-revision-4.md) supersedes only Adaptive Storage:
it aligns unlimited-sentinel semantics with the fixed native 1.6 descendant,
adds deterministic reconstruction and full source/dependency inventories, and
strengthens initialization/integrity controls. Its 15 cases have still not run in
the game (see below). Zombieland and the other task semantics are unchanged.

## Engine validation (2026-09-24)

All runs used the Hub (`rhenium run` for the operator records and
`rhenium-study e0 run` for the study controls) with the images rebuilt as described
under [Runtime and acquisition boundary](#runtime-and-acquisition-boundary), on one
Linux x86_64 Docker host, networkless. Before these runs no RimWorld task had ever
completed: the private harnesses had never been compiled or executed. The following
verifier-side defects were repaired. No case ID, expected value, gate, weight, exam,
starter or reference changed.

- All harnesses except Combat Readiness and Zombieland lacked
  `using System.Globalization` for the explicit serializer (CS0103).
- R⁴ material basis (protocol v2): `MaterialUtility` was ambiguous between `RRRR` and
  `Verse` (aliased to `RRRR.MaterialUtility`); `VerifierBootstrap` had no
  `[StaticConstructorOnStartup]`, so the verifier never ran and the game idled until
  the 600 s timeout; RimWorld 1.6 `CostListAdjusted` reads
  `Find.Storyteller.difficulty`, so the case loop now runs inside a temporary `Game`;
  Core's `MarketValue` stat clamps at 0 and rounds values above 200 to fives, and no
  float32 market value reaches a quotient of exactly 3.5 or 100 over Core Plasteel's
  price of 9, so the case loop lifts the floor and rounding and prices Plasteel at 8
  (all restored afterwards). The fixtures specify quotients, so expected counts are
  unchanged.
- R⁴ small bench: the same ambiguity; the fixture read `InteractionCell` of an
  unspawned bench without one (RimWorld 1.6 resolves it through map pathing), so it
  now uses the bench position, the origin the scored code uses; `ThingGrid.Deregister`
  gained a `doEvenIfDespawned` parameter, which broke fixture cleanup.
- Project RimFactory: `tests/Support.cs` lacked upstream
  `Utilities.CanPlantRightNow` (CS1061), now copied from the target commit; the
  seeds-area stub called `OccupiedRect` on the def-less fixture cultivator.
- Bill Autopilot, Total Control and Zombieland: `tests/Submission.csproj` lacked the
  publicized `Assembly-CSharp` build every upstream project uses (`Bill.loadID`,
  `Bill_Production.playerCustomName`, `PawnWeaponGenerator.GetCommonality`,
  `Need.pawn`); `Krafs.Publicizer` 2.3.0 now publicizes it and the lock files record
  its content hash.
- Bill Autopilot fixtures: the fixture recipe lacked a default ingredient filter and
  the fixture map lacked a pawn registry.
- Customize Weapon: `ThingDef.verbs` is private in 1.6 (set by reflection) and the
  fixture pawn lacked the `mindState` that 1.6 `AddEquipment` writes.
- Total Control: Core ships no `ThingStyleDef` (the fixture authors one), Core weapons
  are not colorable (the color case gives its weapon a `CompColorable`), and 1.6
  leaves `HitPoints` unset on things without hit points (the non-hit-point cases
  compare with an identical new thing).
- Playwright: `Scenario.AllParts` is an enumerable in 1.6 and yields the
  player-faction and surface-layer parts first (the fixture scenario now has them
  and reads the first sell-items part by type); Harmony must patch the declared
  `Transferable.get_CountToTransferToDestination`; the trade-ship faction field is
  declared on `PassingShip`; the scenario-part doubles now carry distinct defs.
- Zombieland: the fixture need lacked the abstract `NeedInterval`, and
  `NeedDefOf.Mood` no longer exists in 1.6.

The Customize Weapon and Adaptive Storage `validation/mutation-controls.json`
digests of `tests/Harness/Verifier.cs` were recomputed from the repaired files; their
anchors, replacements and must-fail lists are unchanged.

| Task | Cases | Reference (`rhenium run`, three runs) | Unchanged starter (`rhenium run`) | Study controls |
| --- | --- | --- | --- | --- |
| `r4-uncraftable-material-basis` | 38 | `run-49c6888766274629`, `run-38724cc02f5e4353`, `run-452d4451b886430f`: 100, 38/38 each | `run-1eaeba110d2f43b8`: 10, 7 pass / 31 fail (targets only) | alternative-a (as declared); compat-negative-extension-first (as declared); target-negative-undefined-tech-level (as declared) |
| `r4-small-bench-ingredient-consumption` | 16 | `run-d5cd9fa7aa0743c3`, `run-cbcbdf8df90f4f0d`, `run-5992b56afd4e46b5`: 100, 16/16 each | `run-fdbc4769d7244f5c`: 10, 10 pass / 6 fail (targets only) | alternative-a (as declared); alternative-strict-reading-vanilla-200 (rejected by `outside-radius-preserved`, flagged over-constrained); compat-negative-consumes-non-items (as declared); compat-negative-impassable-not-skipped (as declared); target-negative-radius-five (as declared) |
| `project-rimfactory-cultivator-environment` | 12 | `run-52b63ba3dc314278`, `run-bf2e3b808a0348ae`, `run-6be50b7d8ce34bee`: 100, 12/12 each | `run-01b7a4d9fdb147da`: 10, 9 pass / 3 fail (targets only) | alternative-a (as declared); compat-negative-ignores-sow-blocker (as declared); target-negative-no-vacuum-check (as declared) |
| `combat-readiness-colony-wealth` | 16 | `run-39bcdda283da4d58`, `run-3115c73ac20f464b`, `run-09d77c4ad0d34a54`: 100, 16/16 each | `run-7f8eb9890b054399`: 10, 5 pass / 11 fail (targets only) | alternative-a (as declared); compat-negative-armoury-queried-twice (as declared); target-negative-fixed-wealth-overridden (as declared) |
| `customize-weapon-ability-tracker` | 18 | `run-169880b19aff4131`, `run-ef338d8f840b44bb`, `run-95ca3d9298e6484b`: 100, 18/18 each | `run-3c5d095073dc4769`: 10, 14 pass / 4 fail (targets only) | alternative-a (as declared); compat-negative-tracker-created-eagerly (as declared); target-negative-tracker-never-created (as declared) |
| `total-control-vanilla-gear-generation` | 18 | `run-982b83ea17234882`, `run-668bd15a15574a8e`, `run-4f06591586f643ae`: 100, 18/18 each | `run-a8eaa4f9760646d5`: 10, 14 pass / 4 fail (targets only) | alternative-a (as declared); compat-negative-hit-points-for-every-thing (as declared); target-negative-no-hit-point-floor (as declared) |
| `bill-autopilot-repeat-mode-ownership` | 17 | `run-b0b9af2e411c4533`, `run-f7acecdd3b194b71`, `run-a1f126612b8a4e7c`: 100, 17/17 each | `run-6e13dc05026a491b`: 10, 11 pass / 6 fail (targets only) | alternative-a (as declared); compat-negative-name-not-saved (as declared); target-negative-mode-not-saved (as declared) |
| `playwright-nonbulk-trade-accounting` | 14 | `run-668675cce8b248b4`, `run-5fbff2f37d2f4d8d`, `run-f948c42e65b749ae`: 100, 14/14 each | `run-f094d90a0f154091`: 10, 8 pass / 6 fail (targets only) | alternative-a (as declared); compat-negative-factionless-trader-notified (as declared); target-negative-no-thing-guard (as declared) |
| `zombieland-dynamic-needs-capacities` | 19 | `run-af954a4216224655`, `run-ecbfa55fc6e34445`, `run-a7954f5d90494544`: 100, 19/19 each | `run-1a6a6b0e04394aad`: 10, 13 pass / 6 fail (targets only) | alternative-a (as declared); compat-negative-dead-pawns-raised (as declared); target-negative-capacity-pinned-to-one (as declared) |

Every run was complete. Each starter failed only cases the clause maps classify as
`target`; the five target cases that already pass on the starter
(`map-temperature-not-authoritative`, both vanilla-quality cases,
`foreign-drift-not-flattened` and `need-max-two`) cannot detect their defect and are
recorded as weak evidence in the clause maps. The E0 study controls
(`private/study-controls/<task>/`, run with `rhenium-study e0 run` in a separate study
state) behaved as declared for all nine tasks. One extra strict-reading control shows
that `r4-small-bench-ingredient-consumption` over-constrains the exam: a search over
vanilla's first 200 radial cells, a literal reading of "vanilla-equivalent", fails
`outside-radius-preserved`, which is now flagged `over_constrained`. Starter/base,
reference/oracle and no-op outcomes are also recorded in each task's
`validation/controls.json` and `validation/provenance.md`.

Adaptive Storage is blocked. Its starter and reference `StorageRenderer.cs` use C# 14
lambda parameters with modifiers but no types (`static (data, phase, in transform) =>`),
which the pinned .NET SDK 8.0.422 compiler rejects under the pack's C# 12 build
(CS1001). The authoring revision lowered C# 14 field-backed properties but missed
these three lambdas. A newer Roslyn cannot run in the pinned SDK image
(`Microsoft.Net.Compilers.Toolset` 4.14 needs .NET 9). Making the task compile
requires either lowering the three lambdas in both starter and reference or a newer
pinned SDK image, both beyond a verifier repair. In a scratch copy with the lambdas
lowered, the reference and harness compiled, and the first gate then failed its
`StorageCellRect` enumeration check, so further harness work is also needed.

## Adaptive Storage compatibility repair (2026-10-26)

Catalog 0.3.4 / authoring revision 5 supersedes the Adaptive Storage compilation
blocker above. With the same SDK 8.0.422 and C#12 build, the original reference
reproduced all three CS1001 errors. Explicit parameter types in the three lambdas
now let fresh base, reference and independent no-op candidates and their matching
verifiers compile successfully on macOS arm64 with locked NuGet restore. The
candidate builds retain upstream warnings; this is not warning-free validation.

The authored rectangle adapter now enumerates the public `CellRect.Cells`
property. Its existing empty-width, coordinate, area and containment verifier
checks are unchanged. This change still needs a real-game rerun to confirm that
it resolves the previously recorded enumeration failure. No case, expected value,
weight, public exam or slot-limit implementation changed.

The original nine tasks retain their recorded engine evidence under their
original identities. Adaptive Storage remains blocked for full use: this host
has no Docker or licensed controlled Linux x86_64 game environment. No matching
role images, oracle/base/no-op game runs or mutation controls were executed for
these changed inputs. Fresh reference compilation is checked separately and is not
an engine pass. See [revision 5](rimworld-authoring-revision-5.md) for commands,
version/evidence decisions and remaining acceptance gates.

## Adaptive Storage acceptance (revision 6)

Catalog 0.4.1 / authoring revision 6 repairs one fixture check in the Adaptive
Storage verifier. When revision 5 first ran in the real game on this host, the
`runtime-defs-ready` gate failed with "storage rectangle enumeration differs from
game API". The cause is in the game, not the candidate: `CellRect`'s own struct
enumerator yields one cell for a zero-width rectangle whose `Cells` and `Area` are
empty, so the authored `StorageCellRect` adapter could never agree with both. The
self-check now compares the adapter with the public `CellRect.Cells` and
`CellRect.Area` pair. No case, expected value, weight, public exam, starter or
reference changed. The five fixture mutations in `validation/mutation-controls.json`
carry the new verifier's input and mutated hashes.

On the Linux x86_64 Docker host, `rhenium runtime prepare` rebuilt the role images
for 0.4.1. The following ran through the Hub's `full` profile on 2026-10-30:

- the reference passed 15/15 three times with identical case outcomes;
- the unchanged starter and an independently materialized no-op each completed and
  failed exactly `saved-unlimited-restored` and `setter-not-skipped`;
- each of the nine behavioral mutations completed and failed at least its planned
  cases.

The five fixture mutations change the verifier itself, so the Hub refuses them
against the prepared adapter. They ran on a diagnostic path instead: the prepared
builder and evaluator images, the evaluator's sandbox flags and the mutated adapter
source. Each ended incomplete with a fatal ("fixture cleanup failed", or the
injected fixture fault), so no fixture fault can produce a pass. Their planned
`fixture-state-restored` failure is not reached, because the observer stops
first. The record is the task's `validation/controls.json`; revision 5's
compile-only record is its history.

The study inventory now admits the task. In its E0 baseline the starter failed
exactly those two target cases and the reference passed; see
`private/study-controls/adaptive-storage-slot-limit-restore/NOTES.md`.

## Research-tab task (catalog 0.4.0)

**Keep research-tab state consistent after re-layout** (`research-organized-tab-state`)
is based on Research: Organized's real fix
[4941919](https://github.com/Cruesoe/ResearchOrganized/commit/4941919bf33fb84ff280fa64c500c4439118b5e0)
over its single parent `8d978d5`. Both exact trees carry byte-identical MIT
licenses, and all thirteen production C# files are retained byte-exact in the
starter and reference. The English exam covers native per-tab visibility through
hide, restore and re-index transitions, and the persistent research window while
it is closed. Calls happen on the game thread; background-thread game loading,
DLC, other Mods, screenshots and disk saves are outside the scored scope.
Difficulty is set to hard and has not been measured against a model.

The task was authored as an unregistered reserve (draft catalog 0.1.0 and 0.2.0,
2026-10-26; selection review and inputs in the task's `validation/authoring.md`).
Catalog 0.4.0 registers it as the eleventh task. It is the only task that declares
`runtime_data_files`: the Mod's two unchanged `Defs` XML files, which the runtime
builder stages and hashes into adapter evidence and the task's `tests/test.sh`
installs into the candidate Mod (see the plugin README). The 22 protocol v3 cases
use the real `ResearchManager`, `DefMap`, `ResearchTabDef` and the game's
persistent `MainTabWindow_Research`, opened and closed through the native
`WindowStack`. A checkpoint restores every touched native object without calling
candidate code.

### Verifier repairs (authoring revision 3)

The first real-game runs on 2026-10-29 exposed two fixture defects. Neither
changes a case ID, expected value, gate, weight, exam, starter or reference.

- The verifier started on the game's first finish-loading callback, before the
  entry UI exists. `Find.UIRoot` was still null, so the readiness gate threw and
  no case ran. Observation now starts on the first main-thread frame with an entry
  window stack and no pending long event, after at most 120 seconds. The gate also
  fails closed with an explicit message when that stack is missing.
- The view-width fixture moved a project's `researchViewX`, but the research
  window sizes its view from `ResearchViewX`, which only the game's own
  `ResearchProjectDef.GenerateNonOverlappingCoordinates()` copies across. The
  fixture now calls that native routine after the move. The checkpoint already
  restores every project's coordinates.

### Engine validation (2026-10-29)

All runs used `rhenium run --profile full` against the role images that
`rhenium runtime prepare` built for catalog 0.4.0, on the same Linux x86_64 Docker
host, networkless. Controls were materialized by the task's
`validation/reference_compile.py`.

| Control | Run | Result |
| --- | --- | --- |
| Reference (three runs) | `run-50c8489160074ca7`, `run-6b59bb1eabec4946`, `run-94276ef7761d4963` | 100, 22/22 each, identical case outcomes |
| Unchanged starter | `run-df04630b57914c11` | 10; 8 pass, 14 fail (targets only) |
| Independently copied no-op | `run-83729fe2022449f7` | 10; the starter's 14 failures exactly |
| `no-resize` | `run-7184169c6909484b` | 10; fails the seven flag-storage cases |
| `default-flags` | `run-47e8af0447c64176` | 10; fails `edited-visibility-preserved`, `flags-follow-tabs`, `repeated-relayout` |
| `open-window-only` | `run-3089a458349c44d7` | 10; fails the five closed-window cases |
| `stale-view` | `run-2937484be45046d7` | 10; fails `closed-view-recomputed`, `open-view-recomputed` |
| `closed-window-only` | `run-3667db8d3763413d` | 10; fails `explicit-open-refresh`, `open-view-recomputed`, `open-window-relayout` |
| Alternative fix (`alternative-a`) | `run-b877e983c7b3426e` | 100, 22/22 |

Every run was complete. Each authored negative failed at least every case its
plan names. The starter's 14 failures are all `target` cases in the clause map;
`edited-visibility-preserved`, `selected-project-preserved` and
`current-tab-preserved` already pass on it and are recorded as preserved overlap.
E0 study controls (`private/study-controls/research-organized-tab-state/`) were
run with `rhenium-study e0 run` in a separate study directory: starter,
reference, three target-negatives, one compat-negative and the alternative fix all
behaved as declared. The study inventory now includes the task. The run IDs, image
identities and hashes are in the task's `validation/controls.json`.

No model has attempted the task.

## Compiler evidence

The repository has no CI workflow. On 2026-10-28 the former Linux RimWorld CI job,
after installing `libicu74` for the pinned SDK, compiled all twenty-two assemblies for
commit `c40c44a2`: three Adaptive Storage controls and the then-unregistered
research-tab reserve's eight controls. Both compile reports retain
`engineValidated=false`; compilation does not change engine-validation status.

## Local checks

With the configured development environment, run the repository checks locally:

```sh
devenv shell -- check
```

This runs Ruff, Mypy, the Python suite, frontend lint/tests/build, ShellCheck and
`git diff --check`. The separate fixed-SDK compile commands are documented in
[Adaptive Storage revision 5](rimworld-authoring-revision-5.md) and the research-tab task's
[authoring notes](../../benchmarks/rimworld-core/private/harbor/research-organized-tab-state/validation/authoring.md).
Local macOS compilation does not exercise Ubuntu container setup.
Linux-only checks need their declared environment, and full game acceptance still
requires the licensed controlled Linux x86_64 runtime. Preserve unavailable engine
skips and report environment failures; a local subset is not a full benchmark pass.

The [compile and game-acceptance loop](rimworld-acceptance-loop.md) defines the
iteration policy, evidence identities, retry limits and separate acceptance gates.
