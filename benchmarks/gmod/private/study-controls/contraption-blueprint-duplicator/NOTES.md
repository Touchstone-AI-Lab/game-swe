# E0 notes: garrys-mod/addons/contraption-blueprint-duplicator

Task version 2.1.0. Verifier image `gcb-gmod-addons-verifier:23150012` (real Linux dedicated server, Phase A + Phase B), profile `full`. All outcomes below are from `rhenium-study e0 run` records under `e0/records/garrys-mod/addons/contraption-blueprint-duplicator/`.

## Map summary

- Clauses: 42 (35 asserted, 6 weak, 1 unasserted: T5-SCOPE-01).
- Cases: 37 (35 target, 2 static, 0 preserved, 0 runtime-sentinel/setup).
- Status policy used for every gmod addons task: `asserted` = the clause's central obligation is checked by an executed, discriminating assertion (unchecked sub-obligations are listed in the clause note); `weak` = the evidence is only implicit/proxy (sandbox load, truthiness, a vacuous or nominal case, a hand-called stored callback where the clause demands the native event), or more than half of the clause's enumerated obligations are never exercised; `unasserted` = no case measures it.
- Case-to-clause links start from `contract-traceability.json`; links the cited case does not exercise were dropped or re-pointed and acceptance clauses were added. Every change is recorded in the case `note`.

## Preserved contracts and compat-negative

None. The starter is empty (`task.json` + `TASK.md` only): `starter.execution.json` observes just `check:required-files` and `check:lua-syntax`, both failing, and no suite case runs (runner error, 0 cases). No case probes ordinary host behavior that passes on the empty starter, so there is no `preserved` case and no compat-negative control. The task enters general completion only.

## Controls

| control | kind | admissible | score | failed cases | unobserved | server phases (raw record) |
| --- | --- | --- | --- | --- | --- | --- |
| starter | starter | yes | 0.0 | both static checks | all 35 suite cases (nothing to run) | A: no result; B not run |
| reference | reference | yes | 100.0 | - | - | A: pass; B ran |
| alternative-second-reference | alternative | yes | 100.0 | - | - | A: pass; B ran |
| alternative-strict-reading | alternative | NO | 58.33 | integration:adapter installs lifecycle hooks and timer | all 7 server cases | A: cleanup failed; B not run |
| alternative-strict-reading-layout | alternative | NO | 96.66 | hidden:malformed persisted graphs hashes requests and paste rows are rejected<br>integration:saved state restores a pasteable canonical schema | - | A: pass; B ran |
| alternative-strict-reading-params | alternative | NO | 98.33 | hidden:constraint params are validated detached and included in hash | - | A: pass; B ran |
| target-transform-x-skipped | target-negative | yes | 98.33 | hidden:paste plan applies target transform to every node | - | A: pass; B ran |
| constraint-params-omitted-from-hash | target-negative | yes | 98.33 | hidden:constraint params are validated detached and included in hash | - | A: pass; B ran |
| gettable-graph-mismatch-ignored | target-negative | yes | 98.33 | integration:constraint GetTable mismatch rejects capture atomically | - | A: pass; B ran |
| partial-paste-not-rolled-back | target-negative | yes | 98.33 | integration:partial Paste failure rolls back every live object | - | A: pass; B ran |
| shutdown-leaks-timer | target-negative | yes | 55.0 | lifecycle:shutdown removes hooks and timer | all 7 server cases | A: cleanup failed; B not run |

Controls whose run is incomplete are not reused by the tool and were therefore executed twice; both executions gave the same score. A control marked NO is an intentional strict-reading alternative (see its section), not an unfinished control.

### alternative-second-reference

Copy of `references/graph-rows` (the Harbor oracle installs `graph-map`). The core stores blueprints, requests and paste results as row lists (`blueprints`/`requests`/`pastes` arrays in the saved state) instead of the oracle's keyed `owners` map; the adapter differs textually too. Resolves with every case passing. Caveat: it shares the undisclosed hook naming with the oracle, and the suites accept exactly these two save layouts.

