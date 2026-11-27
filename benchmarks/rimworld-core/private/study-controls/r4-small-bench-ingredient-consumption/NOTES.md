# rimworld/core/r4-small-bench-ingredient-consumption — E0 notes

Repair task over R⁴'s MaterialUtility (MIT, CheaterEater-RM/RRRR, upstream base and fix commits).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 17 cases: 8 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 6 `target` (4 marked `overlap`).
- Weak clauses: delivery (see the clause notes).
- Unasserted clauses: req-5.
- The exam asks for vanilla-equivalent radial placement cells, but radius-boundary-included and outside-radius-preserved fix the search at radius 6 (the upstream MaxIngredientSearchRadius). Vanilla Toils_JobTransforms.IngredientPlaceCellsInOrder walks the first 200 radial cells, which reach the item seven cells east that outside-radius-preserved expects to remain; the alternative-strict-reading-vanilla-200 control records this.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-8a61e2220042417a` | score 10; fails `duplicate-costs-aggregate` (target), `interaction-cell-origin` (target), `multiple-stacks-exact` (target), `partial-stack-preserved` (target), `radius-boundary-included` (target), `small-bench-adjacent` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-33a1f8181ed744fc` | score 100; every case passes; admissible |
| `target-negative-radius-five` | target-negative | reference whose radial search stops at radius 5 | `run-56a366a7faac464f` | score 10; fails `radius-boundary-included` (target); admissible |
| `compat-negative-impassable-not-skipped` | compat-negative | reference that also takes ingredients from impassable no-surface cells | `run-bdab0785152d4b6b` | score 10; fails `impassable-cell-skipped` (preserved); admissible |
| `compat-negative-consumes-non-items` | compat-negative | reference that also consumes non-item things of a requested def | `run-d9b3f5533b614ab5` | score 10; fails `non-item-preserved` (preserved); admissible |
| `alternative-a` | alternative | own search: DistanceToSquared-sorted stack cells, radial loop with a HashSet of checked cells, snapshot-based consumption | `run-c7b4ffefd77d4402` | score 100; every case passes; admissible |
| `alternative-strict-reading-vanilla-200` | alternative | reads vanilla-equivalent literally: the first 200 radial cells, as Toils_JobTransforms.IngredientPlaceCellsInOrder walks | `run-a146dd9889124853` | score 10; fails `outside-radius-preserved` (preserved); a valid reading the suite rejects, as recorded for strict-reading controls; `rhenium-study e0 flag` marked `case:outside-radius-preserved` `over_constrained` in `clause-map.json` |

Recorded on 2026-09-24 with `rhenium-study e0 run`.
