# Harbor workspace

Complete this task in `/app/addon`; every required file must be written under that directory.

# Prop Ownership and Quota Manager

## 1. Background and goals

- **T1-GOAL-01** Implement a GMod server-side Addon that manages `prop_physics` ownership for logical players; each player has at most two Props, cleanup at the five-second disconnect boundary, and reconnecting before the boundary cancels it.
- **T1-GOAL-02** Ownership, quota, generation, replay and time belong to the plain Lua 5.1 core; real Hook, Timer, Player and Entity belong only to the adapter.

## 2. Required files

- **T1-FILE-01** You must submit:

```text
addon.json
lua/rhenium_prop_registry/registry.lua
lua/rhenium_prop_registry/server.lua
```

`addon.json` must be valid; you must not depend on the Workshop, third-party Addons, external packages, network services or client-authoritative code.

## 3. Core public interface

- **T1-API-01** `lua/rhenium_prop_registry/registry.lua` returns `Registry` and provides:

```lua
Registry.new(options)
registry:register(request_id, player_id, entity_id, revision)
registry:can_modify(player_id, entity_id, revision, operation)
registry:remove(request_id, entity_id, revision)
registry:disconnect(player_id, now)
registry:reconnect(player_id, now)
registry:tick(now)
registry:snapshot(now)
registry:save(now)
registry:shutdown()
```

- **T1-API-02** new returns an instance on success and `nil,error_code` on failure; register/remove/disconnect/reconnect/tick return `ok:boolean,code:string,data:fresh_table`; can_modify returns `allowed:boolean,code:string`; snapshot/save return a detached table or `nil,error_code`; shutdown returns `true,"shutdown"` every time.

## 4. Configuration, identifiers and operation

- **T1-DATA-01** `options.max_props=2`, `options.cleanup_delay=5`; optional `state` and a storage implementing `load()/save(state)`; an explicit state takes precedence. Any other configuration, or a saved configuration that does not match, returns `invalid_options` and `state_configuration_mismatch` respectively.
- **T1-DATA-02** request/player/entity IDs have length `1..128` and match `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`; revision is a positive integer; now is a non-negative finite number.
- **T1-DATA-03** operation is closed to `physgun`, `tool`, `property_remover`, `delete`.

## 5. Stable error codes

- **T1-ERR-01** The core must stably distinguish `invalid_options`, `invalid_state`, `state_configuration_mismatch`, `invalid_request_id`, `invalid_player_id`, `invalid_entity_id`, `invalid_revision`, `invalid_now`, `invalid_operation`, `not_found`, `not_owner`, `stale_revision`, `quota_exceeded`, `request_conflict`, `storage_error`, `shutdown`.
- **T1-ERR-02** The adapter additionally uses, stably, `invalid_player`, `invalid_entity`, `not_installed`, `invalid_context`, `not_owner`. Invalid input must be rejected before any state change.

## 6. Ownership, quota and generation

- **T1-SEM-01** Each entity_id has only one current generation. A successful register records the owner and returns `{entity_id,revision,owner_id,count}`; each owner's current entity count does not exceed 2.
- **T1-SEM-02** A third new Prop returns `quota_exceeded` and must not replace or modify existing entities. If the current owner of the same entity is replacing it with a higher revision, only the post-replacement quota is counted.
- **T1-SEM-03** Entity identity is `entity_id+revision`. A revision lower than or not equal to the current/historical generation returns `stale_revision`; a higher revision may replace the old generation exactly once. `EntIndex()` reuse does not inherit permissions.
- **T1-SEM-04** can_modify returns `true,"allowed"` only when owner, exact revision and a valid operation all match; remove releases quota once only for the exact generation.

## 7. Request idempotency

- **T1-SEM-05** register and remove share a global request-ID namespace. An exact retry with the same method and same arguments returns a new copy of the original result with no side effects; a different method or different arguments returns `request_conflict`.
- **T1-SEM-06** Both successful and business-failure results go into the request history; after save/load they must still be replayed exactly, and a duplicate EntityRemoved must not release twice.

## 8. Time, disconnect and boundary

