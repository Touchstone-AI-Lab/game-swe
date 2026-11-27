# terraria/core/terraria-calamity-overhaul-time-replication-hard: clause map provenance

Drafted on 2026-09-25 by `rhenium-study e0 draft-maps` from the recorded
starter and reference baselines below, then checked by the maintaining AI agent
(not independently human-reviewed). A case is
`target` when it fails on the unchanged starter and passes on the reference,
`preserved` when it already passes on the starter, `runtime-sentinel` when it only
proves the engine loaded the submission, and `static` for delivery gates.

Case names carry report letters; they were matched one-to-one, in order, with the
exam's report markers.

Cases: {'preserved': 35, 'runtime-sentinel': 1, 'static': 1, 'target': 45}.

| control | run | date | score | complete | passed |
| --- | --- | --- | --- | --- | --- |
| starter | run-c2d133a5b13f41b0 | 2026-09-25 | 10.0 | True | False |
| reference | run-a7550bf5d1db479f | 2026-09-25 | 100.0 | True | True |

No target-negative, compat-negative or alternative control has been authored for
this task yet, so E0 can record its baseline but cannot admit it.
