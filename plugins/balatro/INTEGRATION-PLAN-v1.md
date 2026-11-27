# Balatro platform adapter work record

Maintainer: **Sangyu Pan** (explicitly supplied; no account/contact inferred).

This is repository maintenance in the independent staging checkout. The original
SWE-Game checkout, PoC frozen source, dependency pins, protected data, 76 previously
staged files and historical evidence remain unchanged. No commit, push or PR.

## Scope and sequence

1. Add an independently packaged entry point, schema-v2 catalog, identity record,
   anonymous starter materialization and strict result projection.
2. Bind byte-identical authored private task assets below `pack_root`; reuse the
   existing Python 3.13 Session/runtime/RPC through a versioned sidecar. Keep the
   Python 3.12 core independent of the game dependencies. Generated state belongs
   only in the platform state/cache directories.
3. Verify discovery, all ten anonymous attempts, read-only packs, identity
   separation, malformed results, failure isolation and packaging using local
   tests. Install development dependencies only in a separate ignored workspace
   environment, never the fixed PoC environment.
4. Present a concrete licensed native Windows execution decision before launching
   any platform game. The root rules currently document only a non-licensed native
   server exception; no silent reinterpretation or rule edits are authorized.
5. If that decision authorizes the scoped honest development runs, validate real
   platform gold/base controls, three clean interleaved flows for each of ten
   tasks. Record new fingerprints and regressions. Historical PoC results do not
   count as platform results. No model experiment or untrusted-host support claim.

## Acceptance and evidence

Use the actual installed `rhenium.benchmarks` entry point, `prepare-attempt` and
`run-attempt --profile full`. A missing runtime, missing assertion, protocol error,
timeout or cleanup failure stays incomplete. A complete behavioral rejection is
distinct from infrastructure failure. No fixed dependency is changed or repinned.

Record every required root verification command as pass, fail, skipped or unrun.
Build and inspect affected wheels. Preserve the previous staged OIDs and source
hashes in a new local verification record without changing the old baseline.

## Estimates and current status

Initial estimate: 10–16 hours of effective work, including an estimated 4–7 hours
of serial engine validation, conditional on runtime authorization and a reusable
environment. This is an estimate, not a completion promise.

Update 2026-09-21: the user approved `RUNTIME-APPROVAL-v1.md`. A new matching smoke
and growth gold/base platform pilot passed. The native matrix and its predeclared
targeted controls are in `NATIVE-VALIDATION-PLAN-v1.md`. Final validation completed:
60 interleaved gold/base workflows and 14 targeted workflows all matched, with
208 normal native process exits. Actual matrix time was about 5 h 58 min.
Entry-only and pilot records remain separate. No model has been launched.

Current outcome: the approved native honest-maintenance bridge is validated;
whole-repository Mypy/pytest gates still fail on unchanged POSIX dependencies on
Windows and ShellCheck remains unavailable. These limits are not converted into
passes. See `NATIVE-REPORT-v1.md`, `validation-native-v1.json`,
`runtime-manifest-native-v1.json` and `regression-scope-native-v1.json`.
