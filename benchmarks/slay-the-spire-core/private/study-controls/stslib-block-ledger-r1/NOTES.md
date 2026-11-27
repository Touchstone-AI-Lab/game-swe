# slay-the-spire/core/stslib-block-ledger-r1 — E0 notes

Repair task over StSLib's custom block accounting, run in the real game under ModTheSpire on the Steam-prepared native runtime.
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 28 cases: 6 `preserved`, 1 `runtime-sentinel`, 1 `static`, 20 `target`.
- Roles come from the 2026-10-30 E0 baseline on the real game: a case the unchanged starter already passes is preserved, every other case is a target. Clauses are not yet split per exam paragraph: each target case cites the whole requested repair.

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-c3782e83e0ce4203` | score 10; fails `monster-cap-full` (target), `monster-cap-loss` (target), `monster-cap-multiple` (target), `monster-cap-plain` (target), `monster-cross-owner` (target), `monster-nested-loss` (target), `monster-nested-specific` (target), `monster-refund` (target), `monster-zero-gain` (target), `monster-zero-specific` (target), `player-cap-full` (target), `player-cap-loss` (target), `player-cap-multiple` (target), `player-cap-plain` (target), `player-cross-owner` (target), `player-nested-loss` (target), `player-nested-specific` (target), `player-refund` (target), `player-zero-gain` (target), `player-zero-specific` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-9611b8bc26f44ad4` | score 100; every case passes; admissible |

Recorded on 2026-10-30 with `rhenium-study e0 baseline` and judged by `e0 run`, in a study directory of its own on the Lab host.
