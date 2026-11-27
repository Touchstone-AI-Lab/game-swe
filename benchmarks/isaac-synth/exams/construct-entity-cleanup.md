# Construct: Owned-entity lifecycle cleanup

You are creating a new Lua mod for **The Binding of Isaac: Rebirth — Afterbirth+
v1.06.T1**. The starter contains only `mod/main.lua` and `mod/metadata.xml`.

## Task

Implement `SpawnTrackedOwner(type, variant, subtype, position, velocity,
spawner)` and `SpawnTrackedEffect(owner, type, variant, subtype, position,
velocity, spawner)` wrappers around `Isaac.Spawn`. The wrappers track only the
entities they themselves spawn; arbitrary room entities must never be adopted
as owned.

## Required behavior

- Give each tracked owner a monotonically increasing token scoped to the mod
  instance and run, based on `Entity.InitSeed` plus a mod serial—not the
  reusable `Entity.Index`. `SpawnTrackedEffect` accepts only a live tracked
  owner, stores that exact owner token in `Entity:GetData()`, and registers the
  effect. A nil, dead, foreign, or untracked owner must not spawn/claim an
  effect.
- If `Isaac.Spawn` returns nil or an entity that no longer exists, a spawn
  wrapper returns nil and does not create a registry entry.
- `MC_POST_UPDATE` sweeps a snapshot of the registry. If an owner is missing,
  dead, or no longer exists, remove each still-existing owned effect once and
  clear its registry entry. If an effect was removed elsewhere, clear only its
  reference. Removing entries during a sweep must not skip later owners or
  effects.
- Use `MC_POST_ENTITY_REMOVE` for both owner and effect removal. Removing an
  owner removes all and only effects with its token; removing an effect clears
  only that effect reference. Repeated and out-of-order callbacks are
  idempotent, and an already removed entity is safe.
- `MC_POST_NEW_ROOM` cleans effects and owners from the room being left and
  records the new room visit. Use a monotonically increasing room-visit token
  together with `Room:GetSpawnSeed()` so visits cannot alias. Never restore or
  adopt stale entities on re-entry by scanning `GetData()` tags. Untagged and
  foreign-token room entities stay untouched.
- Reuse of an `Entity.Index` must not transfer an old ownership token or
  registry slot to a new entity. Multiple owners and multiple effects per
  owner are independent; cleaning one does not skip or delete another owner's
  live entries.

Use only Afterbirth+ entity and callback APIs. Do not add third-party code or
assets.

## Public observation and control API

Export IsaacConstructEntities with exactly SpawnTrackedOwner(type, variant,
subtype, position, velocity, spawner), SpawnTrackedEffect(owner, type, variant,
subtype, position, velocity, spawner), and Snapshot(). The callback
implementation and other mods use these same wrappers; there is no separate
verifier-only spawn path. Snapshot returns `{owners = {...}}`, a fresh list of registry records, each
`{token, initSeed, index, roomSpawnSeed, roomVisit, effects = {{token, initSeed,
index}, ...}}`: the owner's ownership token, its InitSeed, its current Index, the
spawn seed of the room it was spawned in, the room-visit token of that visit, and
one record per owned effect. Spawn wrappers return the spawned entity or nil.

## Acceptance cases

created_effect_is_tracked, foreign_entity_is_not_tracked, live_owner_keeps_effect,
dead_owner_removes_effect, removed_owner_removes_effect,
owner_missing_clears_reference, room_change_removes_old_owned_effect,
room_change_keeps_foreign_effect, reentry_does_not_restore_old_owner,
repeated_cleanup_is_idempotent, duplicate_remove_callback_is_safe,
already_removed_entity_is_safe, nil_owner_is_safe, effect_removed_once,
registry_entry_removed_once, reused_entity_index_not_reused,
ownership_token_matches_entity, ownership_token_survives_update,
ownership_token_cleared_on_room_change, new_owner_does_not_adopt_stale_effect,
two_owners_clean_independently, multiple_effects_per_owner_clean,
foreign_sibling_effect_survives_cleanup, entity_removed_callback_scoped,
partial_effect_remove_clears_only_one, post_update_catches_missing_remove_event,
room_identity_prevents_cross_room_cleanup, cleanup_order_does_not_skip_entries,
cleanup_after_owner_death, cleanup_after_owner_remove,
cleanup_after_transition_then_remove, no_double_free_on_transition,
foreign_entity_untouched_on_bulk_scan, registry_empty_after_all_owners_removed,
reused_index_does_not_adopt_new_entity.
