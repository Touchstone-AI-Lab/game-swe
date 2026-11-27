# Authoring evidence

Version 1.1.0 adds one bounded-string / finite-writeback interaction case (42
cases total) and makes the existing representation requirement explicit. New
engine validation is recorded in `validation/revision-controls.json` and
[`../../../review-revisions.md`](../../../review-revisions.md); the 41-case receipts below are
historical version 1.0.0 evidence, not a pass claim for this revision.

This is author-assessed **hard**, at the lower end of the pack's hard range; the original
authoring controls did not include model calibration. It retains the full frozen Competitive
Rework tree, with previously accepted release and score repairs incorporated.
The new surface is Confogl's ConVar lifecycle. The core challenge is a batch
snapshot before engine writes, finite cross-ConVar callback reentry, delayed
binding into an active profile, and restoring only activated ownership. Argument
and diagnostic boundaries supplement those interacting state requirements.

The trusted suite loads the complete submitted Confogl plugin, not a rewritten
module or private helper bridge. It uses public commands, real ConVars/change
hooks and the public `OnConfigsExecuted` forward. Forward replay covers callback
semantics; it is not evidence of a full map transition. The standard Confogl
reload marker initializes match mode without the production `unload_all` path
removing the trusted test driver. The real match reset command and asynchronous
plugin unload/reload are exercised. A wake guard keeps the all-bot server ticking
when match unload resets `sb_all_bot_game`.

SourceMod may retain a ConVar's requested string separately from its bounded
numeric value. Tests observe numeric bounds and preserve in-range string forms,
including `01`. Reference enforcement repeats correction after a finite callback
chain; it does not promise convergence against another plugin that continually
enforces a conflicting value. The test includes A -> B -> A finite writeback, discovered
in the initial independent review, plus 255-byte baselines and 63/64-byte inputs.

Late entries exercise batch restoration, but the selected late-entry insertion
order is not an exhaustive proof of all permutations. Early-entry cross-write
tests separately check the shared two-phase snapshot behavior. A second profile
is tested after real plugin reload; the normal match loader unloads/reloads the
plugin rather than providing a public same-instance reactivation command.

Historical version 1.0.0 evidence is in `validation/control-receipts.json` and
`control-matrix.tsv`, with raw local runs under
`.rhenium/authoring/confogl-final-controls/`. Other `confogl-*` directories hold
superseded authoring diagnostics and are not final evidence. The runner uses an
existing immutable local runtime image without network access. Tree hashes use
lexically sorted relative POSIX paths and NUL-delimited file bytes.

The alternative reverses batch application order and uses an equivalent string
comparison. It is reference-derived, not an independently authored solution.
Per-report mutations and targeted finite-writeback/bounded-string mutations
check representative omissions. All seven report omissions and the finite-writeback
mutation fail. The historical `minus-bounded-string` mutation survived 41/41. Version 1.1.0
adds bounded A -> B -> A finite correction with a numeric-equivalent but
string-distinct writeback. Both callbacks are armed once and their completion
is observed; the final value must retain the desired in-range `01`. This targets
the uncovered interaction without depending on private helper names. New control
evidence is required to establish mutation rejection; complete mutation coverage
is not claimed. Negative diagnostics deliberately provoke a
SourceMod exception; the verifier fails the entire suite closed when any such
exception occurs, even if some raw behavioral markers say PASS.

Reproduce using `python -B validation/run-control.py gold --output-root
/absolute/path/outside/task`. Generated state belongs outside the benchmark.

## Hub full-profile validation and harness revision (2026-09-24)

The receipts above were direct maintainer runs. This task was then run through the
Hub full profile (`rhenium run`) on a Linux x86_64 Docker host, where `tests/verify.py`
needed these plumbing corrections; the suites, case names, pass criteria and source
checks are unchanged:

- the message after a fail-closed `FAIL <case>:` now names the SourceMod exception or a missing FINAL marker instead of the last engine line containing `error` (such as "Invalid counterterrorist spawnpoint"); the text never changes a verdict.
- a server that has been sent SIGKILL is now waited for up to 120 seconds instead of five (a still-unreaped server is `INVALID_ENVIRONMENT`), because a loaded host took 8 to 15 seconds to reap the multithreaded srcds and the verifier crashed with a traceback.
- each boot now has 240 seconds instead of 55 to reach its FINAL marker. A healthy boot needs 5 to 15 seconds; on this host one L4D2Lib reference boot stalled during plugin loading for over 55 seconds, and the old budget turned that into a complete failing verdict for every case of the boot.

The historical receipts in `validation/` still carry the previous tests hash and stay
historical evidence. Current starter, reference (three runs) and control results are in
[`../../../validation/hub-full-profile-hard-tasks.md`](../../../validation/hub-full-profile-hard-tasks.md).
