# E0 notes: garrys-mod/addons/persistent-loadout-profiles

Task version 2.1.0. Verifier image `gcb-gmod-addons-verifier:23150012` (real Linux dedicated server, Phase A + Phase B), profile `full`. All outcomes below are from `rhenium-study e0 run` records under `e0/records/garrys-mod/addons/persistent-loadout-profiles/`.

## Map summary

- Clauses: 39 (30 asserted, 8 weak, 1 unasserted: T3-SCOPE-02).
- Cases: 32 (30 target, 2 static, 0 preserved, 0 runtime-sentinel/setup).
- Status policy used for every gmod addons task: `asserted` = the clause's central obligation is checked by an executed, discriminating assertion (unchecked sub-obligations are listed in the clause note); `weak` = the evidence is only implicit/proxy (sandbox load, truthiness, a vacuous or nominal case, a hand-called stored callback where the clause demands the native event), or more than half of the clause's enumerated obligations are never exercised; `unasserted` = no case measures it.
- Case-to-clause links start from `contract-traceability.json`; links the cited case does not exercise were dropped or re-pointed and acceptance clauses were added. Every change is recorded in the case `note`.

## Preserved contracts and compat-negative

None. The starter is empty (`task.json` + `TASK.md` only): `starter.execution.json` observes just `check:required-files` and `check:lua-syntax`, both failing, and no suite case runs (runner error, 0 cases). No case probes ordinary host behavior that passes on the empty starter, so there is no `preserved` case and no compat-negative control. The task enters general completion only.

## Controls

| control | kind | admissible | score | failed cases | unobserved | server phases (raw record) |
| --- | --- | --- | --- | --- | --- | --- |
| starter | starter | yes | 0.0 | both static checks | all 30 suite cases (nothing to run) | A: no result; B not run |
| reference | reference | yes | 100.0 | - | - | A: pass; B ran |
| alternative-second-reference | alternative | yes | 100.0 | - | - | A: pass; B ran |
| alternative-strict-reading | alternative | NO | 52.5 | integration:adapter installs only meaningful spawn and disconnect hooks<br>integration:spawn hook reapplies without accumulating pickups<br>integration:disconnect removes object binding but retains profile<br>integration:Install is idempotent | all 7 server cases | A: no result (timeout); B not run |
| alternative-strict-reading-layout | alternative | NO | 97.86 | hidden:malformed persisted profiles choices requests and plans are rejected | - | A: pass; B ran |
| shared-ammo-overwritten | target-negative | yes | 51.96 | hidden:shared ammo is merged once and sorted<br>hidden:ammo caps are checked after aggregation<br>integration:shared ammo is granted once at the merged amount<br>integration:spawn hook reapplies without accumulating pickups | all 7 server cases | A: ammo failed; B not run |
| save-drops-preference | target-negative | yes | 72.85 | hidden:save load preserves preference revisions and replay<br>hidden:malformed persisted profiles choices requests and plans are rejected<br>server:profiles<br>server:ammo<br>server:failure<br>server:identity | - | A: pass; B ran |
| give-failure-continues | target-negative | yes | 98.12 | integration:partial Give failure stops before ammo | - | A: pass; B ran |
| fake-spawn-wiring | target-negative | yes | 58.12 | integration:spawn hook reapplies without accumulating pickups | all 7 server cases | A: ammo failed; B not run |
| shutdown-leaks-spawn-hook | target-negative | yes | 55.0 | lifecycle:shutdown removes all meaningful hooks | all 7 server cases | A: cleanup failed; B not run |

Controls whose run is incomplete are not reused by the tool and were therefore executed twice; both executions gave the same score. A control marked NO is an intentional strict-reading alternative (see its section), not an unfinished control.

### alternative-second-reference

Copy of `references/profile-rows` (the Harbor oracle installs `profile-map`). The core stores profiles, choices and requests as row lists and saves them as `profiles`/`choices` lists instead of the oracle's nested `players` map; the adapter differs textually as well. Resolves with every case passing. Caveat: it shares the undisclosed `HookPrefix` and `.Spawn`/`.Disconnect` hook names with the oracle, and the hidden malformed-state case is written for exactly these two save layouts.

