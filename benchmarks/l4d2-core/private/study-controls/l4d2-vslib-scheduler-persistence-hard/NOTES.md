# E0 notes: l4d2-vslib-scheduler-persistence-hard

Workspace layout: `/app/linge-hud`; every overlay uses `root = linge-hud`. Clause ids are `R<report>.<n>` for the numbered reports (anchor = report, sentence, short quote) and `Task-*` for the surrounding paragraphs.

Baseline through the operator Hub full profile (`rhenium run`, Linux x86_64 Docker host, 2026-09-24, verifier image `sha256:96293b942d52...`): unchanged starter 15/52 (`run-3ab1ea8570e7409b`, complete, score 10); reference 52/52 three times with identical case outcomes (`run-37cde9bbcb384741`, `run-911d9563955f4a86`, `run-5b3990e74ac446e1`, score 100). These are not study-Hub records: the study Hub must be re-seeded from the operator database before `rhenium-study e0` can reproduce them, because the verifier images changed on 2026-09-24.

Overlays patch `vscripts/LinGe/VSLib/timer.nut`, `vscripts/LinGe/VSLib/fileio.nut` and, for
the alternative, the other oracle files. The eight reports are task-authored contracts over
the frozen upstream snapshot, not reverted upstream commits.

## Preserved contracts (all `P` in the unchanged starter)

| case | public statement |
| --- | --- |
| `data-shared-noncyclic` (overlap) | R6 s2 repeated noncyclic references still save; R6 s5 independent containers |
| `legacy-clean-data` | R7 s1 existing clean legacy files stay readable |
| `data-missing-file` (overlap) | R8 s1 a missing file returns null |
| `timer-opaque-scalar-payloads` | R3 s8 opaque scalar payloads are delivered unchanged |
| `timer-array-payload-identity` | R3 s8 array payloads keep their identity (no wrap or clone) |
| `timer-base-delayed-array-event` | R3 s11 delayed LinGe event delivery keeps working |
| `timer-duration-count` (overlap) | R3 s4 DURATION runs floor(duration / delay) times |
| `timer-exception-peer-survives` (overlap) | R2 s1 a throwing callback does not stop its peers |
| `timer-shared-params-preserved` | R3 s7 callback parameter tables keep their shared identity |
| `timer-false-stops-repeat` | R1 s6 callback-returning-false stops a repeat |
| `timer-remove-due-peer` (overlap) | R1 s3 removed work does not run later in the update |
| `timer-new-work-own-delay` (overlap) | R1 s4 new work waits for its own delay |
| `clock-negative-allowed` (overlap) | R4 s4 allowing negatives still crosses zero |
| `clock-unknown-null` | R4 s6 null for an unknown clock |
| `clock-explicit-reset` (overlap) | R4 s3 an explicit value resets value and baseline |

`timer-moresi-team-refresh` is stated in the exam as behaviour that must keep working but fails
on the unchanged starter, so it is a `target` by observation.

## Controls (all executed through `rhenium run`; all behaved as declared)

- `tn-legacy-key-substring` (target-negative): the oracle whose legacy loader decodes any key containing `_vslInt_` (report 7 whole-key rule unrepaired, minus-report-7). Observed: `run-6e3608ced565479e`, 51/52, failing `legacy-prefix-not-substring`.
- `cn-removed-peer-still-runs` (compat-negative): the oracle without the stale-entry checks in the scheduler update (`validation/candidates.py` minus-report-1). The starter already honoured removal by a peer, so this breaks only the preserved case. Observed: `run-e28fa2d626414c20`, 51/52, failing `timer-remove-due-peer`.
- `cn-copy-array-payloads` (compat-negative): the oracle plus a two-line defensive copy of array payloads in `AddTimer`, against the explicit "do not wrap, clone, or reject them". Observed: `run-f16d432e6b9248c8`, 51/52, failing `timer-array-payload-identity`.
- `alternative-reversed-exponent` (alternative): the pack's reference-derived alternative (reverse due-timer order, `%.9e` floats, space-separated arrays). Observed: `run-4754ec191d3949d8`, 52/52, failing none.

The pack's `reject-opaque-payloads` mutation is not used as a control. The 1.2.0 review
records it at 48/52 with `timer-moresi-team-refresh` (a target here) among the failures, so it
is neither a clean target-negative nor a compat-negative.

## Exclusions / remarks

- Unasserted (excluded) clauses: `R3.8` (0.1 s minimum delay not exercised), `Task-preserve-mit`
  (pre-case licence gate), `Task-no-tests-edit`.
- No task-level exclusion recommended.
