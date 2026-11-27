# terraria/core/terraria-overhaul-entity-chunk-lifetime-hard: clause map provenance

Drafted on 2026-09-25 by `rhenium-study e0 draft-maps` from the recorded
starter and reference baselines below, then checked by the maintaining AI agent
(not independently human-reviewed). A case is
`target` when it fails on the unchanged starter and passes on the reference,
`preserved` when it already passes on the starter, `runtime-sentinel` when it only
proves the engine loaded the submission, and `static` for delivery gates.

Case names carry report letters; they were matched one-to-one, in order, with the
exam's report markers.

Cases: {'preserved': 25, 'static': 1, 'target': 56}.

| control | run | date | score | complete | passed |
| --- | --- | --- | --- | --- | --- |
| starter | run-f4dd35750e9e4766 | 2026-09-25 | 10.0 | True | False |
| reference | run-b46c20b40e034f32 | 2026-09-25 | 100.0 | True | True |

No target-negative, compat-negative or alternative control has been authored for
this task yet, so E0 can record its baseline but cannot admit it.
