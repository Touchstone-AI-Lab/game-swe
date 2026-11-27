# mindustry/construct/blueprint-layout-reconciler: clause map provenance

Written on 2026-11-12 with the task by the maintaining AI agent (not independently
human-reviewed), from the starter and reference runs below. A case is `target` when it
fails on the unchanged starter and passes on the reference, and `static` for delivery
gates. The construct evaluator reports only an aggregate live-server verdict
(`check:private-headless-verifier`), no per-case outcomes, so the whole request is one
target case linked to one `request` clause, as for the other tasks of this pack.

Cases: {'static': 1, 'target': 1}.

All runs used `rhenium run mindustry/construct/blueprint-layout-reconciler --profile full`
on the Lab Linux x86_64 Docker host, from catalog 1.2.0 in an isolated Hub state
(runtime artifact `sha256:b92271763cedab187317c740c07a11fe2d6ca088f451cb64e2ee5349b9382f0f`).

| control | run | date | score | complete | passed |
| --- | --- | --- | --- | --- | --- |
| starter | run-5922eadff9ee4335 | 2026-11-12 | 0.0 | False | False |
| reference | run-b5a78722bb79481b | 2026-11-12 | 100.0 | True | True |
| target-negative-refund-sum-rounding | run-726dfdb8c1ec47db | 2026-11-12 | 10.0 | True | False |
| target-negative-placement-rows-first | run-35ccee9478d049c1 | 2026-11-12 | 10.0 | True | False |
| target-negative-place-without-footprint-check | run-c100974de95c47f6 | 2026-11-12 | 10.0 | True | False |

The three target-negative controls are the reference with one defect each. Running the
same trees through the task's verifier directly in a prepared construct image shows which
of the nine rubric cases each fails:

| control | failed cases | passed |
| --- | --- | --- |
| target-negative-refund-sum-rounding | `conflict removal and ordering`, `budget refund and deferral` | 7 of 9 |
| target-negative-placement-rows-first | `conflict removal and ordering`, `reconcile a real world region` | 7 of 9 |
| target-negative-place-without-footprint-check | `apply rejects unsafe operations` | 8 of 9 |

These runs were made with `rhenium run`, not with `rhenium-study e0`, so they are not E0
ledger records. No compat-negative or alternative control has been authored, so E0 can
record this task's baseline but cannot admit it.
