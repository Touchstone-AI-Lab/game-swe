# slay-the-spire/core/stslib-icon-layout-r1 — E0 notes

Repair task over StSLib's card icon layout, run in the real game under ModTheSpire on the Steam-prepared native runtime.
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 44 cases: 18 `preserved`, 1 `runtime-sentinel`, 1 `static`, 24 `target`.
- Roles come from the 2026-10-30 E0 baseline on the real game: a case the unchanged starter already passes is preserved, every other case is a target. Clauses are not yet split per exam paragraph: each target case cites the whole requested repair.

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-03ca6cb454994f20` | score 10; fails `cn-height-colored` (target), `cn-height-five` (target), `cn-height-lowercase` (target), `cn-height-mixed` (target), `cn-height-orb` (target), `cn-height-three` (target), `cn-wrap-five` (target), `cn-wrap-lowercase` (target), `cn-wrap-newline` (target), `cn-wrap-three` (target), `en-height-five` (target), `en-height-newline` (target), `en-height-spacing` (target), `en-height-three` (target), `header-lowercase` (target), `header-multiple` (target), `header-one` (target), `width-after-newline` (target), `width-cn` (target), `width-lowercase` (target), `width-narrow` (target), `width-one` (target), `width-short-code` (target), `width-wide` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-328d0eccd1c94f45` | score 100; every case passes; admissible |

Recorded on 2026-10-30 with `rhenium-study e0 baseline` and judged by `e0 run`, in a study directory of its own on the Lab host.
