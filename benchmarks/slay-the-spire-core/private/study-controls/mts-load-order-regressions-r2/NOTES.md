# slay-the-spire/core/mts-load-order-regressions-r2 — E0 notes

Load order repair task over ModTheSpire, run in the real game under ModTheSpire on the Steam-prepared native
runtime; it replaces r1's loader-only run. The evaluator reports each private assertion as `case:<id>` (from
`runtime.caseOutcomes`) plus the static `check:submission-shape` gate.

## Roles

- 10 cases: 5 `preserved`, 1 `static`, 4 `target`.
- Report #734 is not enforced: both circular assertions pass on the starter (validation/per-defect-matrix.md records this as the top follow-up).
- The six starter edits interact: the transposed relation alone fails five assertions, all six together fail four; two edits (the removed cycle guard and the narrowed accessor type check) are inert distractors.
- `check:native-engine` is left out: it is the evaluator's all-or-nothing verdict over the same per-case outcomes, so mapping it would count a preserved-case failure as a target failure.
- Clauses and roles carry over from `mts-load-order-regressions` (same exam and assertions); the 2026-11-02 E0 baseline on the real game observed the same starter failures.

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-faa3214e05384e89` | score 10; fails `gcb.ByRefBoxingTest.byRefWritesBackThroughAWrapperArray` (target), `gcb.LoadOrderTest.aChainOfDependenciesResolves` (target), `gcb.LoadOrderTest.aDependencyIsInitialisedBeforeItsDependent` (target), `gcb.LoadOrderTest.anEdgeIntoTheNewestModTakesEffect` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-cda6fd3e7eaf4cbd` | score 100; every case passes; admissible |

Recorded on 2026-11-02 with `rhenium-study e0 baseline` and checked with `e0 check-maps` and `e0 run`, in a
study directory of its own on the Lab host. The authoring controls (alternative and partial repairs) are in
`validation/native-engine/mts-load-order-regressions-r2/`.
