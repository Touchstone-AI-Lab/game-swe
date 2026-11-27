# Independent review: competitive score lifecycle

Reviewer: fresh review agent, without author implementation history. Date: 2026-09-19.

Final decision: **PASS** for the revised 57-case contract; see the final re-review addendum below. Historical initial decision: **NEEDS_REVISION** (53-case draft). This is a benchmark-authoring review, not an exam attempt. The reviewer read the public contract before inspecting private fixtures and reference changes, did not write a reference implementation, did not run a model experiment, and did not modify the shared engine container.

## Required revisions

1. **Zero-debit ledge episodes are not represented.** In the reviewed reference, `OnPlayerLedgeGrab` uses `iLedgeDebt[client] > 0` to identify an outstanding episode. A grab whose pre-incap temporary health is zero (or negative before normalization) creates an episode with zero debt; a duplicate grab with a positive reported buffer is then accepted and adds loss. Public report 5 promises one nonnegative debit per outstanding episode, including zero. Represent episode existence independently of its amount and add engine cases for zero and negative initial debit followed by a duplicate grab with positive input. A normal subsequent episode must still be accepted. This is a concrete reference-contract defect, not an implementation-style preference.
2. **Clarify the zero-player roster contract.** Public report 3 says to use at least one player in divisor calculations. Hidden `bounds_zero_team` additionally requires a one-player effective roster and one-player maximum budget. State explicitly that `max(1, configured survivor_limit)` governs roster selection and all coefficients as well as divisors, so a solver need not infer this extra normalization from the reference.
3. Refresh all controls against the resulting final instruction, tests, solution and case map. The reviewed gold receipt is valid evidence for the old 53-case contract only. NOP, alternative and seven group-reversion receipts were still pending at initial review.

## Additional coverage feedback

The initial `round_finalized_ledger_frozen` case covers ADM, incap and death events, but does not exercise real SDKHooks damage or the player-hurt path, despite its broad description. Add a finalized-round real damage check and confirm that health actually changes, so a frozen-ledger result is not a no-op fixture. The initial suite also does not independently prove every client snapshot-clear path. Group 6 currently reverts only `RoundStartEvent`, so it is not evidence that every closed-round guard is necessary. These observations should remain distinct from complete-match coverage claims.

## Findings that support the design

- The complete Competitive Rework source tree, its GPL license, the public compile smoke helper, and one clearly identified target plugin make the repair scope discoverable. Existing easy-task repairs are explicitly identified as already included; the new contracts are honestly described as task-authored, not historical upstream patches.
- The ordinary score formula is preserved: map budget is distance times multiplier times effective team size; health/damage pools split by proportion; interior temporary capacity is `team * 100 * (1-p) / p`; the exposed results are floored. Existing first-N roster selection and post-incap permanent-health policy remain visible in the starter. Test arithmetic for the normal proportion, live proportion, team-size repricing and bounded pills agrees with this formula.
- Fixtures observe the public `SMPlus_*` natives, public compatibility/end-round forwards, ConVars, game rules, real client entities, public events and deferred frames. They do not inspect candidate-private variables, require reference helper names, compare patches, or load a reference implementation into the verifier.
- Deferred ledge sequences include duplicate events, event-time versus next-frame buffer changes, bounded refunds, new rounds, halves, new episodes, team transitions, death, finalization and queued disconnect. The coop half-property setup is documented honestly; setting it immediately before the callback is a controlled public-engine-state fixture rather than a private callback shortcut. Unload checks allow SourceMod's deferred unload to complete.
- The verifier compiles candidate score and L4D2Lib sources and private Left4DHooks with the pinned SourceMod toolchain, then boots five separate real L4D2 dedicated-server processes. Exact nonce-bound case sets, one consistent FINAL, duplicate detection, and runtime exception/unbound-native/load-failure detection prevent missing assertions from passing. Public smoke is answer-free and cannot substitute for the engine gate.
- The alternative candidate changes connection identity from serials to user IDs and uses alternate bounded-minimum/normalization expressions. That is useful evidence against a narrow implementation prescription, although it is a transformed reference rather than an independently authored complete second solution.
- Stateful coupling between live coefficients, losses, ledge episodes, round identity, connection identity and ConVar ownership supports the hard **design target**. Source-tree size and assertion count alone do not establish difficulty. No model calibration has been performed or inferred; comparisons with the existing Mutant Tanks hard and Linge hard-v3 tasks are qualitative only.

## Evidence inspected

Initial gold run: `.rhenium/authoring/score-runs/l4d2-competitive-score-lifecycle-hard-gold-1789761892993103700`.

