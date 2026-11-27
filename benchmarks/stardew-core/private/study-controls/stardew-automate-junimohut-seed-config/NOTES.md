# E0 notes: stardew-valley/core/stardew-automate-junimohut-seed-config

Private study material. It names the defect and the reference; never copy it into an attempt workspace.

## Sets

- Target (1 case): `seeds stay in the hut when the seed behavior is Ignore`.
- Preserved (1 case): `sentinel: fertilizer is moved out of the hut per config` (fertilizer and gems both reach the side
  chest under `MoveIntoChests`). It passes in the unchanged starter. Publicly stated in the exam (Task: "without changing
  how the other item types are handled"; Problem: "The gem option works exactly as advertised") and discoverable in the
  supplied source (`Automate/Framework/Models/ModConfig.cs:30-40`, `Framework/Machines/Buildings/JunimoHutMachine.cs`).
- Setup: `setup: build a Junimo hut with a connected chest`. Static: `check:submission-shape`.

The verifier installs `tests/mod-config.json` (seeds=Ignore, fertilizer=MoveIntoChests, gems=MoveIntoChests); every case
runs under that one configuration in one boot.

## Controls (all patches apply with `patch -p1` in `/app/StardewMods`)

| control | kind | base | change | expected | observed |
| --- | --- | --- | --- | --- | --- |
| `target-negative-reads-gem-option` | target-negative | reference | The repaired line reads `JunimoHutBehaviorForGems` instead of `...ForSeeds`. Under the verifier config gems=MoveIntoChests, so seeds are still moved out. The starter reads the fertilizer option; this is the same defect class wired to a different wrong field. | target F, setup/sentinel P | static P, setup P, sentinel P, target F. Admissible. |
| `compat-negative-fertilizer-reads-seed-option` | compat-negative | reference | One identifier changed in the reference: `fertilizerBehavior` now reads `JunimoHutBehaviorForSeeds` (Ignore). Seeds correctly stay; fertilizer is no longer moved. The mirror image of the original bug. | sentinel F, target P | static P, setup P, sentinel F, target P. Admissible. |
| `alternative-machine-resolves-config` | alternative | starter | The factory no longer computes behaviors. `JunimoHutMachine` takes `ModConfig` + `isBetterJunimosLoaded` and resolves each category from its own option through one `Resolve(configured, autoDetected)` helper; `HasInput`/`HasIgnoredOutput` are derived from the resolved array. Different file and structure from the one-identifier reference fix; AutoDetect semantics are unchanged (gems -> Ignore; seeds/fertilizer -> Ignore with Better Junimos, else MoveIntoChests). | all P | all P. Admissible. |

The unchanged starter is the first target-negative (target F, everything else P).

## Assertion-strength findings

- `Task-1` ("follow its own config option") is **weak**: only seeds=Ignore is ever exercised. An implementation that
  never moves seeds (hard-coded Ignore) would pass all cases. Not run as a control because no manifest kind fits an
  invalid implementation that is expected to pass; recorded here and in `known_issues` instead. Recommendation: keep the
  task, but report its target as "reported symptom fixed", not "option honored in general".
- The target case is a negative assertion (seeds absent from the side chest). It is meaningful only together with the
  sentinel, which proves the hut pipeline moved something. Read the two together.
- No over-constraining assertion found; the structurally different alternative passes unchanged.

## Harness note

The only wait predicate is null-guarded and cannot throw; the `SuiteRunner` fix does not affect this suite. The
prepared evaluator image still contains the pre-fix runner (see `known_issues`).

## Not run

- A second boot with the opposite configuration (seeds=MoveIntoChests, fertilizer=Ignore) would be needed to assert
  `Task-1` fully; the suite has no such boot and none was added (assertions must not be edited).
- Each control was run once; no repeat runs for flakiness.

Starter, reference and the three declared controls were executed with the full profile in the real game container
(records under `e0/records/stardew-valley/core/stardew-automate-junimohut-seed-config/`); `rhenium-study e0 run` reported an empty `problems` list for all five.
