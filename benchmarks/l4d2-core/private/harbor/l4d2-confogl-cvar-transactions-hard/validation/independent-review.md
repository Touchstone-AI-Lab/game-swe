# Independent review: Confogl ConVar transactions

Reviewer: fresh maintenance review agent. Date: 2026-09-19.

Final decision: **PASS** for the revised 41-case contract; see the final review below. Historical initial decision: **NEEDS_REVISION** for the 34-case draft. This is repository maintenance, not an exam attempt. The reviewer read root AGENTS.md and the public contract before private implementation and assertion review. No model experiment, system installation, reference implementation, or engine rerun was performed by the reviewer.

## Blocking finding in the initial reference

Public report 3 requires finite cross-ConVar callbacks to settle without drift. The initial `CVS_ApplyEntry` marks an entry as writing, writes its desired value, reads whatever value remains, and stores that result as the canonical enforced value. Its callback ignores an entry while that entry is writing. A finite A-to-B-to-A chain can therefore leave A at a wrong value and promote that value to `CVSE_enforced`: correcting A to 7 causes B to drift; correcting B to 8 causes a one-shot callback to write A=99; the recursive A correction is skipped, and the outer call records 99. The original suite only exercises one-way A-to-B callbacks, which cannot expose this defect. The author accepted this as a blocking issue and is revising the implementation and real-engine coverage. A 34/34 result is valid evidence for that original suite, not proof that this broader public promise was met.

## Scope, solvability, and difficulty

The frozen full project and answer-free Confogl compilation check provide an adequate working environment. Existing release and score fixes are explicitly described as pre-applied. The intended behaviors are honestly task-authored rather than attributed to an upstream patch. Public commands and callbacks give a solver enough information to implement staging, activation, pending resolution, enforcement, and release without private oracle access.

Relative to accepted Mutant Tanks hard and LinGe hard-v3, this task has much narrower file and engine-feature breadth. Duplicate replacement, argument validation, and offset checking alone would not justify hard. Its stronger basis is the coupled state machine: registration differs from activation; whole-batch snapshots precede callback-producing writes; late binding shares activation semantics; enforcement must handle bounded values and reentrant cross-entry effects; release must relinquish hooks before restoration and support later profile ownership. With the finite-return-chain contract implemented and observed, hard is a reasonable lower-end design target. No model calibration or empirical solve-rate claim is implied.

## Test fairness and coverage

The verifier compiles and loads the complete submitted Confogl plugin. Fixtures use public server commands, a broadcast configuration forward, engine ConVars and SourceMod hooks; they do not require helper names, private array layouts, or patch equality. Exact nonce-bound case sets, one consistent final marker, duplicate detection, and runtime-exception/load/native checks prevent missing observations from passing. The callback fixture is a controlled invocation of the public lifecycle forward, not an actual map/config transition; any final documentation should retain this distinction.

The initial suite directly observes normal and bounded enforcement, two-phase activation baselines, passive and active late binding, rejected active reset, inactive release/unload, fresh reload, long strings, and diagnostic nonmutation. Recommended additions tied to explicit public promises are finite A-to-B-to-A callback return, reset and reactivation within the same plugin instance, 255-byte restoration baseline, oversized names and longer oversized values, exact end-of-list diagnostic offsets, and two late-resolved entries sharing one activation batch. The author is adding these before final validation.

The alternative is a reference-derived reversed-application-order/equivalent-string-comparison variant. It is useful evidence against one ordering requirement, not an independently designed second solution. Report-specific mutations are representative sensitivity checks, not proof that every clause is independently tested. In particular, a single release mutation does not establish that all release bugs would be caught.

## Evidence scope

Initial supplied gold run: `.rhenium/authoring/confogl-runs/l4d2-confogl-cvar-transactions-hard-gold-1789764198041434800`, 34/34, exit 0, contract `63bc9b1fcc0aff18f50966106ebaad047932cb377963a9bd995a6faaabd7732d`, pinned image `sha256:3604481021c1b605741e994fb623834fb0725b2309e53b7ed9a4c86fe3fb65cd`. Its receipt was inspected. This initial report does not claim final hash verification or approval of pending revisions.

Static inspection included the public instruction, metadata, starter and reference CvarSettings module, complete suite/common fixture/verifier, smoke helper, Dockerfiles, solution application script, control generator and runner, case map, and accepted hard-task instructions/review records. Only this review document is written by the reviewer. Repository-wide lint, type, frontend and unit checks are outside this review-only change and were not rerun.

## Final review (2026-09-19)

Decision: **PASS**. The initial gold defect is fixed. This approval covers task-local public-contract clarity, reasonable solvability, the authored hard design target, reference correctness for the reviewed behavior, implementation-independent assertions, and the supplied real-engine controls. It does not claim empirical model difficulty, exhaustive callback-order coverage, or repository-wide release readiness.

