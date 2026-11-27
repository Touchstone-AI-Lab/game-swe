# Slay the Spire benchmark support

## Ownership and status

| Field | Value |
| --- | --- |
| Maintainer | Changyi Yang |
| Status | `In Development` |
| Plugin ID | `slay-the-spire` |
| Catalog | `slay-the-spire-core` 1.8.0: nine native-runtime repair tasks; the three standalone ModTheSpire tasks are retired |
| Plugin distribution | `plugins/slay-the-spire/` (`rhenium-slay-the-spire`) |
| Benchmark pack | `benchmarks/slay-the-spire-core/` |

The integration is In Development: the catalog, container runtime builder and evaluator
are implemented and unit-tested. Plugin 0.7.0 prevents loader-only tasks from
producing complete or passing benchmark results. The three original standalone tasks historically completed loader-only
starter/reference controls on a Linux x86_64 host with Docker (every unchanged starter is
complete and fails only the assertions its defects cover; every reference scores 100/100). The pack's own
`validation/` directory records how each task was built and validated.

The three tasks are registered in the `tools/study` inventory. E0 admission on 2026-09-23
(3 starter, 3 reference, 3 target-negative, 3 compat-negative and 3 alternative control
executions on the real evaluator) admitted and qualified all three with no flagged case.
Four report clauses are recorded as `weak` because their only assertions already pass on
the starter: #734 and #737 in `mts-load-order-regressions`, #1019 and #909 in
`mts-loader-internals-regressions`. Clause maps, controls and notes are under
`benchmarks/slay-the-spire-core/private/study-controls/`. Catalogs 1.6.0 to 1.8.0
retire all three; their inventory entries were removed with them.

## Native-runtime tasks

Native preparation has a single explicit command in the
[runtime guide](../../benchmarks/slay-the-spire-core/private/native-runtime/README.md):
it pulls the published `ghcr.io/changyiyang/swe-game-sts-tools` image by its locked
registry digest, validates the operator's licensed game JAR and reconstructs the
nine admitted task images locally. `--build-tools` rebuilds the public tools layer from
the pinned recipe instead. The public layer contains no game, mod SDK, task or
verifier payloads. The resulting game-bearing images remain local. The Hub's
Steam-managed runtime `slay-the-spire/sts-native-646570-build10180494` runs the same
recipe on a JAR it downloads from the pinned Steam depot with the operator's own
account, and its evaluator runs each task's offline verifier on the submission.

Nine further tasks (`basemod-dynamic-descriptions-r2`, `stslib-block-ledger-r1`,
`mts-enum-identity-r3`, `stslib-icon-layout-r1`, `downfall-stasis-lifecycle-r1`,
`basemod-phase-transitions-r1`, `downfall-socket-flow-r3`, `mts-load-order-regressions-r2`,
`mts-mod-identity-regressions-r2`) repair BaseMod, StSLib, ModTheSpire and Downfall source
trees. All nine launch the real
game under ModTheSpire. `mts-enum-identity-r3` launches it once per case through
the submitted ModTheSpire build; it replaces the retired `mts-enum-identity-r2`,
whose standalone JVM probe never launched the game. `mts-load-order-regressions-r2` and
`mts-mod-identity-regressions-r2` launch the game with the submitted build and run r1's
unchanged JUnit suites inside it. They need the licensed `desktop-1.0.jar`, which the Hub downloads
from Steam (`rhenium auth login steam`, then
`rhenium runtime prepare slay-the-spire/sts-native-646570-build10180494`) or which an
operator supplies to the manual Harbor workflow in
[`private/native-runtime/README.md`](../../benchmarks/slay-the-spire-core/private/native-runtime/README.md);
their control records are in `benchmarks/slay-the-spire-core/validation/native-engine/`.
Their starter is `project/`. Without the prepared runtime the Hub reports a real-game
evaluation as incomplete. A task without a runtime binding always returns
incomplete, including when legacy artifacts exist; catalog 1.8.0 has no such task.
The native builder admits only the nine tasks that launch the game; a new or unknown task
is unavailable until explicitly admitted by the plugin. All nine game-backed tasks are
registered in the study inventory. `mts-enum-identity-r3`, `mts-load-order-regressions-r2`
and `mts-mod-identity-regressions-r2` were admitted on 2026-11-02, after an E0 baseline on
the real game on the Lab host: each unchanged starter scored 10 and failed exactly its
target cases, and each reference scored 100. The two r2 tasks keep r1's reviewed clause
maps under their new case ids. Their clause maps and E0 notes are under
`benchmarks/slay-the-spire-core/private/study-controls/`. The retired enum r2 was never
registered.

