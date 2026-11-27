# rimworld/core/project-rimfactory-cultivator-environment — E0 notes

Repair task over Project RimFactory Revived's cultivator (MIT, zymex22/Project-RimFactory-Revived).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 13 cases: 6 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 4 `target` (2 marked `overlap`).
- Weak clauses: req-1, req-5, delivery (see the clause notes).
- map-temperature-not-authoritative cannot fail on the starter (tests/Harness/Verifier.cs CanPlantPrefix reads any false bool argument), so bullet 1 is weak.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-50d6552d51464c62` | score 10; fails `local-season-rejects` (target), `vacuum-boundary-rejects` (target), `vacuum-sensitive-rejects` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-27e00777aca94e8a` | score 100; every case passes; admissible |
| `target-negative-no-vacuum-check` | target-negative | reference without the local vacuum condition | `run-d422c05ccf3a4c17` | score 10; fails `vacuum-boundary-rejects` (target), `vacuum-sensitive-rejects` (target); admissible |
| `compat-negative-ignores-sow-blocker` | compat-negative | reference that drops the adjacent sow-blocker check | `run-4c158d779f5d41bb` | score 10; fails `adjacent-blocker-rejects` (preserved); admissible |
| `alternative-a` | alternative | own guard sequence with early returns per condition | `run-0e6ee92977fb4a86` | score 100; every case passes; admissible |

Recorded on 2026-09-23 with `rhenium-study e0 run`.
