# slay-the-spire/core/basemod-dynamic-descriptions-r2 — E0 notes

Repair task over BaseMod's dynamic card descriptions, run in the real game under ModTheSpire on the Steam-prepared native runtime.
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 47 cases: 14 `preserved`, 1 `runtime-sentinel`, 1 `static`, 31 `target`.
- Roles come from the 2026-10-30 E0 baseline on the real game: a case the unchanged starter already passes is preserved, every other case is a target. Clauses are not yet split per exam paragraph: each target case cites the whole requested repair.

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-af92b8b5a0c3412a` | score 10; fails `cn-nested` (target), `cn-suffix` (target), `coherent-initialization` (target), `decimal-leading-zero` (target), `escaped-braces` (target), `escaped-open` (target), `escaped-pipe` (target), `fraction-operand` (target), `generated-refresh` (target), `generated-rewrite` (target), `inactive-lazy` (target), `large-operand` (target), `literal-backslash` (target), `literal-dollar` (target), `nested-card` (target), `nested-fallback` (target), `nested-repeat` (target), `nested-selected` (target), `overridden-lazy` (target), `payload-equals` (target), `raw-refresh` (target), `repeated-key` (target), `subscriber-refresh` (target), `suffix-minimum` (target), `suffix-two` (target), `suffix-width` (target), `ticking-render` (target), `unmark` (target), `zero-divisor` (target), `zero-repeat-lazy` (target), `zero-zero-divisor` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-232b97d1ef8f4f73` | score 100; every case passes; admissible |

Recorded on 2026-10-30 with `rhenium-study e0 baseline` and judged by `e0 run`, in a study directory of its own on the Lab host.
