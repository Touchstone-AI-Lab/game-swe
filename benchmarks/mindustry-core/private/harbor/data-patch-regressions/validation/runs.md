# Acceptance record: data-patch-regressions

Real Mindustry v159.7 dedicated server through `rhenium run mindustry/mindustry-core/data-patch-regressions <submission>` with the prepared `mindustry/mindustry-159.7` runtime (verifier image built from this task's `tests/`), every run with `--network=none --cap-drop=ALL --cpus=4 --memory=8g`, Linux x86_64 host with Docker. 7 frozen server cases: 3 target, 3 preserved, 1 sentinel.

| Submission | Run | Date | Score | Complete | Passed | Failed cases |
| --- | --- | --- | --- | --- | --- | --- |
| starter (`environment/mindustry`) | `run-635837b9fcfe4d59` | 2026-09-24 | 10.0 | True | False | `a server-defined item can be used by a patch`; `patching a build tower also changes the drones it builds with`; `a patch for another planet is neither applied nor listed` |
| reference #1 (starter + `solution/after`) | `run-7305d0e4ad074730` | 2026-09-24 | 100.0 | True | True | none |
| reference #2 (starter + `solution/after`) | `run-d0891aed0f734fc7` | 2026-09-24 | 100.0 | True | True | none |
| reference #3 (starter + `solution/after`) | `run-191fa39c14364ba3` | 2026-09-24 | 100.0 | True | True | none |

The starter is complete and fails exactly the 3 target cases: admissible. The reference scored 100.0, 100.0, 100.0 with identical per-case outcomes in the three runs.
