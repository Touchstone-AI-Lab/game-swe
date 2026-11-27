# Independent maintenance review

Verdict: **PASS** for the clarified geometry/copy contract and its final controls.

A subsequent context-free review clarified the supported entity-property
boundary and added observations for worldspawn rejection and present-copy
replacement. This reviewer rechecked those changes and all twelve new controls;
the final evidence below includes those revisions.

Review completed on 2026-09-19. This reviewer was newly assigned to this task but
received parent conversation context; this is an independent source/evidence
review, not a claim of a context-free blind review.

This fresh reviewer was assigned only this task, read the repository maintenance
rules, task specification, frozen affected source, reference replacements,
private suites, verifier and candidate runner, and compared the task with the
accepted LinGe hard-v3 and Mutant Tanks hard tasks. The reviewer changes only
this review file; implementation and suite changes belong to the author.

## Initial findings

The eight reports are reasonable release requirements. Map image replacement,
cursor independence, native output capacity, geometry, event eligibility, delayed
death ownership, connection identity and reentrant observers are distinct
contracts. The starter contains corresponding observable faults. Public API
compatibility and source-only packaging remain explicit requirements.

Author-assessed hard is justified by the interaction of shared KeyValues state,
connection lifetimes, timers and synchronous observer reentrancy. This is at the
lower end of the accepted hard tasks: less broad than Mutant Tanks, but materially
more complex than a set of isolated parameter corrections. No empirical model
difficulty claim is established by these deterministic controls.

The reference stages an incoming map image before replacing the last valid one,
reselects the current map for each lookup, honors native capacities, and commits
Tank ownership and pass numbering before forwarding notifications. Death state
is retired before observers run. SourceMod connection serials and disconnect
cleanup protect replacement clients. No blocking reference/spec contradiction
was found during source review.

Private observations use public natives and forwards, dispatched game events,
real entity properties, and actual SourceMod timers. They do not require private
helper names or a prescribed patch. Present-subsection copies correctly follow
the engine's CopySubkeys behavior; missing copies must preserve their target.
The slot-reuse fixture has a real disconnect and new connection. Its fixture
assertion intentionally fails closed if index reuse was not actually exercised.

The following findings were resolved before final acceptance:

- The duplicate-death scenario initially dispatched both deaths in the same
  frame. A wrong implementation that restarted the timer on each duplicate
  would pass. The revised fixture separates events by 0.30 seconds and checks
  0.65 seconds after the first event. Its deliberate postponement control fails.
- The public specification now explicitly states slash-separated subsection paths.
- The original report-2 mutation used a correct native slash-path lookup and
  passed. It was replaced with a genuinely cursor-dependent integer lookup;
  the final mutation fails the lookup after a nested copy.
- The author strengthened the handoff cancellation observation after noticing
  that merely counting death notifications missed a timer silently resetting
  the new owner. The final case observes another transfer's owner and pass count
  after the old timer deadline. Its dedicated mutation fails.
- The final public geometry contract explicitly uses the existing networked
  `m_vecOrigin` send-property domain; worldspawn and unsupported entities return
  Neither. The suite additionally checks worldspawn rejection and replacement of
  destination children for a successful subsection copy. These expectations are
  now explicit, consistent with the reference and appropriate to the native API.

## Final evidence verification

The reviewer independently recomputed the six component digests, the assembled
contract, all twelve materialized source/test tree hashes, twelve verifier-log
hashes and twenty-four engine-log hashes. Committed receipts exactly match their
local originals apart from the documented local-run locator. The NOP source tree
is byte-identical to the starter. All eight report mutations fail a case mapped
to their own public report, and the extra postponement mutation fails the timing
case. Package checks and compilation succeeded for all candidates.

Final contract:
`c25bb16c312a4c750ec4a238b72900b8c13865f871226c340d59b0debf914cce`.

Immutable runtime:
`sha256:3604481021c1b605741e994fb623834fb0725b2309e53b7ed9a4c86fe3fb65cd`.

Final raw evidence directory: `.rhenium/authoring/library-accepted-controls/`.
Earlier `library-reviewed-controls/`, `library-final-controls/` and
`library-runs/` are superseded diagnostics.

| Candidate | Scored cases passed |
| --- | ---: |
| gold | 43/43 |
| alternative | 43/43 |
| NOP | 0/43 |
| minus-report-1 | 41/43 |
| minus-report-2 | 42/43 |
| minus-report-3 | 41/43 |
| minus-report-4 | 42/43 |
| minus-report-5 | 36/43 |
| minus-report-6 | 42/43 |
| minus-report-7 | 42/43 |
| minus-report-8 | 42/43 |
| minus-death-postponed | 39/43 |

Each non-NOP run has exactly 43 raw CASE markers and two consistent FINAL
markers, matching every recorded verdict. NOP has 21 raw Tank CASE markers,
eight passing, and one FINAL; its map boot has no completed marker contract.
The NOP Tank plugin emits an invalid first-spawn client of zero, which also
causes the observer's diagnostic GetClientSerial call to throw. Its 0/43 score
therefore reflects fail-closed suite validation, not 43 separately observed
behavioral failures. The remaining Tank failures and report mutations provide
direct sensitivity evidence without relying solely on that exception.

## Limits and conclusion

The alternative is reference-derived, using equivalent squared-distance geometry
and explicit count commitment; it is not an independently designed solution.
NOTES truthfully distinguishes the public lifecycle-forward replay from a full
provider reload and records unexercised initial-import-failure, negative-radius,
observer-round-reset and full-map-transition paths. The raw engine is real, but
these focused fixtures do not establish end-to-end managed-worker support.

No paid/model calibration was run or claimed. The review establishes a reasonable,
solvable, author-assessed hard task with fair public-contract observations and
verified positive/negative controls, within the coverage limits stated above.
