# Score lifecycle: authoring record

Status: **independent review PASS; current controls complete; catalogue integration complete**.

This task uses the complete GPL Competitive Rework source snapshot at
`6cb2fcbe092776c8287944ab541244e2b8262662`. The existing easy task's three repairs
are already present in the starter; this task targets the distinct ZoneMod
hybrid scoring plugin. The seven intended contracts and reference repairs are
task-authored, not claimed as historical upstream commits.

The hard design target comes from coupled score coefficients, stateful health
loss, reentrant game events, deferred ledge settlement, connection and round
identity, and plugin ownership of server settings. No model calibration or paid
experiment has been conducted. Source-tree size alone is not difficulty evidence.

## Test boundary

The verifier compiles candidate score and L4D2Lib sources with the pinned compiler
and runs five independent real dedicated-server boots. A pinned private
Left4DHooks dependency supplies its actual native implementations. The snapshot's
ZoneMod mapinfo is installed at L4D2Lib's documented default configuration path.
No SDKTools/SDKHooks runtime gamedata is overwritten by candidate files.

The private consumer drives documented public forwards, normal game events,
ConVars, entity properties and real deferred frames. It observes public SMPlus
natives and published engine score properties. It never calls a private target
helper or inspects the reference patch. Fake clients are controlled engine
entities; these are focused contract checks rather than a complete competitive
match simulation. In particular, the cross-half callback check establishes the
engine half property immediately before the pending callback because coop game
rules otherwise restore that flag each frame. The unload checks wait for
SourceMod's deferred unload to complete.

The 57 named assertions are mapped in `validation/case-contracts.tsv`. A runtime
exception, duplicate/missing case, inconsistent final total, or absent completion
fails the entire affected suite. Control receipts must be bound to the final
source/tests/specification, not inferred from earlier draft runs.

## Controls

`validation/run-control.py` stages an isolated candidate and private suite,
resolves the existing local image to an immutable ID, disables networking,
and records component/source/log hashes and every case verdict. Generated sources
and raw logs stay in ignored authoring state outside the benchmark pack.
Its tree hash uses relative POSIX paths in explicit lexical order on every host.

Available controls: `nop`, `gold`, `alternative`, and `minus-report-1` through
`minus-report-7`, plus `minus-finalized-guards` for the SDK/Hurt callback guards.
The alternative uses connection user IDs and an explicit bounded
minimum for deferred refunds, with independent normalization of ADM inputs.
Partial controls revert existing function bodies or missing change hooks. Some
contracts interact: stale config hooks also affect boundary-value tests, and
round-reset defects affect delayed-work checks; those overlaps are intentional
observable dependencies, not claims of orthogonal tests.

All 11 final controls completed all 57 cases under one component contract,
recorded in `validation/control-receipts.json` and `control-matrix.tsv`:

| Candidate | Passing cases | Outcome |
| --- | ---: | --- |
| Reference | 57/57 | pass |
| Alternative | 57/57 | pass |
| Broken starter | 17/57 | fail |
| Revert report 1 | 54/57 | fail |
| Revert report 2 | 49/57 | fail |
| Revert report 3 | 46/57 | fail |
| Revert report 4 | 52/57 | fail |
| Revert report 5 | 45/57 | fail |
| Revert report 6 | 44/57 | fail |
| Revert report 7 | 55/57 | fail |
| Remove finalized SDK/Hurt guards | 55/57 | fail |

The independent reviewer found and required a real zero-debit episode fix,
an explicit effective-roster contract, and refreshed controls. The added SDK
probe removes real temporary health (51 to 42); reference damage bonus remains
200, while removing the guards lowers it to 186. The reviewer verified all
current component/source/tests hashes, raw cases/finals, and 66 raw log hashes.
The full review and initial findings are retained in `validation/independent-review.md`.
These controls do not cover every possible snapshot interaction or a full match.

## Hub full-profile validation and harness revision (2026-09-24)

The receipts above were direct maintainer runs. This task was then run through the
Hub full profile (`rhenium run`) on a Linux x86_64 Docker host, where `tests/verify.py`
needed these plumbing corrections; the suites, case names, pass criteria and source
checks are unchanged:

- the compiled plugins are now created in their numbered load order (Left4DHooks, L4D2Lib, the score plugin, the suite) and verification fails closed with `INVALID_ENVIRONMENT` when the directory would still enumerate them in another order. SourceMod autoloads raw directory order; on this host's creation-ordered overlay the old copy order loaded the score plugin first, its OnMapStart called `L4D_GetVersusMaxCompletionScore` before Left4DHooks had started, and the resulting SourceMod exception failed every suite closed, reference included.
- the message after a fail-closed `FAIL <case>:` now names the SourceMod exception or a missing FINAL marker instead of the last engine line containing `error` (such as "Invalid counterterrorist spawnpoint"); the text never changes a verdict.
- a server that has been sent SIGKILL is now waited for up to 120 seconds instead of five (a still-unreaped server is `INVALID_ENVIRONMENT`), because a loaded host took 8 to 15 seconds to reap the multithreaded srcds and the verifier crashed with a traceback.
- each boot now has 240 seconds instead of 55 to reach its FINAL marker. A healthy boot needs 5 to 15 seconds; on this host one L4D2Lib reference boot stalled during plugin loading for over 55 seconds, and the old budget turned that into a complete failing verdict for every case of the boot.

The historical receipts in `validation/` still carry the previous tests hash and stay
historical evidence. Current starter, reference (three runs) and control results are in
[`../../../validation/hub-full-profile-hard-tasks.md`](../../../validation/hub-full-profile-hard-tasks.md).
