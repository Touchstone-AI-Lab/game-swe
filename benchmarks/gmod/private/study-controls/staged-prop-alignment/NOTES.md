# E0 notes: garrys-mod/addons/staged-prop-alignment

Task version 2.1.0. Verifier image `gcb-gmod-addons-verifier:23150012` (real Linux dedicated server, Phase A + Phase B), profile `full`. All outcomes below are from `rhenium-study e0 run` records under `e0/records/garrys-mod/addons/staged-prop-alignment/`.

## Map summary

- Clauses: 39 (27 asserted, 11 weak, 1 unasserted: T2-SCOPE-01).
- Cases: 33 (31 target, 2 static, 0 preserved, 0 runtime-sentinel/setup).
- Status policy used for every gmod addons task: `asserted` = the clause's central obligation is checked by an executed, discriminating assertion (unchecked sub-obligations are listed in the clause note); `weak` = the evidence is only implicit/proxy (sandbox load, truthiness, a vacuous or nominal case, a hand-called stored callback where the clause demands the native event), or more than half of the clause's enumerated obligations are never exercised; `unasserted` = no case measures it.
- Case-to-clause links start from `contract-traceability.json`; links the cited case does not exercise were dropped or re-pointed and acceptance clauses were added. Every change is recorded in the case `note`.

## Preserved contracts and compat-negative

None. The starter is empty (`task.json` + `TASK.md` only): `starter.execution.json` observes just `check:required-files` and `check:lua-syntax`, both failing, and no suite case runs (runner error, 0 cases). No case probes ordinary host behavior that passes on the empty starter, so there is no `preserved` case and no compat-negative control. The task enters general completion only.

## Controls

| control | kind | admissible | score | failed cases | unobserved | server phases (raw record) |
| --- | --- | --- | --- | --- | --- | --- |
| starter | starter | yes | 0.0 | both static checks | all 31 suite cases (nothing to run) | A: no result; B not run |
| reference | reference | yes | 100.0 | - | - | A: pass; B ran |
| alternative-second-reference | alternative | yes | 100.0 | - | - | A: pass; B ran |
| alternative-strict-reading | alternative | NO | 53.33 | integration:adapter installs CanTool lifecycle hooks and timer<br>integration:CanTool denial blocks staging before mutation<br>integration:execute creates one constrained copy and one undo unit<br>integration:disconnect clears adapter staging identity | all 8 server cases | A: no result (timeout); B not run |
| probe-z-dropped | target-negative | yes | 97.69 | hidden:three point frames map origin axes and probe | - | A: pass; B ran |
| budget-not-counted | target-negative | yes | 92.69 | hidden:operation budget is consumed once per solve<br>server:move | - | A: pass; B ran |
| cantool-bypassed | target-negative | yes | 98.33 | integration:CanTool denial blocks staging before mutation | - | A: pass; B ran |
| move-falls-through-to-copy | target-negative | yes | 58.33 | integration:move changes original without clone and undo restores transform | all 8 server cases | A: move failed; B not run |
| shutdown-leaks-timer | target-negative | yes | 55.0 | lifecycle:shutdown removes every hook and timer | all 8 server cases | A: cleanup failed; B not run |

Controls whose run is incomplete are not reused by the tool and were therefore executed twice; both executions gave the same score. A control marked NO is an intentional strict-reading alternative (see its section), not an unfinished control.

### alternative-second-reference

Copy of `references/frame-rows` (the Harbor oracle installs `frame-map`). Core, adapter and STOOL all differ textually from the oracle; the core stores sessions/requests/spent as row lists instead of keyed maps (this is why Phase B accepts `state.spent[1].count`). Resolves with every case passing. Caveat: it shares every undisclosed convention with the oracle (hook prefix/suffixes, `TimerName`, `data.stage`, `data.created`).

### alternative-strict-reading

The second reference with changes the public exam permits: hook prefix/timer name changed, `HookPrefix`/`TimerName` not exported, and the undisclosed `created`/`moved` fields removed from Execute's data. Kept as the honest strict-reading alternative: it is REJECTED (53.33, incomplete). Four integration cases fail (install lookup, CanTool denial lookup, `#d.created`, disconnect lookup) and Phase A never emits a result (a Lua error on the nil `S.HookPrefix`/`S.TimerName` in the suite's timer chain; the runner kills it at the 180 s timeout), so all eight server cases are unobserved. The lifecycle case passes vacuously. Evidence of over-constraint, not a defective control; the passing alternative is alternative-second-reference.

### probe-z-dropped

Pack mutation: solve drops the probe's local z. Kills exactly the hidden probe-mapping case. The real-server copy is unaffected because the adapter's probe is the source origin (local z = 0), so this is a single-layer kill.

### budget-not-counted

Pack mutation: a successful solve does not consume budget. Kills the hidden budget case and `server:move` (Phase B reads the persisted budget, which is no longer 2).

### cantool-bypassed

Pack mutation: HandleTrace ignores an explicit CanTool false. Kills exactly the integration denial case; no real-server assertion denies CanTool.

### move-falls-through-to-copy

Pack mutation: `move` runs the copy path. Kills the integration move case. On the real server the Phase A `move` assertions fail, which stops the run before Phase B: all eight server cases are unobserved (`U`), `complete` is false, and no server case is recorded as failed. Admissible because the integration case is a target failure and nothing outside the target set fails.

### shutdown-leaks-timer

Pack lifecycle mutation: Shutdown keeps the timer. All 13 hidden and 9 integration cases still pass. It fails `lifecycle:shutdown removes every hook and timer`; on the real server the Phase A cleanup assertion (`timer.Exists` after Shutdown) fails, so Phase B never runs and all eight server cases are unobserved with `complete` false (score 55.0).

## Exclusion recommendations

- Exclude `T2-SCOPE-01` from clause-level scoring (scope disclaimer, unasserted).
- Weak clauses (11): T2-GOAL-02, T2-API-04, T2-DATA-01, T2-SEM-03, T2-GEO-03, T2-SEM-07, T2-ADAPTER-02, T2-TRUST-01, T2-ROLLBACK-01, T2-SCOPE-02, T2-ACC-02. Quantization (GEO-03) and detachment (API-04/SEM-07) have a named case that is vacuous (hidden:13); a pass is no evidence for them.
- Task-level: keep, with two cautions. (1) Server cases are all-or-nothing for this task: nearly every engine-backed assertion is in Phase A, so a real-server defect shows up as eight unobserved cases and `complete=false`, never as a named failing group. Analyses that count failed cases per clause will under-report server-layer failures here. (2) The undisclosed naming conventions reject a valid strict-reading implementation.

## Not run / limits

- 12 of the 17 pack mutations were not run as controls (the five chosen cover core geometry, core budget, stub CanTool, stub+server move, lifecycle).
- No Windows/native-runner evidence; everything ran in the local Linux verifier image.
