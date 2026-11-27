# Don't Starve Together benchmark support

## Ownership and status

| Field | Value |
| --- | --- |
| Maintainer | Xingzhi Li |
| Status | `Experimental` |
| Plugin ID | `dst` |
| Catalogs | `dst-core` 4.0.0 (five repair tasks over real open-source mods); `rhenium-dst-v2` 2.1.0 (ten construct tasks) |
| Plugin distribution | `plugins/dst/` (`rhenium-dst`) |
| Benchmark packs | `benchmarks/dst/` (`dst/core`, repair); `benchmarks/dst-construct/` (`dst/construct`, construct) |

The integration is Experimental. Its task and evaluator pipeline is implemented,
covered by tests and validated against one pinned dedicated-server build on
Linux x86_64. It has not completed multi-model calibration, and no other host
has engine evidence.

The plugin serves two kinds of task and picks the machinery by catalog id. A
repair task (`dst/core`, catalog `dst-core`) hands the model a real mod with
upstream fixes reverted. A construct task (`dst/construct`, catalog
`rhenium-dst-v2`) asks for a mod written from an empty workspace. The two packs
have separate runtime keys built from the same pinned server image, and their
scores are not comparable with each other.

## Repair tasks (`dst/core`)

Every task vendors a real open-source Don't Starve Together mod at an upstream
commit, with one or more real upstream fixes reverted. The exam reports only
symptoms from operators, players or mod authors, and never says how many defects
there are. The reference is the upstream tree with its fixes, so every gold patch
is an upstream fix (`gold_patch_origin = "upstream"`); no task has injected
defects.

