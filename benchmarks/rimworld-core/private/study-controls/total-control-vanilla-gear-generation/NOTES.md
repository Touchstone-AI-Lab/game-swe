# rimworld/core/total-control-vanilla-gear-generation — E0 notes

Repair task over Total Control's apparel and weapon generation patches (MIT, feldoh/TotalControl).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 19 cases: 10 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 6 `target` (4 marked `overlap`).
- Weak clauses: req-2, req-3, delivery (see the clause notes).
- tests/Harness/Verifier.cs gives the Core weapon a CompColorable for color-preserved (Core weapons are not colorable), authors a ThingStyleDef for style-preserved (Core ships none) and compares non-hit-point gear with the hit points the game gives an identical new thing (RimWorld 1.6 leaves them unset).

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-8f971105acbd42b3` | score 10; fails `apparel-low-health` (target), `apparel-min-one-hp` (target), `weapon-low-health` (target), `weapon-min-one-hp` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-584957fc2fca4668` | score 100; every case passes; admissible |
| `target-negative-no-hit-point-floor` | target-negative | reference without the one-hit-point floor | `run-1e1ad46e4c064a0b` | score 10; fails `apparel-min-one-hp` (target), `weapon-min-one-hp` (target); admissible |
| `compat-negative-hit-points-for-every-thing` | compat-negative | reference that applies the gear health range to things without hit points | `run-7628c5fa797f4234` | score 10; fails `non-hitpoint-apparel` (preserved), `non-hitpoint-weapon` (preserved); admissible |
| `alternative-a` | alternative | one shared VanillaGearFinish helper for both generators, Royalty clamp left out | `run-43e29efe45624ab6` | score 100; every case passes; admissible |

Recorded on 2026-09-24 with `rhenium-study e0 run`.
