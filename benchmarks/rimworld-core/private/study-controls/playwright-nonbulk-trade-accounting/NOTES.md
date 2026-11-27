# rimworld/core/playwright-nonbulk-trade-accounting — E0 notes

Repair task over Playwright's trade patch (MIT, morerokk/Rimworld-Playwright).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 15 cases: 6 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 6 `target` (4 marked `overlap`).
- Weak clauses: delivery (see the clause notes).
- The suite reads the prefix state as a nested public struct Tradeable_ResolveTradePatches.SoldThing with fields Def and Count, and invokes methods named Prefix and Postfix; the exam names none of these.
- tests/Harness/Verifier.cs gives its fixture scenario the player-faction and surface-layer parts RimWorld 1.6 always yields first, and tests/Support.cs gives the scenario-part doubles distinct defs, so the starter's def-based filter behaves as it would in a real game.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-a3ce7c69899a415c` | score 10; fails `definition-preserved-after-resolve` (target), `empty-tradeable-not-counted` (target), `nonbulk-sale-captured` (target), `nonbulk-sale-counted` (target), `purchase-not-counted` (target), `zero-transfer-not-counted` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-e00751a7b4e44902` | score 100; every case passes; admissible |
| `target-negative-no-thing-guard` | target-negative | reference whose prefix captures sales with neither a colony nor a trader thing | `run-febdf0f4d7a84831` | score 10; fails `empty-tradeable-not-counted` (target); admissible |
| `compat-negative-factionless-trader-notified` | compat-negative | reference that notifies faction parts when the trader has no faction | `run-056c8e72c7ab4f2d` | score 10; fails `null-faction-skipped` (preserved); admissible |
| `alternative-a` | alternative | own prefix and a single type-switch loop over AllParts in the postfix | `run-c9d1484734b9437a` | score 100; every case passes; admissible |

Recorded on 2026-09-24 with `rhenium-study e0 run`.
