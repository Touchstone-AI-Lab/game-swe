# rimworld/core/adaptive-storage-slot-limit-restore — E0 notes

Repair task over Adaptive Storage's `ThingClass.PostInitialize` slot-limit transition (fixed native 1.6 descendant with the historical regression reconstructed; mixed MIT/MPL dependencies, see `validation/provenance.md`).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 16 cases: 11 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 2 `target` (1 preserved case marked `overlap`).
- Weak clauses: req-7 and delivery (see the clause notes).
- `unlimited-sentinel-preserved` is a behavior case (an already-unlimited storage keeps `int.MaxValue`), not a runtime sentinel; the E0 draft guessed otherwise from its name.
- Roles come from the 2026-10-30 E0 baseline on the real game: the unchanged starter fails only saved-unlimited-restored and setter-not-skipped, so every other behavior case is preserved.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-4d64711b8fe64d10` | score 10; fails `saved-unlimited-restored` (target), `setter-not-skipped` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-51fc62e7c161402e` | score 100; every case passes; admissible |

Recorded on 2026-10-30 with `rhenium-study e0 baseline` and checked with `e0 check-maps` and `e0 run`,
in a study directory of its own on the Lab host. The task's own acceptance controls (three reference
runs, base, independent no-op, nine behavioral and five fixture mutations) are recorded in
`private/harbor/adaptive-storage-slot-limit-restore/validation/controls.json`.
