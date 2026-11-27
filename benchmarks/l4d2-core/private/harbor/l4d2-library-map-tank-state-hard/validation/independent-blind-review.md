# Independent blind review

Status: PASS. No unresolved blocking finding.

Reviewed on 2026-09-19 as repository maintenance. This reviewer independently read the public instruction, starter L4D2Lib sources, both private suites, verifier, and reference implementation before reading NOTES or control results. Neither `independent-review.md` nor another reviewer's report was read. No model attempt or new engine run was performed. Only this review file is authored by this reviewer.

## Resolved public-contract clarification

The initial blind read identified that report 4 promised geometry for all "valid origin-bearing entities" while the reference supports positioned networked entities through `Prop_Send` `m_vecOrigin`. The final instruction now explicitly states that supported domain and returns Neither for worldspawn, non-networked entities, or entities without that property. This is a reasonable preservation of the existing native rather than a claim of new data-map geometry support. The final suite also asserts worldspawn rejection and successful subsection-copy replacement of pre-existing destination children. Both additions observe public contract behavior and do not constrain the patch. The original scope mismatch is resolved; remaining unexercised entity categories are disclosed as coverage limits.

## Solvability and reference implementation

The eight reports otherwise form a coherent, implementable task. Public instructions specify observable behavior and compatibility, including zero-based passes, duplicate event handling, transactional import failure, nested subsection paths, caller buffer capacity, connection identity, and reentrant observers. The starter contains the target implementation and the public compile smoke check; no hidden helper names are needed to solve it.

The reference uses a temporary KeyValues image and syntax validation before swapping it, reselects the current map before each value/copy operation, preserves defaults, writes output-only native arrays without reading them, and bounds string copies by the supplied capacity. Its saferoom calculations implement inclusive spheres and naturally disable negative effective radii. It retains the existing medkit fallback and clears stale end geometry when a valid file lacks the map. Tank ownership is committed using connection serials; timer cancellation, identity checks, and reset-before-observer ordering make nested transitions survive callback return. The top-level plugin invokes reset on map end. Source review found no remaining requirement/reference blocker.

## Fairness and evidence

All 43 behavioral verdicts observe public natives, forwards, engine events, actual KeyValues operations, client properties, disconnects, and timers. The complete submitted L4D2Lib is compiled and loaded. Tests do not inspect a particular private helper, variable layout, or reference diff. The trusted Confogl fixture invokes the library-added callback contract; it is not an actual provider unload/reload integration test. The verifier requires the exact case set, one final marker, correct totals, and no SourceMod runtime exception. NOP's 0/43 is a fail-closed score and does not mean every raw engine marker failed.

Reviewed evidence is the 12 controls under `.rhenium/authoring/library-accepted-controls`, bound to contract `c25bb16c312a4c750ec4a238b72900b8c13865f871226c340d59b0debf914cce`. Independently recomputed all six current component digests with lexical POSIX paths and NUL-delimited exact bytes; all matched the gold receipt. Independently recomputed all 24 server-log SHA-256 values; all matched their receipts. Read the gold engine markers: map 22/22 and Tank 21/21, including actual slot reuse; final gold and alternative logs additionally confirm the strengthened subsection-copy/worldspawn case predicates pass. Receipts report gold and alternative 43/43, NOP 0/43, each of eight omission controls failing, and the death-postponement control 39/43. The controls name immutable runtime image `sha256:3604481021c1b605741e994fb623834fb0725b2309e53b7ed9a4c86fe3fb65cd`. This verifies existing recorded evidence, not a fresh independent engine execution.

The alternative changes distance arithmetic and count increment form but derives from the reference. It supplies limited evidence against one exact-patch requirement; it is not an independent solution. Eight representative omissions plus a timer-postponement mutation demonstrate meaningful sensitivity without proving every possible broken implementation is rejected.

## Coverage boundaries

NOTES accurately discloses unexercised initial import failure, explicit negative radii, observer-triggered round resets, and a full map transition. Additional limits observed here: no explicit free-slot or separately constructed non-networked/property-less entity geometry case; the medkit heuristic is preserved by source inspection rather than directly asserted; most scalar/vector/default behavior is sampled rather than exhaustively combined. Worldspawn rejection and replacement of old destination children are now asserted. These limits are not evidence that those paths fail. They must not be presented as exhaustive verification of the complete public contract.

## Difficulty assessment

Compared against the actual instructions of accepted `l4d2-linge-release-regressions-hard-v3` and `l4d2-mutant-tanks-release-regressions-hard`, this task is narrower: two active L4D2Lib modules and their lifecycle wiring, rather than broad damage/accounting or multi-ability systems. Nevertheless, hard is defensible because a correct repair must coordinate transactional configuration, shared cursor isolation, SourcePawn native memory contracts, timers, connection reuse, and callback reentrancy. The hardest errors concern transitions after a seemingly correct immediate fix, not merely eight unrelated conditional edits. Treat this as an author/reviewer difficulty judgment; no model calibration or empirical success-rate claim is available.

`git diff --check` passed during review. Repository-wide lint/type/unit/frontend checks were not rerun for this documentation-only review. No benchmark source, tests, solution, or existing review was modified by this reviewer.


