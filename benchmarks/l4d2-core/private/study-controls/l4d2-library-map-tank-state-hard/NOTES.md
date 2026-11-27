# E0 notes: l4d2-library-map-tank-state-hard

Workspace layout: `/app/l4d2-competitive`; every overlay uses `root = l4d2-competitive`. Clause ids are `R<report>.<n>` for the numbered reports (anchor = report, sentence, short quote) and `Task-*` for the surrounding paragraphs.

Baseline through the operator Hub full profile (`rhenium run`, Linux x86_64 Docker host, 2026-09-24, verifier image `sha256:696134f77e37...`): unchanged starter 0/44 (`run-a8ecfb858ffd443c`, complete, score 10); reference 44/44 three times with identical case outcomes (`run-8c076b5a048b43a5`, `run-310d4046691f4fe1`, `run-b504d548f92a4f03`, score 100). These are not study-Hub records: the study Hub must be re-seeded from the operator database before `rhenium-study e0` can reproduce them, because the verifier images changed on 2026-09-24.

Overlays patch `addons/sourcemod/scripting/l4d2lib/mapinfo.sp` and `tanks.sp`. The eight
reports are task-authored contracts over the frozen upstream L4D2Lib, not reverted
upstream commits.

## Preserved contracts

None. On every starter run the map boot's server process exits a few seconds after
map load without printing any case or FINAL marker (an instrumented run with a
300-second budget showed the exit at about 4 s, so this is starter behaviour, not host
delay), and the Tank boot throws `Client index 0 is invalid`. Both boots fail closed, so all 44 cases are `F`. The maintainer NOP recorded the
same 0/44. Every behavioural case is therefore a `target` by observation.
`missing-reload-valid-baseline` and `connection-slot-reused-fixture` are `setup` cases.
There is no preserved set and no compat-negative control.

## Controls (all executed through `rhenium run`; all behaved as declared)

- `tn-syntax-validation-missing` (target-negative): the oracle that trusts `ImportFromFile` without the full-document syntax check (`validation/candidates.py` minus-syntax-validation). Observed: `run-159331ec3ae449f2`, 43/44, failing `failed-reload-keeps-image`.
- `tn-death-timer-postponed` (target-negative): the oracle whose repeated owner death deletes and restarts the pending death timer (minus-death-postponed). Observed: `run-0b45fdbfe1b74bec`, 40/44, failing `duplicate-death-once`, `handoff-cancels-death`, `new-encounter-after-death`, `new-encounter-count-reset`.
- `alternative-squared-geometry` (alternative): the pack's reference-derived alternative (squared-distance geometry with negative-radius guards, separately committed pass count). Observed: `run-c52679c991594a0b`, 44/44, failing none.

## Exclusions / remarks

- Unasserted (excluded) clauses: `R1.3` (no initial failed import), `R4.5` (medkit heuristic),
  `R8.3` (observer-triggered round reset), `Task-preserve-gpl`, `Task-no-tests-edit`.
- Admissible for target evidence; not qualified for joint compatibility (no preserved case).
