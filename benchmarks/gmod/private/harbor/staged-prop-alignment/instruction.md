# Harbor workspace

Complete this task in `/app/addon`; every required file must be written under that directory.

# Staged Three-Point Prop Alignment

## 1. Background and goals

- **T2-GOAL-01** Implement a server-authoritative Sandbox Toolgun Addon. The player collects, in order, three anchors each for the source frame and the target frame, uses a deterministic rigid-body transform to compute the position of a `prop_physics` copy, and can optionally constrain the copy to the source entity.
- **T2-GOAL-02** Geometry, stages, replay, budget and persistence belong to the plain-Lua 5.1-compatible core; real Player, Entity, Toolgun, trace, constraint and Undo belong only to the server-side adapter.

## 2. Required files

- **T2-FILE-01** The submission must contain, and may depend only on, the files built into this task:

```text
addon.json
lua/rhenium_prop_alignment/alignment.lua
lua/rhenium_prop_alignment/server.lua
lua/weapons/gmod_tool/stools/rhenium_align.lua
```

`addon.json` must be a valid GMod Addon manifest. You must not depend on the Workshop, third-party Addons, external Lua packages, network services or client code.

## 3. Core module and constructor parameters

- **T2-API-01** `lua/rhenium_prop_alignment/alignment.lua` returns the `Alignment` table and provides `Alignment.new(options)`. `options` must be a table, and `options.max_operations` must be exactly `2`; the optional `options.state` must be a saved state of this contract with `schema_version=1`.
- **T2-API-02** Construction returns an instance on success and `nil, error_code` on failure; the error code is `invalid_options` or `invalid_state`.

```lua
Alignment.new(options)
alignment:stage(request_id, player_id, entity_id, revision, frame, slot, point)
alignment:solve(request_id, player_id, entity_id, revision, probe)
alignment:clear(request_id, player_id)
alignment:snapshot()
alignment:save()
alignment:shutdown()
```

## 4. Inputs, return values and stable error codes

- **T2-API-03** `stage`, `solve`, `clear` return `ok:boolean, code:string, data:fresh_table`. An exact replay must also return a new copy of `data`.
- **T2-API-04** `snapshot()` returns a detached state table; `save()` returns a detached persistence table; `shutdown()` returns `true, "shutdown"` every time.
- **T2-DATA-01** `request_id`, `player_id`, `entity_id` are strings of length `1..128` matching `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`; `revision` is a positive integer; point/probe is an `{x,y,z}` whose three components are all finite numbers.
- **T2-ERR-01** Must stably distinguish: `invalid_options`, `invalid_state`, `invalid_stage`, `invalid_request`, `request_conflict`, `stage_identity_mismatch`, `bad_stage_order`, `degenerate_frame`, `collinear_frame`, `incomplete_stage`, `budget_exceeded`, `shutdown`.

## 5. Stage state and identity

- **T2-SEM-01** Each player has at most one staging session, bound to the `entity_id + revision` of the first valid input. Switching entity or revision within the same session returns `stage_identity_mismatch` and does not change state.
- **T2-SEM-02** The six-step order is strictly `source/origin`, `source/x`, `source/y`, `target/origin`, `target/x`, `target/y`. Skipping a step, going backward or repeating a slot returns `bad_stage_order`.
- **T2-SEM-03** `clear(request_id, player_id)` deletes only the specified player's session, does not affect other players, consumed budget or request history, and on success returns `true, "cleared", {}`.

## 6. Three-point geometry contract

- **T2-GEO-01** For each set of three points, X is the unit vector of `origin→x`; Z is the unit vector of `X × (origin→y)`; Y is the unit vector of `Z × X`. An axis with length less than `0.000001` returns `degenerate_frame`; a cross product with length less than that threshold returns `collinear_frame`; a failed third point must not be retained.
- **T2-GEO-02** `solve` expresses probe in local coordinates of the source basis, then reconstructs world coordinates with the target basis. The result `data` is at least `{position={x,y,z}, basis={x={x,y,z}, y={x,y,z}, z={x,y,z}}}`.
- **T2-GEO-03** All public position/basis components are quantized to the nearest `1e-6`. Any mathematically equivalent implementation is acceptable; you must not require or assume the reference implementation's table layout, hashing or function decomposition.

## 7. Replay, budget, revision and ordering

- **T2-SEM-04** `stage`, `solve`, `clear` share a global request-ID namespace. An exact retry with the same method and same arguments returns the original result with no side effects; for the same ID, a different method or any different argument returns `request_conflict`.
- **T2-SEM-05** `solve` accepts only a session that is complete and whose generation matches exactly; otherwise it returns `incomplete_stage`. A successful solve consumes exactly one unit of that player's budget and deletes that session; a retry of the same request does not consume again.
- **T2-SEM-06** Each player can solve successfully at most twice. A third new solve returns `budget_exceeded`. A new revision does not inherit the old session.
- **T2-SEM-07** Player sessions and budget in snapshot/save must be expressed by stable player ID and must not depend on `pairs`, Entity objects or `EntIndex()`; returned objects must be detached.

## 8. Persistence schema

- **T2-PERSIST-01** `save()` returns `schema_version=1`, plus complete `sessions`, `requests`, `spent`. After passing it back in via `Alignment.new({max_operations=2,state=saved})`, stage, budget, exact replay and conflict behavior remain unchanged.
- **T2-PERSIST-02** Saved state must not contain Player, Entity, Vector, Angle, functions, userdata or process-local references. The constructor must validate the fields, types, unique IDs, generation, six-step prefix and budget range of all session/request/spent rows; unknown, missing, duplicate or mutually contradictory state uniformly returns `invalid_state`; it must not check only `schema_version`.

