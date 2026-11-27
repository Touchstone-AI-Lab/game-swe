# slay-the-spire/core/mts-mod-identity-regressions — E0 notes

Repair task over the vendored ModTheSpire tree (MIT). The private suite has seven JUnit
cases; the evaluator names each one as `suite:gcb.<class>.<method>`.

## Roles

- 8 cases: 4 `target` (one per report #802, #805, #808, #811), 3 `preserved`, 1 `static`.
- Every report clause is asserted; the defect groups are independent (see the pack's
  `validation/per-defect-matrix.md`).

## Controls (real JDK 8 Maven evaluator, networkless, 2026-09-23)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `starter` | starter | unchanged tree | fails exactly the four target cases; admissible |
| `reference` | reference | pack reference | 100; admissible |
| `target-negative-strict-versions` | target-negative | reference with strict version parsing kept | fails only `ordinaryVersionStringsAreAccepted`; admissible |
| `compat-negative-title-over-identifier` | compat-negative | reference that prefers the readable title over any identifier | every target passes; fails only `control_aNormalModIsKnownByItsId`; admissible |
| `alternative-a` | alternative | starter plus an independently written blank check, explicit one-sided identifier rule, loose (not NPM) version parsing and a first-match loop guard | 100; admissible |
