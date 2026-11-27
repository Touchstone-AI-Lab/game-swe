# Re-review disposition: PASS

Final review date: 2026-09-19. The current **41-case version passes independent review**. This supersedes the initial NEEDS_REVISION disposition preserved below. Approval applies to the examined contract `6b27303496e551ec48444d854021c090f2d946c41c20c99552f5a27bba74b49c`; it does not pre-approve subsequent semantic edits or claim model-derived difficulty calibration.

## Resolution of initial blockers

- **R1 resolved.** Gold cache_restore captures the desired cached state before disabling Config.enabled and executing cleanup. Valid and invalid restore cases now begin with active quantity, whitelist, interval, initial-delay and common-cleanup options, then check that all corresponding Director keys are absent before round start. Desired-state transition cases remain present.
- **R2 resolved.** Valid-file Save and SaveAll now check modified registered values, a second registered section and the unrelated Other section. Bulk reserveKey=false is explicitly exercised. Cleanup is tested through real infected entities: an enabled controller removes the first entity and a disabled controller leaves a subsequently spawned entity valid after another timer interval. The NoOverrides helper enumerates all relevant Director keys. These cases observe public effects without requiring a private timer name.
- **R3 resolved.** Thirteen current-contract controls are retained with component, source, staged-test, verifier-log and server-log hashes, immutable runtime image identity and complete per-case results. Both gold runs and the alternative pass 41/41. NOP fails 30 cases, passing 11/41. Each of the nine report-removal controls fails at least one case, executes all 41, and fails only cases mapped to its own public report.

The three original case weaknesses are repaired: prepend retains an original tail callback, the whitelist duplicate count changes the expected ceiling, and invalid-cache desired state is established explicitly. Top-level array payload ownership is now covered. The public instruction clarifies current registered values on malformed-file recovery and the existing registration requirement for delayed events.

## Independent evidence audit

The reviewer independently recomputed every recorded component hash against the current task, every staged source/test hash, every raw verifier/server log hash, and the overall contract digest for all 13 receipts. Committed receipt values were compared with their raw local receipt.json counterparts. Every raw verifier log contained exactly the 41 mapped unique case names, and every report-removal failure belonged to that report. Raw engine logs were separately reparsed with the current verifier parser: duplicate/final-marker consistency and reported pass counts matched all receipts.

Recorded results: gold 41/41 twice; alternative 41/41; NOP 11/41; minus-report-1 through minus-report-9 respectively 37, 39, 36, 38, 37, 39, 39, 40 and 35 out of 41. No required case is skipped or missing in these controls. The alternate uses a different numeric-index reconstruction algorithm and different snapshot, persistence and whitelist implementation choices; it is sufficient to demonstrate that those assertions do not require the reference helper layout or patch text.

The reviewer used read-only repository mounts in the already available image for hash and log analysis. The reviewer did not independently launch another game server; runtime findings rely on the inspected author engine runs, whose retained evidence and exact content binding were independently checked. This is an authored-task acceptance decision, not a fresh model/exam score or an empirical hard calibration.

## Remaining nonblocking limitation

The current hash helper sorts pathlib.Path objects, so tree-hash order follows the author's Windows path-component ordering. Linux's default Path sorting produces a different digest for the same mixed-case tree. The independent audit reproduced the recorded hashes using PureWindowsPath ordering. Record that algorithm/platform detail alongside these receipts; a future portable hashing change should be versioned and must not silently relabel these existing digests. This portability limitation does not invalidate the verified current-content correspondence or engine results.

The original inherited anti-probe heuristic remains limited, as noted below. It is not represented here as comprehensive tamper protection. Hard remains a defensible design target, and the repaired baseline continues to distinguish this task from hard-v3's HUD/Hint/RewardHP defects.

---
# Independent review: LinGe Director state hard

Decision: **NEEDS_REVISION** (initial 36-case authoring draft, 2026-09-19).

This is an independent repository-maintenance review, not an exam attempt. The reviewer read the worktree AGENTS.md, inspected status, and reviewed instruction.md, task.toml, NOTES.md, all 36 original suite cases, verifier/fixture code, Base and MoreSI starter/reference differences, and the accepted LinGe hard-v3 and Mutant Tanks hard contracts and validation records. Only this review document was created by the reviewer. Authoring was continuing concurrently; amendments require a follow-up review and current-contract runtime evidence.

## Assessment

The task is viable and structurally credible as a hard repository debugging task. Its nine reports cover three substantial areas: recursive configuration ownership/migration, reentrant and delayed event dispatch, and Director configuration/lifecycle. It uses an actual existing MIT project and retains its API and addon integration. Base changes affect multiple addon clients, making compatibility reasoning material. The reference remains localized to Base.nut and MoreSI.nut and uses the existing cloning and VSLib infrastructure.

The task is not a duplicate of the accepted LinGe hard-v3 defects. Comparing starter trees showed changes only in HUD, Hint and RewardHP; these correspond to the prior task's repaired baseline. The new reports instead target Base and MoreSI. Mutant Tanks covers a different SourcePawn codebase and unrelated gameplay regressions.

Hard is defensible as a design target, not a measured capability classification. This draft gives much more direct diagnoses, API names, and algorithms than hard-v3, and has less cross-file search difficulty than Mutant Tanks. Its difficulty must come from correctly handling the combined ownership, reentrancy and lifecycle contracts. The existing NOTES appropriately disclaims model-derived calibration. No paid/model run is required merely to resolve this review, and no empirical hard claim is supported by the evidence inspected.

