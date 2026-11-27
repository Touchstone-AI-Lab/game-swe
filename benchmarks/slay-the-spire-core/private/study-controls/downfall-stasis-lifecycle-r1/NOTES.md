# slay-the-spire/core/downfall-stasis-lifecycle-r1 — E0 notes

Repair task over Downfall's Stasis lifecycle, run in the real game under ModTheSpire on the Steam-prepared native runtime.
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 39 cases: 18 `preserved`, 1 `runtime-sentinel`, 1 `static`, 19 `target`.
- Roles come from the 2026-10-30 E0 baseline on the real game: a case the unchanged starter already passes is preserved, every other case is a target. Clauses are not yet split per exam paragraph: each target case cites the whole requested repair.

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-6ee27d5b1bdc4fc7` | score 10; fails `generated-existing` (target), `generated-mixed` (target), `generated-overflow` (target), `native-dualcast-hook` (target), `native-dualcast-volatile` (target), `native-recursion-hook` (target), `native-recursion-normal` (target), `native-recursion-upgraded` (target), `native-recursion-volatile` (target), `placement-already-held` (target), `placement-duplicate` (target), `placement-moved` (target), `placement-moved-retained` (target), `placement-moved-unretained` (target), `random-zero` (target), `return-queued-twice` (target), `stale-return` (target), `stale-volatile` (target), `volatile-queued-twice` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-7b3d11b65c544b8b` | score 100; every case passes; admissible |

Recorded on 2026-10-30 with `rhenium-study e0 baseline` and judged by `e0 run`, in a study directory of its own on the Lab host.
