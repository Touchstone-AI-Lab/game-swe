# E0 notes: stardew-valley/core/stardew-automate-release-regressions-v3

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `StardewMods/`; every patch applies with `patch -p1` from
`/app/StardewMods` (`root` = `StardewMods`). Reference = starter + `solution/gold.patch`.

## Case roles

9 cases: 1 static, 1 setup, 5 target, 2 preserved.

| report | target cases | fails in the unchanged starter |
| --- | --- | --- |
| #241 stuck machine | `a zero-size output is discarded and the machine empties`, `the machine resumes processing input after the discard` | both |
| #243 API after save load | `machine overlay data is available right after a save loads` | yes |
| #248 / #249 duplicate buildings (one root cause) | `machines in the first coop run`, `machines in the second coop run too` | only the second; the first coop always works in the starter |
| #246 removed bush | none | not observable |

`machines in the first coop run` passes in the starter. It stays `target`: it is half of the evidence
for the duplicate-building reports and fails for a repair that moves the collision to the other coop.

Preserved contract (passes in `starter.execution.json`): plain chest automation on the farm, stated
in report #248 ("machines everywhere else on the farm still work") and in the Task sentence "Behavior
on the paths that already work must not change" (`sentinel: a chest feeds an adjacent furnace`,
`sentinel: the finished bar is collected`).

## Controls (all run in the real game, all admissible)

| control | kind | change | observed |
| --- | --- | --- | --- |
| `tn-241-zero-size-output` | target-negative | reference with `MachineGroup.cs` reverted | fails exactly the two #241 cases |
| `tn-243-api-initial-scan` | target-negative | reference with `MachineManager.cs` reverted | fails exactly the #243 case |
| `tn-248-249-location-identity` | target-negative | reference with `GameLocationNameComparer.cs` and `MachineGroupFactory.cs` reverted | fails exactly `machines in the second coop run too` |
| `cn-discard-single-item-output` | compat-negative | reference whose zero-size special case became `stackSize <= 1` and runs before storage is tried | all five target cases pass; only `sentinel: the finished bar is collected` fails (single bars are thrown away) |
| `alternative` | alternative | starter + independent repair | 9/9 |

`cn-discard-single-item-output` is an over-broad repair of #241. It had to be built this way because the
#241 cases reuse the sentinel chest and furnace: a compat-negative that stops the furnace from being
emptied or refilled would fail target cases too. Destroying the collected bar keeps the machine cycling.

`alternative` differs from `gold.patch` in every group: the empty output is discarded in the machine
layer (`GenericObjectMachine.TryDiscardEmptyOutput`, called from `GetOutput`); `GetForApi` reads the
per-location scan result instead of changing when the flattened caches are rebuilt; one shared
`GameLocationNameComparer.GetIdentity` (unique name when present) feeds both the comparer and
`GetLocationKey`; and the unasserted #246 is repaired as well (`BushMachine.GetState` returns
`Disabled` for a bush without a location).

## Probe (not in `manifest.tsv`; its row is kept in `probes.tsv`)

`probe-246-unfixed`: the reference with only the #246 fix reverted. Result: 9/9, score 100, i.e. it is
indistinguishable from the reference (`e0/records/.../probe-246-unfixed.json`, recorded while the row was
in the manifest as a target-negative: "must fail at least one target case"). This is the empirical
confirmation that #246 is unasserted.

## Exclusions and weak clauses

- `#246` unasserted and excluded: public, real, fixed by the gold patch, no assertion (suite class comment,
  `task.toml`). A submission that ignores it resolves the task.
- `#243-preserve` unasserted and excluded: v1/v2 check the API after a group exists; v3 dropped that case.
- `#243` weak: only non-emptiness of `GetMachineStates` over the whole farm.
- `#249` weak: no shed or preserves jar is built; covered through its shared root cause with #248.
- `Task-preserve` weak: one working path sampled.
- `Notes-tests` unasserted and excluded.
- No task-level exclusion is recommended, but with two preserved cases on one path the preserved set is thin.

## Findings a reader of results needs

- The release-notes answer key (`DEBUG-HARDENING.md` section 0) is gone from the starter, the Hub workspace
  and the prepared image for all three v3 entries (zero-size output, `GetMachineStates`, chopped bush).
- `task.toml` `base_ref`/`fix_commit` now name 19b32715, f1a3b840 and 001e64aa, matching `gold.patch`;
  the staleness noted in `DEBUG-HARDENING.md` is fixed in this tree.
- Report #241 does not say that the stuck output has an empty stack; see `known_issues`.
- The prepared image bakes the harness that predates the wait-predicate fix (commit 276a070); in this
  suite a throwing predicate still ends in a failed case.
- `catalog.json` publishes a summary that names all four defect areas including the unasserted one.

## Not run

Nothing. Every control and the probe have real-engine records under
`e0/records/stardew-valley/core/stardew-automate-release-regressions-v3/`.
