# GameCodeBench — Stardew Valley engineering log

Sibling of the `darkrp-harbor-tasks` suite. Same Harbor format, same validation
discipline. This file is the running log: design decisions, task catalog, QC
status, and everything learned the hard way. Started 2026-08-04.

## Status (final, 2026-08-06)

> **Catalog 1.3.0 (2026-09-24).** The pack holds fifteen tasks: thirteen repair tasks
> and the two generation tasks described below. Catalog 1.1.0 added two engineered
> Automate repair tasks (see `DEBUG-HARDENING.md`). Catalog 1.2.0 removed the two
> generation tasks and added three repair tasks built from other real mods (Content
> Patcher 2.6.1, CJB Cheats Menu 1.42.0, Tractor Mod 4.24.4); their provenance, cases
> and validation are in each task's `validation/NOTES.md`. Catalog 1.3.0 restored the
> two generation tasks unchanged, with their write-ups below. Current real-game
> controls for every task are in `docs/games/stardew-valley.md`; this entry and the
> notes below are as of 2026-08-06.
>
> Restore controls, 2026-09-24 UTC, through `rhenium run` (`full` profile) after
> `rhenium runtime prepare stardew-valley/stardew-1.6.15-smapi-4.1.10` rebuilt all
> fifteen images (Steam source through the operator-local `RHENIUM_STEAM_HELPER`
> override); every run completed:
>
> | task | submission | run | score | cases |
> |---|---|---|---:|---:|
> | `stardew-summon-horse-anywhere` | reference | `run-ec149d8080b34fd7` | 100 | 3/3 |
> | `stardew-summon-horse-anywhere` | empty starter | `run-fc0b6b2b324c4a26` | 10 | 2/3 |
> | `stardew-auto-workshop` | reference | `run-b67a74aa2b934340` | 100 | 11/11 |
> | `stardew-auto-workshop` | empty starter | `run-63b5aa2669f0462f` | 10 | 3/11 |
> | `stardew-automate-zero-stack-output` | reference | `run-88c86d8f4aab4f6e` | 100 | 3/3 |
> | `stardew-automate-zero-stack-output` | unchanged starter | `run-293d8125193d4ef9` | 10 | 1/3 |
>
> Evaluator images: summon `sha256:c60f02035450…`, workshop `sha256:157a02fccd6a…`,
> zero-stack `sha256:29d618cd440e…`. The empty starters fail exactly the behaviour
> cases, as in the 2026-09-17 catalog 1.0.0 controls.

**10 tasks two-way validated in the real game** (8 debugging + 2 generation), 3
more parked in `_blocked/` with evidence and unblocking steps. Seven difficulty
levers for the debugging category were built and tried along the way; the
write-ups below record them. Remaining before full DarkRP QC parity: Harbor-level
`nop` negative controls.

Two suite-design lessons from validation, now rules:

- **The discriminating observable must be reachable through the platform's real
  event flow — read the event handlers, not just the fixed function.** First
  machine-states design placed a chestless furnace at runtime; Automate's
  `ReloadIfNeeded` only queues a reload for machines connected to a chest, so
  the fixed code path never ran on either tree. The honest reproduction is the
  initial save-load scan, and the farm's own shipping bin is already a chestless
  machine — the suite now probes before placing anything.
- **Know the pump cadence before asserting "already there".** Junimo huts output
  one item stack per automation cycle; waiting for the first stack then
  asserting the second exists fails on both trees. Wait for every expected
  transfer, then assert.

Runtime API corrections, each resolved by decompiling the real game DLL instead
of guessing (ilspycmd scratch under /data04/jaxan/gcb-check/decomp on hyper01):

- `Game1.loadForNewGame` is an instance method (`Game1.game1.loadForNewGame`).
- `Furniture` bounds are `boundingBox.Value`, not `getBoundingBox()`.
- Mini-fridge placement is indoor-only AND requires farmhouse upgradeLevel >= 1
  (kitchen); the fixture save now sets `Game1.player.houseUpgradeLevel.Value = 1`.
