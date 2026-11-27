# Acceptance record: payload-and-save-regressions

Real Mindustry v159.7 dedicated server through `rhenium run mindustry/mindustry-core/payload-and-save-regressions <submission>` with the prepared `mindustry/mindustry-159.7` runtime (verifier image built from this task's `tests/`), every run with `--network=none --cap-drop=ALL --cpus=4 --memory=8g`, Linux x86_64 host with Docker. 10 frozen server cases: 3 target, 6 preserved, 1 sentinel.

| Submission | Run | Date | Score | Complete | Passed | Failed cases |
| --- | --- | --- | --- | --- | --- | --- |
| starter (`environment/mindustry`) | `run-49ccb04033ed457d` | 2026-09-24 | 10.0 | True | False | `a derelict payload conveyor keeps its payload through a save`; `a builder with more than a thousand queued plans survives a save`; `a unit can set down a carried derelict block near a core` |
| reference #1 (starter + `solution/after`) | `run-30e0d412410b4466` | 2026-09-24 | 100.0 | True | True | none |
| reference #2 (starter + `solution/after`) | `run-ac748f0a06fa4a67` | 2026-09-24 | 100.0 | True | True | none |
| reference #3 (starter + `solution/after`) | `run-791a22091b5d489a` | 2026-09-24 | 100.0 | True | True | none |

The starter is complete and fails exactly the 3 target cases: admissible. The reference scored 100.0, 100.0, 100.0 with identical per-case outcomes in the three runs.

`run-dac556caf0fd42bb` (the first reference run) was voided as incomplete because `docker rm` on the congested shared Docker daemon timed out after 300 s once the report had been collected; it was rerun as reference #1. The runtime now allows container removal 900 s and cleans up a container whose creation timed out.