## 9. Server-side adapter public interface

- **T2-API-05** `lua/rhenium_prop_alignment/server.lua` returns the adapter and provides:

```lua
adapter.Install(options)
adapter.BindPlayer(player, logical_id)
adapter.BindEntity(entity, entity_id, revision)
adapter.HandleTrace(player, trace)
adapter.Execute(player, entity, request_id, mode)
adapter.Save()
adapter.Shutdown()
```

- **T2-ADAPTER-01** `mode` can only be `copy` or `move`; any other value must return `invalid_mode` before calling core solve. `copy` creates the transformed clone, creates a Weld from the source entity to the clone, and puts the clone and Weld into one Undo. `move` creates no clone/Weld but instead moves the original entity; on failure it restores the original position/angle, and on success uses `undo.AddFunction` to restore the original transform within one Undo. The real Tool's RightClick always uses `copy`; `move` is called only from a non-predicted server-side `Execute` context.
- **T2-ADAPTER-02** The adapter stably returns `invalid_trace`, `unbound_entity`, `permission_denied`, `invalid_context`, `invalid_mode`, `create_failed`, `constraint_failed`, `undo_failed`, `executed`, `shutdown`; core errors are forwarded unchanged.

## 10. GMod native API and STOOL

- **T2-NATIVE-01** `Install` registers named `CanTool`, `PlayerDisconnected`, `EntityRemoved` Hooks and one named repeating Timer; before every stage change it calls `hook.Run("CanTool", player, trace, "rhenium_align")`, and an explicit `false` must return `permission_denied` before the core changes. This Addon's `CanTool` Hook may return `false` only when denying, must return `nil` when allowing, and must not use `true` to mask a denial from later Hooks.
- **T2-NATIVE-02** `HandleTrace` accepts only a bound player, a real Hit trace and a bound `prop_physics`. The adapter copies the numbers from `trace.HitPos` into a plain-Lua point and does not pass a Vector or Entity into the core.
- **T2-NATIVE-03** copy's `Execute` uses `ents.Create`, the source entity's public class/model, the solved position/basis angle, and `constraint.Weld`; move uses the original entity's `SetPos/SetAngles` and must not call `ents.Create` or `constraint.Weld`.
- **T2-NATIVE-05** copy uses `undo.Create/AddEntity/SetPlayer/Finish`; move uses `undo.Create/AddFunction/SetPlayer/Finish`. Both success paths produce exactly one Undo unit.
- **T2-NATIVE-04** The STOOL's `LeftClick(trace)` calls `HandleTrace(self:GetOwner(), trace)` on the SERVER side; `RightClick(trace)` calls `Execute(...,"copy")`. The real integration drives LeftClick via the real `gmod_tool` SWEP `PrimaryAttack()` and produces the trace with the real `util.TraceLine`.

## 11. Authority, transactions and rollback

- **T2-TRUST-01** Logical player ID, entity ID, revision and budget come only from server-side binding; any client owner/entity/revision payload is untrusted. `EntIndex()` cannot be used as a persistent identity.
- **T2-ROLLBACK-01** Invalid mode/context, permission failures and core failures must not change entities. If copy's clone creation fails, return `create_failed`; if the Weld fails, delete the clone; if Undo completion fails, delete this call's clone and constraint. If move's transform or Undo fails, restore the original position/angle. For every adapter failure, the net number of new objects is zero and the old entity's transform is unchanged. Note: once mode/context pass, `Execute` first successfully calls core solve and then operates on runtime objects, so when create/constraint/Undo fails, that solve has already consumed one unit of budget and cleared the session; the submission must not secretly restore or double-consume that core result.

## 12. Lifecycle, out-of-scope and prohibitions

- **T2-LIFE-01** `Install` and `Shutdown` are idempotent. Shutdown removes all of this Addon's Hooks and Timers, clears object bindings and uncommitted adapter progress, and freezes core write operations.
- **T2-SCOPE-01** This task does not cover real client input, prediction, HUD, network messages, arbitrary constraint types, arbitrary models or multi-entity graph transforms; the real Toolgun verifies only the fixed copy, and move is verified in a non-predicted server-side context.
- **T2-SCOPE-02** The plain-Lua core must not reference `hook`, `timer`, `Player`, `Entity`, `Vector`, `Angle`, `CurTime`, `IsValid`, the file system, the network or the console; it must not leave TODOs, empty shells or an actively thrown "not implemented".

## 13. Acceptance criteria

- **T2-ACC-01** The six anchors work strictly in the public order; degenerate/collinear input fails atomically, and the two three-point bases and the probe mapping satisfy the `1e-6` quantization contract.
- **T2-ACC-02** Player, entity generation, CanTool and server-side binding cannot be forged; the sessions of two players do not affect each other.
- **T2-ACC-03** The two-solve budget, exact replay, conflicts, clear, save/load and detached output have the same semantics before and after a restart.
- **T2-ACC-04** Real Toolgun PrimaryAttack, `util.TraceLine`, Prop, Weld and a single Undo complete copy; a real server-side move creates no clone/Weld and a single Undo restores the original transform; all faults roll back fully.
- **T2-ACC-05** After Shutdown, no Hook, Timer or temporary object of this Addon remains, and every subsequent core modification returns `shutdown`.

Suggested completion time: 360 minutes.