Most assertions inspect public API results, persisted files, callback order and Director option values. No helper-name or exact-reference-diff oracle was found. The real timer path is retained. The Squirrel-only config/event assertions are correctly described as VM-level API scenarios, rather than simulated campaign behavior or measured spawn frequency.

## Blocking findings

### R1: cache restore disables a flag but leaves the live controller active

The original gold MoreSI.cache_restore reads the cached desired state and sets Config.enabled=false, but does not clear SessionOptions or stop the common-infected cleanup timer. Reproduction from the code is: enable quantity/whitelist/respawn/common cleanup, dispatch valid or invalid cache_restore, inspect the interval before round_start. The old cm_MaxSpecials and related overrides remain active, and AutoKillCI remains scheduled. This contradicts report 9's statement that restore keeps live MoreSI disabled until round start.

The original valid-cache test begins disabled. The invalid-cache test checks only Config.enabled. Neither detects the live-state violation. Required revision: disable the actual controller during restore while preserving the desired state; test enabled-to-valid and enabled-to-invalid restore against observable overrides before round_start and desired state afterward. The author acknowledged this finding and proposed a fix; it is not accepted until revised evidence is reviewed.

### R2: cleanup and persistence preservation promises have material blind spots

No original scenario enables sinoci=true. Therefore report 9's cleanup-timer removal promise can be broken entirely without affecting any case. The idempotent-disable check samples only five override names and omits cm_CommonLimit, cm_BaseSpecialLimit, several class limits and SpecialInitialSpawnDelayMax. Required revision: enable common cleanup, demonstrate its observable effect on a real infected entity, disable, and demonstrate that a newly created infected survives after the previous timer interval. Do not require a private timer name. Cover the relevant override cleanup too.

The original config-single-recovery-and-preservation case calls Save only on malformed input, and Load on a valid file. It never verifies Save on a valid file preserves Other. No case directly tests SaveAll on a valid file with unrelated sections and changed registered values. A reconstruction-only Save/SaveAll implementation can drop unrelated data yet pass the original cases. Required revision: valid-file Save and SaveAll round trips with at least two registered sections and an unrelated section, checking both new registered values and preserved unrelated content.

### R3: controls do not yet establish acceptance of the final contract

The inspected gold run `l4d2-linge-director-state-hard-gold-1789760241016195900` reports 36/36 with exit 0. The inspected NOP run `l4d2-linge-director-state-hard-nop-1789760275994868400` reports 12/36 with exit 1, completes all cases, and fails intended config/event/Director defects. These are useful real-engine receipts, not proof of a subsequently modified suite. No independent engine process was launched by this reviewer.

At the initial inspection, task validation contained only case-contracts.tsv. The receipts retained container identifiers but not a frozen contract digest or immutable runtime/verifier image IDs. No completed alternate-implementation or defect-group controls were available for review. In comparison, both accepted quality baselines retain detailed differential/predicate/control matrices and contract hashes.

Required revision before acceptance: finalize the suite; bind evidence to instruction/tests/solution/starter hashes and immutable image identity; run current-contract gold and unchanged NOP through every required case; retain at least one meaningfully different valid implementation control, and targeted defect-group regressions showing that partial repairs cannot pass. Distinguish runtime failures, unexecuted cases and behavioral failures. Preserve raw generated logs outside the benchmark tree. Source/hash receipts and compact matrices may be committed under validation.

## Author-discovered issues independently confirmed

- The original prepend case had only one original subscriber. The old implementation therefore passed it. Add an original tail subscriber so mutation changes the current traversal observably.
- The original quantity-disabled whitelist used three entries for two distinct classes. ceil(4/3) and ceil(4/2) both equal 2, so it did not distinguish duplicate counting. Use a duplicate count that changes the ceiling.
- The invalid-cache desired-state case could inherit _enabled from preceding cases. Establish its desired state explicitly through supported commands/cache transitions before the action being tested.

The author notified the reviewer of these findings and is revising them. A failure-inducing case should establish its own initial state and not rely on a preceding regression being repaired. The common ResetSI helper's use of public sioff is acceptable when complete NOP execution demonstrates it does not abort the entire suite.

## Additional recommendations and contract clarity

- Add a direct reserveKey=false bulk-load test. Merge's separate unknown-key guard helps, but does not establish that LoadAll passes the requested policy into each registered section.
- Exercise an array as the top-level event payload as well as nested arrays. The public contract explicitly permits both table and array payloads.
- Clarify whether delayed dispatch of a never-registered event is in scope. The starter and original gold queue only previously registered event names. Preserving this behavior is reasonable, but the broad phrase 'select subscribers when the delay expires' can imply that a later first subscription should receive a previously queued event. Do not add that interpretation as a hidden assertion without stating it publicly.
- Document that 'currently registered defaults' on malformed files means the current registered tables, if that is intended. The original gold does not retain a pristine registration-time snapshot after values have been changed. The current cases use fresh defaults only.
- The inherited verifier only scans HUD.nut for explicit verifier-probe strings even though this task edits Base/MoreSI. This is not an observed ordinary-solution false positive, but the inherited anti-probe heuristic should not be represented as broad tamper protection.
- Bootstrap/real-player and 55-second server deadline behavior should be covered by repeat gold runs. A fixture failure before Finish correctly fails closed, but its missing-case outcome must not be mislabeled as a candidate's behavioral defect.

## Acceptance conditions

Resolve R1 and R2, repair the three confirmed case weaknesses, and supply R3 evidence for the final suite. Re-review the amended prompt/reference/test alignment and observed controls. Keep the task uncatalogued until that review returns PASS. Current status is NEEDS_REVISION; the earlier 36/36 gold result must not be used to mark the amended task accepted.