- **T1-TIME-01** All time-taking calls use `effective_now=max(valid_now,last_now)`; time going backward does not advance or restore state.
- **T1-TIME-02** The first disconnect records `cleanup_at=effective_now+5`; repeated disconnects keep the original boundary. Strictly less than cleanup_at retains; a tick/snapshot/save with `effective_now>=cleanup_at` clears all of that owner's entities.
- **T1-TIME-03** A reconnect before the boundary deletes the pending cleanup and returns `canceled`; with no pending cleanup it returns `connected`. Entities already cleaned up once the boundary is reached cannot be restored.

## 9. snapshot, ordering and detached output

- **T1-PERSIST-01** snapshot returns `schema_version=1,now,owners,entities,pending_cleanup`. owners are sorted by player_id, entities by entity_id/revision, pending by player_id.
- **T1-PERSIST-02** An owner row contains `player_id,count,disconnected,cleanup_at`; an entity row contains `entity_id,revision,owner_id`. Every level is a new table; modifying the return value does not affect internal state.

## 10. Save schema and storage

- **T1-PERSIST-03** save returns `schema_version=1,max_props,cleanup_delay,last_now,next_entity_sequence,entities,latest_revisions,pending_cleanup,requests`, with all lists stably sorted.
- **T1-PERSIST-04** load must validate the schema, configuration, identifiers, revisions, time, duplicate IDs and request shape. When storage.save returns false, save returns `nil,"storage_error"`. After a round trip, quota, generation, pending and replay are consistent.

## 11. Server-side adapter and native API

- **T1-API-03** `lua/rhenium_prop_registry/server.lua` returns the adapter:

```lua
adapter.Install(options)
adapter.BindPlayer(player, logical_id)
adapter.BindEntity(entity, entity_id, revision)
adapter.RegisterProp(player, entity, request_id)
adapter.HandleDeleteRequest(player, entity, request_id)
adapter.Snapshot()
adapter.Save()
adapter.Shutdown()
```

- **T1-NATIVE-01** Install registers named `PhysgunPickup`, `CanTool`, `CanProperty`, `EntityRemoved`, `PlayerDisconnected`, `PlayerInitialSpawn` Hooks and one named repeating Timer of `.1` seconds.
- **T1-NATIVE-02** PhysgunPickup/CanTool perform the owner check on managed entities; CanProperty checks as `property_remover` only when `property=="remover"`; HandleDeleteRequest checks `delete` first and then Removes.
- **T1-NATIVE-03** A valid `prop_physics` that has not been explicitly bound via BindEntity can be assigned `prop:<n>`, revision 1, by RegisterProp using the monotonic `next_entity_sequence`. On a quota rejection, the just-submitted third runtime Prop is deleted.

## 12. Authority, lifecycle, out-of-scope and prohibitions

- **T1-TRUST-01** The owner comes only from BindPlayer's binding to a real Player; client owner payloads are ignored. Entity ID/revision come only from server-side binding/generation; EntIndex is for diagnostics only.
- **T1-LIFE-01** Install/Shutdown are idempotent. Shutdown removes all of this Addon's Hooks/Timers, clears object bindings and freezes core write operations; EntityRemoved, disconnect and reconnect must each advance the core exactly once.
- **T1-SCOPE-01** Only the four modification entry points above, `prop_physics`, and the specified quota lifecycle are covered; no claim is made to intercept arbitrary third-party delete/tool/admin commands.
- **T1-SCOPE-02** The core must not reference Player, Entity, hook, timer, file, CurTime, IsValid, the network or the console; it must not leave TODOs, empty shells or "not implemented".

## 13. Acceptance criteria

- **T1-ACC-01** A's Prop belongs to A; B cannot modify or delete it via any of the four entry points physgun/tool/property remover/delete.
- **T1-ACC-02** The third Prop is rejected and the old state is unchanged; register/delete retries, EntityRemoved and quota release each happen exactly once.
- **T1-ACC-03** Higher-revision replacement works; the old generation and EntIndex reuse cannot inherit permissions.
- **T1-ACC-04** Disconnect strictly less than 5 seconds retains, cleanup at the boundary, reconnect before the boundary cancels; time going backward does not change the result.
- **T1-ACC-05** snapshot/save are sorted and detached; load across two processes preserves request/revision/time; after Shutdown there are no Hooks/Timers and writes are frozen.

Suggested completion time: 180 minutes.
