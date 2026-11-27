# slay-the-spire/core/mts-mod-identity-regressions-r2 — E0 notes

Mod identity repair task over ModTheSpire, run in the real game under ModTheSpire on the Steam-prepared native
runtime; it replaces r1's loader-only run. The evaluator reports each private assertion as `case:<id>` (from
`runtime.caseOutcomes`) plus the static `check:submission-shape` gate.

## Roles

- 8 cases: 3 `preserved`, 1 `static`, 4 `target`.
- `check:native-engine` is left out: it is the evaluator's all-or-nothing verdict over the same per-case outcomes, so mapping it would count a preserved-case failure as a target failure.
- Clauses and roles carry over from `mts-mod-identity-regressions` (same exam and assertions); the 2026-11-02 E0 baseline on the real game observed the same starter failures.

## Controls (real game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-de1f178958b442ca` | score 10; fails `gcb.ModIdentityTest.aBlankIdentifierFallsBackToTheName` (target), `gcb.ModIdentityTest.aModWithAnIdIsNotTheSameAsOneWithout` (target), `gcb.ModIdentityTest.aRequirementResolvesToTheFirstMatch` (target), `gcb.ModIdentityTest.ordinaryVersionStringsAreAccepted` (target); admissible |
| `reference` | reference | the task's reference over the starter | `run-4df20d2a62454ffb` | score 100; every case passes; admissible |

Recorded on 2026-11-02 with `rhenium-study e0 baseline` and checked with `e0 check-maps` and `e0 run`, in a
study directory of its own on the Lab host. The authoring controls (alternative and partial repairs) are in
`validation/native-engine/mts-mod-identity-regressions-r2/`.
