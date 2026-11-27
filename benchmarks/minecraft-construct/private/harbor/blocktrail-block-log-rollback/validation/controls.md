> Historical validation for pack version 1.0.0 (2026-09-24).

# Acceptance record: blocktrail-block-log-rollback

Real Paper 1.21.11 build 132 server, runtime `minecraft/paper-1.21.11-132-construct` prepared with
`rhenium runtime prepare`, every control evaluated through the Hub with
`rhenium run minecraft/construct/blocktrail-block-log-rollback <submission>` (offline Maven build, `--network=none`).

| Control | Submission | Run | Score | Complete | Failed cases |
| --- | --- | --- | --- | --- | --- |
| reference-1 | skeleton + `solution/after` | `run-b4a1329d416b46e9` | 100.0 | True | none |
| reference-2 | skeleton + `solution/after` | `run-f235c3838bb547c4` | 100.0 | True | none |
| reference-3 | skeleton + `solution/after` | `run-c3be18978b1d4125` | 100.0 | True | none |
| starter | the unchanged skeleton (`nop`) | `run-ea54b5b4781f4015` | 10.0 | True | 24 of 25 (every case but the sentinel) |
| target-negative | reference + the study-controls target-negative patch | `run-6583382450494afe` | 10.0 | True | `rollback undoes changes newest first` |
| alternative | skeleton + the study-controls alternative tree | `run-cad1d4bf486947eb` | 100.0 | True | none |