The [initial 2026-10-27 Lab controls](../../benchmarks/slay-the-spire-core/validation/native-engine/lab-steam-runtime-controls.json)
preserve five real-game NOP/gold pairs (186/186 reference cases) and the socket
r2 failure (3/13 gold; initial NOP timeout). Catalog 1.4.0 retires r2 (SG-138)
and introduces the explicitly authorized r3 baseline (SG-159), preserving the
old source and control records.

The [final r3 Lab controls](../../benchmarks/slay-the-spire-core/validation/native-engine/lab-steam-runtime-controls-r3.json)
completed all six real-game NOP/gold pairs on the automatically Steam-prepared
runtime: gold passed 199/199 assertions and every NOP failed-case set matched its
intended baseline. Socket r3 passed gold and an independent alternate 13/13;
the two isolated repairs matched their original 10/13 and 9/13 outcomes. The
[revision review](../../benchmarks/slay-the-spire-core/validation/native-engine/downfall-socket-flow-r3/revision.md)
documents fixture initialization, the software-renderer frame guard and action
phase checks. No r2 result is relabeled as r3. At catalog 1.4.0, four
loader-only paths remained unavailable for full results.

Catalog 1.5.0 retires the enum JVM probe r2 (SG-134) and introduces the explicitly
authorized real-game r3 baseline (SG-161), preserving the old source and control records. The
public exam, starter, reference, fixture mods and fifteen expected observations are unchanged;
only the execution vehicle changes. The
[revision review](../../benchmarks/slay-the-spire-core/validation/native-engine/mts-enum-identity-r3/revision.md)
describes the in-game observer, and its
[Lab receipt](../../benchmarks/slay-the-spire-core/validation/native-engine/mts-enum-identity-r3/author-controls.json)
records the Hub controls on the Steam-prepared catalog 1.5.0 runtime: NOP 5/15 with r2's
ten intended failures, gold 15/15 twice, the r2 alternative 15/15, and r2's three isolated
repairs with their original failure sets. The
[catalog 1.5.0 replay](../../benchmarks/slay-the-spire-core/validation/native-engine/lab-steam-runtime-controls-catalog-1.5.0.json)
repeats NOP and gold of the six other admitted tasks on the same runtime with their
recorded outcomes (214/214 gold cases across the seven tasks). No r2 result is relabeled
as r3.

Catalog 1.6.0 retires `mts-load-order-regressions` (SG-129) and introduces the
explicitly authorized real-game `mts-load-order-regressions-r2` (SG-162). Its exam,
starter, reference and private JUnit suite are byte-identical to r1. The verifier builds
the submitted sources with the upstream build template and the licensed game, always
leaving out the starter's two loader-only stand-ins for game classes, and runs the suite
inside the game that build launched. The
[revision review](../../benchmarks/slay-the-spire-core/validation/native-engine/mts-load-order-regressions-r2/revision.md)
and [Lab receipt](../../benchmarks/slay-the-spire-core/validation/native-engine/mts-load-order-regressions-r2/author-controls.json)
record the Hub controls on the catalog 1.6.0 runtime: NOP 5/9 with r1's four target
failures, gold 9/9 twice, the study-control alternative 9/9 and both negative controls
with their recorded failures. The JUnit artifacts the suite needs are pinned in the native
Maven lock. Catalog 1.7.0 does the same for `mts-mod-identity-regressions` (SG-130), now
`mts-mod-identity-regressions-r2` (SG-163); its
[Lab receipt](../../benchmarks/slay-the-spire-core/validation/native-engine/mts-mod-identity-regressions-r2/author-controls.json)
records NOP 3/7 with r1's four target failures, gold 7/7 twice, the study-control
alternative 7/7 and both negative controls with their recorded failures. The
[catalog 1.7.0 replay](../../benchmarks/slay-the-spire-core/validation/native-engine/lab-steam-runtime-controls-catalog-1.7.0.json)
repeats NOP and gold of all nine admitted tasks on that runtime with their recorded
outcomes (230/230 gold cases). Two attempts there were superseded and are disclosed in
the receipt: a descriptions NOP returned no complete observation set under high host load
(372 seconds against the verifier's unchanged 300-second game bound; the private log was not
inspected), and a mod-identity control stopped before evaluation on a Hub task-lookup error.
Each was re-run once unchanged.