### alternative-strict-reading

The second reference with the hook prefix changed, hooks named `<prefix>.PlayerSpawn`/`<prefix>.PlayerDisconnected` and `HookPrefix` not exported. Kept as the honest strict-reading alternative: it is REJECTED (52.5, incomplete). Four integration cases that index the hook table through `S.HookPrefix` fail, the lifecycle case passes vacuously (its leak scan looks for the private name fragment), and Phase A never emits a result (Lua error on the nil `S.HookPrefix` in the suite's cleanup step; killed at the runner timeout), so all seven server cases are unobserved. Evidence of over-constraint; the passing alternative is alternative-second-reference.

### alternative-strict-reading-layout

The second reference with ONE change: the saved-state lists are called `profile_rows`/`choice_rows` instead of `profiles`/`choices` (T3-PERSIST-02 publishes no key names). Hook names and everything else are untouched. REJECTED (97.86): it fails exactly `hidden:malformed persisted profiles choices requests and plans are rejected`, whose mutators index one of the two authored layouts and error on a third; all other cases, including both server phases, pass. Evidence of over-constraint attributable to the save layout alone.

### shared-ammo-overwritten

Pack mutation: a shared ammo type is overwritten instead of summed (SMG1 becomes 10, and the Pistol cap case no longer aggregates). Kills two hidden cases and two integration cases. On the real server the Phase A `ammo == 70` assertion fails, which stops the run: all seven server cases are unobserved and `complete` is false.

### save-drops-preference

Pack mutation: save() writes an empty players table. Kills the hidden save/load case and the malformed-state case (its mutator indexes the missing player). Phase A still passes, so Phase B runs and records named failures: `server:profiles`, `server:ammo`, `server:failure`, `server:identity` (nothing to Apply in the fresh process). This is the control that shows Phase B failures ARE visible per group.

### give-failure-continues

Pack mutation: Apply continues after a failed Give. Kills exactly the integration partial-Give case; the real server never injects a Give failure.

### fake-spawn-wiring

Pack mutation: the PlayerSpawn hook is registered but empty. Kills the integration spawn-hook case. In Phase A only the `ammo` group fails (pickup ammo is not reset to 70); the `spawn` group still PASSES with the empty hook, because the fixture weapons (pistol, SMG1) are part of the Sandbox default loadout and come back on any respawn (raw record: `result.runtime.phase_a.payload.cases`). The Phase A failure stops the run: all seven server cases unobserved, `complete` false. This is the paper's example seen from the other side: the only NAMED failing evidence is the weaker stub intervention; the native one acts as a gate.

### shutdown-leaks-spawn-hook

Study-authored lifecycle mutation (the pack matrix has none for this task): Shutdown removes only the PlayerDisconnected hook. All 14 hidden and 8 integration cases pass. It fails `lifecycle:shutdown removes all meaningful hooks`; the Phase A cleanup assertion fails too, so all seven server cases are unobserved and `complete` is false (score 55.0).

## Exclusion recommendations

- Exclude `T3-SCOPE-02` from clause-level scoring (disclaimer + no-TODO rule, unasserted).
- Weak clauses (8): T3-GOAL-02, T3-DATA-01, T3-ADAPTER-01, T3-ROLLBACK-01, T3-SEM-07, T3-NATIVE-02, T3-TRUST-01, T3-SCOPE-01. T3-SEM-07/T3-NATIVE-02 are weak for the reason the paper gives: the only case-level evidence sets ammo to 999 and calls the stored hook by hand; native pickup + Kill + Spawn is Phase A gate evidence only.
- Task-level: keep, with the same two cautions as the other addons tasks (undisclosed hook naming rejects a strict-reading implementation; Phase A failures surface as seven unobserved cases).

## Not run / limits

- 10 of the 14 pack mutations were not run as controls.
- No Windows/native-runner evidence; everything ran in the local Linux verifier image.
