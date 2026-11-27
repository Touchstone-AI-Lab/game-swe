> Historical validation for pack version 1.0.0 (2026-09-24).

# Acceptance record: wardstone-region-protection

Real Paper 1.21.11 build 132 server, runtime `minecraft/paper-1.21.11-132-construct` prepared with
`rhenium runtime prepare`, every control evaluated through the Hub with
`rhenium run minecraft/construct/wardstone-region-protection <submission>` (offline Maven build, `--network=none`).

| Control | Submission | Run | Score | Complete | Failed cases |
| --- | --- | --- | --- | --- | --- |
| reference-1 | skeleton + `solution/after` | `run-bc0bf4fe61da47a3` | 100.0 | True | none |
| reference-2 | skeleton + `solution/after` | `run-657401905bb84742` | 100.0 | True | none |
| reference-3 | skeleton + `solution/after` | `run-cd2dc8dd935547b3` | 100.0 | True | none |
| starter | the unchanged skeleton (`nop`) | `run-a1ecd21817834656` | 10.0 | True | 24 of 25 (every case but the sentinel) |
| target-negative | reference + the study-controls target-negative patch | `run-b40314c50c0a48ca` | 10.0 | True | `deny wins between equal priorities and the first name decides` |
| alternative | skeleton + the study-controls alternative tree | `run-8898ea1f438a4b6b` | 100.0 | True | none |