Catalog 1.8.0 retires `mts-loader-internals-regressions` (SG-131) without a replacement.
Its starter's injected `PostfixPatchInfo` defect makes the loader treat a void method's first
postfix parameter as a result. ModTheSpire's own core postfix `ModsScreenUpdateRender$Render`,
on the void `MainMenuScreen.render`, then fails to compile, patching aborts and the real game
never launches for an unrepaired submission. No assertion can be observed in the game for
the NOP, so the required NOP gate is impossible there; the reference passed 16/16 in a Lab
prototype of the in-game harness. Its exam, source, verifier and study controls are
preserved unchanged.

Those socket r3 controls ran on an isolated classic-store Docker daemon. The
[2026-10-30 containerd-store controls](../../benchmarks/slay-the-spire-core/validation/native-engine/lab-containerd-runtime-controls.json)
repeat them on Lab's host Docker 29.8.1 with the containerd image store, after the
recipe began accepting the pinned manifest digest that store reports for the tools
image. `rhenium runtime prepare` built every verifier image there, gold passed
199/199 assertions, and each NOP failed exactly the case set of the r3 record.

## Task inventory

Historical loader diagnostics measured on 2026-09-23. These are not real-game
benchmark results; plugin 0.7.0 returned incomplete for all three tasks. Catalogs 1.6.0
to 1.8.0 retire all three: two in favor of real-game r2 revisions, and
`mts-loader-internals-regressions` without a replacement.

| Task | Assertions | Difficulty | Starter | Reference |
| --- | --- | --- | --- | --- |
| `mts-load-order-regressions` | 9 | hard | 10/100, 4 assertions fail | 100/100 |
| `mts-mod-identity-regressions` | 7 | hard | 10/100, 4 assertions fail | 100/100 |
| `mts-loader-internals-regressions` | 16 | hard | 10/100, 5 assertions fail | 100/100 |

Each task vendors the upstream ModTheSpire `master` tree with several defects put back into
it: some reverse upstream fixes, the rest were injected by the pack's author, and the
reference removes all of them (`task.toml` records `gold_patch_origin` per task). The
public exam reports only what a mod author observed;
it never states how many underlying defects there are, and the assertion count lives in
the private verifier rather than in the catalog.

## The retired standalone tasks ran without the paid base game

Slay the Spire's `desktop-1.0.jar` is not redistributable, so no standalone task linked
against it (the managed runtime acquires its copy from Steam and keeps it local).
ModTheSpire's loader, dependency resolution, mod descriptors, patch generation,
parameter binding and enum injection all compile and run against the JDK and Javassist
alone. Each task image strips the `systemPath` dependency on the game jar and excludes the
two source trees that genuinely need it (`patches/**` and `PackageJar.java`).

The original standalone tasks and the retired `mts-enum-identity-r2` do not meet the real-game
requirement in AGENTS.md. Their historical loader results cannot count as full
game-backed results. The manual Harbor workflow also does not satisfy automatic
acquisition; use the explicit Steam runtime lifecycle for the nine game-backed tasks.

**JDK 8 is required, not incidental.** `MTSClassLoader` and `EnumBusterReflect` use
`sun.misc` and `sun.reflect` internals and `ReflectionHelper` rewrites `Field.modifiers`;
all of that is removed or blocked from Java 9 onwards.

## Version policy

- Legacy loader evaluator base image (no task is bound to it): `maven:3.9-eclipse-temurin-8`, pinned by digest in
  `benchmarks/slay-the-spire-core/runtimes.json` and acquired through the
  [public-container provider](../../providers/container/README.md).
