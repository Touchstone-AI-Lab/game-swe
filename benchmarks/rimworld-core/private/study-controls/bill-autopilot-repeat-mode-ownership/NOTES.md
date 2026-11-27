# rimworld/core/bill-autopilot-repeat-mode-ownership — E0 notes

Repair task over Bill Autopilot's repeat-mode lifecycle, three files (MIT, vbardales/Rimworld-Bill-Autopilot).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 18 cases: 8 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 7 `target` (2 marked `overlap`).
- Weak clauses: req-2, delivery (see the clause notes).
- The suite reaches production code by name: AutoBillSync.IsForeignMode, Create, Remove, CaptureDrift and ShouldRetire, BillMemory.repeatModeDefName saved under the Scribe label "repeatMode", and RecipeProbe.TryShouldDoNow(table, recipe, memory, mode, target, floor, out due). The exam names none of these, so an otherwise correct fix with other names fails target cases.
- busy-bill-not-retired never makes the bill busy (the fixture map has no pawns); it observes that a non-foreign bill below target is not retired.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-31ab3141c6ff42ef` | score 10; fails `foreign-mode-recognized` (target), `foreign-mode-remembered` (target), `foreign-mode-restored` (target), `foreign-should-do-now-false` (target), `foreign-should-do-now-true` (target), `memory-roundtrip` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-2aaf48a9231d4a58` | score 100; every case passes; admissible |
| `target-negative-mode-not-saved` | target-negative | reference whose BillMemory does not save the remembered repeat mode | `run-e56cd591e8cc4022` | score 10; fails `memory-roundtrip` (target); admissible |
| `compat-negative-name-not-saved` | compat-negative | reference whose BillMemory no longer saves the bill name | `run-9a74a76eb1a342a7` | score 10; fails `bill-name-persisted` (preserved); admissible |
| `alternative-a` | alternative | own helpers (IsForeignMode, RememberedMode) and a generic attached-probe runner behind TryShouldDoNow | `run-d0db0f30ab5346f5` | score 100; every case passes; admissible |

Recorded on 2026-09-24 with `rhenium-study e0 run`.
