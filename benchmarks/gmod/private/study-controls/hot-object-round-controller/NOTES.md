# E0 notes: garrys-mod/addons/hot-object-round-controller

Task version 2.1.0. Verifier image `gcb-gmod-addons-verifier:23150012` (real Linux dedicated server, Phase A + Phase B), profile `full`. All outcomes below are from `rhenium-study e0 run` records under `e0/records/garrys-mod/addons/hot-object-round-controller/`.

## Map summary

- Clauses: 40 (34 asserted, 5 weak, 1 unasserted: T4-DATA-01).
- Cases: 34 (32 target, 2 static, 0 preserved, 0 runtime-sentinel/setup).
- Status policy used for every gmod addons task: `asserted` = the clause's central obligation is checked by an executed, discriminating assertion (unchecked sub-obligations are listed in the clause note); `weak` = the evidence is only implicit/proxy (sandbox load, truthiness, a vacuous or nominal case, a hand-called stored callback where the clause demands the native event), or more than half of the clause's enumerated obligations are never exercised; `unasserted` = no case measures it.
- Case-to-clause links start from `contract-traceability.json`; links the cited case does not exercise were dropped or re-pointed and acceptance clauses were added. Every change is recorded in the case `note`.

## Preserved contracts and compat-negative

None. The starter is empty (`task.json` + `TASK.md` only): `starter.execution.json` observes just `check:required-files` and `check:lua-syntax`, both failing, and no suite case runs (runner error, 0 cases). No case probes ordinary host behavior that passes on the empty starter, so there is no `preserved` case and no compat-negative control. The task enters general completion only.

## Controls

| control | kind | admissible | score | failed cases | unobserved | server phases (raw record) |
| --- | --- | --- | --- | --- | --- | --- |
| starter | starter | yes | 0.0 | both static checks | all 32 suite cases (nothing to run) | A: no result; B not run |
| reference | reference | yes | 100.0 | - | - | A: pass; B ran |
| alternative-second-reference | alternative | yes | 100.0 | - | - | A: pass; B ran |
| alternative-strict-reading | alternative | NO | 51.67 | integration:adapter installs lifecycle hooks and one timer<br>integration:object binding is single use and removal restores original callbacks<br>integration:PlayerDeath hook changes holder once<br>integration:PlayerSpawn rebinds a new revision<br>integration:timer reaches fixed deadline exactly once | all 8 server cases | A: no result (timeout); B not run |
| alternative-strict-reading-layout | alternative | NO | 55.71 | hidden:infectious variant excludes every infected survivor from winners<br>hidden:malformed players events audit result and revisions are rejected | all 8 server cases | A: no result (timeout); B not run |
| holder-successor-unsorted | target-negative | yes | 56.19 | hidden:holder death and disconnect choose stable successor<br>integration:PlayerDeath hook changes holder once | all 8 server cases | A: lifecycle failed; B not run |
| infected-survivors-can-win | target-negative | yes | 97.86 | hidden:infectious variant excludes every infected survivor from winners | - | A: pass; B ran |
| fake-death-lifecycle | target-negative | yes | 58.33 | integration:PlayerDeath hook changes holder once | all 8 server cases | A: lifecycle failed; B not run |
| callback-restoration-removed | target-negative | yes | 53.33 | integration:object binding is single use and removal restores original callbacks<br>lifecycle:shutdown removes hooks timer restores callbacks and freezes adapter | all 8 server cases | A: cleanup failed; B not run |
| shutdown-leaks-timer | target-negative | yes | 55.0 | lifecycle:shutdown removes hooks timer restores callbacks and freezes adapter | all 8 server cases | A: cleanup failed; B not run |

Controls whose run is incomplete are not reused by the tool and were therefore executed twice; both executions gave the same score. A control marked NO is an intentional strict-reading alternative (see its section), not an unfinished control.

### alternative-second-reference

Copy of `references/player-rows` (the Harbor oracle installs `player-map`). The core keeps players and events as sorted row lists (`player_rows`, `event_rows`) instead of the oracle's keyed maps (`players`, `seen`); the adapter differs textually too. Resolves with every case passing. Caveat: the suites read player state through exactly these two layouts and both references share the undisclosed hook naming.

### alternative-strict-reading

The second reference with the hook prefix/timer name changed, hooks named `<prefix>.<HookEvent>` and `HookPrefix`/`TimerName` not exported. Kept as the honest strict-reading alternative: it is REJECTED (51.67, incomplete). Five integration cases that look hooks/timer up through the private fields fail; the lifecycle case passes because `timers[nil]` is nil and the leak scan looks for the private fragment; Phase A never emits a result (Lua error on the nil fields in the suite's clean step, killed at the timeout), so all eight server cases are unobserved. Evidence of over-constraint; the passing alternative is alternative-second-reference.

### alternative-strict-reading-layout

The second reference with ONE change: the snapshot/save lists are exposed as sorted lists under `players`/`events` instead of `player_rows`/`event_rows` (T4-PERSIST-01 asks for all player state with stably sorted lists and names no key). Hook names untouched. REJECTED (55.71, incomplete): the hidden infectious and malformed-state cases fail because the suite reads `players.B`/`players.A` as a keyed map, and Phase A never emits a result for the same reason (Lua error in the suite, killed at the timeout), so all eight server cases are unobserved. Every other hidden and integration case passes, which also shows the rename is self-consistent.

### holder-successor-unsorted

Pack mutation: successor candidates sorted descending. Kills the hidden successor case and the integration PlayerDeath case. Phase A's real-Kill successor assertion fails (`lifecycle` group), which stops the run: all eight server cases unobserved, `complete` false.

### infected-survivors-can-win

Pack mutation: infectious settlement no longer excludes infected survivors. Kills exactly the hidden infectious case. Both server phases pass: the Phase A winners assertion runs after the infected bot was kicked, so it cannot see this defect (recorded in known_issues).

### fake-death-lifecycle

Pack mutation: the PlayerDeath hook does not reach the core. Kills the integration PlayerDeath case; Phase A `lifecycle` fails on the real Kill, so all eight server cases are unobserved and `complete` is false.

### callback-restoration-removed

Pack mutation: original StartTouch/Touch callbacks are not restored. Kills the integration binding case and the lifecycle case (which also asserts restoration); Phase A `cleanup` fails (`bound entity callbacks are restored exactly`), so all eight server cases are unobserved.

### shutdown-leaks-timer

Pack lifecycle mutation: Shutdown keeps the tick timer. All 14 hidden and 9 integration cases pass. It fails the lifecycle case; Phase A `cleanup` fails on `timer.Exists`, so all eight server cases are unobserved and `complete` is false (score 55.0).

## Exclusion recommendations

- Exclude `T4-DATA-01` from clause-level scoring: no case passes a malformed identifier, revision, sequence or time (unasserted). It is a real public obligation, so an agent can ignore it at no cost.
- Weak clauses (5): T4-ERR-01, T4-SEM-02, T4-PERSIST-03, T4-ADAPTER-01, T4-SCOPE-01.
- Task-level: keep, with cautions. (1) The private snapshot layout (`players.<ID>` or `player_rows[i]`) rejects a natural strict reading of T4-PERSIST-01 (a sorted `players` list); measured by alternative-strict-reading-layout. (2) Undisclosed hook naming rejects alternative-strict-reading. (3) Four of the five target-negatives above surface on the server only as eight unobserved cases because their evidence is in Phase A.

## Not run / limits

- 11 of the 16 pack mutations were not run as controls.
- No Windows/native-runner evidence; everything ran in the local Linux verifier image.
