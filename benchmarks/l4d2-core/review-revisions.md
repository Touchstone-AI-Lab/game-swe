# Pre-merge review corrections — 2026-09-21

Pack 1.2.0 repairs seven tasks after a production-code and test-fairness review.
The pack contains 444 automatically scored cases across ten repair targets in
five upstream codebases. The five additions contain 236 cases and retain their
author-assessed hard labels. This revision does not establish calibrated hard
difficulty. See [task independence](task-independence.md) for the ten production
surfaces, actual compilation/loading paths, and shared-baseline split risks.

## Problems and corrections

| Task / revised version | Problem | Correction and discriminating control |
| --- | --- | --- |
| Competitive release / 1.1.0 | Empty-clip assertion allowed a rewritten earlier timestamp | Compare with the original seeded timestamp; `empty-timestamp-rewrite` must fail |
| Left4DHooks / 1.10.0 | A fixed prose window and keyword could reject accurate documentation | Remove prose scoring; retain compiled ABI and engine checks, with documentation reviewed manually; accurate `equivalent-long-docs` must pass |
| Infected Bots / 1.1.0 | Sparse observations could miss an early replacement between samples | Observe the queued initial wave and first real replacement throughout the eight-second window; a death-triggered `four-second-replacement` must fail |
| Mutant Tanks / 0.2.1, contract v14 | Respawn/unload observations allowed less creation time than initial spawn | Apply the same allowance from actual post-spawn to each phase; a 0.5-second implementation must pass and a 2-second implementation must fail the Hypno group |
| VSLib / 1.1.0 | Reference rejected ordinary scalar/array payloads used by existing production callers | Preserve opaque payloads except in modes that write `TimerCount`; exercise Base delayed events and MoreSI refresh; `reject-opaque-payloads` must fail |
| Confogl / 1.1.0 | Bounded-string and finite callback-chain interaction was untested | Add a finite A -> B -> A callback case preserving numeric-equivalent strings; `minus-bounded-string` must fail |
| L4D2Lib / 1.1.0 | Malformed-import wording was ambiguous and failure contaminated the next fixture | State malformed/truncated rejection explicitly, seed an independent valid baseline before missing-file testing; `minus-syntax-validation` must fail only malformed import |

The Left4DHooks automatic count changes from 72 to 71. VSLib changes from 47
to 52, Confogl from 41 to 42, and L4D2Lib from 43 to 44. Other case counts stay
unchanged. Only VSLib's production reference required a correctness repair;
the remaining changes repair or clarify contracts, fixtures, and observations.
Public exam text is synchronized with each changed private instruction.

During these controls, the first stricter Infected Bots fixture incorrectly
measured eight seconds from a victim's death. The reference produced a spawn
about six seconds later because the initial wave had already been queued before
that death. Restarting its deadline on every death is not required or desirable.
The corrected fixture uses the public `round_start` request as a conservative
lower bound and continuously records the first replacement. Production startup
polling can schedule the wave later; the test does not claim to measure that
private deadline exactly. An attempted chat-diagnostic fixture was discarded
after its engine control failed; the final fixture adds no diagnostic API
requirement or implementation-specific queue observation.
The prompt now states that an existing wave retains its deadline and that a
normal-delay replacement must not advance it. The negative control actually
queues a four-second replacement from the death callback. The earlier failed
control and ineffective mutation remain in external evidence; neither is used
to certify the final revision.

## Maintenance validation

Fresh controls use the pinned, already installed headless L4D2/SourceMod runtime
with networking disabled. Submitted production code is compiled or loaded into
the game; no model API or subscription run is involved in these controls.
Source and trusted tests are mounted read-only, either directly or after copying
them to a dedicated Docker volume. Runtime image identity and component hashes
are retained in sanitized receipts. Raw game logs remain outside the repository.

`private/validation/run-review-control.py` materializes a new candidate and
collects fresh evidence without overwriting previous attempts.
`private/validation/summarize-review-controls.py` publishes only matching current
input hashes, exact verdict names/counts, and expected positive/negative outcomes.
It also requires copied engine logs and rejects timeout/infrastructure exits.
Fail-closed NOP outcomes do not imply that every raw assertion executed and
failed; the specific otherwise-correct mutations isolate each repaired gap.

For example, from the repository root with the pinned verifier image installed:

```sh
python benchmarks/l4d2-core/private/validation/run-review-control.py \
  l4d2-vslib-scheduler-persistence-hard gold --output-root /outside/evidence
python benchmarks/l4d2-core/private/validation/run-review-control.py \
  l4d2-mutant-tanks-release-regressions-hard deferred-half-second \
  --group hypno --output-root /outside/evidence
python benchmarks/l4d2-core/private/validation/summarize-review-controls.py /outside/evidence
```

The publisher requires every candidate listed in its `REQUIRED` mapping;
the two examples alone do not constitute the complete review batch.