The reference now repeats a guarded entry write until its desired value is restored after a finite callback chain. It uses a numeric comparison only when the desired value is actually clamped by engine bounds; otherwise it retains exact string comparison. This avoids both promoting callback-produced drift to an enforcement baseline and treating different in-range strings as identical solely because their numeric values match. The new real-engine A-to-B-to-A case passes, while a targeted one-write mutation fails it. Activation retains the two-phase batch snapshot and release removes all enforcement hooks before restoration. The 256-byte baseline buffer preserves the tested maximum 255-byte string.

Additional cases exercise the 63-byte accepted name, a 64-byte name whose truncated prefix names a real ConVar, a 255-byte rejected desired value, a 255-byte restored baseline, two simultaneously late-bound entries, and in-range bounded string preservation. Diagnostic offset 15 now reaches the actual end of the 15-entry active list. The full candidate plugin still compiles and runs through public commands and callbacks.

### Final evidence verification

Final contract:
`7b8a1078630509ea5a29436b14dc80006783e28f146ad2968034cfc4e05b4c47`.

Pinned runtime:
`sha256:3604481021c1b605741e994fb623834fb0725b2309e53b7ed9a4c86fe3fb65cd`.

The reviewer independently recomputed the current six component hashes, all final staged source/test tree hashes, and all 24 server/verifier log hashes. All match their final receipts. All twelve published aggregate receipts match the raw local receipts, and the matrix agrees with the receipt counts, exit codes, hashes, and failed-case names. The replacement NOP run `l4d2-confogl-cvar-transactions-hard-nop-1789765504950017700` was checked separately: its staged source is byte-for-byte hash-identical to the frozen starter. The other eleven final runs remain unchanged from the independently checked batch.

All twelve runs emitted all 41 distinct raw CASE markers and one consistent FINAL, giving 492 observed cases. Ten runs have no verifier-recognized runtime error. NOP and the negative-offset mutation deliberately encounter a SourceMod invalid-index exception, so their complete-suite scoring results are zero despite some passing raw markers. This is the documented fail-closed exception policy, not an assertion that every individual observed behavior failed.

| Candidate | Scored passed / required | Raw passed / observed | Exit |
| --- | ---: | ---: | ---: |
| gold | 41 / 41 | 41 / 41 | 0 |
| alternative | 41 / 41 | 41 / 41 | 0 |
| nop | 0 / 41 | 22 / 41 | 1 |
| minus-report-1 | 33 / 41 | 33 / 41 | 1 |
| minus-report-2 | 39 / 41 | 39 / 41 | 1 |
| minus-report-3 | 34 / 41 | 34 / 41 | 1 |
| minus-report-4 | 34 / 41 | 34 / 41 | 1 |
| minus-report-5 | 39 / 41 | 39 / 41 | 1 |
| minus-report-6 | 38 / 41 | 38 / 41 | 1 |
| minus-report-7 | 0 / 41 | 41 / 41 | 1 |
| minus-finite-return | 40 / 41 | 40 / 41 | 1 |
| minus-bounded-string | 41 / 41 | 41 / 41 | 0 |

All seven required report mutations fail the intended behavior or runtime-safety requirement. The additional finite-return mutation independently exposes the initial review finding. The extra bounded-string mutation survives: the current tests exercise bounded string correction and finite callback return separately, but do not combine an in-range bounded value with same-numeric/different-string drift during its own nested correction. NOTES accurately records this limitation. The reviewed gold handles that combination through its exact-string loop condition; the surviving sensitivity experiment is not presented as evidence that the suite kills every possible defect.

### Limits retained in approval

The task is narrower than the accepted Mutant Tanks and LinGe hard examples; its hard rating rests on the interacting transaction/reentry/ownership state, not seven headings, source-tree size, or 41 assertions. It remains an author-assessed lower-end hard target without model calibration.

The late-batch fixture is order-limited: reverse pending resolution inserts B before A, and the injected cross-write is A-to-B. It does not independently eliminate every late-only single-phase snapshot implementation. Early-entry cross-write assertions exercise the common snapshot algorithm. The second active profile uses real plugin reload; the normal match loader unloads and reloads Confogl, so no public same-instance reactivation claim is made. Forward replay validates callback semantics rather than a complete map transition. Release ordering is statically reviewed and real release behavior is observed, but arbitrary third-party restoration-hook interactions are not exhaustively tested.

These limitations are documented and do not introduce an undisclosed oracle or contradict the final reference. No blocking review finding remains. The reviewer did not rerun an engine, conduct a model experiment, or modify any file other than this review. `git diff --check` passed during review; repository-wide lint/type/unit/frontend gates were not rerun for this documentation-only review.
