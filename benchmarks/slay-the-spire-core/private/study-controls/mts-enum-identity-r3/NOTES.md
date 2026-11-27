# slay-the-spire/core/mts-enum-identity-r3 — E0 notes

Enum identity repair task over ModTheSpire, run in the real game under ModTheSpire on the Steam-prepared native
runtime; it replaces the r2 JVM probe. The evaluator reports each private assertion as `case:<id>` (from
`runtime.caseOutcomes`) plus the static `check:submission-shape` gate.

## Roles

- 16 cases: 5 `preserved`, 1 `static`, 10 `target`.
- `check:native-engine` is left out: it is the evaluator's all-or-nothing verdict over the same per-case outcomes, so mapping it would count a preserved-case failure as a target failure.
- Roles come from the 2026-11-02 E0 baseline on the real game: a case the unchanged starter already passes is preserved, every other case is a target. Each case cites the exam paragraph of its private group (aliases, queries, dispatch; controls are preserved).

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-9929f6f503ce456d` | score 10; fails `alias-existing` (target), `alias-new` (target), `game-color` (target), `late-switch` (target), `switch-add` (target), `switch-delete` (target), `warm-add` (target), `warm-delete` (target), `warm-replace` (target), `warm-undo` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-a6889e2dc4f24ea7` | score 100; every case passes; admissible |

Recorded on 2026-11-02 with `rhenium-study e0 baseline` and checked with `e0 check-maps` and `e0 run`, in a
study directory of its own on the Lab host. The authoring controls (alternative and partial repairs) are in
`validation/native-engine/mts-enum-identity-r3/`.