- Receipt exit code 0, 53/53 cases, contract `74320e7a82436cef4872b40fcf43597ad5871e2ee0069191ed06fb6c02c09ee2`.
- Runtime image `sha256:3604481021c1b605741e994fb623834fb0725b2309e53b7ed9a4c86fe3fb65cd`.
- Raw logs show real `Game_srv.so` loaded for Left 4 Dead 2 and suite FINAL totals of 14, 12, 13, 12 and 2.
- Reviewer independently recomputed the five server-log SHA-256 values and verifier-log SHA-256; all six matched the receipt. This does not imply the pending revised task has the same contract hash.
- Static inspection covered instruction, task metadata, starter scoring formula, full reference source, all five suites, common fixture, verifier, smoke helper, Dockerfiles, control materializer and runner, and the existing hard tasks' maintainer records.
- `git diff --check` passed before writing this report. No engine was rerun by the reviewer. Full repository lint/type/test/frontend checks were not rerun for this review-only document.

Acceptance requires the fixes above and a final evidence addendum; this initial decision is not a final task rejection or a claim that the known 53-case gold run failed.
## Final re-review addendum (2026-09-19)

Decision: **PASS**. All initial required revisions are resolved. This approval covers public-contract clarity, solvability, implementation-independent observations, authored hard-design rationale, and the supplied real-engine validation. It is not a model-calibrated difficulty or failure-rate claim.

The reference now tracks outstanding ledge existence independently of debit amount. Zero/negative initial debit establishes an episode, duplicate grabs cannot turn it into a positive charge, and round/team/death/disconnect invalidation clears the active state. Revival consumes the episode even when its debit is zero, permitting a genuinely later episode. Two added cases expose the original omission. The prompt explicitly applies the effective survivor limit to roster selection, maxima and divisors.

Two further cases observe finalized-round SDK damage and a plasma hurt event. The SDK fixture really respawns its client with `L4D_RespawnPlayer` before applying damage. In the final gold raw log, the temporary buffer changes from 51 to 42 while damage bonus stays 200; in `minus-finalized-guards`, the same buffer change yields 186. This resolves the concern about an unspawned fake client producing a vacuous no-op pass. The dedicated guard mutation fails exactly the two newly added terminal-damage checks.

### Final controls and independent evidence verification

All eleven controls bind to contract:

`777cec4df8806854c5071ffb0f346e816de9dfa2bb4985da2e45d1455d55c55c`

The source task's `validation/control-receipts.json` and `validation/control-matrix.tsv` retain individual cases, hashes and run identifiers. Raw source, tests and logs are under `.rhenium/authoring/score-reviewed-controls/<local_run>`; those local generated artifacts are not benchmark source assets.

| Control | Passed / executed | Exit |
| --- | ---: | ---: |
| gold | 57 / 57 | 0 |
| alternative | 57 / 57 | 0 |
| nop | 17 / 57 | 1 |
| minus-report-1 | 54 / 57 | 1 |
| minus-report-2 | 49 / 57 | 1 |
| minus-report-3 | 46 / 57 | 1 |
| minus-report-4 | 52 / 57 | 1 |
| minus-report-5 | 45 / 57 | 1 |
| minus-report-6 | 44 / 57 | 1 |
| minus-report-7 | 55 / 57 | 1 |
| minus-finalized-guards | 55 / 57 | 1 |

The reviewer independently recomputed all six current component hashes (instruction, task metadata, environment, tests, solution, case map), all eleven staged source-tree hashes, all eleven staged test-tree hashes, and all 66 raw server/verifier log hashes. Every value matches the final receipts. The reviewer then matched all 627 raw CASE verdicts to the receipts, confirmed five FINAL markers per control (55 total), and checked that no inspected run contains the verifier's runtime-exception, unbound-native or failed-load signatures. Each run executed all 57 named cases; failed controls are behavioral failures, not missing engine assertions. The final evidence uses the same immutable runtime image ID recorded in the initial review.

The broken starter fails, complete gold and the alternative pass, every report-group reversion fails its intended behavior, and the extra guard mutation confirms the newly covered terminal damage paths. Some failures overlap between report groups because coefficients, ledger resets and deferred work interact; this is explicitly documented and not represented as seven orthogonal tests.

### Remaining limits

This is focused real-engine contract validation using controlled client/entity properties and event sequences, not a full competitive match simulation or exhaustive exploration of every callback ordering. The initial note about not independently proving every snapshot-clear path remains applicable. The alternative is a meaningfully different identity/refund expression over the reference, not a separately authored complete solution. No model experiment was run, so `hard` remains a supported design target rather than an empirically calibrated model result.

The reviewer did not mutate or rerun the engine container. Full repository lint/type/unit/frontend checks are outside this review-only change and were not rerun here. Only this independent-review document was edited by the reviewer; no reference implementation was written by the reviewer. No blocking review finding remains for the hash-bound final contract above.
