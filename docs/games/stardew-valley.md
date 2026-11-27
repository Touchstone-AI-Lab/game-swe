# Stardew Valley support

The repository-maintenance `rhenium-author` tool can stage clean-room synthetic
debugging tasks for this plugin in a separate `stardew-valley/synth` pack. The
synth runtime is prepared explicitly and uses per-task private evaluator images;
missing real-game evidence prevents publication. No generated synth task is
included by default; see [clean-room authoring](../../tools/authoring/README.md).

| Field | Value |
| --- | --- |
| Maintainer | Jiaxuan Luo |
| Status | `In Development` |
| Plugin distribution | `rhenium-stardew-valley` |
| Plugin / game ID | `stardew-valley` |
| Pack | `stardew-valley/core` |
| Catalog | `stardew-core` 1.5.0; 11 tasks. 9 repair tasks: 5 with real-game controls on 1.2.0 images (one re-run on 1.3.0 images), 1 with an unchanged starter last controlled on 1.0.0, and 3 composites not re-run since their 1.1.0 release-note scrub. 2 generation tasks, restored in 1.3.0 and controlled on 1.3.0 images. Three Automate tasks were retired in 1.4.0 and `stardew-cp-i18n-case` in 1.5.0 |
| Game build | Stardew Valley 1.6.15 Linux depot manifest `6005910083361727734` |
| Mod loader | SMAPI 4.1.10 |
| Submission language | C#/.NET |
| Evaluator languages | Python 3.12, Bash, C# |
| Game runtime platform | Linux x86_64 container |
| Runner platforms | Linux x86_64, macOS Docker |

The plugin integrates the contributed Harbor task suite without adding Stardew
imports or dependencies to the game-neutral `rhenium` package. Nine tasks are
repair tasks on real SMAPI mods (Automate, Content Patcher, CJB Cheats Menu and
Tractor Mod). Two are generation tasks, `stardew-summon-horse-anywhere` and
`stardew-auto-workshop`: each asks for a new mod from a behavioural requirement and
starts from an empty `mod/<Name>/ModEntry.cs` skeleton. All eleven tasks use
canonical keys of the form `stardew-valley/core/<task-id>`. Catalog 1.2.0 removed the
two generation tasks; catalog 1.3.0 restored them unchanged. Catalog 1.4.0 retires
`stardew-automate-junimohut-seed-config` (SG-055), `stardew-automate-machine-states-api`
(SG-056) and `stardew-automate-setup-extension` (SG-063) without replacements: they
were saturated and no longer discriminated. Their exams, Harbor trees and study
controls stay in the pack as history, and the control tables below still list them
where they were measured. Catalog 1.5.0 (2026-11-12) retires `stardew-cp-i18n-case`
(SG-058) the same way and for the same reason. The prepared runtime
records one image per catalog task, so an artifact prepared before 1.5.0 fails `runtime
verify`; prepare the runtime again. The plugin dispatches on
the catalog's `task_kind`: a `generation` task's starter is `mod/`, is synced to
`/app/mod` in the evaluator container, and is marked `fromScratch` in the attempt
marker and public task view. Both kinds use the same real-game evaluator and scoring.

## Runtime setup

Stardew Valley is proprietary and is never distributed by this repository or a
plugin wheel. Log in once through the independent Steam provider, then explicitly
prepare the pinned runtime:

```sh
rhenium auth login steam
rhenium runtime prepare stardew-valley/stardew-1.6.15-smapi-4.1.10
rhenium run stardew-valley/core/stardew-automate-zero-stack-output \
  /path/to/submission --profile full
```

`prepare` downloads the fixed Linux depot manifest, builds every task image, records
their immutable image IDs, and retains the restricted source cache until an explicit
`rhenium runtime prune`. Evaluation never downloads or rebuilds a missing runtime.

Evaluator images pin the Microsoft .NET SDK manifest digest, SMAPI version and
installer SHA-256, game depot manifest, source snapshot, and catalog version. The
result log records the concrete local image ID. Images include proprietary game
files and must not be pushed to a public registry.

## Profiles

