# mindustry/construct/item-reservation-ledger: clause map provenance

Drafted on 2026-09-24 by `rhenium-study e0 draft-maps` from the recorded
starter and reference baselines below, then checked by the maintaining AI agent
(not independently human-reviewed). A case is
`target` when it fails on the unchanged starter and passes on the reference,
`preserved` when it already passes on the starter, `runtime-sentinel` when it only
proves the engine loaded the submission, and `static` for delivery gates.

This task's cases carry no report labels, so every target case is linked to one
`request` clause (the exam body) and every preserved case to one `preserve` clause.
The roles are exact; the clause-level split is coarse.

Cases: {'static': 1, 'target': 1}.

| control | run | date | score | complete | passed |
| --- | --- | --- | --- | --- | --- |
| starter | run-d48efe8c1e8f42c1 | 2026-09-24 | 0.0 | False | False |
| reference | run-816c662cdd064173 | 2026-09-24 | 100.0 | True | True |

No target-negative, compat-negative or alternative control has been authored for
this task yet, so E0 can record its baseline but cannot admit it.

The restored construct evaluator reports only an aggregate live-server verdict
(`check:private-headless-verifier`), no per-case outcomes, so the whole request is one
target case here and case-level analysis is not possible for this pack.
