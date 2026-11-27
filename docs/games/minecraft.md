# Minecraft benchmark support

## Ownership and status

| Field | Value |
| --- | --- |
| Maintainer | Yunge |
| Status | `In Development` |
| Plugin ID | `minecraft` |
| Catalog | `rhenium-minecraft-v1` 0.2.0 (`benchmarks/minecraft-core`): ten repair tasks vendored from open-source Paper plugins (Chatty ×5, BetterTeams ×2, Multiverse-Core ×2, minecraft-prometheus-exporter ×1); `rhenium-minecraft-construct-v1` 1.3.0 (`benchmarks/minecraft-construct`): five construct tasks |
| Plugin distribution | `plugins/minecraft/` (`rhenium-minecraft`) |
| Benchmark packs | `benchmarks/minecraft-core/` (repair tasks), `benchmarks/minecraft-construct/` (construct tasks: a whole plugin written into a frozen Maven skeleton) |

The integration is In Development: the catalog, runtime builder, container
runtime, evaluator and Harbor verifier are implemented and unit-tested, and the
pinned verifier base image has been built and booted on a Linux x86_64 host with
Docker. The task table below records which tasks have completed the
engine-backed acceptance gates. The pool is concentrated on four
repositories because most permissively licensed Paper plugins with merged,
player-free bug fixes either need NMS/paperweight, are Kotlin, or cannot be
built offline. The hand selection kept no list of rejected candidates; the
[project-history authoring mode](../../tools/authoring/REFERENCE.md#project-history-mode)
records a reason for every candidate it drops in its run summary. Version 0.1.0
of the ten tasks passed E0 admission on 2026-09-22 (10 starter, 10 reference, 14
target-negative, 10 compat-negative and 10 alternative control executions on the
real server) and was withdrawn from the `tools/study` inventory on 2026-09-26, to be
replaced by harder tasks. Version 0.2.0 keeps the ten task ids and task numbers and makes every task
harder; see [Version 0.2.0](#version-020). 0.2.0 completed its real-server acceptance gates on 2026-11-04; results
recorded on 0.1.0 do not carry over.

## Task inventory

| Task | Upstream | Build | Unit cases | Server cases (0.2.0) | Gates (0.2.0) |
| --- | --- | --- | --- | --- | --- |
| `multiverse-core-case-insensitive-world-names` | [Multiverse-Core](https://github.com/Multiverse/Multiverse-Core) PR #3408, BSD-3-Clause | Gradle 8.10.2 wrapper, `shadowJar` | 162 (MockBukkit) | 10 (6 target, 3 preserved, 1 sentinel) | passed |
| `chatty-bad-channel-disables-plugin` | [Brikster/Chatty](https://github.com/Brikster/Chatty) `ae83280`, MIT | Gradle wrapper (multi-module), `shadowJar` | 138 (JUnit) | 11 (5 target, 5 preserved, 1 sentinel) | passed |
| `betterteams-help-page-bounds` | [booksaw/BetterTeams](https://github.com/booksaw/BetterTeams) PR #994, MIT | Apache Maven 3.9.11 (installed, no wrapper), `package` | 44 (JUnit) | 10 (4 target, 5 preserved, 1 sentinel) | passed |
| `prometheus-exporter-players-total-main-thread` | [sladkoff/minecraft-prometheus-exporter](https://github.com/sladkoff/minecraft-prometheus-exporter) `e7de226`, MIT | Apache Maven 3.9.11 (installed), `package`, release 17 | 27 (JUnit) | 7 (2 target, 4 preserved, 1 sentinel) | passed |
| `chatty-reload-ignores-chat-commands` | [Brikster/Chatty](https://github.com/Brikster/Chatty) `3c62096`, MIT | Gradle wrapper (multi-module), `shadowJar`; seeded `chats.yml` | 161 (JUnit) | 7 (3 target, 3 preserved, 1 sentinel) | passed |
| `multiverse-core-world-exists-by-key` | [Multiverse-Core](https://github.com/Multiverse/Multiverse-Core) PR #3470, BSD-3-Clause | Gradle wrapper, `shadowJar` | 177 (MockBukkit) | 10 (7 target, 2 preserved, 1 sentinel) | passed |
| `betterteams-description-tag-injection` | [booksaw/BetterTeams](https://github.com/booksaw/BetterTeams) PR #986, MIT | Apache Maven 3.9.11 (installed), `package` | 44 (JUnit) | 9 (4 target, 4 preserved, 1 sentinel) | passed |
| `chatty-reload-leaks-threads` | [Brikster/Chatty](https://github.com/Brikster/Chatty) `c7ba417`, MIT | Gradle wrapper (multi-module), `shadowJar` | 82 (JUnit) | 8 (4 target, 3 preserved, 1 sentinel) | passed |
| `chatty-failed-migration-dead-plugin` | [Brikster/Chatty](https://github.com/Brikster/Chatty) `4072f98`, MIT | Gradle wrapper (multi-module), `shadowJar`; seeded legacy `config.yml` | 54 (JUnit) | 7 (4 target, 2 preserved, 1 sentinel) | passed |
| `chatty-v2-migration-null-spy-format` | [Brikster/Chatty](https://github.com/Brikster/Chatty) `f20b64b` + `b620b36`, MIT | Gradle wrapper (multi-module), `shadowJar`; seeded legacy `config.yml` | 48 (JUnit) | 11 (7 target, 3 preserved, 1 sentinel) | passed |

## Version 0.2.0

Version 0.2.0 (2026-11-02) makes the ten repair tasks harder without changing their ids,
task numbers or starters:

- Every exam now states only the observable symptom, the expected behaviour and the parts
  of the plugin the grader relies on. It no longer names the class or file that holds the
  defect, explains the mechanism or quotes stack frames that point at it. Every asserted
  behaviour is still stated. The catalog's `required_files` lists only `plugin.yml`.
- The server suites cover more of each upstream fix and add preserved cases that stop
  shallow repairs: 90 server cases in total instead of 64.
- `chatty-v2-migration-null-spy-format` merges the adjacent upstream commit `b620b36`
  ("Migrate the v2 locale to a v3 language", same author, same day, same migrator) into
  the task: the starter is still `b9a0645`, the reference is `b9a0645..b620b36` trimmed to
  `spigot/src/main`, and the seed now runs Chatty 2 in Russian. The other nine tasks keep
  their single upstream fix; each task's `NOTES.md` records the neighbouring upstream fixes
  that were considered for a merge and why they were left out (for example `df8385d` in
  BetterTeams can only be reproduced with a real player).
- New negative controls and alternative fixes are in `private/study-controls/<task>/`.
  The alternatives were originally written by isolated agents from the 0.2.0 exam
  and starter only. Three compatibility negatives were maintained during native
  acceptance to isolate preserved regressions while retaining the expanded targets.

| Task | Added in 0.2.0 |
| --- | --- |
| `multiverse-core-case-insensitive-world-names` | targets for loading an unloaded world again, removing an unloaded world, delete and regen; preserved cases for original names everywhere and the lower-case lifecycle |
| `chatty-bad-channel-disables-plugin` | targets for several offending channels, chat and join listeners and ticking notifications after the reload; preserved ticking after a clean reload |
| `betterteams-help-page-bounds` | target for the `/teama chest disableclaims|enableclaims` broadcasts, which carry the same `null` prefix; preserved non-numeric page |
| `prometheus-exporter-players-total-main-thread` | preserved cases that world-state metrics stay on the main thread and that `Metric.disable()` removes a family; the repair is one override, so the task stays easy |
| `chatty-reload-ignores-chat-commands` | target for a chat removed from `chats.yml`; a third start-up chat in the seed |
| `multiverse-core-world-exists-by-key` | targets for import by an existing key (loaded and unloaded), import of `the_end` and clone onto `the_end` |
| `betterteams-description-tag-injection` | targets for `<insertion>` and `<lang>` tags; preserved decoration and `<reset>` formatting |
| `chatty-reload-leaks-threads` | target that switching `send-metrics` off stops the previous bStats thread |
| `chatty-failed-migration-dead-plugin` | out-of-range v2 caps limits in the seed and a target that the migrated `moderation.yml` clamps them; the backup must keep them as written |
| `chatty-v2-migration-null-spy-format` | merged locale fix: targets for the migrated language, a v2 spelling in `settings.yml` and a warning for an unsupported language; preserved supported language tag |

### 0.2.0 validation

Offline evidence, 2026-11-02, on the Lab Linux x86_64 host with Docker: each task's
development image is `eclipse-temurin:21-jdk` with the task's dependency cache warmed from
its starter exactly as the verifier image warms it, and every check runs with
`--network=none`. For all ten tasks the starter, the reference and every negative and
alternative control listed in `private/study-controls/<task>/manifest.tsv` (60 trees in
all) build offline after `verify.py` restores the frozen paths, and every grader suite
compiles against GcbHarness, `paper-api` 1.21.11-R0.1-20260511.115010-91 and the built
jar. Every tree passes all of its frozen upstream unit cases except
`compat-negative-case-sensitive-lookups` of `multiverse-core-case-insensitive-world-names`,
which fails the two case-insensitivity tests by design. Each task's
`validation/controls.md` lists the trees.

The final real-server acceptance batch on 2026-11-04 completed all 90 controls:
ten unchanged starters, 30 references, every manifest alternative and negative,
and ten frozen-input tamper controls. Every execution used the `full` profile on
real Paper 1.21.11 build 132 in a network-disabled Docker container on Linux
x86_64. All frozen cases were observed and every runtime sentinel passed.
References and alternatives passed all 937 upstream unit cases and all 90 server
cases; starters failed intended targets with preserved baselines intact. Negative
controls failed in their declared role. The tamper controls passed after frozen
inputs were restored. Each task's `validation/controls.md` records the run IDs.

The operator explicitly accepted the Minecraft EULA before preparation. Both
runtimes were prepared and verified through `official-download`, with exact local
image IDs and build-context labels. Final acceptance was repeated against the
rebuilt core images. Initial failures exposed two fixture errors (a missing
default notification channel and an import baseline spanning an unrelated unload)
and three outdated compatibility negatives. Their failed records were retained;
corrected fixtures and controls received fresh executions. No case was removed,
scoring lowered or failed result silently relabeled. Authored difficulty and
estimated time remain unchanged.

## Construct tasks

`benchmarks/minecraft-construct` (catalog `rhenium-minecraft-construct-v1` 1.3.0, pack key
`minecraft/construct`, runtime `paper-1.21.11-132-construct`) holds five construct tasks: the
model writes a whole Paper plugin from a skeleton. Each workspace holds only a frozen `pom.xml`
(Maven 3.9.11, Java 21, `paper-api` `1.21.11-R0.1-20260511.115010-91`, which is byte-identical to
the API jar bundled with build 132), a `plugin.yml` with name, version, main class and
`api-version`, and an empty main class. The exam states every command, reply line, file format,
validation order and permission that a hidden case asserts. Suites drive the plugins through
public surfaces only: commands run through the command map with grader-owned senders
(console-like, permission-limited, and `Player` stand-ins that support a listed set of
methods), block and explosion events called through the plugin manager on real blocks, real
TNT, a real furnace, `Server#broadcast` receivers subscribed to permissions, the server's recipe
registry and the files in the plugin's data folder.

| Task | Plugin | Reference | Server cases |
| --- | --- | --- | --- |
| `coinledger-bank-ledger` | CoinLedger: accounts in cents, transfer fees, frozen accounts, audit history, and atomic combined-credit validation when recipient aliases the fee account | 759 lines of Java | 30 |
| `blocktrail-block-log-rollback` | BlockTrail: backward-compatible change log preserving exact directional block data through guarded rollback | 641 lines of Java | 27 |
| `towncrier-timed-announcements` | TownCrier: per-group tick timers preserving the exact remaining delay across pause and resume | 508 lines of Java | 20 |
| `wardstone-region-protection` | Wardstone: priority-resolved regions protecting breaks, places, explosions, fire, and destination-side liquid flow | 656 lines of Java | 27 |
| `recipesmith-config-recipes` | Recipesmith: shaped and shapeless recipes with per-player craft permissions, plus cooking, stonecutting, and vanilla recipe toggling | 555 lines of Java | 18 |

The plugin marks these tasks `task_kind: construct`; their public task has `fromScratch: true`,
their attempt guidance and system prompt describe writing a plugin into the skeleton, and the
repair packs are unchanged. Scoring is 10 points for the offline build and 90 for the live
server, all-or-nothing per layer.

Current version 1.3.0 acceptance on 2026-11-04 completed twenty fresh `full` controls
on real Paper 1.21.11 build 132 on Linux x86_64: one starter, reference,
target-negative and alternative per task. All 122 current server cases were
observed in every applicable run, and every enabled-plugin sentinel passed.
References and alternatives passed every case; starters and negatives failed
their intended targets. CoinLedger, BlockTrail and Wardstone's historical
independent alternatives were maintained for the current public requirements;
their initial failed executions remain separate. Clause-map versions now match
catalog 1.3.0, with fresh records rather than relabeled older evidence. The
[pack validation record](../../benchmarks/minecraft-construct/private/harbor/validation/README.md)
lists every run ID. TownCrier and RecipeSmith retain their documented,
author-approved checkpoint reductions. Construct tasks have no preserved-contract
baseline and are not qualified for joint compatibility analysis.

Historical version 1.0.0 validation on 2026-09-24, after
`rhenium runtime prepare minecraft/paper-1.21.11-132-construct`, ran each control through
`rhenium run minecraft/construct/<task>` (offline Maven build, `--network=none`):

| Task | Reference ×3 (100 each) | Starter (`nop`) | Target-negative | Alternative |
| --- | --- | --- | --- | --- |
| `coinledger-bank-ledger` | `run-603fdc49edbc446a`, `run-dc9244c5107c4082`, `run-5032a29d06674b18` | `run-f4acc4ca786247df`: 10, complete, every case but the sentinel fails | `run-fda967d14b2546b6`: 10, fails only `fees are rounded down to the cent` | `run-98e915c73a624770`: 100 |
| `blocktrail-block-log-rollback` | `run-b4a1329d416b46e9`, `run-f235c3838bb547c4`, `run-c3be18978b1d4125` | `run-ea54b5b4781f4015`: 10, complete, every case but the sentinel fails | `run-6583382450494afe`: 10, fails only `rollback undoes changes newest first` | `run-cad1d4bf486947eb`: 100 |
| `towncrier-timed-announcements` | `run-11e7d194cda9457e`, `run-16c770c34b3841fc`, `run-ded44f5e900541f3` | `run-eb6378d94e914b14`: 10, complete, every case but the sentinel fails | `run-5cf00fe132114d28`: 10, fails only `interval changes the period and is saved` | `run-094d05592dbc4361`: 100 |
| `wardstone-region-protection` | `run-bc0bf4fe61da47a3`, `run-657401905bb84742`, `run-cd2dc8dd935547b3` | `run-a1ecd21817834656`: 10, complete, every case but the sentinel fails | `run-b40314c50c0a48ca`: 10, fails only `deny wins between equal priorities and the first name decides` | `run-8898ea1f438a4b6b`: 100 |
| `recipesmith-config-recipes` | `run-46f9e33d5dd04f15`, `run-ec5bd86de76b478b`, `run-e4578f888bf74b2c` | `run-932b40cfb3d24f35`: 10, complete, every case but the sentinel fails | `run-a15a1c7fb10d4aa8`: 10, fails only `disable and enable edit the file` | `run-2edae80190e148f1`: 100 |

The three reference runs of each task had identical case outcomes. The starter is complete and
failing, not incomplete: the skeleton builds and enables. Each target-negative is a plausible
partial implementation (a fee rounded to the nearest cent, a rollback walked oldest first, an
interval change that keeps the old timer, an exemption for members of any overlapping region,
an `enable` that waits for the next reload). Each alternative was written by an isolated agent
from the public exam and the skeleton alone and scored 100 on its first run. Clause maps,
patches, alternative trees and notes are in `benchmarks/minecraft-construct/private/study-controls/`.

Limitations of the construct tasks:

- A plugin that fails to enable cannot be graded: the harness refuses to run cases and the live
  layer is reported incomplete (score 10 for the build), not failed. The exams say so.
- `Player` stand-ins are proxies, not real players; a plugin that calls a `Player` method outside
  the list its exam gives fails the case that triggered it. The exams list the supported methods.
- All cases of a task share one server session, so a case can see files and world changes left
  by earlier cases. Suites use fresh names and areas per case, and the cases that replace a data
  file run late; a submission that misbehaves early can still make a later case fail.
- Timing-dependent cases (TownCrier) count server ticks with a 10-tick margin around every
  announcement tick, and the TNT case accepts whatever blocks the (random) explosion destroys as
  long as the rollback restores exactly those.
- The shuffle case of TownCrier checks the stated property only (every message once per
  cycle), which a sequential order also satisfies.

## Version policy

- Server distribution: the [PaperMC](https://papermc.io) dedicated server.
- Pinned build: **Paper 1.21.11 build 132** (`paper-1.21.11-132.jar`, SHA-256
  `5ffef465eeeb5f2a3c23a24419d97c51afd7dbb4923ff42df9a3f58bba1ccfba`, Java 21),
  the last 1.21-line build; it is the version line most plugin repositories in
  the task pool target. The 26.x line requires Java 25 and is not supported.
- The jar is **not** stored in this repository. `rhenium runtime prepare`
  downloads it from PaperMC's official download service through the
  [official-download provider](../../providers/official-download/README.md),
  pinned to the exact URL, size (54,846,016 bytes) and SHA-256 above, so a
  substituted, truncated or changed download fails closed before any image is built.
- The Paper jar is a paperclip launcher. During the base-image build it downloads
  Mojang's 1.21.11 server jar from `piston-data.mojang.com`. The pinned Paper jar
  records that download's URL and SHA-256 (`f83b8e09…dd1726`), and paperclip
  checks the download against it. Rhenium does not check that digest itself.
- Tasks are compiled against the vendored repository's own `paper-api`
  declaration; the runtime reports the exact Paper version and build it ran.

## Platforms

| Surface | Supported platforms |
| --- | --- |
| Paper dedicated server | Any JVM platform; this integration runs it in Linux containers |
| Runtime preparation and evaluation | Linux x86_64 with Docker |

## Programming languages

| Component | Language |
| --- | --- |
| Agent submission | Java (a Paper plugin repository, or for construct tasks a plugin written into a Maven skeleton) |
| GcbHarness and hidden grader suites | Java 21 |
| Verifier (`verify.py`), catalog, runtime builder, evaluator | Python 3.12 |
| Build and scoring wrappers | Bash |

## Runtime setup

`rhenium runtime prepare` downloads the pinned Paper jar itself. The Minecraft
EULA is a separate decision that only the operator can make: Rhenium never accepts
it, never writes the acceptance file, and never installs or updates the server
during evaluation.

```sh
rhenium auth login official-download
rhenium runtime doctor  minecraft/paper-1.21.11-132
rhenium runtime prepare minecraft/paper-1.21.11-132
# -> exit status 2: action_required, kind accept-eula, with the file to write
```

The first `prepare` downloads and verifies the jar, then stops with
`RuntimeActionRequired("accept-eula")`. Its `details.file` names the acceptance
record in this pack's local Hub state, `<RHENIUM_STATE_DIR>/packs/minecraft/core/eula.txt`
(by default `.rhenium/hub/packs/minecraft/core/eula.txt`). After reading
<https://aka.ms/MinecraftEULA>, record your acceptance there yourself, and prepare
again:

```sh
# Accepting https://aka.ms/MinecraftEULA is your decision, not Rhenium's:
printf 'eula=true\n' > .rhenium/hub/packs/minecraft/core/eula.txt
rhenium runtime prepare minecraft/paper-1.21.11-132
rhenium runtime verify  minecraft/paper-1.21.11-132
```

The construct pack binds its own runtime key over the same jar and keeps its own
record, `<RHENIUM_STATE_DIR>/packs/minecraft/construct/eula.txt`, so it asks for the
acceptance once more:

```sh
rhenium runtime prepare minecraft/paper-1.21.11-132-construct
```

The [official-download provider](../../providers/official-download/README.md)
fetches only `paper-1.21.11-132.jar` from
`https://fill-data.papermc.io/v1/objects/<sha256>/paper-1.21.11-132.jar`. It
follows no redirect, and it keeps the file only at the pinned size and SHA-256.
It reuses an unchanged cache and never overwrites a partial or changed one. The
builder enforces the catalog's `expectedFiles` (exactly the jar) and `sha256`
itself.

The builder only reads the acceptance record. Without a record that has an
uncommented `eula=true` line it raises `accept-eula` before any image is built;
an `eula.txt` anywhere else, such as in the download cache, does not count.
Paper's own `eula.txt` format, comment lines included, is accepted.
`runtime doctor` reports `eulaAccepted` and `eulaRecord` and writes nothing. If
the record is later removed or no longer accepts, `runtime verify` reports the
runtime unavailable, and every `full` evaluation becomes incomplete with status
`unavailable` before any container starts.

Preparation stages the jar and a copy of the operator's record next to
`benchmarks/minecraft-core/private/runtime/` and the GcbHarness sources, builds
the base image `gcb-minecraft-paper-verifier:1.21.11-132` (paperclip patch-only
bootstrap, server classpath, harness compilation, a one-time flat-world
generation), then builds one verifier image per task from the task's `tests/`
directory (warming the repository's Gradle or Maven dependency cache) and records
each immutable image ID. Base and task image builds need network access;
**evaluation containers run with `--network=none`**. The images contain Mojang
server code and must never be pushed to a registry.

Every Minecraft pack builds its base under the same `gcb-minecraft-paper-verifier:1.21.11-132`
tag, which the task Dockerfiles start from, so that tag names the base of whichever runtime was
prepared last. Docker's containerd image store drops an image as soon as no tag names it, so
each prepared base also carries its own tag,
`rhenium-minecraft:shared-base-<runtime-id>-<fingerprint12>`; preparing one Minecraft runtime
no longer makes another runtime's base (and its `runtime verify`) vanish. `prune` removes only
the tags that still name the pruned base. Preparations are still best run one at a time: a task
image built while another runtime is re-tagging the shared tag starts from that runtime's base,
whose layers are identical but whose labels differ.

The runtime fingerprint covers `runtimes.json` and the plugin version only, not a task's
private `tests/` directory, so editing a task's suite or frozen case set after `runtime
prepare` leaves the record `ready` in `runtime list`. Each verifier image therefore carries
the SHA-256 of the `tests/` tree it was built from (label `io.rhenium.runtime.build-context`).
`runtime verify` compares every image with the pack as it is now, and every `full` evaluation
checks its own task's image the same way before it creates a container: an image that Docker no
longer has, or one built from a different `tests/` tree, makes the evaluation incomplete with
status `unavailable` and the `runtime prepare` command, instead of grading the submission with
the older suite. `runtime prepare` rebuilds such a runtime because its verification fails.
Prepare again after any change under a Minecraft task's `tests/` directory.

### Official-download validation, 2026-10-31

Both runtimes were prepared through the official-download provider. This ran on the Linux
x86_64 Lab host with Docker, in an isolated Hub state, from commit `ac5d446f`:

- The first `prepare minecraft/paper-1.21.11-132` downloaded and verified the jar, then stopped
  at `accept-eula` and built nothing.
- After the operator wrote that record, the next `prepare` reused the verified cache without a
  request.
- Both runtimes then built and verified every image. The core artifact is `sha256:8eecb64b…3690`
  (ten tasks) and the construct artifact `sha256:35004733…59ac` (five tasks).

These `full` controls then ran on the real Paper server (the core task on catalog 0.1.0):

| Task | Starter (`nop`) | Reference |
| --- | --- | --- |
| `prometheus-exporter-players-total-main-thread` | `run-00435484f47f44dc`: 40, complete, fails exactly its two target cases | `run-8c3cfb42f3944092`: 100 |
| `coinledger-bank-ledger` (construct) | `run-5401db2f509f473f`: 10, complete, only the sentinel passes | `run-e42e1be9e5714ef6`: 100, 30/30 |

No other task was rerun under these runtimes. The per-pack validation records hold the
details.

## Evaluation layers

1. `submission-shape` (gate) and `offline-build` (10 points): no symlinks, no
   compiled artifacts outside build directories, required files present; the
   repository builds offline with its own Gradle/Maven after the verifier restores
   every frozen build file and upstream test from `tests/starter`; the artifact's
   `plugin.yml` names the expected plugin.
2. `upstream-tests` (30 points, or 0 for tasks whose repository has no JUnit
   suite): the upstream tests run offline and the observed test ids must equal
   the frozen `unitCases`.
3. `live-server` (60 or 90 points): the candidate jar, GcbHarness and the hidden
   grader suite load into a real Paper server; the harness prints exactly one
   `MINECRAFT_RESULT` envelope with the run's nonce and the case set must equal
   the frozen `serverCases`. The harness force-loads the chunks around each
   world spawn (and around entities it spawns) because a player-less server
   otherwise keeps no chunk in the entity-ticking state.

Construct tasks have no upstream tests: their weights are 10 (offline build) and 90
(live server). Their skeleton builds and enables, so an unchanged workspace is a complete,
failing run that scores 10.

The `core` profile skips every layer and is always incomplete. A complete result
requires the `full` profile and every frozen case observed exactly once; each
layer scores all-or-nothing. `passed` requires a complete result at 100/100.

## Clean-room authoring (`rhenium-author`)

`tools/authoring` supports Minecraft: Java-shaped harvesting (repositories are
mined only when they carry `src/main/resources/plugin.yml`), a Paper generation
contract (Java 21, `org.bukkit`/`io.papermc.paper`/`net.kyori.adventure` only,
no build files), a model-authored `tests/TaskSuite.java` grader on the same
GcbHarness API, a trusted javac build in the verifier, javac preflight scripts
that compile the generated project and suite against the pinned server
classpath, and a publisher that writes `benchmarks/minecraft-synth`
(catalog `minecraft-clean-room-synth`, runtime `paper-1.21.11-132-synth`),
creating the pack when it is absent.

The benchmark registers no pack written by this publisher or by the
[project-history mode](../../tools/authoring/REFERENCE.md#project-history-mode).

## Security boundary

Evaluation containers drop network access, all capabilities and privilege
escalation, and mount the submission read-only. The candidate plugin runs in the
same JVM as the harness: a per-run nonce, the exactly-one-envelope rule, the
`depend:` load order and the frozen case-name set defeat naive forgery, but a
hostile submission could still crash or hang the server (which fails closed) or
read the harness classes. This is the honest-mode boundary; untrusted
submissions should run on a disposable host. The images are built on the host's
Docker daemon, and the jar's integrity rests on the pinned SHA-256 against the
reviewed catalog, not on a publisher signature.

## Official references

- [PaperMC downloads](https://papermc.io/downloads/paper) and the
  [fill v3 API](https://fill.papermc.io/v3/projects/paper/versions/1.21.11/builds/132)
  publish the pinned build, its download URL, size and SHA-256.
- [Minecraft EULA](https://aka.ms/MinecraftEULA) must be accepted by the operator.
- [Paper API javadocs](https://jd.papermc.io/paper/1.21.11/) document the
  plugin API that tasks and grader suites use.
