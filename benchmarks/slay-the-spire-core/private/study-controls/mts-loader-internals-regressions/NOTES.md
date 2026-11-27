# slay-the-spire/core/mts-loader-internals-regressions — E0 notes

Repair task over the vendored ModTheSpire tree (MIT). The private suite has sixteen JUnit
cases; the evaluator names each one as `suite:gcb.<class>.<method>`.

## Roles

- 17 cases: 5 `target`, 11 `preserved` (2 of them `overlap`), 1 `static`.
- Reports #1013, #1016, #1010, #1102 and #912 are asserted. Reports #1019 and #909 are
  `weak`: their only assertions already pass on the starter, so the suite observes five of
  the seven defect groups (see known issues in `clause-map.json`).
- The reference's `hashCode` includes the title while its `equals` ignores the title for
  identified mods; no assertion covers that inconsistency. The alternative below keeps
  the two consistent.

## Controls (real JDK 8 Maven evaluator, networkless, 2026-09-23)

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `starter` | starter | unchanged tree | fails exactly the five target cases; admissible |
| `reference` | reference | author-written reference | 100; admissible |
| `target-negative-valueless-return` | target-negative | reference with the valueless `SpireReturn.Return()` fix left out | fails only `takingOverAValuelessMethodSkipsItsWork`; admissible |
| `compat-negative-strict-stored-loader-version` | compat-negative | reference that reads the stored loader version strictly | every target passes; fails only `aTwoPartVersionSurvivesTheRoundTrip`; admissible |
| `alternative-a` | alternative | starter plus an independently written record layout (authors appended last), equality-consistent hash, a fresh valueless return, exact-type postfix result binding and explicit unboxing | 100; admissible |