- `isTileLocationTotallyClearAndPlaceable` no longer exists in 1.6; the check is
  `GameLocation.CanItemBePlacedHere(tile)`. Suites now scan for placeable tiles
  with it instead of hard-coding interior coordinates.
- Container-root-owned logs break host rsync; validate-task.sh chowns them back.

Pre-runtime verification (done earlier): all five fix commits are real upstream
commits whose gold patches apply cleanly onto their base trees; every
discrimination mechanism was confirmed by reading the mod source at the base tag;
all harness + suite C# passed a compiler parse. Game files were acquired
2026-08-05 with the operator's own Steam account (manifest pinned in
`scripts/game-version.lock`); the ownership gate is no longer a blocker on
hyper01.

## Design history

### `stardew-auto-workshop`

Composite generation: from an empty skeleton, write a chest-feeds-adjacent-machine
automation mod satisfying six behaviours stated verbatim in the instruction:
feeding, collecting, **no item loss when the chest is full** (product stays in the
machine until space opens), zero-quantity glitch tolerance, working inside
duplicate farm buildings, and no overreach. Validation: base 3/11 (only guards and
setups pass), oracle 11/11, in the real game.

The task demands writing stateful machine-cycle code against live engine
semantics with no reference implementation in sight. The reference lets the
game's own `AttemptAutoLoad` do all state changes.

### The generation category opens

`stardew-summon-horse-anywhere` is the suite's first task of the proposal's first
category: the agent starts from an empty ModEntry and a user-level requirement
("the horse flute must summon indoors; every other summoning rule unchanged"), with
the reference implementation kept out of the environment.

**A scoring-harness bug once scored agent patches as the untouched skeleton, and
the per-case shape exposed it.** The agent-run script `run-agent.sh` hard-coded the
debugging tasks' tree root (`/app/StardewMods`) in both the agent-side diff and the
scoring-side patch step; on this task's layout (`/app/mod`) the scoring `cd` failed
and the verifier silently scored the untouched skeleton. The tell was every
"failure" reproducing the base tree's exact case pattern. Fixed root-agnostic; the
saved patches were rescored with no agent re-run. Rule for the log: **when an agent
scores 0, compare its per-case pattern against the base tree's before believing
it** — an agent failure and an unapplied patch look identical in the reward, and
differ only in the trajectory.

The harness lessons from validating this task (all found by decompiler-guided
probes): an unnamed horse is `NoOwnedHorse` to the summon check; the flute needs
`canMove` and no fade after a warp; and standing-room must be chosen with the
game's own live restriction check from the player's actual position — a pre-warp
scan of the same rectangles was measured to disagree with the live check after a
prior summon (base=0/oracle=0 twice before the fix).


### v3 — the per-group difficulty floor

Compound pass rate is multiplicative, so a composite made only of hard groups should
be much harder than any one of them. v3 dropped every identifier-level defect and kept three
groups at edge-case-branch difficulty (zero-size output wedge, initial-scan
publishing gap, engineered SSHOM location-key pair).

### The seventh lever: information outside the repository — attempted, premise falsified

The one structurally different idea left was to put the answer outside the repo: a
second mod shipped as a **compiled assembly only** (built at image build time, source
deleted), Harmony-patching a game method Automate calls during its location scan and
throwing for one machine type. Automate would have to isolate per-entity failures.

