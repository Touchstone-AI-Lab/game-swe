# Acceptance record: server-console-regressions

Real Mindustry v159.7 dedicated server through `rhenium run mindustry/mindustry-core/server-console-regressions <submission>` with the prepared `mindustry/mindustry-159.7` runtime (verifier image built from this task's `tests/`), every run with `--network=none --cap-drop=ALL --cpus=4 --memory=8g`, Linux x86_64 host with Docker. 10 frozen server cases: 4 target, 5 preserved, 1 sentinel.

| Submission | Run | Date | Score | Complete | Passed | Failed cases |
| --- | --- | --- | --- | --- | --- | --- |
| starter (`environment/mindustry`) | `run-ae147d1991044e25` | 2026-09-24 | 10.0 | True | False | `pause on and pause off set the requested state`; `host without a map while shuffling is off keeps the console working`; `pardon lets a kicked player connect again`; `player records survive a server restart` |
| reference #1 (starter + `solution/after`) | `run-44e5500cf7b143c8` | 2026-09-24 | 100.0 | True | True | none |
| reference #2 (starter + `solution/after`) | `run-071586d83e6f4772` | 2026-09-24 | 100.0 | True | True | none |
| reference #3 (starter + `solution/after`) | `run-99580f0240cc44b1` | 2026-09-24 | 100.0 | True | True | none |

The starter is complete and fails exactly the 4 target cases: admissible. The reference scored 100.0, 100.0, 100.0 with identical per-case outcomes in the three runs.