### alternative-strict-reading

The second reference with the hook prefix/timer name changed, hooks named `<prefix>.<HookEvent>` and `HookPrefix`/`TimerName` not exported. Kept as the honest strict-reading alternative: it is REJECTED (58.33, incomplete). The integration install case fails; the other stub cases that use the private fields pass vacuously (`timers[nil]` is nil on both sides of the idempotence comparison, the leak scan looks for the private fragment). On the real server the Phase A `cleanup` group fails (`timer.Exists(S.TimerName)` with a nil name), so Phase B never runs and all seven server cases are unobserved. Evidence of over-constraint; the passing alternative is alternative-second-reference.

### alternative-strict-reading-layout

The second reference with ONE change: the saved-state list is called `blueprint_rows` instead of `blueprints` (T5-PERSIST-01 publishes no key names). Hook names and everything else are untouched. REJECTED (96.66): it fails `hidden:malformed persisted graphs hashes requests and paste rows are rejected` (mutators index `owners` or `blueprints`) and `integration:saved state restores a pasteable canonical schema` (asserts `state.owners or state.blueprints`); everything else, including real Paste/Undo in Phase B, passes.

### alternative-strict-reading-params

The second reference with ONE change in the params normalizer: unknown keys are dropped instead of rejected; malformed values of Bone1/Bone2/forcelimit/nocollide are still rejected. T5-SEM-03 only requires params to be detached and to round-trip AT LEAST those four keys. REJECTED (98.33): it fails exactly `hidden:constraint params are validated detached and included in hash`, which demands `invalid_endpoint` for `{unknown=1}` (hidden:19).

### target-transform-x-skipped

Pack mutation: the paste plan ignores the target x translation. Kills exactly the hidden plan case. Both server phases pass: Phase B never compares pasted positions with the target, so the real server cannot see this defect (recorded in the T5-NATIVE-03/T5-ACC-04 notes).

### constraint-params-omitted-from-hash

Pack mutation: params do not contribute to the hash. Kills exactly the hidden params/hash case.

### gettable-graph-mismatch-ignored

Pack mutation: Capture ignores a GetTable/Copy disagreement. Kills exactly the integration mismatch case; the real server never presents a mismatching view.

### partial-paste-not-rolled-back

Pack mutation: a partially failed Paste leaves live objects. Kills exactly the integration rollback case; no failure is injected on the real server.

### shutdown-leaks-timer

Pack lifecycle mutation: Shutdown keeps the named timer. All 18 hidden and 9 integration cases pass. It fails `lifecycle:shutdown removes hooks and timer`; the Phase A `cleanup` group fails on `timer.Exists`, so Phase B never runs and all seven server cases are unobserved with `complete` false (score 55.0).

## Exclusion recommendations

- Exclude `T5-SCOPE-01` from clause-level scoring (describes the acceptance setup and unsupported features, unasserted).
- Weak clauses (6): T5-GOAL-02, T5-PERSIST-02, T5-ADAPTER-01, T5-TRUST-01, T5-ROLLBACK-01, T5-SCOPE-02.
- Over-constraint that can reject a valid implementation independent of naming: an unknown params key must be refused with `invalid_endpoint` and a persisted `Bone1=-1` with `invalid_state` (hidden:19,21), while T5-SEM-03 only requires params to round-trip AT LEAST four keys. Recommend that failures of `hidden:constraint params are validated detached and included in hash`, `hidden:malformed persisted graphs hashes requests and paste rows are rejected` and `integration:saved state restores a pasteable canonical schema` are not interpreted as a violated public clause without inspecting the message; measured by alternative-strict-reading-params and alternative-strict-reading-layout.
- Task-level: keep. Of the five addons tasks this one has the best case-level server evidence (real Paste, graph and single Undo are Phase B assertions).

## Not run / limits

- 9 of the 14 pack mutations were not run as controls.
- The `Bone1 = -1` persisted-state over-constraint (hidden:21) was established by reading, not by a control.
- No Windows/native-runner evidence; everything ran in the local Linux verifier image.