The synthetic runtime explicitly creates its XDG configuration directory before
the first SMAPI launch; this avoids .NET 6 returning an empty ApplicationData path
and colliding with the game's launcher. The core task images likewise create
`$HOME/.config` before generating their fixture save; without it, SMAPI exited
before saving and runtime preparation failed on a clean Linux host. Generated
compiler/game logs are collected with bounded reads and without following
symlinks. Complete results validate unique named boolean case outcomes as well as
totals, and expose `runtime.caseOutcomes` for authoring control audits. These
changes do not alter authored benchmark cases. The shared harness now fails a case
whose `WaitUntil` predicate throws; it previously resumed the case as if the
awaited condition had been met, so an exception inside a wait could hide a
failure. Every task's harness copy carries the same fix, and task images must be
prepared again to pick it up. Source synchronization does not
preserve host UID/GID. It keeps the image's `obj/` restore state and ignores any
submitted `obj/` or `bin/` output, because trial builds run offline with
`--no-restore`; deleting that state made every submission build fail. Evaluator
logs are written inside the disposable container and copied out before that exact
container is removed, avoiding host ownership errors while retaining
`--cap-drop=ALL` and network isolation. SMAPI's own log is collected as well as
verifier build/game logs. Docker control-plane calls (the daemon probe, image
inspection, and container create, copy and removal) allow 300 seconds each: on a
busy shared host the earlier 10- and 60-second limits made evaluations report an
unavailable runtime or finish incomplete before the game ever started. The game
run itself keeps its own per-task budget.

| Profile | Behavior | Complete eligible |
| --- | --- | --- |
| `core` | Validate the public C# submission tree and required files | No |
| `full` | Compile the submission and private harness, boot the pinned real game, and run every assertion | Yes |

`full` fails closed when Docker, the pinned game build, the evaluator image, or
the real-game assertion run is unavailable. Runtime containers have no network,
drop Linux capabilities, and receive no model credential. Public attempts contain
only the authored exam and editable source snapshot; private tests and reference
solutions stay in the pack.

## Controlled Linux synthesis evidence

On 2026-09-06 (Asia/Shanghai), the Lab Linux x86_64 host completed three
consecutive fresh Kimi-K3 generations of the same two-behavior clean-room contract
(`r10`, `r11`, `r12`). Each generation had different implementation and verifier
content, independent review, and all four real-game `full` controls:

| Control, in each generation | Passing assertions | Intended failing assertions |
| --- | ---: | ---: |
| Combined broken base | 4 | 2 |
| Reference repair | 6 | 0 |
| Birthday-only defect | 5 | 1 |
| Zoom-only defect | 5 | 1 |

Failure identities, not just counts, matched the preserved six-case contract.
This is 72 executed assertions across three generations, including 12 intentionally
failing negative-control assertions. Earlier rejected/failed generations remain
in private state; this is not a 100% first-attempt success claim or evidence for
unrelated task families.

Controls used the licensed 1.6.15.24356 Linux depot and SMAPI 4.1.10 in the already
prepared immutable image
`sha256:136d5b463dfe3308997b6c96363349e2f945b8f3038ba852b6e4ca8dce0204ed`.
The plugin's evaluator contract received fresh submissions/tests per run; runtime
fingerprint and selected-pack verification were checked before execution. Local
receipts live under `.rhenium/authoring/regeneration/r*/`, with per-case outcomes,
bundle hashes and validation reports. No generated task was published into the
checked-in benchmark packs.

Steam acquisition used an operator-local source-built helper override with a
WebSocket transport adjustment because the pinned release asset was unavailable.
This validates the controlled host, not the helper's released download workflow.
It does not establish native macOS or Windows engine support.

## macOS native maintenance diagnostics

The opt-in `macos` profile is available only for clean-room synthetic tasks.
It builds C# with the existing digest-pinned .NET 8 Docker SDK, then runs SMAPI
4.1.10 and the real **macOS 1.6.15.24356 x86_64 game** on the logged-in desktop.
Apple Silicon requires working x86_64 execution (Rosetta); Rhenium does not
install it. Docker, `sandbox-exec`, and a graphical login are prerequisites.
This is a maintenance diagnostic, not native `full` benchmark/exam support.

Current native evidence (2026-09-05, Apple Silicon/macOS 15.7): source acquisition,
pinned Docker compilation of the trusted harness, and real Seatbelt access-denial
tests ran successfully. Real-game preparation was attempted, but the SMAPI apphost
was terminated with SIGKILL and disappeared before producing a game log. The cause
is suspected host security interception, not confirmed from the system log. A
completed fixture, NOP/gold controls, and generated in-game assertions remain
**unvalidated**. Native execution is not yet a supported benchmark pass.

From an existing authoring run, explicitly prepare and then check a candidate:

```sh
devenv shell -- rhenium-author macos-prepare <run-id> <candidate-id> \
  --game-dir "/path/to/Steam/steamapps/common/Stardew Valley"
devenv shell -- rhenium-author macos-check <run-id> <candidate-id>
```

