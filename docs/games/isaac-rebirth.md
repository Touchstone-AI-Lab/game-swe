# The Binding of Isaac: Rebirth support

The repository-maintenance `rhenium-author` tool can stage clean-room synthetic
Afterbirth+ repairs in a separate `isaac-rebirth/synth` pack and runtime. This
does not alter the frozen Exodus task or its checksum. Publication still requires
the licensed controlled host, all verifier processes, and every declared
assertion to complete. The registered `isaac-rebirth/synth` pack holds eight such
construct tasks; see [Clean-room construct pack](#clean-room-construct-pack) and
[clean-room authoring](../../tools/authoring/README.md).

| Field | Value |
| --- | --- |
| Maintainer | Xuesong Ye |
| Status | `In Development` |
| Plugin distribution | `rhenium-isaac-rebirth` |
| Plugin / game ID | `isaac-rebirth` |
| Packs | `isaac-rebirth/core`, `isaac-rebirth/synth` (eight construct tasks) |
| Catalog | `isaac-core` 5.0.0; one validated composite task plus nine derived tasks (engine-validated on two Linux hosts, see [Validation status](#validation-status)) |
| Game build | Native Linux Afterbirth+ v1.06.T1; Steam App 250900 build `22878971` |
| Mod API | Afterbirth+ Lua mod API |
| Submission language | Lua |
| Evaluator languages | Python 3.12, Bash, Lua |
| Game runtime platform | Linux x86_64 container launching the native Steam game |
| Runner platforms | Linux x86_64 |

The plugin integrates the Exodus Harbor task without adding Isaac imports or
dependencies to the game-neutral `rhenium` package. Its canonical key is
`isaac-rebirth/core/isaac-exodus-release-regressions`.

## Harbor task

The `isaac-rebirth/core` pack adds one Harbor 1.4 task from the Exodus repository,
whose root license is MIT. It contains twenty Afterbirth+ regression reports graded by 35
live-game cases: 24 primary behaviors and 11 runtime or regression guards. The
separate, offline verifier boots the native Linux game three times under Xvfb and
grades behavior in the real engine.

Measured v4.1 controls on the pinned native runtime:

| control | result | reward |
|---|---:|---:|
| Harbor `oracle` | 35 pass / 0 fail | 1.0 |
| Harbor `nop` | 9 pass / 26 fail | 0.0 |
| 20 single-report predicate candidates | only mapped cases flipped | 0 each |

All real-game runs completed every process with no fatal marker.

The final pre-integration Harbor 0.20.0 snapshot checksum is
`c96e94dbc64bc2d3df4edf2f50efed33f5dd8486ad409a84b074153e06887f78`.
Its oracle trial ID is `aff23996-6d6e-40da-b406-b31bb3a32cde`; its nop trial ID is
`821e845d-189a-4a17-97bf-6d5e06e4eec4`. Both trials had zero exceptions, three
successful game processes, three suite summaries, three passing runtime sentinels,
and zero fatal markers.

The repository includes the mod snapshot, reference patch, and verifier code. It does
not include installed game executables, Steam state, credentials, or offline tickets. Maintainers
build the proprietary verifier image locally from a licensed installation and must
never publish that image. Reproduction details and measured controls are in the
task's [maintainer notes](../../benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/NOTES.md).
The snapshot's binary room, art, and audio files match the fixed upstream commit;
their per-asset provenance remains an explicit review item.

Prepare the licensed runtime through the Hub before running the controls:

```sh
rhenium auth login steam
rhenium runtime prepare isaac-rebirth/afterbirth-plus-1.06.t1
```

## Runtime setup

Installed game executables, DLC runtime files, Steam state, credentials, and offline
tickets are proprietary and are never distributed by this repository or a plugin wheel.

The provider login, official-client bootstrap, fixed depot download, and immutable
image build are managed through `rhenium`. Isaac keeps Steam DRM, so it needs a
signed-in official Steam client in addition to the pinned depots. `auth login steam`
shows a second QR code for that client, then stages the pinned Steam Linux Runtime
depots every native Linux game starts through; see
[the Steam provider](../../providers/steam/README.md) for the container, its pinned
inputs, and its credential boundary.

```sh
rhenium auth login steam
rhenium runtime prepare isaac-rebirth/afterbirth-plus-1.06.t1
rhenium run isaac-rebirth/core/isaac-exodus-release-regressions \
  /path/to/submission --profile full
```

`prepare` stages the acquired client state and the pinned depots into an isolated
Steam library, then boots the game once so it writes its own zero-progression
`options.ini`. That single run is **online**, because the game's DRM asks the client
for an ownership ticket it can only fetch while signed in; the client caches the
ticket and every later start, evaluation included, runs in a **networkless**
container. The profile run waits for the client to finish logging on and registering
its Steam Linux Runtime tools before it requests the launch, since a request sent
earlier stalls and the game never starts. Without a signed-in client, `prepare` still
reports `action_required` with
the state root and the files it needs. Treat the local source cache, the client
state, and the images as non-redistributable; evaluation runs without network access
and records the concrete image ID.

This managed flow is implemented and unit-tested with a fake container runtime, and
it has completed once for real on a licensed Ubuntu 24.04 x86_64 host with Docker
(2026-09-20): `auth login steam` with both QR sign-ins, a full `prepare` that staged
the depots, minted the zero-progression profile and built the networkless verifier
image, and `rhenium run --profile full` on derived tasks, where the broken base
failed and the reference passed (see [Validation status](#validation-status)).
That run needed three fixes to the bootstrap: a writable client home in the
client image, `apparmor=unconfined` for the client container on AppArmor hosts,
and the settle-before-launch rule described above. `PROVISIONING.md` still
documents the manual bootstrap as the fallback. One completed run on one host is
the evidence; it is not a claim that the flow is robust across hosts.

The integration remains In Development: the authenticated result channel described
under [Security boundary](#security-boundary) is still missing.

## Profiles

| Profile | Behavior | Complete eligible |
| --- | --- | --- |
| `core` | Validate the public Exodus mod tree and required files | No |
| `full` | Boot three pinned native game processes and run every declared assertion (35 for the composite, 54 for a derived task) | Yes |

A complete `full` result reports name-level `runtime.caseOutcomes`, and its private
runtime log keeps the verifier's `[GCB_*]` marker lines, the launch script's own
`GCB_RUNTIME_*` lines and `test.sh`'s closing status line, never Steam's output. All of
these are reporting only; the completeness and pass rules are unchanged, and anonymous
attempts see none of them.

`full` fails closed when Docker, the pinned verifier image, the required
`gcb-isaac-steam` AppArmor profile, or any real-game process is unavailable.
Public attempts contain only the authored exam and editable Exodus snapshot;
private tests, reference solutions, validation data, and model credentials remain
outside the attempt.

## Security boundary

The submitted Lua mod and private assertion mods execute in the same proprietary
game process. The runtime is network-isolated, but this is not a hostile-code
sandbox. Strict benchmark integrity also depends on the repository's honest-exam
rules and a controlled licensed runtime host. Result markers are currently written
to a shared game log without cryptographic authentication, so a deliberately
adversarial submission may be able to forge evidence. An external authenticated
result channel is a blocker for promotion beyond In Development.

## Derived tasks

Catalog 4.2.0 added nine tasks derived from the frozen composite. Each starter is the
fully fixed Exodus tree with only that task's reported regressions reverted, its gold is the
unchanged fixed tree, and every task is bound to the same `afterbirth-plus-1.06.t1` runtime
artifact. Each derived task also ships `tests/run-game.sh`, a launch script the Hub mounts
over the image's copy; it changes only how the offline Steam client is started and asked to
launch the game, and how long it waits (see a derived task's `tests/README.md`). The frozen
composite keeps the image's own script.

Catalog 5.0.0 (2026-10-22) hardens the nine derived tasks. Every composite report is a local
repair next to code the report names, so each derived task keeps its composite reports and
adds three supplementary regressions from `private/supplementary-regressions/`: maintenance edits
injected into the reference tree whose diagnosis depends on how Afterbirth+ itself behaves
(callback arguments and order, when the engine discharges an active item, the Lua 5.3
standard library, missing Repentance-era API members, vector copy and reference semantics).
Their reference repair is the reverse of the injected edit, so the gold is still the
unchanged fixed tree. Exams quote the supplementary reports verbatim and gain one Notes line,
`Afterbirth+ embeds Lua 5.3.`. All nine tasks run the shared 54-case verifier
`private/verifiers/exodus-v2/`, which each catalog entry names in its `verifier` field and
the Hub mounts read-only over the image's `test.sh` and suites; the frozen composite runs its
image unchanged. See `private/verifiers/README.md` for the added cases.

| Task | Composite reports | Added in 5.0.0 |
| --- | --- | --- |
| `isaac-exodus-tear-trajectory` | EX-203, EX-226, EX-258, EX-274, EX-289, EX-327 | EX-441, EX-461, EX-469 |
| `isaac-exodus-active-item-state` | EX-184, EX-191, EX-217, EX-303, EX-311, EX-318 | EX-441, EX-465, EX-447 |
| `isaac-exodus-orphaned-effects` | EX-184, EX-203, EX-247, EX-327, EX-335, EX-342 | EX-427, EX-461, EX-406 |
| `isaac-exodus-projectiles-and-targets` | EX-226, EX-274, EX-289, EX-327, EX-342 | EX-427, EX-463, EX-469 |
| `isaac-exodus-room-floor-state` | EX-203, EX-239, EX-251, EX-266, EX-296, EX-311, EX-318 | EX-441, EX-463, EX-412 |
| `isaac-exodus-numeric-arithmetic` | EX-191, EX-203, EX-217, EX-266, EX-281, EX-303 | EX-427, EX-463, EX-452 |
| `isaac-exodus-passive-reshapers` | EX-184, EX-226, EX-239, EX-251, EX-258 | EX-441, EX-461, EX-436 |
| `isaac-exodus-callback-wiring` | EX-184, EX-217, EX-266, EX-318, EX-335, EX-342 | EX-427, EX-465, EX-467 |
| `isaac-exodus-mixed-triage` | EX-203, EX-217, EX-226, EX-251, EX-266, EX-274, EX-289, EX-318, EX-342 | EX-427, EX-441, EX-465 |

The 4.2.0 report sets and difficulty labels follow; the labels describe that revision.

| Task | Difficulty | Reports |
| --- | --- | --- |
| `isaac-exodus-tear-trajectory` | hard | EX-226, EX-203, EX-258, EX-274, EX-327 |
| `isaac-exodus-passive-reshapers` | hard | EX-226, EX-258, EX-239, EX-251 |
| `isaac-exodus-mixed-triage` | hard | EX-226, EX-318, EX-203, EX-266, EX-342, EX-251, EX-217, EX-274 |
| `isaac-exodus-callback-wiring` | medium | EX-318, EX-266, EX-335, EX-342, EX-184 |
| `isaac-exodus-numeric-arithmetic` | medium | EX-203, EX-191, EX-303, EX-217, EX-281 |
| `isaac-exodus-room-floor-state` | medium | EX-318, EX-311, EX-251, EX-239, EX-266, EX-296 |
| `isaac-exodus-active-item-state` | easy | EX-318, EX-303, EX-311, EX-191, EX-184 |
| `isaac-exodus-orphaned-effects` | easy | EX-335, EX-342, EX-327, EX-247, EX-203 |
| `isaac-exodus-projectiles-and-targets` | easy | EX-226, EX-342, EX-289, EX-327 |

Every derived task reuses at least one of three anchor reports (EX-226, EX-203, EX-318);
the set measures breadth plus a few engine-semantics diagnoses rather than nine independent
skills.

## Validation status

### Catalog 5.0.0, 2026-10-22 (UTC)

Measured on the second controlled host (NixOS x86_64, prepared runtime
`isaac-rebirth/afterbirth-plus-1.06.t1`, verifier image `sha256:c0560b37db5a…`) through the
Hub's `evaluate_task` with profile `full`, on an isolated Hub state seeded only with the
operator's runtime record. Every run completed three game processes with no fatal marker.
Each task's `validation/controls.tsv` and `validation/README.md` hold the run ids.

| Task | Base (starter) | Gold |
| --- | --- | --- |
| `isaac-exodus-tear-trajectory` | 40 pass / 14 fail, reward 0 | 54/54, reward 1 |
| `isaac-exodus-active-item-state` | 42 pass / 12 fail, reward 0 | 54/54, reward 1 |
| `isaac-exodus-orphaned-effects` | 42 pass / 12 fail, reward 0 | 54/54, reward 1 |
| `isaac-exodus-projectiles-and-targets` | 41 pass / 13 fail, reward 0 | 54/54, reward 1 |
| `isaac-exodus-room-floor-state` | 40 pass / 14 fail, reward 0 | 54/54, reward 1 |
| `isaac-exodus-numeric-arithmetic` | 42 pass / 12 fail, reward 0 | 54/54, reward 1 |
| `isaac-exodus-passive-reshapers` | 43 pass / 11 fail, reward 0 | 54/54, reward 1 |
| `isaac-exodus-callback-wiring` | 43 pass / 11 fail, reward 0 | 54/54, reward 1 |
| `isaac-exodus-mixed-triage` | 36 pass / 18 fail, reward 0 | 54/54, reward 1 |

Every base failed exactly its predicted set: the cases of its composite reports, the new
`grid_worm_heading_cross_axis` case where EX-226 is reported, and the cases of its three
supplementary regressions. The prediction was corrected once, after the first
`isaac-exodus-tear-trajectory` base run showed that `welcome_mat_poof_at_rest` also needs
EX-327's repair.

### Catalog 4.2.0, 2026-09-20

The nine derived tasks were two-way validated in the real game on 2026-09-20 (Ubuntu
24.04 x86_64 host, runtime prepared by the managed flow, verifier image
`sha256:649bcb926ce0…`). Every base failed exactly the cases predicted from the
composite's single-fix predicate matrix with reward 0, every gold passed 35/35 with
reward 1, and all twenty runs completed three game processes with no fatal marker.
The composite baseline ran alongside them and reproduced its historical control
(base 9/26, gold 35/35). Each task's `validation/controls.tsv` records the predicted
and measured rows.

| Task | Base (measured) | Gold (measured) |
| --- | --- | --- |
| `isaac-exodus-tear-trajectory` | 27 pass / 8 fail, reward 0 | 35/35, reward 1 |
| `isaac-exodus-projectiles-and-targets` | 29 pass / 6 fail, reward 0 | 35/35, reward 1 |
| `isaac-exodus-passive-reshapers` | 29 pass / 6 fail, reward 0 | 35/35, reward 1 |
| `isaac-exodus-mixed-triage` | 23 pass / 12 fail, reward 0 | 35/35, reward 1 |
| `isaac-exodus-active-item-state` | 27 pass / 8 fail, reward 0 | 35/35, reward 1 |
| `isaac-exodus-orphaned-effects` | 29 pass / 6 fail, reward 0 | 35/35, reward 1 |
| `isaac-exodus-room-floor-state` | 28 pass / 7 fail, reward 0 | 35/35, reward 1 |
| `isaac-exodus-numeric-arithmetic` | 27 pass / 8 fail, reward 0 | 35/35, reward 1 |
| `isaac-exodus-callback-wiring` | 29 pass / 6 fail, reward 0 | 35/35, reward 1 |

The Hub path was exercised end to end on two of them with `rhenium run --profile
full`: `isaac-exodus-callback-wiring` and `isaac-exodus-mixed-triage` scored 10.0
(shape check only, `native-game` failed with the same 6 and 12 case failures) on the
base and 100.0 on the gold, both complete, against the same image ID.

### Second host: congested Linux, 2026-09-23/24 (UTC)

On the second licensed host (NixOS x86_64, Docker 29.8, a rotational RAID shared with
other workers at 100 % utilisation, load 25 to 35) the first study baseline of the
derived tasks was incomplete for base and gold alike. Nothing task-specific caused it:
the frozen image's `run-game.sh` requests the game launch as soon as a Steam process
exists and gives the game 180 seconds. Here the offline client needed 40 to 260 seconds
to start, dropped requests forwarded before it was up, and sometimes wedged and took no
command at all, so one to three of the three game processes never started. A manual
run of the gold through the frozen launch script failed all three (`game_start_timeout`).

Each derived task now ships `tests/run-game.sh`, which the Hub mounts over the image's
copy; the frozen composite keeps the image's own script. It queues the launch request
as soon as the client proper is up, repeats an ignored request once, replaces a wedged
client (up to four client starts per game process) and has longer wall-clock budgets.
Suites, `test.sh`, case names and pass rules are unchanged; a retry only happens before
the game process exists. The evaluator's private runtime log now also keeps the
harness's own `GCB_RUNTIME_*` lines and `test.sh`'s status line, and the per-container
timeout is 7200 seconds.

Results through `rhenium run … --profile full`, on an isolated Hub state seeded only with
the operator's runtime record (verifier image `sha256:c0560b37db5a…`). Controls are
judged with `rhenium-study`'s own verdict rules against each task's clause map in
`private/study-controls/<task>/`:

| Task | Base | Gold runs | Target-negative | Compat-negative | Alternative |
| --- | --- | --- | --- | --- | --- |
| `isaac-exodus-tear-trajectory` | 27/8, complete | 100, 100, 100 | 32/3 (`grid_worm`, `grid_worm_bounce`, `grid_worm_heading`; as declared) | 34/1 (`grid_worm_cadence_regression`; as declared) | 35/0 (none; as declared) |
| `isaac-exodus-passive-reshapers` | 29/6, complete | 100, 100, 100 | 32/3 (`grid_worm`, `grid_worm_bounce`, `grid_worm_heading`; as declared) | 34/1 (`broken_glasses_floor_reset`; as declared) | 35/0 (none; as declared) |
| `isaac-exodus-mixed-triage` | 23/12, complete | 100, 100, 100 | 34/1 (`deja_vu_split_guard`; as declared) | 34/1 (`deja_vu_normal_return`; as declared) | 35/0 (none; as declared) |
| `isaac-exodus-callback-wiring` | 29/6, complete | 100, 100, 100 | 34/1 (`apocryphon_stats`; as declared) | 34/1 (`mutant_clover_stack`; as declared) | 35/0 (none; as declared) |
| `isaac-exodus-numeric-arithmetic` | 27/8, complete | 100, 100, 100 | 33/2 (`ritual_candle`, `ritual_candle_cadence`; as declared) | 34/1 (`familiar_cleanup`; as declared) | 35/0 (none; as declared) |
| `isaac-exodus-room-floor-state` | 28/7, complete | 100, 100, 100 | 34/1 (`james_book_of_secrets_scope`; as declared) | 34/1 (`broken_glasses_floor_reset`; as declared) | 35/0 (none; as declared) |
| `isaac-exodus-active-item-state` | 27/8, complete | 100, 100, 100 | 33/2 (`anamnesis_charge`, `anamnesis_charge_persistence`; as declared) | 34/1 (`cursed_metronome`; as declared) | 35/0 (none; as declared) |
| `isaac-exodus-orphaned-effects` | 29/6, complete | 100, 100, 100 | 34/1 (`iron_lung_orphan_gas`; as declared) | 34/1 (`lil_rune_jera_health`; as declared) | 35/0 (none; as declared) |
| `isaac-exodus-projectiles-and-targets` | 29/6, complete | 100, 100, 100 | 32/3 (`grid_worm`, `grid_worm_bounce`, `grid_worm_heading`; as declared) | 34/1 (`grid_worm_cadence_regression`; as declared) | 35/0 (none; as declared) |

Every base failed exactly the cases measured on 2026-09-20, and every gold run scored 100
with all 35 cases passing and identical case outcomes. Run ids and dates are in each
task's `validation/README.md` and study-controls `NOTES.md`. Of the 67 derived-task
runs, 7 needed one Steam client restart before a game process started, none needed a
second, and none was incomplete.

The four tasks that contain EX-226 also carry the composite's
`alternative-strict-reading` control, which is expected to fail only
`grid_worm_bounce` (over-constrained, see the composite's NOTES), and each did (34/1,
only `grid_worm_bounce` failing). As intended, the study verdict does not admit it as an
alternative.

The frozen composite's gold, through the image's original launch script on the same
host, scored 100 (complete, `run-a892cacb904540aa`, 2026-09-24 03:14 UTC) while the host
was less loaded (load average about 18, against 25 to 35 when that script failed). One
run shows the original script can still work here, not that it is reliable; the frozen
task keeps it only because its verifier is frozen.

Before Hub integration, the composite task was two-way validated in the real
game: the broken base passed 9 and failed 26 cases with reward 0; the reference
solution passed all 35 with reward 1. The plugin contract, discovery, anonymous
starter isolation, missing-runtime behavior, and Docker command are covered by
repository tests. A controlled post-integration `full` run remains required before
promoting the integration beyond In Development.

## Clean-room construct pack

`isaac-rebirth/synth` (catalog 0.1.1) is a registered pack of eight construct tasks.
Each one is written from an empty `mod/` starter on its own runtime,
`afterbirth-plus-1.06.t1-synth`, which pins the Exodus runtime's depots. The plugin
grades these `clean_room_synthetic` tasks through their single verifier process
(`fromScratch: true`, `taskKind: "construct"`). The pack's
[README](../../benchmarks/isaac-synth/README.md) lists the layout and the
`rhenium-author` provenance.

### Measured controls

`benchmarks/isaac-synth/private/harbor/validation/` records both validation rounds:

- **2026-09-26, Azure hosts.** Every reference passed 35/35, and every untouched empty
  starter failed 0/35, both complete.
- **2026-10-30/31, Lab host.** Every task's empty starter (0/35), reference (35/35)
  and unrelated-change mod (0/35) completed through the Hub's `full` profile on the
  first try.

Catalog 0.1.1 changes only the starters' `metadata.xml` `<id>`, which named the task, so the
Hub refused to prepare anonymous attempts. It is now the mod's `<directory>` value; see the
pack README.

The study inventory admits all eight tasks, with clause maps and E0 notes under
`private/study-controls/<task>/`. The `hard` labels are estimates.

### Preparing the construct runtime on a congested host

The first preparation on the Lab host built every image, yet no control launched the
game: each of four client starts ended in `GCB_RUNTIME_INVALID game_start_timeout`.
The cause was preparation itself, not the tasks. The profile step is the one online
start of the official client, and the client downloads its own update during it. It
stages that update as a bare package manifest (`package/steam_client_ubuntu12`) and
applies it at the next start. Every later start is networkless, so the bootstrapper
logged "Steam needs to be online to update" and shut down. The Exodus runtime adopts
an older validated image and was not affected.

Preparation now removes such a staged manifest after the profile step, including from
state an earlier preparation left behind. The installed client and its cached ticket
stay. Preparation also no longer fails a finished profile run on slow Docker work:

- creating, copying from and removing the profile container, and inspecting images,
  get the same 300 seconds the evaluator gives container bookkeeping;
- copying the several-gigabyte client state out gets an hour;
- a slow removal of the profile container is not a failure.

The online profile run itself can still fail to launch the game on a busy host; run
`prepare` again. `prepare` returns a ready artifact unchanged, so a construct runtime
prepared before these fixes must be pruned
(`rhenium runtime prune isaac-rebirth/afterbirth-plus-1.06.t1-synth --yes`) and
prepared again.
