# garrys-mod/darkrp/darkrp-registration-regressions: clause map provenance

Drafted on 2026-09-24 by `rhenium-study e0 draft-maps` from the recorded
starter and reference baselines below, then checked by the maintaining AI agent
(not independently human-reviewed). A case is
`target` when it fails on the unchanged starter and passes on the reference,
`preserved` when it already passes on the starter, `runtime-sentinel` when it only
proves the engine loaded the submission, and `static` for delivery gates.

Case names carry report letters; they were matched one-to-one, in order, with the
exam's report markers.

Cases: {'preserved': 1, 'runtime-sentinel': 1, 'static': 1, 'target': 8}.

| control | run | date | score | complete | passed |
| --- | --- | --- | --- | --- | --- |
| starter | run-805339aa3b344d75 | 2026-09-23 | 10.0 | True | False |
| reference | run-3a7b4c102d774572 | 2026-09-23 | 100.0 | True | True |

No target-negative, compat-negative or alternative control has been authored for
this task yet, so E0 can record its baseline but cannot admit it.
