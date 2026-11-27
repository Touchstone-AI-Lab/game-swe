# Mindustry benchmark support

## Ownership and status

| Field | Value |
| --- | --- |
| Maintainer | Yunge |
| Status | `In Development` |
| Plugin ID | `mindustry` |
| Catalogs | `rhenium-mindustry-v2` 2.0.0 (`benchmarks/mindustry-core`, Hub key `mindustry/mindustry-core`): five repair tasks on the open-source Mindustry v159.7 game sources; `rhenium-mindustry-v1` 1.2.0 (`benchmarks/mindustry-construct`, Hub key `mindustry/construct`): ten construct tasks, a server plugin written from an empty scaffold |
| Plugin distribution | `plugins/mindustry/` (`rhenium-mindustry`), dispatching on the catalog id |
| Benchmark packs | `benchmarks/mindustry-core/` (repair), `benchmarks/mindustry-construct/` (construct) |
| Runtimes | `mindustry/mindustry-159.7` (repair pack), `mindustry/mindustry` (construct pack) |

The integration is In Development and serves two packs. In the repair pack every task
is a repository-debugging task: the model receives the Mindustry v159.7 source tree
(`core/src`, `server/src`, `annotations/src`, GPL-3.0) with real upstream defects and
must repair them; a hidden suite judges the result inside the real headless dedicated
server. The construct pack is the earlier generation catalog `rhenium-mindustry-v1`:
it was deleted in `9b038435` and restored on 2026-09-24 next to the repair pack, with
its task content unchanged (see [Construct pack](#construct-pack-mindustryconstruct)).
The plugin selects the catalog model, evaluator and runtime builder by catalog id, so
the repair evaluator behaves exactly as before the restoration. Both paths are
implemented and unit-tested; the acceptance records below were produced on a Linux
x86_64 host with Docker. No model has been run on the repair tasks yet.

The sections up to [Acceptance record](#acceptance-record) describe the repair pack.

## Task inventory

Each task combines several real upstream bug fixes. A fix that shipped in v159.7 or
earlier is reverted in the starter (the reference is v159.7 as released); a fix first
released after v159.7 is absent from the starter and applied in the reference. No task
contains an injected, non-upstream defect. Provenance, fix commits and the defect
analysis are in each task's private `NOTES.md`.

| Task | Upstream fixes | Server cases | Difficulty |
| --- | --- | --- | --- |
| `logic-processor-regressions` | 4 (`sensor` result on failure, link renaming on block replacement, `format` in a full print buffer, saving query results) | 11 (4 target, 6 preserved, 1 sentinel) | hard |
| `server-console-regressions` | 4 (`pause`, `host` with shuffle `none`, `pardon`, player records after a restart) | 10 (4 target, 5 preserved, 1 sentinel) | medium |
| `defense-and-heat-regressions` | 4 commits, 3 behaviours (turret reload after idling, disabled heat redirectors, shockwave tower range) | 9 (3 target, 5 preserved, 1 sentinel) | medium |
| `payload-and-save-regressions` | 3 (derelict payload conveyors after loading, long build queues in saves, dropping derelict payloads near cores) | 10 (3 target, 6 preserved, 1 sentinel) | hard |
| `data-patch-regressions` | 3 (patches using server-defined content, patched build towers, planet-restricted patches) | 7 (3 target, 3 preserved, 1 sentinel) | hard |

## Version policy

- Server distribution: the official Mindustry dedicated-server release.
- Pinned build: **v159.7** (`server-release.jar`, SHA-256
  `e41289c32bcf765eb50fa131e6b515d741e20f7843fb567d3aa949e7461f22ab`,
  19,158,443 bytes), published as
  [v159.7](https://github.com/Anuken/Mindustry/releases/tag/v159.7) and built from
  commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`, the base commit of every task.
- The jar is **not** stored in this repository. `rhenium runtime prepare` downloads
  it from the release through the
  [official-download provider](../../providers/official-download/README.md), pinned
  to the exact URL, size and SHA-256 above, so a substituted, truncated or changed
  download fails closed before any image is built. GitHub's release API reports the
  same SHA-256 for the asset.
- JDK: `eclipse-temurin:17-jdk` pinned by digest
  (`sha256:bc033b57e11b773c3043babfd664e7a5ef110805548b921cbfc3e8c67a0725d6`); the
  release jar is Java 17 bytecode.

## Platforms

| Surface | Supported platforms |
| --- | --- |
| Mindustry dedicated server | Any JVM platform; this integration runs it in Linux containers |
| Runtime preparation and evaluation | Linux x86_64 with Docker |

## Programming languages

| Component | Language |
| --- | --- |
| Agent submission | Java (the Mindustry game sources) |
| Trusted harness plugin and hidden grader suites | Java 17 |
| Verifier (`verify.py`), catalog, runtime builder, evaluator | Python 3.12 |
| Build and scoring wrappers | Bash |

## Runtime setup

`rhenium runtime prepare` downloads the pinned server jar itself; evaluation never
downloads, installs or updates it:

```sh
rhenium auth login official-download
rhenium runtime doctor  mindustry/mindustry-159.7
rhenium runtime prepare mindustry/mindustry-159.7
rhenium runtime verify  mindustry/mindustry-159.7
```

The [official-download provider](../../providers/official-download/README.md)
requests `https://github.com/Anuken/Mindustry/releases/download/v159.7/server-release.jar`.
It follows GitHub's redirect only to the declared asset host
`release-assets.githubusercontent.com`, over HTTPS, and keeps the file only at the
pinned size (19,158,443 bytes) and SHA-256. A redirect to any other host fails
closed. The provider reuses an unchanged cache and never overwrites a partial or
changed one. The builder enforces the catalog's `expectedFiles` and `sha256`
itself. Preparation stages the jar next to `benchmarks/mindustry-core/private/runtime/`
and the trusted harness sources, builds the base image
`rhenium-mindustry-verifier:159.7` (Debian packages for the verifier, harness
compilation against the jar, and one boot of the real server with the harness in
bootstrap mode), then builds one verifier image per task from the task's `tests/`
directory (the hidden suite is compiled and packaged with the harness there) and records
each immutable image ID with ownership labels. Image builds need network access for the
package installation; **evaluation containers run with `--network=none`**, no
capabilities, and the submission mounted read-only. On a congested Docker daemon an
image build can take tens of minutes; each build is allowed two hours.

## Evaluation layers

1. `submission-shape` (gate): the submission holds the `mindustry/` tree with its source
   roots, and no symlinks, VCS metadata or compiled artifacts.
2. `offline-build` (10 points): every `*.java` file under `core/src` and `server/src`,
   plus `annotations/src/main/java/mindustry/annotations/Annotations.java`, is compiled
   with `javac --release 17 -proc:none` against the pinned `server-release.jar`, which
   supplies Arc, the generated `mindustry.gen` classes and every other dependency. A
   compilation failure makes the run incomplete.
3. `live-server` (90 points): the real dedicated server
   (`mindustry.server.ServerLauncher`) starts with the compiled classes ahead of the
   pinned jar on the class path and the trusted harness plugin, packaged with the task's
   frozen grader suite, in `config/mods`. After `ServerLoadEvent` the harness runs every
   case on the server's main thread in its own freshly built world (or through the
   server console), advancing the game with a fixed one-tick delta, prints exactly one
   `MINDUSTRY_RESULT` line tagged with the run's nonce, and stops the server. The case
   set must equal the frozen `serverCases`; per-case outcomes are reported as
   `runtime.caseOutcomes` for complete runs.

The `core` profile skips every layer and is always incomplete. A missing runtime, a
server timeout, a hung case (60 s watchdog), a malformed or duplicated result line or a
nonce mismatch make the run incomplete, never passing. A complete result can still
fail; `passed` requires 100/100.

Code generated at build time (`mindustry.gen`, including the entity classes generated
from `core/src/mindustry/entities/comp`) and all assets come from the pinned jar and are
not regenerated, so no task depends on a fix inside those generated or asset files.

## Acceptance record

Evaluations through `rhenium run mindustry/mindustry-core/<task> <submission>` with the
prepared `mindustry/mindustry-159.7` runtime on the Linux x86_64 host with Docker,
2026-09-24. "Starter" is the unchanged starter tree, "reference" the starter with
`solution/after` copied over it.

| Task | Starter | Reference (three runs) |
| --- | --- | --- |
| `logic-processor-regressions` | 10.0 (`run-2964971c3042486d`), fails exactly its 4 target cases | 100.0 / 100.0 / 100.0 (`run-1c5b0ca15bd84dbe`, `run-8be5ba344cd2405f`, `run-5028077495b84b04`), identical outcomes |
| `server-console-regressions` | 10.0 (`run-ae147d1991044e25`), fails exactly its 4 target cases | 100.0 / 100.0 / 100.0 (`run-44e5500cf7b143c8`, `run-071586d83e6f4772`, `run-99580f0240cc44b1`), identical outcomes |
| `defense-and-heat-regressions` | 10.0 (`run-8399669fde374efd`), fails exactly its 3 target cases | 100.0 / 100.0 / 100.0 (`run-7c9ac7b5f15840e4`, `run-737ad02c36164c2e`, `run-b01415ea60a0403c`), identical outcomes |
| `payload-and-save-regressions` | 10.0 (`run-49ccb04033ed457d`), fails exactly its 3 target cases | 100.0 / 100.0 / 100.0 (`run-30e0d412410b4466`, `run-ac748f0a06fa4a67`, `run-791a22091b5d489a`), identical outcomes |
| `data-patch-regressions` | 10.0 (`run-635837b9fcfe4d59`), fails exactly its 3 target cases | 100.0 / 100.0 / 100.0 (`run-7305d0e4ad074730`, `run-d0891aed0f734fc7`, `run-191fa39c14364ba3`), identical outcomes |

Two first reference runs (`logic-processor-regressions`, `payload-and-save-regressions`)
were voided as incomplete because `docker create` or `docker rm` on the congested shared
Docker daemon exceeded 300 s; both were rerun (the table lists the reruns), and the
runtime now allows container removal 900 s and removes a container whose creation timed
out. Each run took 5 to 15 minutes on that host.

After the construct pack was restored and the plugin began dispatching on catalog id
(2026-09-24), `mindustry/mindustry-159.7` was prepared again. It produced the same
artifact identity
(`sha256:f7a7b942c458a0bcca66fe9215c0cf35ffeb78722100a37826b464eaa9cc8d05`) and the
same image IDs. Two tasks were then evaluated again through `rhenium run`:

- `server-console-regressions`: the starter scored 10.0 (`run-895a59af02a74233`) and
  failed exactly its 4 target cases; the reference scored 100.0
  (`run-303931f81660438e`).
- `data-patch-regressions`: the starter scored 10.0 (`run-96ee6563776e4da7`) and failed
  exactly its 3 target cases; the reference scored 100.0 (`run-08b3690344f44ce7`).

On 2026-10-31 the runtime moved to the official-download provider. `mindustry/mindustry-159.7`
was then prepared on the same Linux x86_64 host, in an isolated Hub state, from commit `ac5d446f`:

- `prepare` downloaded the release jar through GitHub's redirect to the declared asset host and
  verified its size and SHA-256.
- A deliberately interrupted first attempt was retried, and the retry reused the verified cache
  without a request.
- The base and all five images were built and verified, with artifact identity
  `sha256:5cf2e2b6…291c`.

`server-console-regressions` was then evaluated again:

- The starter scored 10.0 (`run-8368f148bb53422a`), complete, and failed exactly its 4 target
  cases.
- The reference scored 100.0 (`run-0679c6701ee14afc`).

E0 study controls are kept in `benchmarks/mindustry-core/private/study-controls/<task>/`
(`manifest.tsv`, `clause-map.json`, control patches and trees, `NOTES.md`). For every task
a target-negative (a plausible partial repair), a compat-negative (a repair that breaks a
preserved behaviour) and an independently written alternative repair were evaluated with
`rhenium run` on 2026-09-24: each target-negative failed only target cases, each
compat-negative failed only preserved cases while every target passed, and each
alternative scored 100. Run IDs are in each control directory's `NOTES.md`. The study
tooling registration of these tasks (`tools/study`) is outside this pack.

## Construct pack (`mindustry/construct`)

The construct pack (`benchmarks/mindustry-construct`, catalog `rhenium-mindustry-v1`
1.2.1) holds ten `hard` generation tasks. The model starts from a scaffold that holds
only `plugin.hjson`, `build-reference.sh` and an empty `src/`, and writes a
dependency-free Java core plus a Mindustry server plugin whose public API is fixed by
the exam. The tasks were deleted in `9b038435` and restored on 2026-09-24 from
`9b038435^`. For the nine restored tasks, exams, catalog entries, Harbor task trees,
oracles, graders, rubrics and ablations are byte-identical to that commit, with these
exceptions:

- `benchmark.json` uses `pack_id: construct`, because the repair pack now owns
  `mindustry-core`; task keys are `mindustry/construct/<task>`.
- The pack `README.md` was rewritten to describe the restored pack.
- Plumbing fix: five `environment/Dockerfile`s (`command-rate-limiter`,
  `core-failover-coordinator`, `item-reservation-ledger`, `logic-link-registry`,
  `wave-budget-planner`) used `FROM mindustry:latest`. Preparation only builds
  `mindustry:159.7`, so on 2026-09-24 the restored runtime failed to build at
  `item-reservation-ledger` (`mindustry:latest: failed to resolve`). These five files
  now use `FROM mindustry:159.7`, like the other five tasks. The task semantics did not
  change.

Catalog 1.1.0 retires `command-rate-limiter` (SG-086) without a replacement because it
was saturated and no longer discriminated. Its exam, Harbor tree and ablation stay in
the pack as history, and the control table below still lists its runs. The prepared
`mindustry/mindustry` artifact records one image per catalog task, so an artifact
prepared before 1.1.0 fails `runtime verify`; prepare the runtime again.

Catalog 1.2.0 (2026-11-12) adds `blueprint-layout-reconciler` (SG-164), a new task
written for this pack, so the pack is back at ten tasks. It asks for a planner that
reconciles observed buildings with a desired layout (footprints, conflict removal,
budgeted placement, replay, checkpoints) and an adapter that observes and edits real
buildings. On the Lab host its reference passed all nine rubric cases through
`rhenium run` (`run-b5a78722bb79481b`), the empty scaffold stopped at the shape gate
(`run-5922eadff9ee4335`), and four single-defect variants of the reference each failed
with a complete run (`run-959ee3fc6daa46c9`, `run-726dfdb8c1ec47db`,
`run-35ccee9478d049c1`, `run-c100974de95c47f6`); see `private/harbor/NOTES.md` in the pack.

Catalog 1.2.1 (2026-11-12) renames that task's plugin from its task id to
`layout-reconciler` in the exam, the scaffold, the reference and the grader's dependency.
The Hub refuses attempt material that contains a task id, so under 1.2.0 no anonymous
attempt could be prepared and no model attempt was recorded. On the Lab host, under 1.2.1, the
reference passed all nine cases again through `rhenium run` (`run-1cf5108cf04b47ec`), the
empty scaffold failed (`run-77ac330c67cb4cd3`), and `scripts/prepare-exam` prepared an
anonymous attempt of the task. The four single-defect variants were not run again; the change
touches no source file or assertion. An artifact prepared before 1.2.1 fails `runtime verify`;
prepare `mindustry/mindustry` again.

| Task | Required sources | Rubric cases |
| --- | --- | --- |
| `transactional-core-router` | `TransferEngine`, `TransactionalCoreRouterPlugin` | 13 |
| `build-quota-auditor` | `BuildQuotaEngine`, `BuildQuotaAuditorPlugin` | 8 |
| `unit-lease-scheduler` | `LeaseScheduler`, `UnitLeaseSchedulerPlugin` | 7 |
| `power-grid-controller` | `GridController`, `PowerGridControllerPlugin` | 8 |
| `wave-threat-arbiter` | `ThreatArbiter`, `WaveThreatArbiterPlugin` | 7 |
| `item-reservation-ledger` | `ReservationLedger`, `ItemReservationLedgerPlugin` | 4 |
| `wave-budget-planner` | `WaveBudgetPlanner`, `WaveBudgetPlannerPlugin` | 4 |
| `logic-link-registry` | `LogicLinkRegistry`, `LogicLinkRegistryPlugin` | 4 |
| `core-failover-coordinator` | `CoreFailoverCoordinator`, `CoreFailoverCoordinatorPlugin` | 4 |
| `blueprint-layout-reconciler` | `LayoutReconciler`, `BlueprintReconcilerPlugin` | 9 |

### Construct runtime and evaluation

The construct pack binds every task to its own runtime, `mindustry/mindustry`, which
uses the same pinned `server-release.jar` as the repair pack:

```sh
rhenium auth login official-download
rhenium runtime prepare mindustry/mindustry
rhenium runtime verify  mindustry/mindustry
```

The provider downloads the same pinned release asset into this runtime's own
cache. Preparation verifies the jar digest. It then builds the base image `mindustry:159.7`
from `benchmarks/mindustry-construct/private/runtime/Dockerfile`, with the jar as the
build context and no network. After that it builds one evaluator image per task from
the task's `environment/`. Those builds run `apt-get` for `bash` and `python3`, so they
need network access. The artifact records only the task image IDs. The base Dockerfile
uses `FROM eclipse-temurin:17-jdk`, which is **not** pinned by digest, as it was before
the deletion. On 2026-09-24 that tag resolved on this host to
`sha256:bc033b57e11b773c3043babfd664e7a5ef110805548b921cbfc3e8c67a0725d6` (JDK
17.0.20+8), the image the repair pack pins, but a later pull of the tag can change it.
The images use fixed tags (`mindustry:159.7`, `rhenium-mindustry-<task>:159.7`). A new
build replaces the image a tag pointed to: the 2026-09-24 preparation replaced the
images of the 2026-09-18 artifact, which had covered only the first five tasks.

An evaluation mounts the submission read-only, copies it over the scaffold in the
task image and runs the task's `tests/test.sh` with `--network=none`. `verify.py`
compiles the candidate with `build-reference.sh` (`javac --release 17` against the jar),
compiles the private grader plugin, starts the headless server on the `Fortress` map
(60 s limit) and reads exactly one `MINDUSTRY_RESULT` line. Scoring:

1. `submission-shape` (10 points): every `required_files` entry exists, with no symlinks,
   `.git`, or `.class`/`.jar`/`.zip` outside `build/`. If this check fails, the run ends
   here and is **incomplete**. This includes the empty scaffold, whose `src/` is empty,
   so an empty starter is incomplete by design.
2. `private-headless-verifier` (90 points): reward 1, verifier exit 0 and every rubric
   case reported and passed. The run is complete when the reported case names equal
   the rubric; `criteriaScore` is 1 plus the number of passed cases.

The `core` profile runs only the shape check and is always incomplete. Per-case
outcomes are not stored in the Hub result.

### Construct acceptance record

These evaluations ran through `rhenium run mindustry/construct/<task> <submission>` on
2026-09-24, with `mindustry/mindustry` prepared on the Linux x86_64 host
(artifact identity
`sha256:5c7f29646dd076f994851b2e7c4a769f847c715fbcb81fdf392cd31942671bec`). The
submissions were built as follows:

- **Reference**: the materialized scaffold with the task's `solution/solve.sh` applied.
- **Starter**: the unchanged empty scaffold.
- **Ablation**: the reference with the task's single-defect patch from
  `validation/ablations/` applied.

| Task | Reference | Starter (empty scaffold) | Ablation |
| --- | --- | --- | --- |
| `transactional-core-router` | 100, complete, 13/13 cases (`run-56eae951f2154172`) | 0, incomplete (`run-22755d3fde1c4d53`) | 10, complete, 2 of 13 cases failed (`run-aece75e30f974118`) |
| `build-quota-auditor` | 100, complete, 8/8 cases (`run-7c51395da5ca4252`) | 0, incomplete (`run-4efaefd7e5d6459e`) | 10, complete, 1 of 8 cases failed (`run-40c111933e3d4324`) |
| `unit-lease-scheduler` | 100, complete, 7/7 cases (`run-c823d2f0499b41ae`) | 0, incomplete (`run-1bc2637f822b4bd9`) | 10, complete, 1 of 7 cases failed (`run-2d9a3a980c4f44f4`) |
| `power-grid-controller` | 100, complete, 8/8 cases (`run-5c8f2be076ba4aa6`) | 0, incomplete (`run-c0d52c6b37614707`) | 10, complete, 1 of 8 cases failed (`run-85f3f682a0634990`) |
| `wave-threat-arbiter` | 100, complete, 7/7 cases (`run-10fc450025024836`) | 0, incomplete (`run-bc5455c37fd640e3`) | 10, complete, 1 of 7 cases failed (`run-3688f26563c84d1d`) |
| `item-reservation-ledger` | 100, complete, 4/4 cases (`run-0e17042328c442e3`) | 0, incomplete (`run-261e8aab05c54bf0`) | 10, complete, 1 of 4 cases failed (`run-312a9065e62d4f20`) |
| `wave-budget-planner` | 100, complete, 4/4 cases (`run-f4485ad5add84563`) | 0, incomplete (`run-1ab67d8d3343448c`) | 10, complete, 1 of 4 cases failed (`run-0117c5e6fe9a448e`) |
| `command-rate-limiter` | 100, complete, 4/4 cases (`run-21ecdcb5cfa74ba7`) | 0, incomplete (`run-f0d3f3d65c3e4f15`) | 10, complete, 1 of 4 cases failed (`run-e6ee5eadef834c0a`) |
| `logic-link-registry` | 100, complete, 4/4 cases (`run-a86986893e9d465e`) | 0, incomplete (`run-a3e0f6e25dcc48c0`) | not run: `expiry-boundary.patch` does not apply |
| `core-failover-coordinator` | 100, complete, 4/4 cases (`run-2a511bc80e81462e`) | 0, incomplete (`run-b22125c17b5f4c9a`) | not run: `capacity-order.patch` does not apply |

Summary of the controls:

- Every reference scored 100 with a complete run.
- Every empty starter was rejected at the shape gate: score 0, incomplete, not passed.
- Every ablation that applies produced a complete, failing run of 10/100. The Hub
  result keeps no per-case record, so the eight ablations were also rerun directly in
  their prepared images through the evaluator's container runner. In each rerun the
  case named in the ablation manifest failed and every other case passed, except
  `transactional-core-router`, where `source-compensation.patch` also fails
  `compensation failure remains recoverable`.
- Two ablation patches do not apply to their oracle (`patch` reports a failed hunk), so
  those two tasks have no complete failing control: `logic-link-registry`
  (`expiry-boundary.patch`) and `core-failover-coordinator` (`capacity-order.patch`).
  This defect is in the restored content and was left unchanged.

Other limitations of the restored content, left unchanged:

- In the five tasks added on 2026-09-22 (four rubric cases each), the grader's
  `persistence round trip` case is `req(true, "ok")` and always passes.
- Every task's Harbor `tests/Dockerfile` still uses `FROM mindustry`, a tag that
  preparation never builds. The Hub path does not use these files, and no Harbor run
  was made.
- `private/harbor/scripts/validate-task.sh` needs the Harbor CLI, which was not run.

On 2026-10-31 `mindustry/mindustry` was prepared through the official-download provider, in an
isolated Hub state on the same host, from commit `ac5d446f`. It downloaded and verified the
release jar into its own cache and built all ten task images, with artifact identity
`sha256:e47cbe24…9f59`. The unpinned `eclipse-temurin:17-jdk` tag still resolved locally to
`sha256:bc033b57…25d6`.

`build-quota-auditor` was then evaluated again:

- The reference scored 100, complete, 8/8 cases (`run-a6fb4b0593c14884`).
- The empty starter scored 0 and was incomplete at the shape gate (`run-ffbf4f3791434830`).

No other construct task or ablation was run under this runtime.

## Security boundary

Evaluation containers of both packs drop network access, all capabilities and privilege
escalation, and mount the submission read-only. In the repair pack the candidate code
*is* the game: it runs in the same JVM as the harness, before the harness is loaded. A
per-run nonce, the exactly-one-result-line rule, the frozen case-name set and the
watchdog defeat naive forgery, but a hostile submission could still crash or hang the
server (which fails closed) or read the harness classes.

In the construct pack the candidate plugin runs in the same JVM as the private grader
plugin. The candidate's own `build-reference.sh` runs as root inside the container. The
result line has no nonce, and the evaluator reads case outcomes from the verifier
output with a pattern match. A hostile submission could therefore forge a passing
report. The construct path offers only an honest-mode boundary.

Untrusted submissions to either pack should run on a disposable host. The images are
built on the host's Docker daemon, and the jar's integrity rests on the pinned SHA-256
against the reviewed catalog, not on a publisher signature.

## Official references

- [Mindustry v159.7 release](https://github.com/Anuken/Mindustry/releases/tag/v159.7)
  publishes the pinned `server-release.jar`.
- [Mindustry source](https://github.com/Anuken/Mindustry) is GPL-3.0; the vendored task
  trees keep its `LICENSE`, and the server jar is redistributed by its publisher, not by
  this repository.
