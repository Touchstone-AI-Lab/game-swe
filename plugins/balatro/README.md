# Balatro candidate-pack adapter

Maintainer: **Sangyu Pan**. Account/contact not supplied.

The **0.3.0** Linux container profile and its explicit migration
boundary are described in the [container guide](../../docs/games/balatro-container-v1.md).
It retains the ten frozen task specifications. All ten full gold/base pairs
completed through the core CLI: **20 controls, 56 real game processes and 912
required outcomes**. Every gold passed and every base failed for its intended
behavior. The 0.2.2 Windows and WSL records below are historical.

The complete [container-v1 matrix](runtime/linux/LINUX-CONTAINER-REPORT-v1.md)
contains **68 controls, 197 normally exited game processes and 3461 required
outcomes**, all with their intended results. Its [sanitized record](runtime/linux/validation-linux-container-v1.json)
keeps these identities separate from earlier hosts and source versions.

The preceding 0.2.2 worktree introduced fixed-depot preparation and controlled
native scoring. Its [WSL support boundary](../../docs/games/balatro-linux-v1.md)
and [runtime work record](runtime/linux/README.md) retain their historical scope.
No updated 0.2.2 release or relabeling of its artifact identities is claimed.
The later [repository checks v3](runtime/linux/REPOSITORY-CHECKS-REPORT-v3.md)
record passing Linux repository/frontend/shell gates and Windows helper tests,
with explicit skips and remaining release boundaries. Historical Windows and
engine reports below retain their original scopes and fingerprints.

## Preserved Windows validation scope

Recorded plugin: **0.2.2, Experimental on the controlled local Windows host**.
It adds explicit source-review records for new submissions and a live read-only
runtime doctor. The historical Windows entry is the
[support matrix](../../docs/games/balatro-branch-v2.md); use the
[Windows operator workflow](OPERATIONS.md) for discovery, binding and exact-byte review.
The [v2 replay guide](REPLAY-branch-v2.md) is a preserved controlled-host record.
Final wrapper validation completed
**22 workflows / 58 native processes**, with ten full gold/base pairs and two
new-byte review admission probes. Final related tests: **192 passed**. See the
[branch report](BRANCH-READINESS-REPORT-v2.md) and [scoped replay](REPLAY-branch-scope-v3.md).
Whole-repository Windows gates remain incomplete, as recorded there. This evidence
is separate from the completed native-v1 matrix below.

Plugin **0.2.2** is distinct from task pack **v0.2 / catalog 0.2.0**. Ten tasks have
author-designed 3 Easy / 4 Medium / 3 Hard labels; no model calibration was run.
Plugin registration, anonymous submissions and the local honest scoring entry are
implemented and validated. The historical JSON field `formal_integration_status`
remains unchanged; it must not be read as absence of those implemented entry points.
At that Windows revision, automatic acquisition/cross-host preparation and a
formal untrusted host were unimplemented. Stable or whole-repository release
readiness is not claimed.

The Python 3.12 suite includes portable Balatro/contract and discovery tests. Real
Windows lock/Job/helper tests retain their explicit platform conditions; real game
evaluations are outside the unit suite.

Native-v1 status: **honest maintenance matrix passed; whole-repository gates remain incomplete**.
The user approved the scoped decision in `RUNTIME-APPROVAL-v1.md`. This distribution
registers `balatro` through `rhenium.benchmarks`, prepares anonymous repair attempts,
seals starter files and invokes the fixed external Python 3.13 controller only
with an explicit local binding and current matching smoke. Without that binding,
`full` stays incomplete with `runtime_action_required`. Only source-reviewed,
hash-listed maintenance controls or explicitly reviewed submission bytes may execute.
`core` cannot pass. Inspection alone does not authorize execution; an operator
must review the actual source and record its exact seal using `review-submission`.

The original staged candidate snapshots and historical PoC summaries are unchanged.
They are provenance, not platform results. See
[runtime decision](RUNTIME-DECISION-REQUEST-v1.md) and
[work record](INTEGRATION-PLAN-v1.md).
The [pack guide](../../benchmarks/balatro/CURRENT.md) distinguishes frozen
participant materials, maintainer-only source assets and generated private state.
Execution scope: [native plan](NATIVE-VALIDATION-PLAN-v1.md).
Final [native report](NATIVE-REPORT-v1.md): all ten gold/base pairs passed their
declared outcomes in three repetitions, plus ten rejected mutations and four
passing correct alternatives (74 workflows / 208 native processes). The
[replay guide](REPLAY-native-v1.md) uses fresh state and the installed CLI entry.
Full-repository Mypy and pytest remain blocked by unchanged POSIX dependencies on
Windows; ShellCheck is unavailable. This is not an all-checks-passing release or
an untrusted evaluation host.

Raw evidence paths cited by historical reports are operator-local and are not
provided with the repository. Published JSON summaries/manifests are sanitized;
the replay guides require the separately prepared approved host and retained
private evidence. Do not upload raw logs, saves or local runtime bindings.

## Asset and identity boundaries

- Catalog/public assets are loaded only below `BenchmarkContext.pack_root`.
- Submitted executable files are limited to the package's starter allowlist;
  immutable metadata is verified byte-for-byte. A copied SHA-256 seal is checked
  again after copying. This is an integrity check, not an untrusted-code sandbox.
- Generated starters and sealed submissions belong in platform state. Existing
  intact starters can be reused; conflicting edits are never silently deleted.
- Anonymous EXAM.md contains the original rules with only the local task ID
  replaced by `this-exercise`, plus delivery instructions. Supplied API.md follows
  the same identity-only presentation transform. Starter bytes are unchanged.
- Package indexes, package.json, PoC command README files, history, private tests,
  gold, logs, save data and licensed content are not copied into attempts.
- Anonymous results use an allowlist: opaque run ID, submission hash, score,
  completeness, outcome category and ordinal check outcomes. Arbitrary exception,
  path, expected-value and runtime-log strings are discarded.
- Canonical identity stays in the Hub's private records as
  `balatro/core/<local-task-id>`; no central core registry change is made.

## Development

Use a separate Python 3.12 workspace environment. Do not change the fixed PoC
Python 3.13 environment or its dependency pins. From the repository root:

```text
python -m pip install --no-deps --no-build-isolation -e plugins/balatro
python -m pytest plugins/balatro/tests
python -m ruff check plugins/balatro
python -m mypy src plugins providers tests
```

Core and the independent contract fixture plugin must be installed for integration
tests. Tests do not need game files, Steam credentials or a real engine. The
protocol tests use synthetic results and do not constitute engine evidence.

The catalog's 30/60/90-minute values are required Hub planning estimates, not
measured solve times. All authored 3E/4M/3H labels remain uncalibrated.
