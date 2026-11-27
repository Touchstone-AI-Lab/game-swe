# Balatro benchmark support

This page preserves the **Windows plugin 0.2.2** validation scope. The current
Linux development path and its separate evidence are documented in
[Balatro Linux runtime support](balatro-linux-v1.md). Statements below about
unimplemented acquisition/Linux support describe that earlier Windows revision.

## Ownership and status

| Field | Value |
| --- | --- |
| Maintainer | Sangyu Pan |
| Status | `Experimental` |
| Plugin ID | `balatro` |
| Catalog | `balatro/core` 0.2.0 |
| Plugin distribution | `plugins/balatro/` (`rhenium-balatro-plugin` 0.2.2) |
| Benchmark pack | `benchmarks/balatro/` (v0.2) |

The integration is Experimental. All ten tasks have been evaluated through the
installed plugin's anonymous submission and full-profile scoring entry on a real
Windows Balatro desktop. The final 0.2.2 wheel completed 22 workflows, 58 native
processes and 948 required check outcomes: one full gold/base pair per task, plus
two source-review admission probes with new comment-only byte identities. Every
gold passed and every base was rejected for complete observed behavior. The
[validation report](../../plugins/balatro/BRANCH-READINESS-REPORT-v2.md) records
the scope and exact versions; the admission probes do not add task semantics.

It remains Experimental because the runtime depends on a separately prepared
installation, the controls have run on one host, and execution requires review
of the exact submitted source. No model pass rate has been measured.

## Runtime setup

There is no managed runtime builder. The operator must have a licensed,
separately prepared game installation and the fixed external controller.
The [operator guide](../../plugins/balatro/OPERATIONS.md) gives the commands:

1. Install the plugin in the Python 3.12 workspace environment and preserve the
   separate fixed Python 3.13 controller.
2. Create a new state binding to the prepared runtime, run its smoke check, then
   run read-only doctor to verify live bytes, protected data and matching evidence.
3. Prepare an anonymous attempt with the task's public instructions and starter.
4. Review the actual submission source and record its exact hash before running
   the printed scoring wrapper. Editing the source invalidates that review.

Hash inspection alone does not authorize execution. Evaluation does not log in,
acquire, install, update or rebuild the game. Doctor does not launch it or repair
the environment. Runtime preparation on another host needs a separately reviewed
route; changing pins is not a bootstrap procedure.

## Version policy

- Game: Balatro **1.0.1o-FULL**.
- Engine: LÖVE **11.5 r2**, as reported by the Windows file version.
- Mod loaders: Lovely **0.9.0** and Steamodded **26.829.0**.
- Control interface: BalatroBot **v1.5.2**, commit
  `9052d76f14723293f6c6b2cecaa791a5c4ae68f3`. Its paired Lua manifest still
  reports 1.5.1; the loaded bytes are checked, not just the version label.
- Platform/plugin Python: **3.12**. External controller Python: **3.13.12**;
  the controller is never imported into core.
- Runtime compatibility: component bytes, controller sources and protected data
  are verified independently of task and candidate identities. A different
  candidate does not change the environment fingerprint.

Plugin 0.2.2, task pack v0.2 and catalog 0.2.0 are separate version identifiers.
Historical reports retain their original fingerprints and validation scope.

## Platforms

| Surface | Supported platforms |
| --- | --- |
| Real Balatro engine evaluation | Recorded, prepared Windows desktop only; visible serial runs, gamespeed=1, FAST=0, HEADLESS=0 |
| Linux and macOS engines | Not implemented or validated |
| Plugin development checks | Windows checks recorded; portable fake-engine tests are configured for Ubuntu/Python 3.12 CI, but remote CI has not run |
| Cross-host runtime setup | No automatic discovery, acquisition or bootstrap; the current binding uses the controlled installation and its protected baseline |

Windows repository-wide checks have POSIX/WSL-related failures documented in the
validation report. Linux-platform static analysis is not Linux test execution or
engine evidence. Plugin checks and real-engine controls are reported separately.

## Programming languages

| Component | Language |
| --- | --- |
| Agent submission and Balatro mods | Lua with JSON mod metadata |
| Game fixtures and observers | Lua |
| Catalog, submission admission and plugin evaluator | Python 3.12 |
| External Session/runtime/RPC controller and scenarios | Python 3.13.12 |
| Windows scoring wrapper | PowerShell |

## Evaluation levels

1. Validate immutable task metadata and the editable-file allowlist, then seal
   the submitted bytes with a bounded SHA-256 manifest.
2. Verify source-review admission, runtime identity and readiness in both the
   parent and sidecar before launching the game.
3. Run all required task scenarios through the real engine and grade their
   observations against the frozen behavioral requirements.