| Task | Version | Upstream | Licence | Base commit | Reverted fix commits | Target / preserved cases |
| --- | --- | --- | --- | --- | --- | --- |
| `dst-fixed-bundle-regressions` | 2.0.0 | [angribot/DST-Fixed](https://github.com/angribot/DST-Fixed) | Apache-2.0 | `841cd02d5d` | `f46026c`, `e71c729`, `77f8107`, `c28d65c`, `b982089` | 6 / 7 |
| `dst-fixed-module-regressions` | 2.0.0 | [angribot/DST-Fixed](https://github.com/angribot/DST-Fixed) | Apache-2.0 | `841cd02d5d` | `44d9e2e`, `f435f2e`, `cbd4ee9`, `72b78c8`, `2f5482b`, `170b20b`, `c4c2875` | 8 / 8 |
| `composting-together-regressions` | 1.0.0 | [dont-starve-modding/composting-together](https://github.com/dont-starve-modding/composting-together) | MIT | `16c995051d` | `c625623`, `d3bbe2b`, `0bd23c8`, `4a19750`, `2115763`, `b846487` | 8 / 3 |
| `dsmmo-release-regressions` | 2.0.0 | [JodliDev/DsMMO](https://github.com/JodliDev/DsMMO) | Apache-2.0 | `783ab7baff` | `0d7c62d`, `6d1351f`, `c957bd5`, `783ab7b`, `9b93e05` | 7 / 7 |
| `glassic-api-regressions` | 2.0.0 | [angribot/DST-GlassicAPI](https://github.com/angribot/DST-GlassicAPI) | Apache-2.0 | `795af813e0` | `234b02c`, `bd4c073`, `2a96834`, `6721c64`, part of `795af81` | 8 / 6 |

`catalog.json` holds the full commit hashes. Some fixes are reverted only in
part: the other changes of the same commit stay in the starter. Each suite also
has one runtime sentinel. Composting Together has one `setup` case and the DST
Fixed module task has two; each starts a check that runs later on the world
clock.

A sixth candidate, built on Wolly Logger from `Crestwave/dst-misc`, was
authored and validated but then dropped because its licence provenance is not
reliable. The mod was first published on the Steam Workshop by its author
without a licence, and someone else later imported it into the MIT-licensed
repository. The pack excludes Workshop-only code that has no licence from its
author.

## Construct tasks (`dst/construct`)

The ten tasks of catalog `rhenium-dst-v2` 2.1.0 each ask for a server-authoritative
mod written from an empty workspace against a public exam: a pure plain-Lua core
module plus the DST components, RPCs and persistence around it. They are
`camp-supply-ledger`, `container-transfer-transaction`, `rescue-dispatch-queue`,
`world-rule-ballot`, `combat-target-arbiter`, `waystone-route-network`,
`status-effect-stack`, `fuel-ration-allocator`, `trade-escrow-exchange` and
`loot-roll-arbiter`. Every task has a hand-written reference, and each has
alternative implementations and negative controls under
`benchmarks/dst-construct/private/study-controls/<task>/`.

These tasks were the `dst/core` pack until catalog 3.0.0 replaced them with the
repair tasks. They were then restored unchanged into `benchmarks/dst-construct/`
with the pack ID `construct`, so their keys are now `dst/construct/<task>`. The
catalog, exams, plain-Lua and server suites, references, Harbor packages and
study controls are byte-for-byte the pre-3.0.0 files, except for the paths and
keys that name the pack (the materialize script, each `task.toml`
`content_reference`, and the `task` and `exam` fields of each clause map).

On 2026-09-24 every construct task was run again through
`rhenium run dst/construct/<task> --profile full` on the
`dst/dst-dedicated-24700372-construct` runtime. All ten references scored 100
(complete, passed). All ten empty starters scored 0 and were incomplete, which is
the construct evaluator's design (see [Evaluation levels](#construct-pack-dstconstruct)).
The same day two repair tasks were checked on the rebuilt repair images: each
starter still fails exactly its target cases and each reference still scores 100.
Run IDs are in the
[construct validation record](../../benchmarks/dst-construct/private/harbor/validation/README.md)
and the [repair validation record](../../benchmarks/dst/validation/README.md). The
construct alternative and negative controls, the Docker `validate-all.sh` controls
and the Harbor CLI trials were not rerun after the move.

## Harbor packages

The `dst/core` pack exports its five repair tasks as standalone Harbor 1.4
packages. Each task vendors a real open-source mod with upstream fixes reverted.
The `dst/construct` pack exports its ten construct tasks, each written from an
empty workspace, the same way. Unlike a portable reimplementation, each
separate, networkless verifier image contains the pinned real dedicated server
and a byte-for-byte copy of the repository's own evaluator, so a Harbor reward is
exactly the Rhenium `full` verdict: every check of the task's evaluator,
including every real-server assertion, has to run and pass.

| Pack | Verifier image | Server | How the image is obtained |
| --- | --- | --- | --- |
| [`dst/core`](../../benchmarks/dst/private/harbor/README.md) | `gcb-dst-dedicated-verifier:24700372` | Steam app 343050, build 24700372 | `rhenium runtime prepare dst/dst-dedicated-24700372` (anonymous SteamCMD download, build-checked) |
| [`dst/construct`](../../benchmarks/dst-construct/private/harbor/README.md) | `gcb-dst-dedicated-verifier:24700372` | Steam app 343050, build 24700372 | `rhenium runtime prepare dst/dst-dedicated-24700372-construct` (same pinned server layers) |

On Linux x86_64 every repair starter failed only its target cases and every
repair reference scored 100 with the real server running. For catalog 3.0.0 this
was shown through `rhenium run`. For catalog 4.0.0 it was shown through each
task's Harbor verifier image with `private/harbor/scripts/validate-task.sh`
(`nop` and `oracle`), and the E0 controls ran on the same images; `rhenium run`
through the Hub has not been repeated for 4.0.0. The pack's
[validation record](../../benchmarks/dst/validation/README.md) lists the exact runs and
what was not run. Every construct reference scored 100 through `rhenium run`
and every construct empty starter failed; see the construct
[validation record](../../benchmarks/dst-construct/private/harbor/validation/README.md).
The DST images are also the packs' managed Hub runtimes. They are
local and must never be pushed to a registry.

## Version policy

- Game distribution: Steam release of Don't Starve Together.
- Managed runtimes: `dst/dst-dedicated-24700372` (repair pack) and
  `dst/dst-dedicated-24700372-construct` (construct pack). Both are the anonymous
  dedicated server (Steam app 343050) at public build `24700372` in a
  digest-pinned Ubuntu 24.04 image, built from byte-identical build contexts that
  each pack carries. The repair starters fail only their target cases and every
  repair reference passes against this build; see the
  [repair validation record](../../benchmarks/dst/validation/README.md). Every
  construct reference passes and every construct empty starter fails (incomplete
  by design); see the
  [construct validation record](../../benchmarks/dst-construct/private/harbor/validation/README.md).
- SteamCMD can request only the currently published public build. When Klei
  publishes a newer one, `runtime prepare` fails closed on the build check instead
  of accepting it. An existing local `gcb-dst-dedicated-verifier:24700372` image
  and the Docker build cache of its server layers are therefore irreplaceable: do
  not remove them. Preparing either runtime after an evaluator change rebuilds
  only the layers from `COPY evaluator` on. Moving the pin requires rerunning
  every starter, reference and control of both packs first.
- The native runner used outside the Hub (see below) does not check a build
  number; it accepts whatever server the operator points it at.
- Mod contract: DST Mod API 10.

## Running a full evaluation

Runtime preparation is an explicit operator action and needs Docker:

```sh
rhenium auth login container
rhenium runtime prepare dst/dst-dedicated-24700372
rhenium runtime verify dst/dst-dedicated-24700372
rhenium run dst/core/dsmmo-release-regressions /path/to/workspace --profile full

rhenium runtime prepare dst/dst-dedicated-24700372-construct
rhenium runtime verify dst/dst-dedicated-24700372-construct
rhenium run dst/construct/camp-supply-ledger /path/to/mod --profile full
```

A repair submission is a workspace directory that contains the repaired mod
under `mod/`. A construct submission is the mod directory itself (the workspace
root holds `modinfo.lua` and `modmain.lua`). Each `prepare` builds the server
image from its own pack's `private/runtime/dst-harbor-runtime` and one verifier
image per task from that pack's `private/harbor/<task>/tests`. Both packs tag the
server image `gcb-dst-dedicated-verifier:24700372`, which the Harbor verifier
Dockerfiles start from; that tag follows the pack prepared last. Each prepared
runtime keeps using its own server image by ID and also tags it
`rhenium-dst:shared-base-<fingerprint>`, because Docker's containerd image store
drops an image that no tag names.
A `full` evaluation runs
the task's image without network and with every capability dropped, mounts the
submission read-only, and returns the report written by the same evaluator code
inside the image. It fails closed when the image is missing, the container exits
abnormally, or the report and its reward disagree. Evaluation never downloads,
updates or rebuilds anything; without a prepared runtime a `full` run stops with
the exact `runtime prepare` command.

The image embeds a byte-for-byte copy of the whole plugin, including both
evaluators. After an evaluator change, run both packs'
`private/harbor/scripts/materialize.py` and prepare both runtimes again; after a
suite change, regenerate and prepare the affected pack. `runtime verify` reports
the old images as unavailable because their build-context fingerprint no longer
matches.

The same images back the Harbor task packages of the
[repair pack](../../benchmarks/dst/private/harbor/README.md) and the
[construct pack](../../benchmarks/dst-construct/private/harbor/README.md), so a
Harbor reward and a Hub `full` verdict come from identical content.

### Migration from catalog 3.x

Catalog 4.0.0 is a breaking, task-semantic release that makes four of the five
repair tasks harder. Each of them reverts further real upstream fixes and has a
new task version, 2.0.0:

- `dsmmo-release-regressions`: two fixes of `9b93e05`. A save made under
  another Exp-gain setting must have its levels recalculated, and an incomplete
  `#dsmmo eat` command must not raise an error.
- `glassic-api-regressions`: `2a96834`, `6721c64` and the skin-selection part
  of `795af81`. `AnimState:GetSkinBuild()` must return an empty string for an
  unskinned entity, also while the entity is removed. The skin inventory must
  leave out mod skins that their test refuses, and the default skin selection
  must offer a character-exclusive skin only to its character.
- `dst-fixed-module-regressions`: the stack fix of `170b20b` and `c4c2875`. A
  rename uses up one Feather Pencil of a stack, and a Glommer statue loaded from
  a save the base game wrote can be repaired with Marble. The task now also
  switches on the `GLOMMER` option.
- `dst-fixed-bundle-regressions`: the `show_spoiled` part of `b982089`. A
  bundle preview draws Rot on the spoiled background.

`composting-together-regressions` is unchanged at task version 1.0.0. Every
hardened exam, suite, clause map and control set changed, and the
`dsmmo-release-regressions` and `glassic-api-regressions` difficulty is now `hard`.
Results recorded under a task's version 1.0.0 are not comparable with 2.0.0
results. A prepared `dst/dst-dedicated-24700372` runtime still holds the 3.0.0
suites until `rhenium runtime prepare dst/dst-dedicated-24700372` runs again.

### Migration from catalog 2.x

Catalog 3.0.0 is a breaking, task-semantic release. In `dst/core` it replaces the
ten `rhenium-dst-v2` tasks and their `fixed-v1.json` catalog with five repair
tasks in `catalog.json` (catalog id `dst-core`), so `dst/core` results are not
comparable with any 2.x result. The repair workspace holds the mod under `mod/`.
The repair catalog schema has no plain-Lua suite, core module, integration
regexes or minimum-size fields. It requires upstream provenance, `server_cases`,
and optional `mod_options` that are written into the server's
`modoverrides.lua`.

The ten 2.1.0 tasks were later restored unchanged as the `dst/construct` pack
(see [Construct tasks](#construct-tasks-dstconstruct)). A 2.1.0 result recorded
under `dst/core/<task>` corresponds to `dst/construct/<task>`, graded by the
restored construct evaluator. The plugin loads a catalog whose id is not `dst-core` with the
construct model, but the repository-maintenance `rhenium-author` publisher still
refuses to publish a clean-room synthetic `dst/synth` pack for this plugin.

## Platforms

| Surface | Supported platforms |
| --- | --- |
| Don't Starve Together | Windows, macOS, SteamOS/Linux |
| GameCodeBench development environment | macOS and Linux |
| Managed container runtime (Hub `full`, Harbor) | Linux x86_64 with Docker: validated. macOS is allowed by `runtimes.json` but has no evidence |
| Native runner discovery (direct evaluator use) | Common macOS and Linux Steam locations |
| Native runner override | `RHENIUM_PLUGIN_DST_ROOT` and `RHENIUM_PLUGIN_DST_SERVER_BIN` |

The game is available on all three desktop platform families, but the current
benchmark toolchain does not claim native Windows runner support.

## Programming languages

| Component | Language |
| --- | --- |
| Vendored mods and submissions | Klei's Lua 5.1-compatible runtime |
| Private server suites and construct plain-Lua suites | Lua |
| Catalog, orchestration, analyzer, and evaluator | Python 3.12 |
| Harbor harness and scoring wrappers | Bash |

## Evaluation levels

### Repair pack (`dst/core`)

1. **Submission shape** (10 points). The workspace has the `mod/` tree with every
   required file, no symbolic links or native modules, and Lua that tree-sitter
   parses.
2. **Headless dedicated server** (90 points). The mod is copied under the
   server's `mods` directory as a uniquely named mod. A loader that runs the
   task's private suite on the master simulation is prepended to its
   `modmain.lua`, so the suite runs in the mod's own environment after the world
   loads. The task's `mod_options` are written into the cluster's
   `modoverrides.lua`. The suite reports a nonce-bound JSON case list.

Scoring is binary above the shape check: the 90 points are awarded only when
every case passes. The `core` profile skips level 2 and is always incomplete. A
complete result requires the `full` profile and a case list that matches the
catalog's frozen `server_cases` exactly; a missing, extra, renamed or duplicated
case is an `error`, not evidence. A complete result reports
`runtime.caseOutcomes` (case name to a boolean pass flag), which the study tooling
reads as `case:<name>` next to `check:submission-shape`.

The suites drive the game through public surfaces: spawned prefabs (a spawned
Wilson stands in for each player), buffered actions, pushed events, components,
save records (`GetPersistData`/`SetPersistData`) and long updates for elapsed
time. Some suites also force a skill roll through `math.random` or read the
lines a mod prints through its own `print`. Each exam's Evaluation section states
what its suite does. `benchmarks/dst/private/study-controls/<task>/clause-map.json`
maps every exam clause to its cases and records each suite's known limits.

### Construct pack (`dst/construct`)

The construct evaluator is the one the tasks were validated with before 3.0.0.
It scores out of 100:

1. **Required files** (5) and **Lua syntax** (5): every catalog `required_files`
   entry exists inside the submission, and every Lua file parses.
2. **Hidden plain-Lua behavior** (30, proportional): the task's `hidden/` suite
   runs in a separate Python process under `lupa`. It loads the submitted core
   module in a sandbox without dangerous globals, with CPU, memory and file
   limits and an 8-second wall-clock limit.
3. **Implementation depth** (5): at least the catalog's `minimum_lua_lines`
   non-comment Lua lines.
4. **Integration contracts** (15 in total): regular-expression groups over the
   comment-stripped Lua sources that require the documented base-game
   registrations.
5. **Headless dedicated server** (40, proportional): the task's `server/` suite
   runs on the master simulation of the pinned server with a 90-second limit.
   In a temporary copy of the mod, `modmain.lua` becomes a wrapper that imports
   the submitted main chunk with `modimport` and then registers the suite, so a
   main chunk that ends in, or leaves early through, a top-level `return` is
   still scored. The copy reserves `rhenium_candidate_modmain.lua` and
   `scripts/rhenium_server_test.lua`; a submission that ships either path fails
   this check.

A result is complete only on the `full` profile when the server reported cases.
Both suites must report exactly the catalog's `hidden_cases` and
`server_cases`; a missing, extra, renamed or duplicated case is an `error`. A
pass requires every check to pass. An empty starter has no `modmain.lua`, so the
server suite cannot be loaded and the result is incomplete as well as failed.
That is the evaluator's design, not an infrastructure fault.

## Security boundary

For the construct pack, the plain-Lua runner additionally removes dangerous
globals, applies resource limits where supported and disables core dumps so a
CPU-limit kill cannot write private suite memory to the host. The
managed container runs with `--network=none`, all capabilities dropped,
`no-new-privileges`, CPU, memory and PID limits, and a read-only submission
mount; the private suite is baked into the task image. Inside it, as on a native
host, the Dedicated Server uses temporary storage, an offline/LAN cluster
configuration, a process group and bounded TERM/KILL cleanup. These controls
provide repeatability and containment, not a boundary against hostile code: the
submission and the injected suite share one Lua state, a container is not a
disposable host, and on the native path the operator-provided server remains
host-visible and the offline game configuration is not an OS-level network
block.

Development and reference checks use the default `honest` security mode. Formal model-generated
or external submissions must explicitly use `--security-mode untrusted` with an approved
credential-free, networkless disposable-host provider and immutable image identity. Missing
host evidence fails closed and never falls back to the local DST evaluator. The common contract
and comparison with GMod are documented in [Disposable evaluation hosts](../disposable-evaluation-hosts.md)
and the [DST/GMod security matrix](../dst-gmod-security-matrix.md).

## Official references

- [Don't Starve Together on Steam](https://store.steampowered.com/app/322330/Dont_Starve_Together/)
  lists Windows, macOS, and SteamOS/Linux support.
- [Klei developer response on DST Mod API](https://forums.kleientertainment.com/forums/topic/142806-what-is-the-current-api-version/)
  identifies Mod API 10; a 2024 follow-up confirms it remained 10.
- [Klei modding introduction](https://forums.kleientertainment.com/forums/topic/50773-guide-modding-practices-introduction-to-modding/)
  documents Lua mod files and the DST API setting.
- [Klei forum Lua runtime discussion](https://forums.kleientertainment.com/forums/topic/68404-lua-version/)
  records the game's modified Lua 5.1 lineage.
