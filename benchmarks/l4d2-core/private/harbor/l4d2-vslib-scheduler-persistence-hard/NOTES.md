# Version 1.1.0 review correction

The previous reference wrongly rejected all non-table timer payloads. Real
MoreSI player-team handling passes an integer to `Delay_siauto`, and Base's
`EventTrigger` can schedule arrays. Registration now preserves opaque payloads
for ordinary and DURATION_VARIANT callbacks. COUNTDOWN/DURATION alone require
a table or null so `TimerCount` can be published safely; invalid replacements
remain atomic. The public contract explicitly states these existing caller
requirements and the TimerCount-mode validation boundary.

Five additional real-engine cases cover scalar values, array identity (also
DURATION_VARIANT), atomic invalid countdown/duration replacement, Base delayed
event delivery, and the real MoreSI handler-to-Director refresh path. The latter
two invoke production callers and observe their effects across engine ticks.
The `reject-opaque-payloads` control recreates the prior reference bug.

Fresh 1.1.0 engine controls and independent review are recorded in
[`../../../review-revisions.md`](../../../review-revisions.md) and
`validation/revision-controls.json`.
The 47-case receipts below describe 1.0.0 only and must not be treated as evidence
for the revised 52-case task. Prior solver results are likewise historical.

# Historical 1.0.0 authoring evidence

Status: reference implementation and 11 deterministic engine controls complete;
independent review **PASS**. Catalogue integration complete.

This is an author-assessed **hard** task, not a calibrated model result. No solver
experiment was run. The full LinGe tree is retained at the same pinned upstream
revision as the accepted LinGe tasks. The starter incorporates the older HUD,
hint, reward and Director-state repairs so the eight new reports are distinct.
The problem requires tracing the effective post-load FileIO override, designing
a nonexecuting recursive codec compatible with legacy data, and repairing
mutation-safe timer identity, bookkeeping ownership and clock transitions.

All assertions run inside the actual L4D2 Squirrel VM. A trusted SourceMod driver
starts the suite and advances observations independently of candidate timers.
Timer callbacks run on the engine's existing VSLib think path; file cases use
real scriptdata files. Round cleanup calls the existing public
`VSLib_RemoveDeadTimers` function directly: full `ScriptMode_OnShutdown` deletes
the entire VSLib namespace, so continuing callbacks after that shutdown would
be an invalid fixture. This test covers the cleanup operation, not a map change.
No assertion inspects a candidate helper, formatting choice or reference diff.

The final 11 controls are recorded in `validation/control-receipts.json` and
`control-matrix.tsv`, including component/tree/log hashes and immutable runtime
image identity. Local raw evidence is outside the pack under
`.rhenium/authoring/vslib-controls/<local_run>/`. Hashes use relative POSIX paths
sorted lexically, NUL-delimited with file bytes (algorithm stated in receipts).
Gold and alternative both pass 47/47; untouched starter passes 12/47. Eight
single-report defect mutations each fail a mapped case, with pass counts
46, 41, 45, 44, 43, 46, 46, 43. Each run completes all 47 cases.

The alternative is a transformed reference, not a separately authored solution:
it reverses the scheduler snapshot traversal and changes float/entry formatting.
It demonstrates that tests accept different independent-timer ordering and
serialization layouts. The partial controls are representative omissions, not
an exhaustive proof against every incorrect implementation.

Reproduce one control with an already prepared runtime:

```sh
python validation/run-control.py gold --output-root /absolute/path/outside/task
```

The runner refuses output inside the task and uses an existing pinned image
with no network. Historical debugging runs under other authoring directories
are not final validation evidence.

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
