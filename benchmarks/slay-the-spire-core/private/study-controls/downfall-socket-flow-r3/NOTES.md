# slay-the-spire/core/downfall-socket-flow-r3 — E0 notes

Repair task over Downfall's socket selection flow (r3 verifier baseline), run in the real game under ModTheSpire on the Steam-prepared native runtime.
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 14 cases: 4 `preserved`, 2 `runtime-sentinel`, 1 `static`, 7 `target`.
- Roles come from the 2026-10-30 E0 baseline on the real game: a case the unchanged starter already passes is preserved, every other case is a target. Clauses are not yet split per exam paragraph: each target case cites the whole requested repair.

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-66d4c5b3dab44a35` | score 10; fails `back-reselect-escape` (target), `back-reselect-mouse` (target), `cancel-gem-smith-escape` (target), `cancel-gem-smith-guardian` (target), `cancel-gem-smith-mouse` (target), `cancel-socket-escape` (target), `cancel-socket-mouse` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-dd0747649bb24d42` | score 100; every case passes; admissible |

Recorded on 2026-10-30 with `rhenium-study e0 baseline` and judged by `e0 run`, in a study directory of its own on the Lab host.
