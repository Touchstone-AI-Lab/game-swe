# E0 notes: stardew-valley/core/stardew-automate-release-regressions

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `StardewMods/`; every patch applies with `patch -p1` from
`/app/StardewMods` (`root` = `StardewMods`). Reference = starter + `solution/gold.patch`.

## Case roles

12 cases: 1 static, 1 setup, 6 target, 4 preserved.

| report | target cases | fails in the unchanged starter |
| --- | --- | --- |
| #211 mini-fridge | `mini-fridge feeds an adjacent furnace`, `furnace output is collected back into the mini-fridge` | both |
| #213 API after save load | `machine overlay data is available right after a save loads` | yes |
| #216 stuck machine | `a zero-size output is discarded and the machine empties`, `the machine resumes processing input after the discard` | both |
| #218 hut seed option | `seeds stay in the hut when the seed behavior is Ignore` | yes |

Preserved contracts (all pass in `starter.execution.json`) and where the exam states them:

- plain chest automation: report #211, "My regular chests and stone chests out in the yard are fine"
  (`sentinel: a chest feeds an adjacent furnace`, `sentinel: the finished bar is collected into the chest`);
- the API once a group exists: report #213, "The moment the player sets up any chest next to any machine,
  everything pops into the overlay" (`the API reports the automated machine group`). This case has no
  `sentinel:` prefix but is PASS_TO_PASS and checks a path the report says works, so it is `preserved`;
- hut gem/fertilizer options: report #218, "The gem option works exactly as advertised"
  (`sentinel: fertilizer and gems are moved out of the hut per config`);
- all of them fall under the Task sentence "Behavior on the paths that already work must not change".

## Controls (all run in the real game, all admissible)

| control | kind | change | observed |
| --- | --- | --- | --- |
| `tn-211-minifridge` | target-negative | reference with `AutomateConstants.cs` reverted | fails exactly the two #211 cases |
| `tn-213-api-initial-scan` | target-negative | reference with `MachineManager.cs` reverted | fails exactly the #213 case |
| `tn-216-zero-size-output` | target-negative | reference with `MachineGroup.cs` reverted | fails exactly the two #216 cases |
| `tn-218-hut-seeds` | target-negative | reference with `AutomationFactory.cs` reverted | fails exactly the #218 case |
| `cn-hut-gems-follow-seed-option` | compat-negative | reference, one identifier: the gem behaviour is read from `JunimoHutBehaviorForSeeds` | all six target cases pass; only the hut sentinel fails (gems stay in the hut because the test config sets seeds to Ignore) |
| `alternative` | alternative | starter + independent repair | 12/12 |

The four target-negatives are single-report reverts, so they also validate the case-to-report mapping
above: every report's cases fail alone and nothing else moves.

`cn-hut-gems-follow-seed-option` is the mirror image of the shipped defect (the starter reads the seed
behaviour from the fertilizer option); it is the kind of slip a repair of #218 can introduce.

`alternative` differs from `gold.patch` in every group and uses only public behaviour:

- #211: `AutomationFactory.GetFor` accepts a player chest whose `fridge` flag is set, instead of adding
  item id 216 to the default chest id list;
- #213: `MachineManager.GetForApi` reads the per-location scan result (`MachineData`) instead of changing
  when the flattened caches are rebuilt;
- #216: the empty output is discarded in the machine layer (`GenericObjectMachine.TryDiscardEmptyOutput`,
  called from `GetOutput`), mirroring what the game does on manual collection, instead of in
  `MachineGroup`'s push loop;
- #218: a local resolver gives every item type its own option and its auto-detect fallback.

## Exclusions and weak clauses

- `#213` is `weak`: the probe only asserts that `GetMachineStates` over the whole farm is non-empty.
- `#213-preserve` is `weak` for the same reason (non-emptiness inside the sentinel rectangle).
- `Task-preserve` is `weak`: an open-ended clause sampled on three paths.
- `Notes-tests` is unasserted and excluded (no behavioural content).
- No task-level exclusion is recommended.

## Findings a reader of results needs

- The release-notes answer key described in `DEBUG-HARDENING.md` section 0 is no longer in the starter
  (checked in the pack tree, in the Hub workspace and in the prepared image).
- Report #216 does not say that the stuck output has an empty stack; see `known_issues`.
- The NOTES.md risk-register confound (unfixed tree passing the initial-scan probe spuriously) did not
  occur: the starter fails that case in the E0 baseline.
- The prepared image bakes the harness that predates the wait-predicate fix (commit 276a070); in this
  suite a throwing predicate still ends in a failed case.
- `catalog.json` publishes a brief that names the four defect areas.

## Not run

Nothing. Every control above has a real-engine record under
`e0/records/stardew-valley/core/stardew-automate-release-regressions/`.
