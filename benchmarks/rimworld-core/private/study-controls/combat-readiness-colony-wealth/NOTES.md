# rimworld/core/combat-readiness-colony-wealth — E0 notes

Repair task over Combat Readiness Check's storyteller wealth prefix (MIT, faithful RimWorld 1.6 reconstruction of the upstream base).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 17 cases: 3 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 11 `target` (2 marked `overlap`).
- Weak clauses: delivery (see the clause notes).
- Every percentage case also fails on the starter through the points curve (bullet 4), so bullet 5 has no case that isolates the percentage arithmetic.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-897aca78f1814eb8` | score 10; fails `above-full-percentage-preserved` (target), `armoury-wealth-stays-raw` (target), `building-percentage-stays-raw` (target), `fixed-wealth-passes-through` (target), `fixed-wealth-skips-armoury` (target), `fractional-building-percentage` (target), `full-building-percentage` (target), `nonhome-map-passes-through` (target), `wealth-components-add` (target), `zero-building-percentage` (target), `zero-components-remain-zero` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-87833b19b94b4421` | score 100; every case passes; admissible |
| `target-negative-fixed-wealth-overridden` | target-negative | reference that still overrides the getter in fixed wealth mode | `run-333dd904772c4fb4` | score 10; fails `fixed-wealth-passes-through` (target), `fixed-wealth-skips-armoury` (target); admissible |
| `compat-negative-armoury-queried-twice` | compat-negative | reference that asks the armoury for its points twice | `run-554dcc19a88a4c8f` | score 10; fails `home-map-queries-armoury-once` (preserved); admissible |
| `alternative-a` | alternative | own prefix: one combined pass-through condition, raw armoury plus building share | `run-d464d43204c84098` | score 100; every case passes; admissible |

Recorded on 2026-09-23, 2026-09-24 with `rhenium-study e0 run`.
