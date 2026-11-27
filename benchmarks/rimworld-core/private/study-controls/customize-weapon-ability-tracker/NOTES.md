# rimworld/core/customize-weapon-ability-tracker — E0 notes

Repair task over Customize Weapon's CompAbilityProvider (MIT, realloon/CustomizeWeapon).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 19 cases: 12 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 4 `target` (2 marked `overlap`).
- Weak clauses: delivery (see the clause notes).

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-b768928ac41a466c` | score 10; fails `duplicate-props-deduplicated` (target), `holder-update-adds-ability` (target), `managed-ability-added` (target), `missing-tracker-created` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-64c0c12d6b0349dc` | score 100; every case passes; admissible |
| `target-negative-tracker-never-created` | target-negative | reference without lazy tracker creation | `run-95b8bbc3829243f3` | score 10; fails `duplicate-props-deduplicated` (target), `holder-update-adds-ability` (target), `managed-ability-added` (target), `missing-tracker-created` (target); admissible |
| `compat-negative-tracker-created-eagerly` | compat-negative | starter whose tracker lookup always creates a tracker, even with nothing to manage | `run-3680442d2935473b` | score 10; fails `empty-management-no-tracker` (preserved); admissible |
| `alternative-a` | alternative | own EnsureAbilityTracker used only when SyncAbilities has something to manage | `run-a8e80ec064b440f4` | score 100; every case passes; admissible |

Recorded on 2026-09-24 with `rhenium-study e0 run`.
