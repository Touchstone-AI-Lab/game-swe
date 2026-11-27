# Approved native maintenance validation v1

Maintainer: Sangyu Pan. Authorization: `RUNTIME-APPROVAL-v1.md`.
This supplements the historical entry-only plan and never updates its evidence.

The adapter binds the frozen Python 3.13 controller and byte-identical pack-local
authored fixtures. It relocates only the Runtime initializer's generated-state
root and the smoke evidence location, adds cancellation observation between RPC
calls, and verifies a versioned result envelope. It leaves original RPC timeouts,
single-send actions, start/load readiness, scoring, lifecycle and cleanup intact.
No task semantic, required assertion, gold, base or mutation changes are made.

Before final controls: one fresh matching smoke and a growth gold/base pilot;
source review, unit/contract tests, wheel inspection/install, final source freeze,
new state binding and fresh matching smoke for the installed wheel.

Final core matrix: task order from `assets.json`; for each of three repetitions,
each task's gold immediately followed by base. All 60 flows use newly prepared
strict anonymous attempts through installed CLI `prepare-attempt` and exactly one
`run-attempt --profile full --security-mode honest`. The existing task scenarios
require 168 native processes in total, not one process per flow.

The following targeted controls were selected before their native execution.
Each runs the full unchanged task suite once, using the same platform entry.

| Task | Error control | Adapter regression purpose |
| --- | --- | --- |
| growth-v2 | M03-per-hand | A complete wrong callback lifecycle remains a behavior failure |
| reversible-hand-limit-v1 | M02-no-remove | Removal cleanup is observed by real subsequent play |
| seeded-effect-stream-v1 | M03-score-advances | All seed/restart scenarios remain required |
| bounded-generator-v2 | M02-fixed-release | Reservation leak and later operation evidence survive transport |
| deck-removal-consistency-v2 | M02-area-only | Physical/global object checks remain distinct |
| live-joker-adjacency-v2 | M02-stale-index | Multi-instance reorder behavior remains rejected |
| isolated-card-wear-v2 | M04-additive-refresh | Refresh lifecycle is not reduced to one successful use |
| durable-charge-v2 | M06-display-only | Real restored score cannot be replaced by display equality |
| shop-price-coherence-v2 | M04-stale-accepted | Structured business rejection is preserved |
| pack-choice-commit-v2 | M07-repeat-commit | Repeated commit and delayed settlement remain distinct |

Correct alternatives: growth `alternative`, durable `gold-journal`, price
`gold-ledger`, pack `gold-journal`. These protect implementation independence.
Targeted matrix: 14 flows, 40 native processes. Other historical mutation roles
are retained byte-for-byte but are not claimed as revalidated by this matrix.
The scope is justified by unchanged task assertions/control code; the new common
adapter is covered across every task and lifecycle, with malformed-result and
process-ownership tests. Expand only if new evidence identifies an uncovered risk.

`scripts/native_matrix_v1.py` records the plan before starting, saves immutable
per-flow records and numbered progress snapshots, and stops on incomplete or an
unexpected control outcome. It never retries an action or a workflow. Any recovery
requires diagnosis and a new evidence directory; completed flows are not silently
replaced. The evaluator grades semantic checks, never role names. Role-specific
expected failures are checked only by this operator regression script afterward.

Checks that cannot run on this host remain failed/unrun in the final report.
No claim of model calibration, arbitrary submission safety, generic MENU loading,
managed licensed acquisition or disposable evaluation-host support is made.
