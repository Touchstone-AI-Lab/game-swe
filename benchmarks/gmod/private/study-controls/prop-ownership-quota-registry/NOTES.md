# E0 notes: garrys-mod/addons/prop-ownership-quota-registry

Task version 2.1.0. Verifier image `gcb-gmod-addons-verifier:23150012` (real Linux dedicated server, Phase A + Phase B), profile `full`. All outcomes below are from `rhenium-study e0 run` records under `e0/records/garrys-mod/addons/prop-ownership-quota-registry/`.

## Map summary

- Clauses: 36 (30 asserted, 5 weak, 1 unasserted: T1-SCOPE-01).
- Cases: 31 (29 target, 2 static, 0 preserved, 0 runtime-sentinel/setup).
- Status policy used for every gmod addons task: `asserted` = the clause's central obligation is checked by an executed, discriminating assertion (unchecked sub-obligations are listed in the clause note); `weak` = the evidence is only implicit/proxy (sandbox load, truthiness, a vacuous or nominal case, a hand-called stored callback where the clause demands the native event), or more than half of the clause's enumerated obligations are never exercised; `unasserted` = no case measures it.
- Case-to-clause links start from `contract-traceability.json`; links the cited case does not exercise were dropped or re-pointed and acceptance clauses were added. Every change is recorded in the case `note`.

## Preserved contracts and compat-negative

None. The starter is empty (`task.json` + `TASK.md` only): `starter.execution.json` observes just `check:required-files` and `check:lua-syntax`, both failing, and no suite case runs (runner error, 0 cases). No case probes ordinary host behavior that passes on the empty starter, so there is no `preserved` case and no compat-negative control. The task enters general completion only.

## Controls

| control | kind | admissible | score | failed cases | unobserved | server phases (raw record) |
| --- | --- | --- | --- | --- | --- | --- |
| starter | starter | yes | 0.0 | both static checks | all 29 suite cases (nothing to run) | A: no result; B not run |
| reference | reference | yes | 100.0 | - | - | A: pass; B ran |
| alternative-second-reference | alternative | yes | 100.0 | - | - | A: pass; B ran |
| alternative-strict-reading | alternative | NO | 46.9 | hidden:first registration increments quota<br>hidden:remove retries release quota exactly once<br>hidden:save load round trip preserves request idempotency<br>integration:adapter installs required hooks and timer<br>integration:all modification entry points reject non-owner<br>integration:entity removal releases once and revision blocks EntIndex reuse<br>integration:disconnect cleanup and reconnect use real hooks | all 5 server cases | A: persistence failed; B not run |
| quota-not-enforced-oracle | target-negative | yes | 80.19 | hidden:third prop is rejected without replacing state<br>integration:quota rejects and removes third prop<br>server:quota<br>server:lifecycle | - | A: pass; B ran |
| non-public-options-accepted | target-negative | yes | 97.86 | hidden:only the exact public two prop five second options are accepted | - | A: pass; B ran |
| client-owner-trusted | target-negative | yes | 79.0 | integration:all modification entry points reject non-owner<br>integration:client owner payload cannot override server player<br>integration:quota rejects and removes third prop<br>server:authority<br>server:quota | - | A: pass; B ran |
| disconnect-cleans-immediately | target-negative | yes | 90.33 | integration:disconnect cleanup and reconnect use real hooks<br>server:cleanup | - | A: pass; B ran |
| shutdown-leaks-timer | target-negative | yes | 87.0 | lifecycle:shutdown removes hooks and timer<br>server:cleanup | - | A: pass; B ran |

Controls whose run is incomplete are not reused by the tool and were therefore executed twice; both executions gave the same score. A control marked NO is an intentional strict-reading alternative (see its section), not an unfinished control.

### alternative-second-reference

Copy of `private/tasks/<task>/references/table-registry` (the Harbor oracle installs `array-registry`). The core keeps entities, latest revisions, pending cleanups and requests in keyed tables instead of the oracle's scanned arrays; `server.lua` is byte-identical in both references, so the structural difference is confined to the core. Resolves with every case passing. Caveat: both references were authored with the private suite and share every undisclosed convention (hook prefix, success codes, entity marker).

### alternative-strict-reading

The second reference with four changes that the public exam permits: success codes `registered`/`removed` replaced by `ok`; hook prefix and timer name changed to `rhenium_prop_registry...`; `Server.HookPrefix`/`Server.TimerName` no longer exported; no `RheniumBenchmarkEntity*` fields written on entities. Kept as the honest strict-reading alternative: it is REJECTED (46.9, incomplete). The three hidden failures come from the success codes, the four integration failures from the hook/timer lookup, and Phase A fails on the literal `registered` comparison, so Phase B never runs and all server cases are unobserved. This is evidence of over-constraint (see `known_issues` in the clause map), not of a defective control. The passing alternative is alternative-second-reference.

### quota-not-enforced-oracle

Reference + `if false and ...` on the quota test in `Registry:register`. Port of pack mutation `quota-not-enforced`, whose text exists only in table-registry. Kills the hidden, integration and Phase B quota cases; `server:lifecycle` also fails because owner A, no longer limited, holds one more prop than the EntityRemoved count assertion expects. All four are target cases.

### non-public-options-accepted

Pack mutation: `Registry.new` accepts any numeric max_props/cleanup_delay. Kills exactly the named hidden case and nothing else (single-layer kill).

### client-owner-trusted

Pack mutation: HandleDeleteRequest skips the ownership check when a client owner argument is present. Kills the named integration case, the preceding entry-point case (same forged call) and `server:authority`. It also fails `integration:quota rejects and removes third prop` and `server:quota`: the forged delete really removes A's first prop, so the later third registration is within quota. This is state cascading between sequential cases, all inside the target set.

### disconnect-cleans-immediately

Pack mutation: PlayerDisconnected advances the core by five seconds at once. Kills the stub disconnect case and `server:cleanup` (real Kick).

### shutdown-leaks-timer

Pack lifecycle mutation: Shutdown keeps the repeating timer. Behavior is otherwise intact: all 14 hidden and 9 integration cases pass; it fails `lifecycle:shutdown removes hooks and timer` and `server:cleanup` (`timer.Exists` after Shutdown) only.

## Exclusion recommendations

- Exclude `T1-SCOPE-01` from clause-level scoring (scope disclaimer, unasserted).
- Treat `T1-GOAL-02`, `T1-SCOPE-02`, `T1-DATA-02`, `T1-ERR-02`, `T1-NATIVE-03` as weak: a pass says little about them.
- Task-level: keep, but results must be read with the over-constraints in mind. An agent that follows the exam and picks its own hook names or success codes scores like alternative-strict-reading (46.9) without violating any public clause. If the study needs target-set failures to mean "requested behavior missing", the affected cases are: hidden first-registration, remove-retries, save-load; integration installs-hooks, entry-points, entity-removal, disconnect-cleanup; lifecycle; and every server case.

## Not run / limits

- 10 of the 14 pack mutations were not run as written. Four of them (`register-not-deduplicated`, `remove-repeats`, `quota-not-enforced`, `malformed-state-shape-accepted`) do not apply to the oracle reference text; `quota-not-enforced` was ported.
- No Windows/native-runner evidence; everything ran in the local Linux verifier image.