**It never reached a model run, because the premise was wrong.** Automate 2.6.1
already isolates exactly this, in a method named for the purpose —
`MachineGroupFactory.TryGetEntityWithErrorHandling` — with `ModEntry` wrapping
location updates and machine processing in `HandleError` on top. The injected
exception fires (twice in the base run's log) and bystander machines keep working, so
base and oracle both score 1. Details and evidence: `_blocked/README.md`.

**That failure is itself the most useful thing this attempt produced.** A mature,
actively-maintained mod has already absorbed the realistic robustness defects. What is
left to build tasks from is either identifier-level or was never a defect. Difficulty
is therefore partly a property of picking a well-maintained codebase, which is
exactly what a *fair* benchmark requires.

Three iterations were needed to reach that conclusion, each diagnosed from measured
data rather than assumption (missing SDK reference; the injected exception firing
during the harness's own placement call, since `placementAction` also reads machine
data; and no re-scan occurring after the mod armed, since Automate only re-scans on
world changes). The validation guard aborted before spending model quota every time.


### v2 — the darkrp-release-regressions-v3 blueprint, ported

v2 reproduces every lever the DarkRP v3 task used:

| v3 lever | v2 implementation |
|---|---|
| instruction never states the defect count | 7 reports → 6 groups, two reports one root cause |
| SSHOM (mutually-masking pair, four-tree validated) | `GetLocationKey` drops uniqueName **and** `GameLocationNameComparer` compares bare `Name` — self-consistent, only bites with two buildings of one type |
| unasserted haystack revert | incubator guards reverted, reported as #224, no assertion |
| composite scale | 6 groups, 8 source files, 155-line gold |

The SSHOM is engineered, not upstream, so it exists in no commit history and
pretraining cannot help. It is self-consistent with its own class documentation
("considers two locations equal if they have the same name").

Levers still to try, in order of expected yield: defects whose symptom is only
reachable through multi-step gameplay state (save/load round-trips, day rollovers)
rather than a single automation cycle; defects that require joint reasoning across
the mod and the game's own data assets; and the game-version-migration category
(the CP task below), where the answer depends on knowledge of two game data formats
rather than on reading this repository.

## Multi-step gameplay state — measured boundary conditions

Attempted after the composite tasks, on the reasoning that defects needing several
gameplay steps might be harder for a strong scaffold. **The attempt failed, and the
reason is worth more than the task would have been.**

**Finding 1 — multi-step state does not make a bug harder to *find*.** A coding
agent localizes by reading source, not by playing. Requiring several in-game steps
raises the cost of *writing the test*, not of diagnosing the defect. Design effort
belongs in test subtlety instead: assertions a plausible-but-wrong fix fails.

**Finding 2 — a tick-driven suite cannot cross a day boundary in-process.** SMAPI's
`UpdateTicked` does not fire during `Game1.NewDay`, so a coroutine suite never
observes the transition finish. The day-rollover helpers written for this were
removed rather than left in as a trap for the next author.

**Finding 3 — the game's other time entry points do not substitute.** Measured on
the real game (probe suite, `_blocked/stardew-automate-incubator-egg-theft`):
`GameLocation.DayUpdate(day)` does not advance machine countdowns at all, and
`Object.minutesElapsed(n)` drives the countdown to zero but deliberately does not
set `readyForHarvest` for a machine whose data says `OnlyCompleteOvernight` — that
flag is set only inside the real overnight sync. Any defect gated on an
overnight-completing machine is therefore unreachable in a single boot.

**Consequence — the category needs a multi-phase verifier**, i.e. `tests/test.sh`
booting the game more than once (set up and save → advance a day per boot → final
boot loads and asserts). Feasible rather than speculative: `gen-save` already calls
`Game1.NewDay(0f)` from `GameLaunched` and writes a save, which is exactly the
out-of-tick-loop context where it works. Until that exists, prefer defects whose
observable is reachable within one loaded day.

**Two smaller measured facts, recorded so nobody re-derives them:** casks only age
in a Cellar (`Cask.IsValidCaskLocation` requires `location is Cellar` or a
`CanCaskHere` map property), so a cask cannot be used as an in-place trap on the
farm; and any suite touching `MachineData` needs a `StardewValley.GameData`
reference in the harness project (now added).

## Inherited rules (from the DarkRP suite, unchanged)

- **Two-way validation**: base tree fails the suite, reference solution passes it.
  Oracle (reward 1.0) and `nop` negative control (reward 0.0) on every task.
- **Reward gate**: `passed == expected && failed == 0`. Exit codes gate nothing;
  a staging failure that runs zero tests must score 0.
- **PASS_TO_PASS sentinel** in every suite — a green "before" run must be
  distinguishable from a broken harness.
- **Assertion discipline**: for every assertion, point at the sentence in
  `instruction.md` or the artefact in the repo that requires it; otherwise delete
  the assertion or add the sentence. Build pre-state through public entry points,
  never by poking internals. Never pin incidental implementation choices.
- **Difficulty lever**: symptom precision on bug-fix tasks. API-contract and
  implement-from-spec tasks need precise contracts and land easy; that is fine —
  they are the lower half of the distribution.
- **Network isolation**: environment/verifier `no-network`; agent allowlisted to
  `api.anthropic.com` only. Everything else baked into the image at build time.
- **Real platform over stubs**: all seven DarkRP false alarms trace to stubbed or
  fake harness surfaces. Stardew runs the real game; keep it that way.

## What is different about Stardew

| axis | DarkRP | Stardew Valley |
|---|---|---|
| platform | GMod dedicated server (free via steamcmd anonymous) | the game itself — paid, proprietary, no free server |
| mod language | GLua, interpreted in-place | C# compiled against game + SMAPI DLLs |
| test harness | GLuaTest inside the server | custom SMAPI harness mod asserting on live `Game1` state |
| redistribution | DarkRP tree (MIT) committed per task | mod source (MIT) committed per task; game files acquired by the operator |

Consequences: (1) ownership-gated acquisition via `rhenium auth login steam` and
`rhenium runtime prepare`
(DepotDownloader, manifest-pinnable) + `scripts/prepare-task.sh` staging into each
build context; nothing proprietary in git, images stay private; (2) a compile
layer exists — the verifier builds the submission (`dotnet build --no-restore`
against a NuGet cache warmed at image build) before any behavioral check; (3)
boot is slow (llvmpipe software GL; expect 1–3 min to a loaded save), so verifier
timeouts are generous.

## Runtime design (decided, pending validation)

Everything below follows production-proven patterns from the MIT-licensed
JunimoServer dedicated-server project and its lineage, not invented mechanisms:

- **Headless display**: Xvfb with `+extension GLX` + Mesa llvmpipe. The game is
  MonoGame/DesktopGL and hard-requires a GL context; SDL's dummy driver does not
  work and no production project uses it.
- **Pinned pair**: game 1.6.15 (Linux depot 413153) + SMAPI 4.1.10 (the release
  synced with 1.6.15). All five base trees target exactly this pair (release
  notes state "for SMAPI 4.1.10 or later"; the CP base says 4.1.5+).
- **Scripted SMAPI install**: `printf '2\n\n' | SMAPI.Installer --install
  --game-path ...` with `SMAPI_NO_TERMINAL=true SMAPI_USE_CURRENT_SHELL=true`;
  update checks disabled via `smapi-internal/config.user.json`.
- **Save bootstrap**: harness mod loads the fixture save from the title screen via
  `Game1.multiplayerMode = 0; SaveGame.Load(name)` (JunimoServer's GameLoader
  pattern); the fixture itself is generated at image build time by the same
  harness in `gen-save` mode (`Game1.loadForNewGame` → `Game1.NewDay(0f)` →
  exit after the save lands, folder name recorded in `/opt/gcb/save-name.txt`).
  Fixed `Game1.startingGameSeed` for determinism.
- **Suites**: per-task C# files compiled into the harness by `tests/test.sh` at
  verify time; cases are tick-driven coroutines (can span in-game time; clock
  advanced via `Game1.performTenMinuteClockUpdate()`); verdict is a JSON file —
  the reward gate parses only that, never exit codes.

## Task catalog (batch 1 — all Pathoschild/StardewMods, MIT)

| task | base | fix | fixed release | patch | expected cases | difficulty |
|---|---|---|---|---|---|---|
| `stardew-automate-minifridge-storage` | `automate/2.4.0` | `0554cd80` | 2.4.1 | 1 ln | 3 | easy |
| `stardew-automate-junimohut-seed-config` | `automate/2.5.0` | `e501b71b` | 2.6.0 | 1 ln | 3 | easy |
| `stardew-automate-machine-states-api` | `automate/2.4.5` | `f1a3b840` | 2.5.0 | 1 ln | 3 | medium |
| `stardew-automate-zero-stack-output` | `automate/2.3.1` | `19b32715` | 2.3.2 | 28 ln | 3 | medium |
| `stardew-cp-i18n-case` | `content-patcher/2.4.3` | `994f8504` | 2.4.4 | 39 ln | 3 | medium |

Discrimination mechanisms, each confirmed by reading the base-tag source:

1. **minifridge**: `ModConstants.GetDefaultChestItemIds()` at 2.4.0 lacks `"216"`,
   so `ModEntry` never adds the `automate_storage` context tag to mini-fridges and
   `AutomationFactory` rejects them as containers. Suite: chest+furnace sentinel;
   mini-fridge+furnace must start smelting and receive the bar.
2. **junimohut-seed-config**: `AutomationFactory` line 160 at 2.5.0 reads
   `JunimoHutBehaviorForFertilizer` for `seedBehavior`. Verifier config sets
   seeds=Ignore, fertilizer/gems=MoveIntoChests; one boot discriminates: on base
   the seeds get moved (they follow the fertilizer setting), fixed they stay.
3. **machine-states-api**: in `MachineManager.ReloadQueuedLocations`, a reload
   pass whose locations gained only non-automated groups (machines with no chest
   → `HasInternalAutomation == false`) leaves `anyChanged == false`, so the
   `DisabledMachineGroups` cache is not rebuilt and `GetForApi` misses them.
   Suite forces two separate passes: farm chest+furnace (sentinel), then a lone
   chestless furnace in the greenhouse (discriminator). NOTE: config-disabled
   machines are *excluded from groups entirely* (`MachineGroupFactory` line 192),
   so they can NOT be used as the discriminator — first design draft got this
   wrong; the shipped suite uses the chestless-machine form.
4. **zero-stack-output**: base `MachineGroup` retries `storage.TryPush` forever
   when the held output has `Stack == 0` (state left by broken third-party
   machine data); fix discards it via `output.Take(1)` and lets the machine
   continue. Suite reaches ready state through real smelting, zeroes the stack
   (that mutation IS the corruption under test), asserts recovery + resumption.
5. **cp-i18n-case**: `TranslationValueProvider` at 2.4.3 returns
   `InvariantSets.FromValue(translation)`, which interns case-insensitively
   against predefined sets, so a translation reading exactly `True`/`FALSE`
   canonicalizes to lowercase. Fix adds `FromCaseSensitiveValue`. Suite reads a
   custom data asset patched by a fixture content pack (`tests/probe-pack/`);
   assertions are timing-independent (i18n tokens are always ready).
   The originally planned dynamic-token task (`db1dba9f`, CP 2.5.1) was dropped
   for now: its bug is only observable in the window before CP's first context
   update, which our world-phase probe can't reliably hit. Revisit with a
   title-phase probe (the harness supports `GcbPhase.Title`) once the runtime is
   up and the timing can be measured.

## Risk register (check these first at runtime validation)

Game-API touchpoints written from training knowledge + mod-source usage, not yet
compiled against the real `Stardew Valley.dll`:

- `Object.placementAction(location, x*64, y*64, Game1.player)` signature and
  whether mini-fridge placement outdoors succeeds (else construct the `Chest`
  directly — and then re-examine fairness).
- `Farm.buildStructure("Junimo Hut", tile, player, out Building, magicalConstruction:
  true, skipSafetyChecks: true)` signature; `JunimoHut.GetOutputChest()`.
- `Chest.Items`, `chest.addItem`, `ItemRegistry.Create(id, count)`,
  `Game1.performTenMinuteClockUpdate()`, `Game1.NewDay(0f)`,
  `Game1.startingGameSeed`, `location.resourceClumps.RemoveWhere`,
  `SaveGame.Load(folderName)` (vs full path), `Constants.SaveFolderName`.
- `SuiteRunner`/`ModEntry` behavior across the save-load transition (world-phase
  runner is created on `SaveLoaded`; suites must not run during the load screen).
- ModBuildConfig deploy folder name (assumed = project name: `Mods/Automate`,
  `Mods/ContentPatcher`) — `tests/test.sh` checks and fails closed.
- Backslash `HintPath`s in the upstream csproj files (`$(GamePath)\smapi-internal\...`)
  on Linux MSBuild — believed fine (these mods build on Linux per upstream docs).
- Task 3 confound: if some unrelated location change lands in the same reload
  pass as the greenhouse furnace, `anyChanged` flips true and the base tree
  passes spuriously. If validation sees that, isolate harder (e.g. quiesce, or
  assert across several passes).
- gen-save: whether `SaveLoaded`/`Saved` fire as assumed for a programmatic new
  game, and total boot time under llvmpipe (budgeted 900 s in the Dockerfile).

## Validation runbook (needs game ownership — the only blocker)

On an x86-64 Linux host with Docker (hyper00/hyper01 fine; the C# parse check ran
on hyper01 via `mcr.microsoft.com/dotnet/sdk:8.0`):

```sh
# one-time, interactive (Steam Guard); account must own Stardew Valley
rhenium auth login steam                        # persistent QR session
rhenium runtime prepare stardew-valley/stardew-1.6.15-smapi-4.1.10
# record the manifest + build id it reports into scripts/game-version.lock
scripts/prepare-task.sh --all

# per task
docker build -t gcb-stardew-minifridge stardew-automate-minifridge-storage/environment
# base tree must FAIL: run tests/test.sh in the container → reward 0, with the
#   sentinel passing and the discriminator cases failing
# oracle must PASS: apply solution/solve.sh first → reward 1
# nop control: unmodified tree through the full Harbor path → reward 0
```

Fix the risk-register items as they surface, then update this log with measured
boot time, per-task wall time, and any suite adjustments.

## Candidate backlog (mined 2026-08-04, for later batches)

From `Pathoschild/StardewMods` (MIT) unless noted; full details in the mining
notes of that session. Bug-fix: Automate tree-seed qualified-ID (`7117f3d5`,
2.0.1), moss cache key (`7d355b8d`, 2.0.5), incubator grab (`d336d22a`, 2.1.0),
indoor-pot double harvest (`cb661f50`, 2.1.0), Junimo-chest shared inventory
(`92c38573`, 2.0.3), crab-pot owner (`225d667a`, 2.2.4), feed hoppers
(`6d5bba2a` 2.2.4 / `b7570f52` 2.2.0), golden cracker luck math (`531d5407`,
2.6.0 — probabilistic, hard to assert fairly), CP `MoveEntries` off-by-one
(`902231ec`, 2.0.0), CP list-field serialization (`9a2ba3fc`), CP `DayOfWeek`
(`3187cfa2`, 1.24.1), CP runtime-migration data loss (`76533d08`+`ccbf4ab1`,
2.0.7 — flagship 1.6-migration task), CP dynamic-token startup (`db1dba9f`,
2.5.1 — needs title-phase probe), ChestsAnywhere range (`26284c3d` — needs a
non-UI assertion surface), TractorMod qualified-ID fixes, CJB one-hit-kill grub
regression pair (bug-fix + regression-test shape). Implement-from-spec: CP
Lexer (in-repo unit tests pin the contract), CP text operations, Automate
`StorageManager` (docs give a worked example), ChestsAnywhere `RangeHandler`,
CJB `ItemRepository` (external oracle in the SMAPI repo).
Skipped as non-permissive: Digus/* and aedenthorn/* (GPL-3.0).

## Decisions

- **SMAPI 4.1.10 over 4.5.2**: 4.1.10 is the release synced with game 1.6.15 and
  is ≥ every base tree's floor; a frozen benchmark wants the contemporaneous
  pair, not the newest loader.
- **Trimmed monorepo per task** (`{Mod}/ + Common/ + root build files`) rather
  than the full 20-mod monorepo: builds are identical (`Common.projitems` is a
  shared-items import), the agent still sees a real repo, and each task stays
  ~2 MB.
- **`environment/gcb-harness/` is a committed copy per task** (like DarkRP's
  self-contained rule). `harness/` at the branch root is the canonical source;
  re-copy after editing it. The authoring templates live only in task 1's files
  now — later tasks were derived from it with `sed`.
- **No Steam credentials anywhere in Docker**: build args leak into image
  history. Acquisition happens on the host, staged as plain files.
