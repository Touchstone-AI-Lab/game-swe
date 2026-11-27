# garrys-mod/darkrp/darkrp-money-regressions: clause map provenance

Drafted on 2026-09-24 by `rhenium-study e0 draft-maps` from the recorded
starter and reference baselines below, then checked by the maintaining AI agent
(not independently human-reviewed). A case is
`target` when it fails on the unchanged starter and passes on the reference,
`preserved` when it already passes on the starter, `runtime-sentinel` when it only
proves the engine loaded the submission, and `static` for delivery gates.

Case names carry report letters; they were matched one-to-one, in order, with the
exam's report markers.

Cases: {'preserved': 1, 'runtime-sentinel': 1, 'static': 1, 'target': 7}.

| control | run | date | score | complete | passed |
| --- | --- | --- | --- | --- | --- |
| starter | run-dc26928e7231438a | 2026-09-23 | 10.0 | True | False |
| reference | run-6072a0dcd6764514 | 2026-09-23 | 100.0 | True | True |

No target-negative, compat-negative or alternative control has been authored for
this task yet, so E0 can record its baseline but cannot admit it.
