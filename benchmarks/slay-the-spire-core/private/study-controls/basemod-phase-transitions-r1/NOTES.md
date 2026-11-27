# slay-the-spire/core/basemod-phase-transitions-r1 — E0 notes

Repair task over BaseMod's phase transitions, run in the real game under ModTheSpire on the Steam-prepared native runtime.
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 33 cases: 12 `preserved`, 1 `runtime-sentinel`, 1 `static`, 19 `target`.
- Roles come from the 2026-10-30 E0 baseline on the real game: a case the unchanged starter already passes is preserved, every other case is a target. Clauses are not yet split per exam paragraph: each target case cites the whole requested repair.

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-b02bd6ae9327478d` | score 10; fails `chain` (target), `enter-direct` (target), `enter-key` (target), `enter-throw-true` (target), `followup-key-clear` (target), `followup-key-phase-clear` (target), `followup-phase-clear` (target), `followup-phase-key-clear` (target), `hide-direct` (target), `hide-key` (target), `hide-throw-true` (target), `invalid-direct` (target), `invalid-key` (target), `latest-request` (target), `reopen-cycle` (target), `reopen-true-false` (target), `reset-direct` (target), `reset-key` (target), `reset-throw-true` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-fad4b3e31d0d4590` | score 100; every case passes; admissible |

Recorded on 2026-10-30 with `rhenium-study e0 baseline` and judged by `e0 run`, in a study directory of its own on the Lab host.