- Upstream source: [ModTheSpire](https://github.com/kiooeht/ModTheSpire) (MIT), vendored
  per task at that task's base commit; upstream's `LICENSE` travels with the snapshot.
- The repository stores and redistributes no licensed content. Native tasks use the
  game JAR from Steam app 646570, depot 646571, manifest 9072802409324604124, checked
  by SHA-256; the Hub downloads it only during an explicit `runtime prepare` with the
  operator's own account, and the built images stay local.

## Platforms

| Surface | Supported platforms |
| --- | --- |
| Evaluator image build and evaluation | Linux x86_64 with Docker |
| Submitted code | Java 8 (Maven) |

## Runtime setup

```sh
rhenium auth login steam
rhenium runtime doctor  slay-the-spire/sts-native-646570-build10180494
rhenium runtime prepare slay-the-spire/sts-native-646570-build10180494
rhenium runtime verify  slay-the-spire/sts-native-646570-build10180494
```

Plugin 0.7.0 changes the runtime fingerprint. Re-run `runtime prepare` after upgrading;
an artifact prepared by 0.6.0 is not accepted as the current runtime. Catalogs 1.4.0
to 1.7.0 also change the runtime version/fingerprint to bind their task sets (socket r3,
enum r3, load-order r2, then mod-identity r2); re-run `runtime prepare` after each upgrade. The legacy
`modthespire-jdk8-maven` specification remains available for verifying/pruning old
SDK artifacts, but no benchmark task is bound to it. Its historical build behavior
is described below.

Preparation pulls the pinned base image, checks that Docker reports the pinned repository
digest and that the image contains the declared Maven and `javac` binaries, then builds one
evaluator image per task from that task's `environment/Dockerfile`. Those builds warm the
Maven repository and therefore need network access; the Dockerfile then re-runs the same
goals offline so an incomplete cache fails the image build rather than a scored run. Each
image is labelled with the runtime fingerprint, the pinned source reference, the task ID
and a digest of its build context, and `verify`/`prune` act only on images carrying those
labels. **Evaluation containers run with `--network=none`.**

## Evaluation levels

Only the nine admitted real-game tasks can produce a complete result. Their two
checks are source shape (10 points) and the native engine verifier (90 points).
All native cases must be observed with valid counts, a successful build and a
successful verifier exit. A loader-only task returns the source-shape diagnostic
and an incomplete engine check without starting a loader or accepting its reward.
`core` is always incomplete.

The following describes the retained internal loader diagnostics for historical
report parsing and regression coverage; these diagnostics are not a public full
benchmark evaluation:

1. `submission-shape` (10 points): the `modthespire/` tree is present, holds every declared
   required file, and carries no symbolic links, version-control metadata or compiled
   artifacts outside build output. The upstream `.mvn/wrapper/maven-wrapper.jar` is part of
   the vendored tree and is allowed.
2. `private-suite` (90 points): the pack's private JUnit suite is staged over the
   submission and run offline with `mvn -B -o clean test`. A result counts as complete only
   when the verifier's own summary reports exactly the declared number of assertions with
   none skipped; it passes only when there are no failures or errors, the verifier exited
   zero and it recorded a reward of 1.

The `core` profile skips the suite and is always incomplete. A submission that does not
compile produces no assertion summary and is therefore incomplete rather than failed.

A complete result also names every observed case (`<class>.<method>`, for example
`gcb.LoadOrderTest.aChainOfDependenciesResolves`) in `runtime.caseOutcomes` and in the
`private-suite` check's `details.cases`, read from the Surefire XML reports the evaluator
copies out of the container. Case names are reported only when they account for exactly the
counted outcomes; they never change the verdict, which the summary line alone decides.

## Security boundary

Standalone evaluation containers drop network access and all capabilities, forbid privilege
escalation, and mount both the submission and the private tests read-only. The base
image's integrity rests on the pinned repository digest recorded in the reviewed catalog,
not on a publisher signature, and the derived evaluator images are identified by their
immutable local image IDs. The private suite runs in the same JVM as the submitted code:
this is the honest-mode boundary, and untrusted submissions belong on a disposable host.

Native verifiers disable network access and mount the submitted Java source
read-only. Their frozen harness starts as container root to build and launch
the game, then uses an unprivileged game process. Tests are copied to private
scratch storage and mounted writable because the harness adjusts their modes.
These containers retain Docker's default capabilities and writable root filesystem;
the standalone container restrictions above do not describe this native path.

Native preparation enforces its deadline while reading output and terminates its
own process group on failure. Runtime pruning leaves cache-directory removal to
core and never recursively deletes the artifact's descriptive location. Full
evaluation also rejects malformed counts, duplicate case IDs, contradictory case
verdicts, and unsuccessful verifier exits.
Preparation errors expose a generic message; recipe output, command arguments
and private paths remain in the operator's mode-0600 preparation log.
Evaluation rejects a missing local image without attempting a Docker pull.
The verifier sets Java's active processor count from the task's CPU allocation.
The pinned JDK 8 otherwise sees all host CPUs on cgroup-v2 hosts and can create
many compiler and GC threads despite a two-CPU quota.

The native recipe builds with Docker's classic builder (`DOCKER_BUILDKIT=0`) from
local image IDs, on either image store. The classic store reports the public tools
image's configuration digest as its ID; Docker 29's containerd image store reports
the pinned manifest digest instead, which content-addresses that configuration. The
recipe accepts exactly those two IDs and fails closed on any other. The host daemon
must not be reconfigured to accommodate a benchmark run.

## Official references

- [ModTheSpire](https://github.com/kiooeht/ModTheSpire) is the MIT-licensed upstream
  project these tasks vendor.
- `benchmarks/slay-the-spire-core/validation/` records how each task was validated.
