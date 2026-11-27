# Construct: Cross-callback transaction ledger

You are creating a new Lua mod for The Binding of Isaac: Rebirth — Afterbirth+
v1.06.T1. The starter contains only mod/main.lua and mod/metadata.xml.

## Task

Implement a transaction ledger driven by MC_USE_ITEM, MC_POST_UPDATE,
MC_POST_NEW_ROOM, MC_PRE_GAME_EXIT, and MC_POST_GAME_END. The effect is a
mod-owned integer count; it does not change player stats, room entities, or
game RNG.

## Required state machine

Maintain the current run start seed, committed_count, derived applied_count,
and at most one pending transaction {seq, stage}. seq is monotonically
increasing; stage is prepared or applied. With no pending transaction,
applied_count equals committed_count. While the pending transaction is
applied, applied_count equals committed_count + 1. `journal` is either empty
or a fresh one-entry list mirroring the pending `{seq, stage}`; it is not a
second source of truth.

- MC_USE_ITEM with no pending transaction creates
  {seq=committed_count+1, stage="prepared"}. Further item-use callbacks are
  ignored until it commits or rolls back.
- MC_POST_UPDATE changes only prepared to applied and stages exactly one unit.
  Re-entry cannot add another unit. A room callback before this stage does
  nothing.
- MC_POST_NEW_ROOM commits only an applied transaction by setting
  committed_count to seq and clearing the pending journal. A prepared
  transaction is not committed by room entry. With no pending transaction it
  is a no-op.
- Every callback transition is atomic: calculate the complete next state
  before publishing it. On error, restore the exact prior snapshot, preserve
  the phase, and do not throw into the game. A consumed one-shot fault clears
  even when the transaction snapshot rolls back; `armedFault` is diagnostic
  test-control state, not committed ledger state.
- `ArmFault(pointName)` accepts exactly `update_before_publish`,
  `room_before_publish`, `encode_before_save`, and `save_data_before_write`.
  At the named point, the next matching transition raises internally; the
  public call returns `false` without throwing, and the injection clears.
  These points make rollback behavior observable through the same transition
  code used by callbacks. Unknown point names are rejected without arming a
  fault.
- Either save callback writes only the committed snapshot, exactly the fields
  schema_version=1, run_seed=<integer>, and
  committed_count=<non-negative integer>. A pending transaction is discarded
  and any staged unit is rolled back before saving. If encoding or SaveData
  fails, restore the pre-callback in-memory snapshot and do not claim a save or
  commit. After a successful save, clear the pending transaction and journal
  and set applied_count back to committed_count. Both callbacks and the
  constructtxn save command call the same routine. SaveNow returns true only
  after SaveData succeeds.
- On continued MC_POST_GAME_STARTED, accept only a decoded table with exactly
  the required schema, valid integer fields, and a run seed matching
  Seeds:GetStartSeed(). Otherwise initialize count 0. A non-continued start
  resets count, pending transaction, and journal. Continue restores committed
  progress, never an in-flight transaction.
- Before any room callback, item-use and update handlers follow the same
  rules and must not dereference a missing room.

Use only public Afterbirth+ callback, seed, and mod save APIs. Do not add
third-party code or assets.

`journal` is created with the prepared transaction, updated when it advances
to applied, and cleared on commit, successful save, or a non-continued run
start. Failed transitions restore its exact prior contents.

## Public observation and control API

Export IsaacConstructTransaction with UseItem(), Update(), NewRoom(),
LoadRaw(hasData, rawData, runSeed), SaveNow(), ArmFault(pointName), and
Snapshot(). Engine callbacks invoke these exact transition methods. Tests may
exercise callback ordering and injected failures through the public methods,
but may not write state directly. Snapshot returns fresh runSeed,
committed_count, applied_count, optional pending, journal, lastSavedRaw, and
armedFault. SaveNow is shared by both save callbacks and constructtxn save.

## Acceptance cases

use_item_starts_transaction, duplicate_use_while_pending_ignored,
one_pending_transaction_max, pending_sequence_is_committed_plus_one,
use_does_not_commit_count, use_without_room_init_safe,
second_use_after_commit_starts_next, update_prepared_to_applied,
applied_count_increments_once, duplicate_update_is_idempotent,
update_noop_without_pending, update_noop_after_applied,
update_failure_rolls_back_snapshot, update_failure_does_not_advance_phase,
room_before_update_does_not_commit, room_applied_commits_exactly_once,
duplicate_room_callback_noop, commit_clears_pending, commit_clears_journal,
callback_order_cannot_skip_update, committed_transaction_not_reapplied,
save_serializes_exact_schema, save_contains_run_seed,
save_after_commit_persists_count, pending_prepared_discarded_on_save,
pending_applied_discarded_on_save, continued_load_restores_count,
save_callback_does_not_advance_count, continued_wrong_seed_defaults,
malformed_save_defaults, missing_save_defaults, new_run_resets_count,
new_run_clears_pending_journal, save_failure_restores_memory_snapshot,
later_valid_save_recovers.
