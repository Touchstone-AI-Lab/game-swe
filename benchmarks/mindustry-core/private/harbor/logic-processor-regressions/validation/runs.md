# Acceptance record: logic-processor-regressions

Real Mindustry v159.7 dedicated server through `rhenium run mindustry/mindustry-core/logic-processor-regressions <submission>` with the prepared `mindustry/mindustry-159.7` runtime (verifier image built from this task's `tests/`), every run with `--network=none --cap-drop=ALL --cpus=4 --memory=8g`, Linux x86_64 host with Docker. 11 frozen server cases: 4 target, 6 preserved, 1 sentinel.

| Submission | Run | Date | Score | Complete | Passed | Failed cases |
| --- | --- | --- | --- | --- | --- | --- |
| starter (`environment/mindustry`) | `run-2964971c3042486d` | 2026-09-24 | 10.0 | True | False | `sensor of an unsupported property yields null`; `format fills a placeholder when the print buffer is full`; `a replaced linked block is reachable under its new name`; `a world processor holding query results can be saved` |
| reference #1 (starter + `solution/after`) | `run-1c5b0ca15bd84dbe` | 2026-09-24 | 100.0 | True | True | none |
| reference #2 (starter + `solution/after`) | `run-8be5ba344cd2405f` | 2026-09-24 | 100.0 | True | True | none |
| reference #3 (starter + `solution/after`) | `run-5028077495b84b04` | 2026-09-24 | 100.0 | True | True | none |

The starter is complete and fails exactly the 4 target cases: admissible. The reference scored 100.0, 100.0, 100.0 with identical per-case outcomes in the three runs.

`run-d81560c186d74eea` (the first reference run) was voided as incomplete because `docker create` on the congested shared Docker daemon timed out after 300 s; it was rerun as reference #1.
