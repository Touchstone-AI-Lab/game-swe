# slay-the-spire/core/mts-load-order-regressions — E0 notes

Repair task over the vendored ModTheSpire tree (MIT). The private suite has nine JUnit
cases; the evaluator names each one as `suite:gcb.<class>.<method>`.

## Roles

- 10 cases: 4 `target`, 5 `preserved` (3 of them `overlap`), 1 `static`.
- Reports #731 and #740 are asserted. Reports #734 and #737 are `weak`: their direct
  assertions already pass on the starter (see known issues in `clause-map.json` and the
  pack's `validation/per-defect-matrix.md`).

## Controls (real JDK 8 Maven evaluator, networkless, 2026-09-23)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `starter` | starter | unchanged tree | fails exactly the four target cases; admissible |
| `reference` | reference | upstream fixes | 100; admissible |
| `target-negative-byref-unboxed` | target-negative | reference with `ParameterPatchInfo` restored from the starter | fails only `byRefWritesBackThroughAWrapperArray`; admissible |
| `compat-negative-reversed-initial-order` | compat-negative | reference whose stable sort starts from the reversed declaration order | every target passes; fails three preserved cases (`control_everyModSurvivesWithNoDependencies`, `mutuallyDependentModsKeepTheirOrder`, `aCircularDeclarationDoesNotRunAway`); admissible |
| `alternative-a` | alternative | starter plus an independently written requirement relation (breadth-first walk with a per-walk visited set) and conditional `($w)` boxing; the inert accessor distractor is left as shipped | 100; admissible |
