# E0 notes: l4d2-linge-director-state-hard

Workspace layout: `/app/linge-hud`; every overlay uses `root = linge-hud`. Clause ids are `R<report>.<n>` for the numbered reports (anchor = report, sentence, short quote) and `Task-*` for the surrounding paragraphs.

Baseline through the operator Hub full profile (`rhenium run`, Linux x86_64 Docker host, 2026-09-24, verifier image `sha256:4cd34822c13d...`): unchanged starter 11/41 (`run-7d142ea9b8494564`, complete, score 10); reference 41/41 three times with identical case outcomes (`run-409c68dbc2194f43`, `run-18fde9775ee74b66`, `run-d1cf05e2cf224e37`, score 100). These are not study-Hub records: the study Hub must be re-seeded from the operator database before `rhenium-study e0` can reproduce them, because the verifier images changed on 2026-09-24.

Overlays patch `vscripts/LinGe/Base.nut` and `vscripts/LinGe/MoreSI.nut`, the files the
oracle changes. The nine reports are task-authored contracts over the frozen upstream
snapshot, not reverted upstream commits.

## Preserved contracts (all `P` in the unchanged starter)

| case | public statement |
| --- | --- |
| `event-duplicates-binding-index` | R4 s4 duplicate registrations, `callOf` binding, `LinEventIndex`/`UnHook` return values |
| `director-nonarray-clears-restriction` (overlap) | R7 s2 nonarray whitelist means no restriction |
| `director-independent-controls` | R8 s3 respawn interval and initial delay with quantity control disabled |
| `director-population-expression` (overlap) | R8 s2 formula for in-range values |
| `director-disable-idempotent` (overlap) | R9 s5 repeated disable removes overrides |
| `director-command-preserves-sentinels` | R9 s7 `-2` keeps a value unchanged |
| `event-delayed-subscribers-at-delivery` (overlap) | R6 s2 subscribers selected when the delay expires |
| `director-pending-refresh-after-disable` (overlap) | R9 s6 a pending refresh does not re-enable |
| `director-common-cleanup-enabled` | R9 s7 existing enabled common-infected cleanup |
| `director-common-cleanup-disabled` (overlap) | R9 s5 cleanup timer removed after disable |

`director-common-cleanup-fixture` is a `setup` case (it spawns a real common infected).

## Controls (all executed through `rhenium run`; all behaved as declared)

- `tn-dispatch-snapshot-unfixed` (target-negative): the oracle with `LinEventTrigger` walking the live callback list instead of the list captured at dispatch start (report 4 unrepaired, minus-report-4). Observed: `run-654ea76414ec4043`, 38/41, failing `event-nested-sees-current-registration`, `event-prepend-next-dispatch`, `event-remove-current-snapshot`.
- `tn-quantity-ceiling-unfixed` (target-negative): the oracle with the 31-special ceiling as an else-branch of the minimum again (report 8 unrepaired, minus-report-8). Observed: `run-a54fdf2810224261`, 40/41, failing `director-minimum-obeys-ceiling`.
- `cn-duplicate-registrations-collapsed` (compat-negative): the oracle plus a three-line change: `LinEventHook` ignores a callback/`callOf` pair that is already registered. Report 4 explicitly preserves duplicate registrations. Observed: `run-acc5787a8ee34409`, 40/41, failing `event-duplicates-binding-index`.
- `alternative-sorted-index-snapshot` (alternative): the pack's reference-derived alternative (sorted-index array reconstruction, explicitly built subscriber snapshot, per-section bulk save, set-based whitelist dedup). Observed: `run-629014149cfa49f2`, 41/41, failing none.

## Exclusions / remarks

- Unasserted (excluded) clauses: `Task-preserve-behaviour` (HUD, hint and reward behaviour are
  not observed; the licence is a pre-case gate), `Task-no-polling`, `Task-no-tests-edit`.
- No task-level exclusion recommended.
