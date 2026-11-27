# E0 notes: stardew-valley/core/stardew-automate-release-regressions-v2

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `StardewMods/`; every patch applies with `patch -p1` from
`/app/StardewMods` (`root` = `StardewMods`). Reference = starter + `solution/gold.patch`.

## Case roles

15 cases: 1 static, 2 setup, 8 target, 4 preserved.

| report | target cases | fails in the unchanged starter |
| --- | --- | --- |
| #211 mini-fridge | `mini-fridge feeds an adjacent furnace`, `furnace output is collected back into the mini-fridge` | both |
| #213 API after save load | `machine overlay data is available right after a save loads` | yes |
| #216 stuck machine | `a zero-size output is discarded and the machine empties`, `the machine resumes processing input after the discard` | both |
| #218 hut seed option | `seeds stay in the hut when the seed behavior is Ignore` | yes |
| #221 / #222 duplicate buildings (one root cause) | `machines in the first coop run`, `machines in the second coop run too` | only the second; the first coop always works in the starter |
| #224 incubator egg theft | none (unscored haystack) | not observable |

`machines in the first coop run` passes in the starter. It stays `target`: it is half of the evidence
for the duplicate-building reports and fails for a repair that moves the collision to the other coop.

Preserved contracts (all pass in `starter.execution.json`) and where the exam states them:

- plain chest automation on the farm: #211 "My regular chests and stone chests out in the yard are fine",
  #221 "machines everywhere else on the farm still work", #224 "Everything else — furnaces, kegs,
  preserves jars — fills and empties exactly when it should" (the two chest/furnace sentinels);
- the API once a group exists: #213 "The moment the player sets up any chest next to any machine,
  everything pops into the overlay" (`the API reports the automated machine group`; no `sentinel:`
  prefix, but PASS_TO_PASS on a path the report says works);
- hut gem/fertilizer options: #218 "The gem option works exactly as advertised" (hut sentinel);
- all under the Task sentence "Behavior on the paths that already work must not change".

## Controls (all run in the real game, all admissible)

| control | kind | change | observed |
| --- | --- | --- | --- |
| `tn-211-minifridge` | target-negative | reference with `AutomateConstants.cs` reverted | fails exactly the two #211 cases |
| `tn-213-api-initial-scan` | target-negative | reference with `MachineManager.cs` reverted | fails exactly the #213 case |
| `tn-216-zero-size-output` | target-negative | reference with `MachineGroup.cs` reverted | fails exactly the two #216 cases |
| `tn-218-hut-seeds` | target-negative | reference with `AutomationFactory.cs` reverted | fails exactly the #218 case |
| `tn-221-222-location-identity` | target-negative | reference with both location files reverted | fails exactly `machines in the second coop run too` |
| `tn-221-222-half-fix-key-only` | target-negative | reference with only `GameLocationNameComparer.cs` reverted (unique key, name-only comparer) | fails exactly `machines in the second coop run too`; confirms the pair must be fixed together |
| `cn-hut-gems-follow-seed-option` | compat-negative | reference, one identifier: the gem behaviour is read from `JunimoHutBehaviorForSeeds` | all eight target cases pass; only the hut sentinel fails |
| `alternative` | alternative | starter + independent repair | 15/15 |

`alternative` differs from `gold.patch` in every group (see the v1 notes for #211/#213/#216/#218). For
#221/#222 one shared `GameLocationNameComparer.GetIdentity` (unique name when present) feeds both the
comparer and `GetLocationKey`, instead of two separate edits with two different key formats. It also
repairs the unscored #224 with an `IsIncubator()` guard in `DataBasedObjectMachine`.

## Probe (not in `manifest.tsv`; its row is kept in `probes.tsv`)

`probe-224-unfixed`: the reference with only the #224 (incubator) fix reverted. Result: 15/15,
score 100, i.e. indistinguishable from the reference (`e0/records/.../probe-224-unfixed.json`, recorded while
the row was in the manifest as a target-negative: "must fail at least one target case"). This is the
empirical confirmation that #224 is unscored.

## Exclusions and weak clauses

- `#224` unasserted and excluded: public, real, fixed by the gold patch, no assertion (`task.toml`:
  the observable needs a real overnight). A submission that ignores it resolves the task.
- `#222` weak: no shed or preserves jar is built; covered through its shared root cause with #221.
- `#213` and `#213-preserve` weak: only non-emptiness of `GetMachineStates`.
- `Task-preserve` weak: three working paths sampled.
- `Notes-tests` unasserted and excluded.
- No task-level exclusion is recommended.

## Findings a reader of results needs

- The release-notes answer key (`DEBUG-HARDENING.md` section 0) is gone from the starter, the Hub
  workspace and the prepared image, including the haystack entry about incubated eggs.
- Report #216 does not say that the stuck output has an empty stack; see `known_issues`.
- `catalog.json` publishes 'location-key defects' / 'location identity collisions' for this task, which
  is the diagnosis of #221/#222 that the exam withholds.
- The prepared image bakes the harness that predates the wait-predicate fix (commit 276a070); in this
  suite a throwing predicate still ends in a failed case.

## Not run

Nothing. Every control and the probe have real-engine records under
`e0/records/stardew-valley/core/stardew-automate-release-regressions-v2/`.
