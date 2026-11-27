# LinGe Director state: authoring record

Status: **independent review PASS; current controls complete; catalogue integration complete**.

This is a new task over the existing MIT LinGe snapshot at
`c27c22d792902193b468bd059a6749a3e71198a0`. Its source contains the repaired
HUD/Hint/RewardHP baseline from hard-v3 so that old defects do not become part of
this task. The nine reports concern existing Base/MoreSI behavior and explicit
task-authored intended semantics. These fixes are not represented as historical
upstream commits. The original MIT licenses and authorship are preserved.

The difficulty target is hard: configuration migration and aliasing, reentrant
subscriber lists, nested payload ownership, deferred work, and lifecycle state
interact across existing modules. This is a design assessment, not model-derived
calibration. No paid/model experiment is included in this authoring stage.

## Verification boundaries

The verifier reuses the established LinGe engine launcher and source packaging
checks. Its replacement suite calls public merge/config/event APIs and the
registered command dispatcher, writes actual VScript configuration files, and
observes the real SessionOptions table. Delayed cases use VSLib's real timers.
Assertions do not inspect a candidate helper name or compare source patches.
The table/array tests are VM-level API tests; they do not claim to simulate a
full campaign or measure Director spawn frequency.

Each case is mapped to a public report in `validation/case-contracts.tsv`.
Raw logs and staging source remain outside the benchmark tree under ignored
authoring state. Validation receipts must distinguish measured runtime controls
from unrun controls. No current draft result is a frozen benchmark claim.

## Measured authoring controls

The current 41-case contract completed all cases on the existing immutable Linux
runtime image recorded in `validation/control-receipts.json`, with networking
disabled. No model experiment was run.

| Control | Passing cases | Expected outcome |
| --- | ---: | --- |
| unchanged broken source | 11/41 | fail |
| reference repair | 41/41 | pass |
| alternative repair | 41/41 | pass |
| undo report 1: merge ownership | 37/41 | fail |
| undo report 2: array migration | 39/41 | fail |
| undo report 3: config persistence | 36/41 | fail |
| undo report 4: subscription snapshot | 38/41 | fail |
| undo report 5: payload ownership | 37/41 | fail |
| undo report 6: queued payload | 39/41 | fail |
| undo report 7: whitelist | 39/41 | fail |
| undo report 8: quantity ceiling | 40/41 | fail |
| undo report 9: desired/live lifecycle | 35/41 | fail |

All nine single-report controls fail only cases mapped to their own report. The
alternative uses sorted-index array reconstruction, an explicitly built subscriber
snapshot, per-section bulk persistence, and set-based whitelist deduplication.
These are maintainer controls over generated candidate copies, not calibrated
agent submissions. The candidate builder is `validation/candidates.py`.

Reproduce one control with an already prepared runtime (no acquisition or runtime
build happens in this command):

```sh
python validation/run-control.py gold --output-root /absolute/ignored/control-state
```

Run from the task directory. Accepted candidates are `nop`, `gold`, `alternative`,
and `minus-report-1` through `minus-report-9`. The runner copies both source and
private tests into a new external state directory, resolves the local image tag
to an immutable image ID, and records component/content hashes and per-case
verdicts. Only compact receipts and matrices are retained in this task.

The recorded tree hashes were produced on Windows: paths are sorted using
Python's Windows Path ordering before hashing relative POSIX path names, NUL,
file bytes, and NUL. To reproduce these existing receipts on another platform,
sort by `PureWindowsPath` explicitly. The independent reviewer reproduced all
recorded hashes with that ordering; the evidence has not been rewritten.

The initial independent review found real gaps in restore cleanup and persistence
preservation coverage. The current repair disables actual Director overrides on
restore; the suite now observes real common-infected cleanup and post-disable
survival, valid-file Save/SaveAll preservation, and isolated mutation boundaries.
The review history and eventual disposition are in
`validation/independent-review.md`; its final disposition is PASS.

## Hub full-profile validation and harness revision (2026-09-24)

The receipts above were direct maintainer runs. This task was then run through the
Hub full profile (`rhenium run`) on a Linux x86_64 Docker host, where `tests/verify.py`
needed these plumbing corrections; the suites, case names, pass criteria and source
checks are unchanged:

- a server that has been sent SIGKILL is now waited for up to 120 seconds instead of five (a still-unreaped server is `INVALID_ENVIRONMENT`), because a loaded host took 8 to 15 seconds to reap the multithreaded srcds and the verifier crashed with a traceback.
- the boot now has 240 seconds instead of 55 to reach its FINAL marker, the same budget as the SourcePawn hard verifiers. Here a stalled boot already ended as an incomplete run rather than a failure; the longer budget only reduces such incomplete runs on a loaded host.

The historical receipts in `validation/` still carry the previous tests hash and stay
historical evidence. Current starter, reference (three runs) and control results are in
[`../../../validation/hub-full-profile-hard-tasks.md`](../../../validation/hub-full-profile-hard-tasks.md).
