# Acceptance record: defense-and-heat-regressions

Real Mindustry v159.7 dedicated server through `rhenium run mindustry/mindustry-core/defense-and-heat-regressions <submission>` with the prepared `mindustry/mindustry-159.7` runtime (verifier image built from this task's `tests/`), every run with `--network=none --cap-drop=ALL --cpus=4 --memory=8g`, Linux x86_64 host with Docker. 9 frozen server cases: 3 target, 5 preserved, 1 sentinel.

| Submission | Run | Date | Score | Complete | Passed | Failed cases |
| --- | --- | --- | --- | --- | --- | --- |
| starter (`environment/mindustry`) | `run-8399669fde374efd` | 2026-09-24 | 10.0 | True | False | `an idle turret keeps its reload interval when it engages`; `a disabled heat redirector passes no heat`; `a shockwave tower spares bullets outside its circular range` |
| reference #1 (starter + `solution/after`) | `run-7c9ac7b5f15840e4` | 2026-09-24 | 100.0 | True | True | none |
| reference #2 (starter + `solution/after`) | `run-737ad02c36164c2e` | 2026-09-24 | 100.0 | True | True | none |
| reference #3 (starter + `solution/after`) | `run-b01415ea60a0403c` | 2026-09-24 | 100.0 | True | True | none |

The starter is complete and fails exactly the 3 target cases: admissible. The reference scored 100.0, 100.0, 100.0 with identical per-case outcomes in the three runs.
