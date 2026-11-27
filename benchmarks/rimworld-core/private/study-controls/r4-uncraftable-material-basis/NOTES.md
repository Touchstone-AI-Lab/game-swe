# rimworld/core/r4-uncraftable-material-basis — E0 notes

Repair task over two C# files of R⁴ (MIT, CheaterEater-RM/RRRR, v1.47 base, v1.48 fix). Legacy private protocol v2 with 38 cases.
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 39 cases: 5 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 31 `target`.
- Weak clauses: delivery (see the clause notes).
- Unasserted clauses: req-7.
- tests/Harness/Verifier.cs lifts Core's MarketValue floor (minValue 0) and round-to-five rule and prices Plasteel at 8 for the case loop, because the authored negative and float32-boundary fixtures cannot exist on unmodified Core data; expected results are unchanged.
- Scalars (marketValue, quotient and so on) are recorded but not graded; only facts and outputs decide a case.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-70bd2683f585425d` | score 10; fails `animal-basis` (target), `archotech-basis` (target), `authored-extension-used` (target), `clean-default` (target), `clean-ignores-repair-settings` (target), `clean-settings` (target), `definition-market-value` (target), `empty-cost-list-fallback` (target), `empty-extension-materials-fallback` (target), `industrial-components-stay-two` (target), `medieval-basis` (target), `negative-market-value` (target), `neolithic-basis` (target), `null-cost-list-fallback` (target), `null-extension-materials-fallback` (target), `positive-minimum-bulk` (target), `public-resolver-contract` (target), `repair-default` (target), `repair-ignores-clean-settings` (target), `repair-settings` (target), `round-even-above` (target), `round-even-below` (target), `round-even-half` (target), `round-odd-above` (target), `round-odd-below` (target), `round-odd-half` (target), `spacer-basis` (target), `spacer-components-stay-two` (target), `ultra-basis` (target), `undefined-basis` (target), `zero-market-value` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-179dcef937284270` | score 100; every case passes; admissible |
| `target-negative-undefined-tech-level` | target-negative | reference that treats TechLevel.Undefined as below Industrial (Steel, no components) | `run-e74071d9090a4bf1` | score 10; fails `undefined-basis` (target); admissible |
| `compat-negative-extension-first` | compat-negative | reference that prefers an authored R4MaterialCostExtension over a real crafting cost | `run-9c2640274c0a4d16` | score 10; fails `craftable-beats-extension` (preserved); admissible |
| `alternative-a` | alternative | own resolver: NullOrEmpty precedence checks, switch over the normalised tech level, explicit float32 locals | `run-7036f87bb932434c` | score 100; every case passes; admissible |

Recorded on 2026-09-23 with `rhenium-study e0 run`.
