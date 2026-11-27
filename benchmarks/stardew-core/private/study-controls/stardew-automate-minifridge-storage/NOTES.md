# E0 notes: stardew-valley/core/stardew-automate-minifridge-storage

Private study material. It names the defect and the reference; never copy it into an attempt workspace.

## Sets

- Target (2 cases): `mini-fridge feeds an adjacent furnace`, `furnace output is collected back into the mini-fridge`.
  The second depends on the fixture left by the first, so they are not independent evidence.
- Preserved (1 case): `sentinel: standard chest feeds an adjacent furnace`. It passes in the unchanged starter.
  Publicly stated in the exam (Task: "without changing the behavior of the other chest types"; Problem:
  "Regular chests and stone chests still work fine") and discoverable in the supplied source
  (`Automate/Framework/ModConstants.cs` lists `"130"`, `Automate/docs/README.md` lists chests as containers).
- Static: `check:submission-shape`.

## Controls (all patches apply with `patch -p1` in `/app/StardewMods`)

| control | kind | base | change | expected | observed |
| --- | --- | --- | --- | --- | --- |
| `target-negative-qualified-id` | target-negative | reference | The added list entry is `"(BC)216"` instead of `"216"`. `ModEntry.OnAssetRequested` looks the entries up as unqualified `Data/BigCraftables` keys, so the mini-fridge is still never tagged `automate_storage`. A fix applied in the right place with the wrong id form. | both target cases F, sentinel P | static P, sentinel P, target F F. Admissible. |
| `compat-negative-drops-chest` | compat-negative | reference | One line removed from the reference: the regular chest id `"130"`. Mini-fridges are storage, regular chests no longer are. | sentinel F, both target cases P | static P, sentinel F, target P P. Admissible. |
| `alternative-factory-recognition` | alternative | starter | Does not touch the default id list. `AutomationFactory.GetFor` accepts a chest when it has the storage tag **or** `ModConstants.IsBuiltInStorage(chest)` (qualified id `(BC)216`), and the config-menu chest list uses the same predicate so the per-type option still shows the mini-fridge. Recognition by item type in the factory instead of context-tag injection through the asset editor. | all P | all P. Admissible. |

The unchanged starter is the first target-negative (static P, sentinel P, target F F).

## Assertion-strength findings

- `Task-preserve-other-types` is unasserted: stone chest, Junimo chest, big chest and big stone chest are named in the
  exam but never placed. Recommend excluding that clause from contract measurement; the task's preserved set is the
  single regular-chest input behavior.
- The preserved case checks the input side only (ore leaves the chest and the furnace starts). Output collection into a
  regular chest is not asserted in this task.
- No over-constraining assertion found: the suite reads only live game state (`heldObject`, chest items), and the
  alternative, which never adds the context tag to the mini-fridge, passes.

## Harness note

No wait predicate in `SuiteMinifridge.cs` can throw, so the `SuiteRunner` wait-predicate fix does not affect this
suite. The prepared evaluator image still contains the pre-fix runner (see `known_issues` in `clause-map.json`).

## Not run

Nothing outstanding. Starter, reference and the three declared controls were executed with the full profile in the
real game container (runtime identity recorded in `e0/records/.../*.json`). Each control was run once; no repeat runs
for flakiness.
