# E0 notes: stardew-valley/core/stardew-tractor-attachment-regressions

Private maintenance material. It names the defects and the reference; never copy it into
an attempt or a model workspace.

Layout: the workspace holds `StardewMods/`; every patch applies with `patch -p1` from
`/app/StardewMods` (`root` = `StardewMods`). Reference = starter + `solution/gold.patch`
(the unmodified Tractor Mod 4.24.4 tree; see the task's `validation/NOTES.md`).

## Case roles

10 entries in `clause-map.json`: 1 static, 1 setup, 4 target, 4 preserved.

| report | target case | defect (upstream fix reverted in the starter) |
| --- | --- | --- |
| Axe and grown fruit trees | `axe: a full-grown fruit tree is left alone ...` | fruit trees are staged with the wild-tree constants, so a grown fruit tree counts as a sapling (`a92f4f9cd`) |
| Seeds and garden pots | `seeds: a garden pot holding a bush is not sown` | the seed attachment ignores a pot's bush (`f35bc8604`) |
| Custom attachments | `custom attachments: an item that can't be placed is never put on the ground` | custom items are placed without checking that they are placeable (`6ad0cb951`) |
| Pickaxe and stones | `pickaxe: stones stay when stone breaking is off` | the break-objects option also breaks breakable stones (`bd38fead3`) |

Preserved (all pass in the unchanged starter): a sapling is cleared, an empty pot is sown,
torches are placed, and a placed torch is broken. Each target that checks something was
left alone runs right after the preserved case that shows the tractor worked the same
patch.

## Controls (all run through `rhenium run`, full profile, in the real game)

| control | kind | base | change | expected | observed |
| --- | --- | --- | --- | --- | --- |
| (starter) | — | starter | none | every target fails, every preserved passes | 5/9, the 4 targets fail (`run-06b7a80c75fc4284`, 2026-09-23) |
| (reference) | — | reference | none | 9/9, three times | 9/9 in `run-8578585b5c2d40bc`, `run-0d8327bc877f47f3`, `run-ac0494748ece42fd` (identical outcomes) |
| `target-negative-only-stones-inside-mines` | target-negative | reference | reads "mine stones" literally: only stones inside the mines are excluded from break-objects | only the stone target fails | 8/9, exactly `pickaxe: stones stay ...` fails (`run-dbd84943a2c94a71`). Admissible. |
| `compat-negative-never-sow-garden-pots` | compat-negative | reference | never sow any garden pot | all targets pass; only the empty-pot preserved case fails | 8/9, exactly `seeds: an empty garden pot is sown` fails (`run-ec36c67123fa431f`). Admissible. |
| `alternative-stage-and-placeability-guards` | alternative | starter | independent repair (see manifest note) | 9/9 | 9/9 (`run-42e97b202cfa4764`). Admissible. |

## Assertion-strength findings

- `Report-seeds-empty-pot` is **weak**: empty garden pots are probed, ordinary tilled soil
  is not.
- One fixed `config.json` is used, so each option is probed in one setting only (for
  example, stone breaking is only probed switched off, and the sapling options only for
  fruit trees).
- No over-constraining assertion found: the alternative, written only from the exam and
  the option descriptions in `TractorMod/i18n/default.json`, passes every case.

## Harness notes

The tractor is spawned by the garage's own stable and mounted with the game's normal
interaction. A ridden horse's tile comes from the mount's bounding box, so the suite
moves the mount with the rider; an early draft moved only the rider and the tractor then
worked the tiles around the garage instead of the prepared patch.

## Infrastructure note

The host's Docker daemon and the shared Hub database were congested during these runs.
Evaluations that never reached the game (container creation or the daemon probe timed
out, or the Hub database was locked) were rerun unchanged; only complete runs are
recorded above.