Install the optional `rhenium-local-files`, `rhenium-stardew-valley`, and
`rhenium-authoring` distributions in the same environment (the development
workspace includes them). `prepare` creates an empty local-files provider session
and invokes the ordinary Hub runtime lifecycle in separate authoring state.
It copies selected game binaries and `Contents/Resources/Content`, excluding
personal Mods and saves. It does not launch a Steam login, alter the Steam
installation, or run a system/SMAPI installer. It verifies the reviewed game DLL
SHA-256 and the fixed SMAPI archive SHA-256, records the compiler image ID, and
content-hashes the game/fixture artifact. Missing or changed artifacts require
explicit preparation; checking never pulls or rebuilds a missing runtime.
Preparation uses operation records and reports a disappeared launcher as
`action_required`. Rhenium does not remove quarantine attributes, re-sign an
intercepted binary, or disable system security protections automatically.

Native preparation first builds the trusted fixture harness and attempts to
create a disposable save in the real game. A `ready` record proves that preparation
and content verification, not that a generated task passes. Each subsequent check
copies the prepared fixture into a fresh directory, builds the original submission
and `tests/TaskSuite.cs`, and runs the declared `tests/native-cases.json` case names.
Unsupported suite layouts, compile errors, crashes, timeouts, missing/duplicate
cases, and inconsistent counts fail closed. No tests or expected outcomes are
silently corrected.

The native profile does **not** execute additional Linux `tests/test.sh` steps.
Its `complete`, `passed`, and publication eligibility are always false; actual
C# suite completion/counts appear separately in `runtime.engineComplete`,
`runtime.assertionsPassed`, and `runtime.cases`. `macos-check` exits 2 for a
diagnostic report (1 for orchestration failure), never 0 as a scoring command.
The default `full` profile, official task assets, and publication gates are unchanged.
Logs and licensed copies remain below
`.rhenium/authoring/runs/<run-id>/macos-diagnostics/<candidate-id>/`; they are local,
non-redistributable, and not release assets. Failed preparations are retained for
diagnosis. Use the standard runtime prune command with that diagnostic pack/state
selected to remove its owned runtime/source caches; per-check logs/copies remain.

Native game processes get an allowlisted environment and isolated XDG save/config
directories. Seatbelt denies direct network connections and file writes outside
the disposable directory; builds with game or generated code use Docker's
`--network=none`. Only the empty targeting-pack restore runs with network access,
before any game/generated code is staged. The policy permits system framework,
graphics, and Mach services and is **not a hostile-code security boundary**. The
suite and submitted mod share a game process. Run only trusted maintenance inputs
on a single-user development machine. Missing Seatbelt support is an error, not
permission to run without it.

## Security boundary

This in-development plugin isolates benchmark assets from the model workspace and
network-isolates evaluation, but it is not a hostile-code sandbox: the submitted
SMAPI mod and the private assertion mod necessarily execute inside the same game
process. Strict benchmark integrity therefore also depends on the repository's
honest-exam rules. Do not promote this integration to Stable until the verifier
has an independently authenticated result channel and the full runtime matrix is
run in controlled CI or release infrastructure.

## Validation status

The contributed tasks were two-way validated against the real game before the
Rhenium integration: each base snapshot fails and its reference solution passes.
The plugin contract, discovery, read-only materialization, missing-runtime
behavior, anonymous starter isolation, and networkless Docker command are covered
in repository tests.

### Catalog 1.3.0 (measured 2026-09-24 UTC on the same licensed Linux x86_64 Docker host)

Catalog 1.3.0 restores the two generation tasks with their exams, catalog entries,
Harbor trees, hidden suites, references and study controls byte-for-byte as they
were in catalog 1.1.0, and the plugin's `generation` handling that catalog 1.2.0 had
removed. Because the plugin changed since those tasks were last run, the runtime was
prepared again with
`rhenium runtime prepare stardew-valley/stardew-1.6.15-smapi-4.1.10`, which built and
verified all fifteen task images. As for catalog 1.2.0, the Steam source came from
the operator's existing cache through the operator-local `RHENIUM_STEAM_HELPER`
override, because the pinned released helper cannot run on this NixOS host. Every
run below went through `rhenium run` with the `full` profile and completed:

| Task | Submission | Run | Score | Assertions passed |
| --- | --- | --- | ---: | ---: |
| `stardew-summon-horse-anywhere` | reference | `run-ec149d8080b34fd7` | 100 | 3/3 |
| `stardew-summon-horse-anywhere` | empty starter | `run-fc0b6b2b324c4a26` | 10 | 2/3 |
| `stardew-auto-workshop` | reference | `run-b67a74aa2b934340` | 100 | 11/11 |
| `stardew-auto-workshop` | empty starter | `run-63b5aa2669f0462f` | 10 | 3/11 |
| `stardew-automate-zero-stack-output` (repair) | reference | `run-88c86d8f4aab4f6e` | 100 | 3/3 |
| `stardew-automate-zero-stack-output` (repair) | unchanged starter | `run-293d8125193d4ef9` | 10 | 1/3 |

