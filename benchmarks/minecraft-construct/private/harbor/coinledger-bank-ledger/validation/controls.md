> Historical validation for pack version 1.0.0 (2026-09-24).

# Acceptance record: coinledger-bank-ledger

Real Paper 1.21.11 build 132 server, runtime `minecraft/paper-1.21.11-132-construct` prepared with
`rhenium runtime prepare`, every control evaluated through the Hub with
`rhenium run minecraft/construct/coinledger-bank-ledger <submission>` (offline Maven build, `--network=none`).

| Control | Submission | Run | Score | Complete | Failed cases |
| --- | --- | --- | --- | --- | --- |
| reference-1 | skeleton + `solution/after` | `run-603fdc49edbc446a` | 100.0 | True | none |
| reference-2 | skeleton + `solution/after` | `run-dc9244c5107c4082` | 100.0 | True | none |
| reference-3 | skeleton + `solution/after` | `run-5032a29d06674b18` | 100.0 | True | none |
| starter | the unchanged skeleton (`nop`) | `run-f4acc4ca786247df` | 10.0 | True | 27 of 28 (every case but the sentinel) |
| target-negative | reference + the study-controls target-negative patch | `run-fda967d14b2546b6` | 10.0 | True | `fees are rounded down to the cent` |
| alternative | skeleton + the study-controls alternative tree | `run-98e915c73a624770` | 100.0 | True | none |
