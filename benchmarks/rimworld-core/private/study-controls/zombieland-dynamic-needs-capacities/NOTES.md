# rimworld/core/zombieland-dynamic-needs-capacities — E0 notes

Repair task over a reproducible Zombieland source slice (MIT, pardeike/Zombieland).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 20 cases: 10 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 7 `target` (6 marked `overlap`).
- Weak clauses: delivery (see the clause notes).
- need-max-two formats its result with "0", so the starter's 0.5 and the required 1.0 both render as "1"; the case cannot detect the defect.
- food-benefit-preserved and rest-benefit-preserved use a need with MaxLevel 2, so despite their names they fail on the starter and are target evidence.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-7e2800c9188f4d99` | score 10; fails `food-benefit-preserved` (target), `infected-capacity-above-one` (target), `need-max-change-observed` (target), `need-max-fractional` (target), `rest-benefit-preserved` (target), `symbiant-capacity-above-one` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-77f93935c6974d9a` | score 100; every case passes; admissible |
| `target-negative-capacity-pinned-to-one` | target-negative | need maxima fixed, but protected capacities are still pinned to exactly one | `run-27f8c501152843fa` | score 10; fails `infected-capacity-above-one` (target), `symbiant-capacity-above-one` (target); admissible |
| `compat-negative-dead-pawns-raised` | compat-negative | reference that also raises the capacity of dead protected pawns | `run-5af59204cd5f4ff7` | score 10; fails `dead-pawn-capacity-preserved` (preserved); admissible |
| `alternative-a` | alternative | own patches: MaxLevel / 2 in the prefix, a postfix that lifts only levels below one | `run-62c6f5aa4c814c53` | score 100; every case passes; admissible |

Recorded on 2026-09-23 with `rhenium-study e0 run`.