The empty generation starters fail only the behaviour cases. The cases they pass are
fixture setup, the outdoor-summon sentinel and the no-overreach check (the far chest
and lone furnace stay untouched), which an empty mod cannot break. These counts equal
the catalog 1.0.0 controls below. The repair row checks that the restored generation
branch leaves repair tasks unchanged. The other twelve repair tasks were not re-run
on catalog 1.3.0 images; their build inputs did not change in 1.3.0, so the catalog
1.2.0 and 1.0.0 evidence below, with its stated gaps, still applies.

### Catalog 1.2.0 (measured 2026-09-23 UTC on a licensed Linux x86_64 Docker host)

Catalog 1.2.0 removed the two generation tasks (catalog 1.3.0 restored them) and
added three composite repair tasks built from real mods other than Automate. Each starter is a real release tree:
Content Patcher 2.6.1 unchanged (five later upstream fixes form the reference), and
CJB Cheats Menu 1.42.0 and Tractor Mod 4.24.4 with five and four upstream fixes
reverted (the reference is the unmodified release). The runtime was prepared with
`rhenium runtime prepare stardew-valley/stardew-1.6.15-smapi-4.1.10`; the Steam
source came from the operator's existing cache through an operator-local helper
override (`RHENIUM_STEAM_HELPER`), because the pinned released helper cannot run on
this NixOS host. Every run below went through `rhenium run` with the `full`
profile and completed:

| Task | Starter assertions passed | Reference assertions passed (3 runs) |
| --- | ---: | ---: |
| `stardew-cp-release-regressions` | 8/16 | 16/16, 16/16, 16/16 |
| `stardew-cjb-cheats-regressions` | 6/11 | 11/11, 11/11, 11/11 |
| `stardew-tractor-attachment-regressions` | 5/9 | 9/9, 9/9, 9/9 |

In every starter run, exactly the target cases fail. Target-negative,
compat-negative and alternative study controls for these three tasks were also run
through the real evaluator and behaved as declared; see
`benchmarks/stardew-core/private/study-controls/<task>/NOTES.md`. The same host
re-ran four earlier tasks on catalog 1.2.0 images, including the two that catalog
1.1.0 had added without real-game controls:

| Task | Starter assertions passed | Reference assertions passed |
| --- | ---: | ---: |
| `stardew-automate-zero-stack-output` | 1/3 | 3/3 |
| `stardew-cp-i18n-case` | 1/3 | 3/3 |
| `stardew-automate-output-count-drift` | 3/6 | 6/6 |
| `stardew-automate-setup-extension` | 3/5 | 5/5 |

The three `stardew-automate-release-regressions*` starters changed in catalog 1.1.0
(release-note entries naming their reverted fixes were removed, a
documentation-only change); they have not been re-run since, and the table below
predates that change. Several runs on this congested host never reached the game
because Docker did not create the container within the evaluator's former 60-second
limit or the shared Hub database was locked; they were rerun unchanged and are not
counted as task results.

### Catalog 1.0.0 controls

On 2026-09-17, the Lab Linux x86_64 host prepared the pinned runtime from the
licensed depot and completed post-integration `full` controls for all ten tasks
through `rhenium run`. Every unmodified public starter failed with a complete
real-game run, and every reference repair passed every assertion:

| Task | Base assertions passed | Reference assertions passed |
| --- | ---: | ---: |
| `stardew-automate-minifridge-storage` | 1/3 | 3/3 |
| `stardew-automate-junimohut-seed-config` | 2/3 | 3/3 |
| `stardew-automate-machine-states-api` | 2/3 | 3/3 |
| `stardew-automate-zero-stack-output` | 1/3 | 3/3 |
| `stardew-cp-i18n-case` | 1/3 | 3/3 |
| `stardew-automate-release-regressions` | 5/11 | 11/11 |
| `stardew-automate-release-regressions-v2` | 7/14 | 14/14 |
| `stardew-automate-release-regressions-v3` | 4/8 | 8/8 |
| `stardew-summon-horse-anywhere` | 2/3 | 3/3 |
| `stardew-auto-workshop` | 3/11 | 11/11 |

These controls required both the `$HOME/.config` image fix and the restore-state
preserving submission sync described above; before those fixes, runtime
preparation or every submission build failed. This is Linux runner evidence only.