| Revised task | Full reference | Full NOP | Other controls |
| --- | ---: | ---: | --- |
| Competitive release | 20/20 | 13/20, rejected | Earlier-timestamp mutation 19/20, only target case fails |
| Left4DHooks | 71/71 | 30/71, rejected | Equivalent long documentation 71/71 |
| Infected Bots | 18/18 | 14/18, rejected | Four-second competing timer 17/18, only target case fails |
| Mutant Tanks | 57/57 | 32/57, rejected | Focused Hypno: 0.5-second alternative 7/7; 2-second mutation 3/7, rejected |
| VSLib | 52/52 | 15/52, rejected | Alternative 52/52; opaque-payload rejection 48/52, rejected |
| Confogl | 42/42 | 0/42, fail-closed | Alternative 42/42; bounded-string mutation 41/42, only target case fails |
| L4D2Lib | 44/44 | 0/44, fail-closed | Alternative 44/44; syntax-validation mutation 43/44, only malformed-import case fails |

Infected Bots observed the first replacement at 9.100 seconds from round start
for the reference, 4.200 for NOP, and 7.100 for the competing-timer mutation.
The eight-second bound allows two engine ticks (0.0676 seconds in these runs).
The negative remains rejected without forcing a correct initial wave to restart
its countdown at the victim's death.

All 25 selected controls met their expected outcomes: 23 full-task runs and two
focused seven-case Hypno runs. The seven full references pass 304/304 cases in
their combined scope. The other three unchanged tasks were not rerun as part of
this correction batch. Selected receipts are in
[review-controls.json](validation/review-controls.json), with per-task copies in
`private/harbor/<task>/validation/revision-controls.json`. The publisher verified
the retained server-log bytes against each receipt's hashes, including the first
VSLib receipt, which predates the explicit `logs_copied` metadata field.

Repository checks ran on a native Linux copy of the working tree. The full
pytest run collected 843 tests: 829 passed, eight skipped, and six failed because
of the check environment. All six passed unchanged after correcting the affected
environment: use a nested checkout rather than `/checktree`, install Git for
temporary-repository fixtures, and provide a real Docker socket for one mocked
launch test's real cleanup. Combined coverage is 835 passes and eight skips;
the initial run was not all green. The new diversity test and all L4D2 plugin
tests passed. Standalone gameplay controls changed afterward and are validated
separately by the engine receipts.

Ruff passed for core, tests, plugins, providers, and authoring tools. Mypy passed
for the main 146-file scope, and Shellcheck passed for seven launchers/scripts.
The additional standalone review helpers passed targeted Ruff. Broadening Mypy
to authoring tests found eight existing errors in five files unchanged from HEAD;
that extra scope is not green and was not silently excluded from this report.

The eight skips cover two DST installation checks, one macOS sandbox check,
one missing-rsync check, two unavailable GMod runtime checks, and two GMod audits
requiring explicit runtime opt-in. These skips are separate from the actual
L4D2 engine controls described here. A Windows-only plugin test launch also
encountered missing symbolic-link privileges; the same test passed in Linux.

## Independent review and limits

Three independent scoped reviewers examined Squirrel caller compatibility,
SourcePawn contracts/fixtures, and the Mutant Tanks timing change. A fourth
reviewer started without this conversation or earlier review reports and
inspected the final changes, production entry points, and task diversity.
None reported a remaining P1/P2 blocker. Their review did not substitute for
engine execution. The blind reviewer also found that an intermediate Infected
Bots queue fixture could reject synchronous scheduling. The final public-event
fixture removes that assumption and the reviewer closed the finding.
The blind review's completeness concern was addressed by
rejecting incomplete full-run exits and checking exact case sets before publishing
receipts; its missing report link is resolved by this document.

Known limits remain explicit:

- Ten distinct repair targets share five upstream codebases. Later starters
  include earlier accepted repairs, so related tasks must stay in the same
  dataset split and use isolated model contexts.
- Exact-content duplicate checks detect cloned references/suites; semantic
  review is still needed to reject disguised duplicates.
- Some fixtures replay events or forwards. Engine execution is not proof of
  complete real-match coverage.
- Hypno uses a 1.4-second observation window for a one-second allowance plus
  scheduling tolerance. The focused controls distinguish 0.5 from 2 seconds;
  they do not certify a precise deadline or a round end during a pending timer.
- Infected Bots continuously checks a public round-start lower bound. Startup
  polling leaves about one second between that bound and the internal scheduled
  deadline; the test catches the four-second competing replacement but does not
  certify every subsecond timing deviation.
- Documentation accuracy in Left4DHooks is a manual review requirement outside
  the automatic score.
- Fair tests and solvable references do not establish high difficulty. A new
  isolated model experiment is needed before claiming calibrated hard performance.
