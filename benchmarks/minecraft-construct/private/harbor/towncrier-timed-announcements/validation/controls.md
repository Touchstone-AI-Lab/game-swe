> Historical validation for pack version 1.0.0 (2026-09-24).

# Acceptance record: towncrier-timed-announcements

Real Paper 1.21.11 build 132 server, runtime `minecraft/paper-1.21.11-132-construct` prepared with
`rhenium runtime prepare`, every control evaluated through the Hub with
`rhenium run minecraft/construct/towncrier-timed-announcements <submission>` (offline Maven build, `--network=none`).

| Control | Submission | Run | Score | Complete | Failed cases |
| --- | --- | --- | --- | --- | --- |
| reference-1 | skeleton + `solution/after` | `run-11e7d194cda9457e` | 100.0 | True | none |
| reference-2 | skeleton + `solution/after` | `run-16c770c34b3841fc` | 100.0 | True | none |
| reference-3 | skeleton + `solution/after` | `run-ded44f5e900541f3` | 100.0 | True | none |
| starter | the unchanged skeleton (`nop`) | `run-eb6378d94e914b14` | 10.0 | True | 19 of 20 (every case but the sentinel) |
| target-negative | reference + the study-controls target-negative patch | `run-5cf00fe132114d28` | 10.0 | True | `interval changes the period and is saved` |
| alternative | skeleton + the study-controls alternative tree | `run-094d05592dbc4361` | 100.0 | True | none |

## Pack 1.2.0 authoring change (2026-09-26)

The standalone `pause preserves the remaining delay without disturbing other groups` server case was removed at the benchmark author's direction to lower this task's difficulty. The task and reference implementation remain unchanged; the remaining 20 cases still exercise group timers and pause/resume. Catalog, Harbor manifest, task version, clause map, and public coverage summary were synchronized.

| Control | Run | Outcome |
| --- | --- | --- |
| reference (`solution/after`) | `run-c4d9feb64ef24e74` | Paper 1.21.11 build 132; 20/20 remaining real-server cases passed; offline Maven build passed; 100/100 |
| NOP (unchanged skeleton) | `run-e5042061590747c6` | Paper 1.21.11 build 132; 1/20 passed (sentinel only), 19 failed; complete negative control |

The task verifier image was rebuilt from the local cache with networking disabled. Its suite and `task.json` contain the same 20 case names. `git diff --check` and catalog/manifest/TOML case-count consistency passed.
