# E0 notes: l4d2-competitive-score-lifecycle-hard

Workspace layout: `/app/l4d2-competitive`; every overlay uses `root = l4d2-competitive`. Clause ids are `R<report>.<n>` for the numbered reports (anchor = report, sentence, short quote) and `Task-*` for the surrounding paragraphs.

Baseline through the operator Hub full profile (`rhenium run`, Linux x86_64 Docker host, 2026-09-24, verifier image `sha256:fa0c3e08df24...`): unchanged starter 17/57 (`run-f96d18bd6faf4b3c`, complete, score 10); reference 57/57 three times with identical case outcomes (`run-3c93b754ae484cdd`, `run-d243a61e85854271`, `run-bc3e81354a474863`, score 100). These are not study-Hub records: the study Hub must be re-seeded from the operator database before `rhenium-study e0` can reproduce them, because the verifier images changed on 2026-09-24.

Every overlay patches `addons/sourcemod/scripting/l4d2_hybrid_scoremod_zone.sp`, the only
file the oracle changes. The seven reports are task-authored contracts over the frozen
upstream plugin (`task.toml` `gold_solution_origin`), not reverted upstream commits.

## Preserved contracts (all `P` in the unchanged starter)

| case | public statement |
| --- | --- |
| `score_normal_budget` | R1 s4c ordinary living/upright scoring; R2 s3 ordinary formula; `SMPlus_*` natives |
| `score_incap_excluded` (overlap) | R1 s3 for incapacitated Survivors (already excluded in the starter) |
| `score_falling_excluded` (overlap) | R1 s3 health half for a falling Survivor |
| `score_revived_health_policy` | R1 s4b permanent-health treatment after an incapacitation |
| `score_upright_pills` | R1 s4c carried pills of an upright Survivor |
| `live_multiplier_preserves_loss` (overlap) | R2: a live multiplier change keeps the incurred loss |
| `live_proportion_reprices` (overlap) | R2: a live proportion change reprices the ledger |
| `score_roster_limit` | R1 s4a first `survivor_limit` roster selection |
| `bounds_one_proportion` (overlap) | R3: proportion 1 gives a finite zero damage pool |
| `bounds_endpoint_events` (overlap) | R3: incap/death callbacks at proportion 1 |
| `adm_positive_loss` | R4 s4 valid ordinary deductions |
| `adm_negative_after_clamped` (overlap) | R4: negative new health clamps to zero |
| `round_independent_half` (overlap) | R6: second-half losses stay independent |
| `round_end_idempotent` | R6 s4 one-shot finalization |
| `adm_tiebreak_compatibility` | R4 s4 existing tiebreak accounting |
| `round_finalized_sdk_damage` (overlap) | R6 s3 finalized ledger frozen against real SDKHooks damage |
| `round_finalized_plasma_event` (overlap) | R6 s3 finalized ledger frozen against a late plasma hurt event |

There is no separate load sentinel: each of the five boots prints nothing unless the
plugin, L4D2Lib and Left4DHooks load, and a SourceMod exception fails that boot.

## Controls (all executed through `rhenium run`; all behaved as declared)

- `tn-unload-baseline-unfixed` (target-negative): the oracle with the starter's `OnPluginEnd` put back (report 7 unrepaired, `validation/candidates.py` minus-report-7). Observed: `run-d432f0ffcebd4255`, 55/57, failing `unload_new_instance_snapshot`, `unload_restores_startup_values`.
- `cn-dead-survivor-frees-roster-slot` (compat-negative): the oracle plus a two-line over-fix of report 1: the health-bonus loop skips dead Survivors before counting the roster, so a later living Survivor takes a dead player's `survivor_limit` slot. The report explicitly preserves the roster selection. Observed: `run-2d963a8fcf7f4399`, 56/57, failing `score_roster_limit`.
- `cn-finalized-damage-guards-removed` (compat-negative): the oracle without the `bRoundOver` guards in `OnTakeDamage`, `OnTakeDamagePost` and `OnPlayerHurt` (`validation/candidates.py` minus-finalized-guards). The starter never debited a finalized round, so the two finalized-damage cases are preserved and this is a compat-negative, not a target-negative. Observed: `run-1bf073f21c164232`, 55/57, failing `round_finalized_plasma_event`, `round_finalized_sdk_damage`.
- `alternative-userid-bounded-refund` (alternative): the pack's reference-derived alternative (connection user ids for deferred ledge refunds, an explicit bounded minimum, independently clamped ADM inputs). Observed: `run-d8510fe3f3f44bf8`, 57/57, failing none.

## Exclusions / remarks

- Unasserted (excluded) clauses: `R6.2` (per-client snapshot clearing on disconnect is not
  observed), `Task-preserve-other`, `Task-preserve-gpl` (pre-case package gate only) and
  `Task-no-tests-edit`.
- 2026-09-24 harness revision: before it, the verifier created the score plugin before
  Left4DHooks and, on a creation-ordered filesystem, every boot failed closed on
  `L4D_GetVersusMaxCompletionScore should not be used before OnMapStart`. See `known_issues`.
- No task-level exclusion recommended.
