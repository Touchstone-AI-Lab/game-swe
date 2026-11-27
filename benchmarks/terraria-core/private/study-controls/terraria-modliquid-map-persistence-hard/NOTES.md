# terraria/core/terraria-modliquid-map-persistence-hard: clause map provenance

Drafted on 2026-09-25 by `rhenium-study e0 draft-maps` from the recorded
starter and reference baselines below, then checked by the maintaining AI agent
(not independently human-reviewed). A case is
`target` when it fails on the unchanged starter and passes on the reference,
`preserved` when it already passes on the starter, `runtime-sentinel` when it only
proves the engine loaded the submission, and `static` for delivery gates.

Case names carry report letters; they were matched one-to-one, in order, with the
exam's report markers.

Cases: {'runtime-sentinel': 1, 'static': 1, 'target': 105}.

| control | run | date | score | complete | passed |
| --- | --- | --- | --- | --- | --- |
| starter | run-bab1c24a117d4e1d | 2026-09-25 | 10.0 | False | False |
| reference | run-da6a4b6daee44b3b | 2026-09-25 | 100.0 | True | True |

No target-negative, compat-negative or alternative control has been authored for
this task yet, so E0 can record its baseline but cannot admit it.