Only `full` with every required case completed can pass. Reduced or unknown
profiles cannot pass. The grader does not use candidate labels, paths or source
structure to decide behavior. A complete behavioral rejection is distinct from
an incomplete result caused by missing cases, RPC, environment or cleanup failure.

## Task-pack and historical materials


The registered schema-v2 [pack](../../benchmarks/balatro/benchmark.json) and
[catalog](../../benchmarks/balatro/catalog.json) are used by plugin 0.2.2.
The original [pack README](../../benchmarks/balatro/README.md) and
[asset-import page](balatro.md) are frozen records of the earlier asset-only stage.
Their statements about a missing plugin/catalog do not describe the current
branch; their bytes remain unchanged to preserve historical manifests.
The [native-v1 supplement](balatro-integration.md) records the subsequent 0.2.1
integration stage.

| Material | Audience and boundary |
| --- | --- |
| `benchmarks/balatro/public/v02/` | Frozen participant contracts, API documents and starters; unchanged task semantics |
| `benchmarks/balatro/candidate-release.json`, `validation/` | Maintainer provenance and sanitized original PoC summaries |
| `benchmarks/balatro/private/native-v1/` | Reviewed, self-authored gold/negative controls, fixtures and private assertions; repository maintenance only |
| Plugin wheel | Python adapter source and distribution metadata only; no task pack, gold or private tests |
| Anonymous attempt | One task's allowed starter and anonymized public instructions, materialized by the plugin; no repository/private assets |
| Operator state/cache | Generated bindings, review records, sealed submissions, logs and saves; not committed or publicly exported |

Maintainer source in Git is not equivalent to participant-visible material.
Do not hand an agent the full repository or this maintenance guide for an exam.
The frozen per-task README commands refer to the original external PoC tool;
they do not install that tool or replace the current anonymous wrapper workflow.

Authorship and third-party boundaries are recorded in
[ownership](../../benchmarks/balatro/OWNERSHIP.json),
[public provenance](../../benchmarks/balatro/validation/provenance.md), and
[private provenance](../../benchmarks/balatro/private/native-v1/PROVENANCE.md).
These records do not grant rights to the game or its third-party runtime components.

Original PoC acceptance (108 submissions / 309 processes), native-v1 (74 workflows /
208 processes) and plugin 0.2.2 (22 workflows / 58 processes) are separate evidence
populations. The final 0.2.2 scope did not repeat all earlier repetitions, mutations
or alternatives. Historical `formal_integration_status=not_implemented` fields
remain unchanged; current plugin registration and local scoring are described above.

## Native-runtime side effects

The runner writes submissions, isolated game directories, review records, RPC
evidence and results under operator state; the benchmark pack remains read-only.
It reuses the external Session/runtime/RPC controller and preserves game-process
protection, graceful shutdown and owned Windows Job cleanup. These controls do
not provide a hostile-code sandbox. Failure halt markers remain for diagnosis.

Licensed game files, dependencies, personal data, raw logs and saves are not
distributed. The recorded 0918 backup covers the installation, not verified
personal-data recovery. The scoped
[runtime approval](../../plugins/balatro/RUNTIME-APPROVAL-v1.md) applies to this
controlled host and does not change repository rules for other games or hosts.

## Engine API reality

- Save restoration uses a new process, a complete seeded initialization, one
  load request and its full completion response. Direct loading from a blank
  MENU remains outside the validated path.
- An unconfirmed non-idempotent action is not automatically retried. Similar
  game state after a timeout does not substitute for a completed response.
- The recorded startup recovery used the operator's agreed headphone-disconnected
  condition. It is not a proven permanent fix or continuous device monitoring;
  the runner does not change audio devices or system settings.

## Not yet claimed

- Managed acquisition, automatic cross-host preparation, Linux/macOS engines
  and Harbor export are not implemented.
- Formal untrusted execution needs a provider satisfying
  [core's host contract](../disposable-evaluation-hosts.md). A missing provider
  fails closed; there is no local fallback or supplied disposable host.
- Other hosts, concurrent runs and unattended execution of arbitrary submissions
  are unvalidated. Task difficulty is uncalibrated.
- No Stable status, model calibration or all-repository-gates-passed claim is made.

## Validation references

- [Operator guide](../../plugins/balatro/OPERATIONS.md): current setup, review and scoring commands.
- [Plugin 0.2.2 report](../../plugins/balatro/BRANCH-READINESS-REPORT-v2.md),
  [validation summary](../../plugins/balatro/validation-branch-v2.json) and
  [replay commands](../../plugins/balatro/REPLAY-branch-scope-v3.md): final wheel and controlled-host evidence.
- [Native-v1 report](../../plugins/balatro/NATIVE-REPORT-v1.md): preserved 0.2.1 integration evidence.
