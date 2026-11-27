# stardew-valley/core/stardew-automate-output-count-drift: clause map provenance

Drafted on 2026-09-24 by `rhenium-study e0 draft-maps` from the recorded
starter and reference baselines below, then checked by the maintaining AI agent
(not independently human-reviewed). A case is
`target` when it fails on the unchanged starter and passes on the reference,
`preserved` when it already passes on the starter, `runtime-sentinel` when it only
proves the engine loaded the submission, and `static` for delivery gates.

This task's cases carry no report labels, so every target case is linked to one
`request` clause (the exam body) and every preserved case to one `preserve` clause.
The roles are exact; the clause-level split is coarse.

Cases: {'runtime-sentinel': 2, 'setup': 1, 'static': 1, 'target': 3}.

| control | run | date | score | complete | passed |
| --- | --- | --- | --- | --- | --- |
| starter | run-951833bffd4d49c8 | 2026-09-24 | 10.0 | True | False |
| reference | run-ebdb20d9e4ea41fd | 2026-09-24 | 100.0 | True | True |

No target-negative, compat-negative or alternative control has been authored for
this task yet, so E0 can record its baseline but cannot admit it.
