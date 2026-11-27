# Harbor workspace

Complete this task in `/app/addon`; every required file must be written under that directory.

# Contraption Blueprint Duplicator

## 1. Background and goals

- **T5-GOAL-01** Implement a server-authoritative contraption blueprint Addon: capture a supported Entity/Constraint graph, produce a deterministic, persistable schema, and in a separate server process restore it at a target offset as a single Undo unit.
- **T5-GOAL-02** Graph validation, normalization, revisions, replay and the paste plan belong to the plain Lua 5.1 core; real duplicator, constraint, Player, Entity, Undo and cleanup belong only to the adapter.

## 2. Required files

- **T5-FILE-01** You must submit:

```text
addon.json
lua/rhenium_contraption_blueprints/blueprints.lua
lua/rhenium_contraption_blueprints/server.lua
```

You must not depend on the Workshop, third-party Addons, external packages, network services, or client-authoritative code.

## 3. Core public interface

- **T5-API-01** `lua/rhenium_contraption_blueprints/blueprints.lua` returns `Blueprints` and provides:

```lua
Blueprints.new(options)
blueprints:capture(request_id, owner_id, name, revision, graph)
blueprints:list(owner_id)
blueprints:get(owner_id, name)
blueprints:plan(request_id, owner_id, name, revision, target)
blueprints:record_paste(request_id, result)
blueprints:save()
blueprints:shutdown()
```

- **T5-API-02** `Blueprints.new({state=optional_state})` returns an instance on success; an invalid schema returns `nil,"invalid_state"`.
- **T5-API-03** capture/plan/record_paste return `ok:boolean,code:string,data:fresh_table`; list always returns a fresh list; get returns a detached blueprint or `nil,"not_found"`; shutdown returns `true,"shutdown"` every time.

## 4. Identifiers, closed allowlist and budgets

- **T5-DATA-01** request/owner/source IDs have length `1..128` and match `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`; blueprint names have length `1..32` and match `^[A-Za-z0-9_-]+$`; revision is a positive integer.
- **T5-DATA-02** The Entity class allowlist is a closed set: only `prop_physics`. After lowercasing, model may only be `models/props_c17/oildrum001.mdl`, `models/props_c17/furniturechair001a.mdl`, `models/props_c17/furnituretable001a.mdl`.
- **T5-DATA-03** The Constraint type allowlist is a closed set: only `Weld`, `NoCollide`. Endpoints must reference two existing, distinct source IDs.
- **T5-DATA-04** Each owner has at most `8` blueprints; each graph has `1..16` entities and `0..24` constraints. Exceeding the graph budget returns `invalid_graph`; a 9th new blueprint returns `blueprint_limit`.

## 5. Input graph and normalized schema

- **T5-DATA-05** The capture graph is `{entities={...},constraints={...}}`. An entity row is `{source_id,class,model,pos={x,y,z},ang={x,y,z}}`; a constraint row is `{type,a,b,params=table}`. The raw type of `source_id` must be a non-empty string satisfying the ID rules; missing/number/boolean/empty must not be accepted after stringification. All transform components must be finite numbers.
- **T5-SEM-01** entities are first sorted by lexicographic string order of source_id, then assigned consecutive local IDs `e1..en`. Missing, non-string, empty or duplicate source_id, as well as unsupported class/model and non-finite transforms, all atomically return `unsupported_entity`; you must not depend on input array/table traversal order or `EntIndex()`.
- **T5-SEM-02** Each edge replaces its endpoints with local IDs, letting the smaller ID be `a` and the larger be `b`; stably sort by `type+a+b`, then assign `c1..cn`. Unknown type, missing endpoints and self-edges return `invalid_endpoint`.
- **T5-SEM-03** The schema is fixed as `{schema_version=1,entities=...,constraints=...,hash=...}`; positions and angles are quantized to the nearest `1e-6`. params must be detached and must round-trip at least `Bone1,Bone2,forcelimit,nocollide`.

## 6. Behavioral contract of the hash

- **T5-HASH-01** The hash must be a stable string obtained, in a fixed order, from the normalized schema's version, local IDs, class, normalized lowercase model, quantized transforms, constraint ID/type/endpoints, and normalized params (key names, types and values); any observable change in params must change the hash.
- **T5-HASH-02** Input table/array order, `pairs` order, original Entity indices and JSON key order must not change the hash; any observable change included in the normalized fields above must change the hash. Any deterministic algorithm may be used; the reference implementation's specific hash formula or bit width is not required.

## 7. capture, revision, list/get

- **T5-SEM-04** capture first fully validates and normalizes, then handles request/revision/budget; on success it stores `{revision,schema}` and returns `true,"captured",{name,revision,hash,entities,constraints}`.
- **T5-SEM-05** When replacing the same owner/name, revision must strictly increase, otherwise `stale_revision`; replacement does not consume a new blueprint slot.
- **T5-SEM-06** list exposes only that owner's `{name,revision,hash}`, sorted by name; get returns only that owner's full detached blueprint. Owners are completely isolated from one another.

## 8. Request idempotency and paste plan

