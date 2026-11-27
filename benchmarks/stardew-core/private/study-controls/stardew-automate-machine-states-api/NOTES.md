# E0 notes: stardew-valley/core/stardew-automate-machine-states-api

Private study material. It names the defect and the reference; never copy it into an attempt workspace.

## Sets

- Target (1 case): `non-automated machines are reported after the initial scan`.
- Preserved (2 cases): `sentinel: an automated machine group is reported` and
  `automated and non-automated machines are reported together`. Both pass in the unchanged starter. Publicly stated in
  the exam (Task: "Behavior for locations with automated machine groups must not change"; Problem: "If the location
  also contains at least one working machine group, the non-automated ones show up fine alongside it") and discoverable
  in the supplied source (`Automate/IAutomateAPI.cs`, `Framework/AutomateAPI.cs`, `MachineManager.GetForApi`).
  The third case asserts non-automated machines in a *mixed* location, which already works; it is therefore preserved,
  not a boundary case of the requested change, and is not marked as overlap.
- Static: `check:submission-shape`.

## Controls (all patches apply with `patch -p1` in `/app/StardewMods`)

| control | kind | base | change | expected | observed |
| --- | --- | --- | --- | --- | --- |
| `target-negative-requires-active-group` | target-negative | reference | The repaired condition is `active.Any() && disabled.Any()` instead of `||`. A reload pass that finds only non-automated groups (the initial scan of the chestless fixture save) still does not rebuild the API caches. | target F, both preserved P | static P, target F, preserved P P. Admissible. |
| `compat-negative-api-drops-active-groups` | compat-negative | reference | `MachineManager.GetForApi` no longer concatenates `ActiveMachineGroups`. Non-automated machines are reported after the initial scan; the automated chest+furnace group disappears from the API. | target P, both preserved F | static P, target P, preserved F F. Admissible. |
| `alternative-api-reads-location-data` | alternative | starter | Leaves the cache-rebuild condition in `ReloadMachinesIn` exactly as in the starter. `GetForApi` becomes an iterator that reads the per-location `MachineData[locationKey]` record (written unconditionally by every reload) plus the Junimo groups, so the API no longer depends on the flattened caches being fresh. Different method, different strategy (remove the stale-cache dependency instead of fixing the invalidation). | all P | all P. Admissible. |

The unchanged starter is the first target-negative (target F, everything else P).

## Assertion-strength findings

- `Task-1` is **weak**: the target case asserts only `states.Any()` over the whole farm before the chest/furnace setup.
  It does not check that the reported tiles belong to the unconnected machines (the shipping bin), nor any state value.
  This is the paper's known example; the same probe is reused by the composite release-regressions tasks.
- `Task-1-matching` ("matching how those machines are already reported when an automated group exists") is
  **unasserted**: no case reads a state value or compares the two reports. Recommend excluding it.
- `Problem-mixed` is **weak**: asserted only as `Count > 1` farm-wide.
- The exam's example (a shed whose machines have no chest) is not what is exercised; the suite uses the initial save-load
  scan of a chestless farm because a chestless machine placed at runtime never queues a reload on either tree
  (`private/harbor/NOTES.md`). A submission is not penalized for this, but a reader should not interpret the target
  case as covering runtime placement.
- No over-constraining assertion found; the alternative, which never touches the cache condition, passes.

## Harness note

`SuiteMachineStatesApi.cs:82-83` is a wait predicate that can throw (null `_api`, or an exception from the submission's
`GetMachineStates`). Under both the fixed and the pre-fix runner the case ends F, because line 85 re-evaluates the same
call; only the message differs. The prepared evaluator image still contains the pre-fix runner (see `known_issues`).

## Not run

Each control was run once; no repeat runs for flakiness. No control for the weak assertion itself (an implementation
that reports a wrong tile or a wrong state) was run: it would be an invalid implementation expected to pass, which no
manifest kind describes.

Starter, reference and the three declared controls were executed with the full profile in the real game container
(records under `e0/records/stardew-valley/core/stardew-automate-machine-states-api/`); `rhenium-study e0 run` reported an empty `problems` list for all five.