- **T5-SEM-07** capture and plan share a request-ID namespace. A retry with the same method, the same arguments in full, and the same normalized hash/target returns the original result; any difference returns `request_conflict`.
- **T5-SEM-08** `plan(request_id,owner,name,revision,target)` requires the blueprint to exist, revision to be exactly equal, and target to be a finite `{x,y,z}`; the failures are `not_found`, `stale_revision`, `invalid_transform` respectively.
- **T5-SEM-09** target is a pure translation: each entity's paste position is the quantized `captured_pos + target`, and the angle is unchanged; return a detached copy of the normalized schema with `request_id` attached.
- **T5-SEM-10** `record_paste` accepts `{entities=number,constraints=number}` the first time and returns `recorded`; recording again for the same request returns the original result and `duplicate`, and must not overwrite.

## 9. Stable error codes and persistence

- **T5-ERR-01** Must stably distinguish: `invalid_state`, `invalid_request_id`, `invalid_request`, `request_conflict`, `invalid_graph`, `unsupported_entity` (also used for duplicate source_id), `invalid_endpoint`, `blueprint_limit`, `stale_revision`, `not_found`, `invalid_transform`, `invalid_result`, `shutdown`.
- **T5-PERSIST-01** save returns `schema_version=1`, all owner blueprints, request results and paste results. After reconstruction, schema/hash, ordering, revisions, success/failure replay and duplicate record behavior are consistent.
- **T5-PERSIST-02** Persistent state must not contain Player, Entity, Vector, Angle, functions, userdata, Hook, Timer or in-process references.

## 10. Server-side adapter public interface

- **T5-API-04** `lua/rhenium_contraption_blueprints/server.lua` returns the adapter and provides:

```lua
adapter.Install(options)
adapter.BindPlayer(player, logical_id)
adapter.BindEntity(entity, entity_id, revision)
adapter.Capture(player, root, name, request_id, revision)
adapter.Paste(player, name, target, request_id, revision)
adapter.List(player)
adapter.Save()
adapter.Shutdown()
```

- **T5-ADAPTER-01** The adapter stably returns `unbound`, `permission_denied`, `capture_failed`, `paste_failed`, `undo_failed`, `pasted` and core errors. List returns an empty table for unbound players.
- **T5-TRUST-01** owner, root logical identity and revision come from BindPlayer/BindEntity; the client cannot submit an owner or a raw graph to bypass the public Copy/CanTool.

## 11. Public GMod APIs and graph adaptation

- **T5-NATIVE-01** Capture first calls `hook.Run("CanTool",player,{Entity=root},"duplicator")`; an explicit false returns permission_denied. Then it really calls `constraint.GetTable(root)` and `duplicator.Copy(root)`: Copy provides the full Entity/Constraint graph, GetTable provides the root entity's public constraint view and must agree with Copy's corresponding type/endpoint set; missing or inconsistent returns `capture_failed`; reading it and then ignoring it is not allowed.
- **T5-NATIVE-02** Copy entity fields use the public `Class,Model,Pos,Angle`. Public constraint endpoints can be resolved from Ent1/Ent2 in entity form or Index/Entity/first-element form; params keep `Bone1,Bone2,forcelimit,nocollide`.
- **T5-NATIVE-03** Paste first calls CanTool, then converts the plan into the public tables required by `duplicator.Paste(player,entities,constraints)`; an entity row contains Class/Model/Vector Pos/Angle/frozen PhysicsObjects, and a constraint row uses a local ID→paste index mapping.
- **T5-NATIVE-04** After success, use `undo.Create/AddEntity/SetPlayer/Finish` to put all new entities and constraints into one Undo; all new entities are attributed to the trusted player with `cleanup.Add(player,"props",entity)`.

## 12. Transactional rollback, lifecycle and prohibitions

- **T5-ROLLBACK-01** When `duplicator.Paste` throws, returns missing/invalid objects, or returns a count not equal to the plan, delete all valid constraints from this paste and then all valid entities, and return `paste_failed,{entities=0,constraints=0}`. If Undo Finish fails, perform the same full rollback and return `undo_failed`. The net additions on failure must be zero.
- **T5-LIFE-01** Install registers named PlayerDisconnected and EntityRemoved Hooks and one named Timer; Install/Shutdown are idempotent. Shutdown removes all Hooks/Timers, clears bindings and freezes core capture.
- **T5-SCOPE-01** Two-process acceptance reuses only the DATA state file, not Lua globals, objects, Hooks or caches. This task does not support arbitrary entities/models/constraints, rotated targets, client UI or internal duplicator APIs.
- **T5-SCOPE-02** You must not require or call `duplicator.CreateConstraintFromTable`, `duplicator.GetAllConstrainedEntitiesAndConstraints`, `undo.Do_Undo`, `cleanup.CC_*`; no TODOs, empty shells or "not implemented" may be left behind.

## 13. Acceptance criteria

- **T5-ACC-01** A real 3 Prop/2 Constraint graph is normalized within the closed allowlist and the 8/16/24 budgets; local IDs, edges, transforms, counts and hash are deterministic.
- **T5-ACC-02** Bad class/model/type/endpoint/self-edge/nonfinite/budget fail before any state change; list/get are isolated per owner, sorted and detached.
- **T5-ACC-03** capture/plan replay, conflicts, revisions, record_paste and save/load are consistent across two separate processes.
- **T5-ACC-04** The public Copy/GetTable/Paste restore the graph, the target translation is applied to every node, and after a single Undo the objects added by this paste are zero.
- **T5-ACC-05** Partial failure of Paste or Undo deletes all objects from this paste; after Shutdown no Hooks, Timers, bindings or temporary objects remain.

Suggested completion time: 420 minutes.
