---
difficulty: hard
estimated_minutes: 420
domains:
  - pathfinding
  - server-authority
  - inventory
  - persistence
---

# Server-authoritative waystone travel network

## Background and goal

Players build "waystones" throughout the world. The server registers waystones as nodes, connects adjacent waystones into a weighted undirected graph, computes the cheapest route for a player, charges a fare in gold nuggets, enforces a personal cooldown and teleports the player. The client can only say "I want to go from this waystone to that waystone"; coordinates, route, price, identity and cooldown are all decided by the server from real entities. A retry of the same request must not charge twice, and a failed teleport must not leave any real side effect.

Starting from an empty workspace, implement a DST-independent pure Lua route network core, and a master simulation world component that connects it to real entities, the real inventory and the real teleport API.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/waystones/network.lua
scripts/components/waystonenetwork.lua
```

The pure module `scripts/waystones/network.lua` must `return` a table and export:

```lua
Network.new(options)
Network.load(data, options)

network:add_node(node_id, owner_id, x, z, now)
network:remove_node(node_id, now)
network:set_blocked(node_id, blocked, now)
network:link(a_id, b_id, now)
network:unlink(a_id, b_id, now)
network:route(from_id, to_id, now)
network:reserve(request_id, traveler_id, from_id, to_id, now)
network:commit(ticket_id, now)
network:abort(ticket_id, now)
network:tick(now)
network:snapshot(now)
network:save(now)
```

The core module may use only plain Lua that is compatible with both Lua 5.1 and Lua 5.4 (the hidden tests load it in a sandbox without `require`, `os`, `io`, `debug` or `load`); all time is passed in through the `now` parameter, and the core must not read any clock.

## Core semantics

1. **Uniform return shape.** Except for `Network.new` and `Network.load`, every method returns a newly created table: on success `ok == true`, on failure `ok == false` and `code` is one of the strings published below. Every returned table (including the `ticket`, the `path` and the snapshot arrays inside it) is a new table, and a caller modifying them must not affect the internal state of the network. A failed call has no side effects at all, except for the clock advance and expiry processing described in item 2, and the `route_changed` of item 8 setting the ticket to `invalidated`.
2. **Time.** The internal clock of the network, `clock`, starts at `0`. Every method that takes `now` validates the time first: `now` must be a number, not NaN, not positive or negative infinity, and `now >= clock`; otherwise it returns `code = "invalid_time"` and has no side effects at all. As soon as validation passes it sets `clock = now` and immediately runs the same expiry processing as `tick(now)` (item 9), and only then performs the method's own remaining validation and logic - so even if the call is subsequently rejected for another reason, the clock has already advanced.
3. **Identifiers, options and nodes.** A valid identifier (`node_id`, `owner_id`, `traveler_id`, `request_id`, `ticket_id`) is a string of length 1 to 64 that contains only the characters `A-Z a-z 0-9 _ . : -`; otherwise `code = "invalid_id"`. The fields of `options` and their default values are `max_nodes_per_owner = 4`, `max_link_length = 60`, `cost_per_unit = 0.25`, `ticket_ttl = 10`, `cooldown = 30`; when a field is missing, or is not a finite positive number (`max_nodes_per_owner` must additionally be an integer), the default value is used. After time validation `add_node` checks in order: the identifiers (`invalid_id`) -> `x` and `z` must be finite numbers (`invalid_position`) -> the node already exists (`duplicate_node`) -> the number of nodes currently owned by this owner has reached `max_nodes_per_owner` (`owner_limit`). On success it returns `{ ok = true, node_id = node_id }`, and the new node is not blocked. A removed node no longer occupies a slot of its owner, and its `node_id` can be passed to `add_node` again (which yields a new node without any links).
4. **Blocking and removal.** `set_blocked` checks in order: the identifier -> `blocked` must be a boolean (`invalid_flag`) -> the node exists (`unknown_node`); on success it returns `{ ok = true, blocked = <new value>, changed = <whether the value changed> }`. `remove_node` checks in order: the identifier -> the node exists (`unknown_node`); on success it deletes the node and all of its links and returns `{ ok = true, removed_links = <number of links deleted> }`.
5. **Links.** Links are undirected, and there is at most one per pair of nodes. `link` and `unlink` check in order: the two identifiers (`invalid_id`) -> `a_id == b_id` (`self_link`) -> both nodes exist (`unknown_node`). `link` then: if this pair of nodes is already linked (regardless of argument order), returns `{ ok = true, created = false, cost = <existing cost> }`; otherwise, letting `dx` and `dz` be the coordinate differences of the two nodes, rejects with `link_too_long` if and only if `dx*dx + dz*dz > max_link_length * max_link_length` (a distance exactly equal to the limit is allowed); otherwise creates the link and returns `{ ok = true, created = true, cost = cost }`, where `cost = math.max(1, math.floor(math.sqrt(dx*dx + dz*dz) + 0.5))` (round to nearest, exactly .5 rounds up, minimum 1). Whether a node is blocked does not affect whether it can be linked. `unlink` returns `{ ok = true, removed = <whether a link was actually deleted> }`.
6. **Routes.** `route` checks in order: the two identifiers (`invalid_id`) -> both nodes exist (`unknown_node`) -> `from_id == to_id` (`same_node`) -> either endpoint is blocked (`blocked_endpoint`) -> search; when no path exists, `no_route`. A path may pass only through existing nodes that are not blocked, and the total cost is the sum of the `cost` of each link on it. On success it returns `{ ok = true, cost = <total cost>, hops = <number of links>, path = { from_id, ..., to_id } }`. Among all feasible paths choose the one with the smallest total cost; when the total cost is equal choose the one with the fewest `hops`; when still equal choose the one whose node ID sequence is lexicographically smallest: compare one by one starting from `path[1]`, and the path whose ID is smaller (Lua string `<`, i.e. byte order) at the first differing position wins. The result must not depend on the insertion order of nodes or links, on `pairs` order or on the search direction (the answer of `route(a, b)` is not necessarily the reverse of `route(b, a)`).
7. **Reservation.** After time validation `reserve` proceeds strictly in the following order:
   1. All four identifiers are valid, otherwise `invalid_id`.
   2. Request deduplication: if `request_id` has ever been reserved successfully, then when `traveler_id`, `from_id` and `to_id` are exactly the same as at that time it returns `{ ok = true, duplicate = true, ticket = <view of the current state of that ticket> }` (regardless of what state the ticket is in now, and regardless of the cooldown), otherwise it returns `request_conflict`. Only a successful reservation is recorded in the request history; a failed `reserve` records nothing, and its `request_id` can be used again afterwards.
   3. Cooldown: if the traveler has a `cooldown_until` and `now < cooldown_until`, it returns `{ ok = false, code = "cooldown", retry_at = cooldown_until }`; at `now == cooldown_until` reserving is already allowed.
   4. Each traveler has at most one live ticket (status `reserved`); if one already exists, `traveler_busy`.
   5. Compute the route according to item 6; on failure return the error code of the route as is.
   6. Create the ticket and return `{ ok = true, duplicate = false, ticket = <view> }`.
   The fields of a ticket view are: `ticket_id` (a non-empty valid identifier that is never repeated within the same network, including after save/load), `request_id`, `traveler_id`, `from_id`, `to_id`, `path` (array of node IDs), `cost` (total cost of the route), `price = math.ceil(cost * cost_per_unit)`, `status`, `created_at = now`, `expires_at = now + ticket_ttl`. The values of `status` are `reserved`, `committed`, `aborted`, `expired`, `invalidated`.
8. **Commit and abort.** After time validation `commit` and `abort` check in order: `ticket_id` is a valid identifier (`invalid_id`) -> the ticket exists (`unknown_ticket`).
   - `commit`: when the ticket is already `committed` it returns `{ ok = true, duplicate = true, ticket = <view>, cooldown_until = <value determined at the first commit> }` and changes no state (the cooldown does not start again); when the ticket is in any other non-`reserved` state it returns `{ ok = false, code = "ticket_closed", status = <current status> }`. For a live ticket the route is re-verified first: every node on `path` currently exists and is not blocked, every pair of adjacent nodes is currently still linked, and the sum of the current `cost` of these links equals the `cost` of the ticket. If re-verification fails, the ticket is set to `invalidated`, the traveler is released (no cooldown) and `route_changed` is returned; new, or even better, links appearing in the graph do not invalidate the ticket. If re-verification passes, the ticket is set to `committed`, the traveler gets `cooldown_until = now + cooldown`, and it returns `{ ok = true, duplicate = false, ticket = <view>, cooldown_until = now + cooldown }`.
   - `abort`: a live ticket is set to `aborted` and it returns `{ ok = true, duplicate = false, ticket = <view> }`; when the ticket is already `aborted` it returns `{ ok = true, duplicate = true, ticket = <view> }`; in any other state it returns `ticket_closed` (with `status`). `abort`, expiry and `route_changed` never produce a cooldown, and the traveler can reserve again immediately.
9. **Expiry.** A ticket is live only while `now < expires_at`; as soon as a call that passes time validation satisfies `now >= expires_at`, the ticket becomes `expired` and the traveler is released (so at `now == expires_at` a `commit` gets `ticket_closed` with `status = "expired"`). `tick(now)` returns `{ ok = true, expired = { ticket_id, ... } }`, which contains only the tickets set to expired by this call, sorted by `expires_at` ascending and then by `request_id` string ascending; a ticket already set to expired by the expiry processing of another method does not appear again, and every ticket expires exactly once.
10. **Snapshot.** `snapshot(now)` returns `{ ok = true, now = now, nodes, links, tickets, cooldowns }`: `nodes` is an array of `{ id, owner_id, x, z, blocked }` in ascending `id` order; `links` is an array of `{ a, b, cost }` in which each link appears only once with `a < b`, in ascending order by `a` and then by `b`; `tickets` contains only the views of live tickets, in ascending order by `expires_at` and then by `request_id`; `cooldowns` is an array of `{ traveler_id, cooldown_until }` that contains only entries with `now < cooldown_until`, in ascending `traveler_id` order.
11. **Save and load.** `save(now)` returns `{ ok = true, data = <table> }`. `data` is newly created plain data: it contains only strings, numbers, booleans and nested tables (whose keys are strings or numbers), carries no metatable, and its internal layout is up to the implementation. `Network.load(data, options)` returns a network that restores the nodes, the links and their costs, the blocked flags, all tickets (including closed ones) and their statuses, the cooldowns, the request history, the ticket sequence and `clock`, so that after loading, `snapshot`, retries, `commit`, `abort`, the cooldown boundaries and the uniqueness of new `ticket_id` values are all consistent with the original network; `load` must not keep a reference to `data` (modifying `data` afterwards does not affect the network). When `data` is not a table or cannot be recognized, `load` returns an empty network equivalent to `Network.new(options)`.

## DST integration

The server configuration is fixed as: `max_nodes_per_owner = 4`, `max_link_length = 60`, `cost_per_unit = 0.25`, `ticket_ttl = 10`, `cooldown = 30`, the currency prefab is `goldnugget` (the fare `price` is the number of gold nuggets to deduct), and the departure radius is `TRAVEL_RADIUS = 4`. The component's `now` is taken from `GetTime()` (after a save is loaded an offset must be added to guarantee that it is not less than the saved `clock`).

- In `modmain.lua`, use `AddPrefabPostInit("world", fn)` to attach the component `waystonenetwork` (file `scripts/components/waystonenetwork.lua`) to the world only on the master simulation (`ismastersim`).
- The return values of the component methods are consistent with the core: a new table, `ok`, and `code` on failure. The component exposes:
  - `Register(entity, node_id, owner_player)`: checks in order: `entity` is a valid entity with a `Transform` (otherwise `invalid_entity`) -> `owner_player.userid` is a non-empty string (otherwise `invalid_player`) -> the entity is already bound to some node (`already_registered`) -> `node_id` is currently bound to another entity (`duplicate_node`). If the `node_id` already exists in the core but has no bound entity (it comes from a save): when the owner differs from the saved one, `owner_mismatch`; when it is the same, rebind and return `{ ok = true, rebound = true, node_id = node_id }` (without changing the coordinates and links in the core). Otherwise call `add_node` with the `x` and `z` of the entity's real coordinates `entity.Transform:GetWorldPosition()`, with `owner_player.userid` as the owner; on success return `{ ok = true, rebound = false, node_id = node_id }`, on failure return the core result as is and do not bind. Coordinates are never obtained from call arguments or from the client.
  - On binding, listen for `onremove` on the entity; when the entity is removed, `remove_node` it from the core, unbind it, and `RemoveEventCallback` with the same callback.
  - `Link(node_a, node_b)` and `Route(from_id, to_id)`: return the results of the core `link` and `route` respectively.
  - `Travel(player, request_id, from_id, to_id)`, which must execute strictly in the following order:
    1. `player.userid` must be a non-empty string, and the player must have a `Transform` and `components.inventory`, otherwise `invalid_player`. The traveler identity is taken only from `player.userid`.
    2. Call the core `reserve`; on failure return it as is. If the result has `duplicate == true`: when the ticket is `committed` return `{ ok = true, duplicate = true, ticket = ticket }` without charging or moving again; otherwise return `{ ok = false, code = "ticket_closed", status = ticket.status }`.
    3. Both the origin node and the destination node must be bound to a valid entity, otherwise `unbound_node`.
    4. The squared horizontal distance between the player's real position and the origin entity's real position must be `<= TRAVEL_RADIUS * TRAVEL_RADIUS` (exactly equal to the radius is allowed), otherwise `too_far`.
    5. If `inventory:Has("goldnugget", price)` is false, return `{ ok = false, code = "insufficient_funds", price = price }`; when there is not enough gold, not a single nugget may be deducted.
    6. Deduct `price` gold nuggets, then move the player to the destination entity's `Transform:GetWorldPosition()`, and then call the core `commit`.
    7. When `commit` fails (for example, an event callback triggered by the deduction removed a waystone on the way, yielding `route_changed`): move the player back to the original position, refund all `price` gold nuggets, and return the failure result of `commit` as is.
    8. On success return `{ ok = true, duplicate = false, ticket = <committed ticket view>, price = price, cooldown_until = <value returned by the core> }`.
    Any failure in steps 3 to 5 must `abort` the ticket before returning: the player's position and inventory stay unchanged, no live ticket is left behind, and no cooldown is produced. Because the reservation has been recorded, a later retry with the same `request_id` gets `ticket_closed` (`status = "aborted"`); the client should switch to a new `request_id`.
  - `OnSave()` returns a plain data table that contains the core `save` data; `OnLoad(data)` replaces the core state with `Network.load`, unregisters and clears all current entity bindings (the nodes stay in the core, waiting for the entities to `Register` again to be rebound), and restores the clock offset.
  - `OnRemoveFromEntity()` cancels the periodic task and unregisters the `onremove` callbacks on all registered entities.
- Use `DoPeriodicTask` to call the core `tick` periodically in order to clean up expired tickets.
- Register `AddModRPCHandler("rhenium_waystone", "travel", fn)`: `fn(player, request_id, from_id, to_id)` accepts only these three string identifiers and calls `Travel` after validating their types; it must not accept coordinates, a price, a route or the identity of another player.

## Base-game API contract

```lua
local x, y, z = entity.Transform:GetWorldPosition()

local inventory = player.components.inventory
local enough, found = inventory:Has("goldnugget", price)   -- enough is a boolean, found is the total held
inventory:ConsumeByName("goldnugget", price)                -- deducts; the player receives an itemlose event when a whole stack is taken

local refund = SpawnPrefab("goldnugget")                    -- refund
refund.components.stackable:SetStackSize(count)             -- a single stack must not exceed stackable.maxsize; split into several stacks beyond that
inventory:GiveItem(refund)

if player.Physics ~= nil then
    player.Physics:Teleport(x, y, z)
else
    player.Transform:SetPosition(x, y, z)
end

entity:ListenForEvent("onremove", on_remove)
entity:RemoveEventCallback("onremove", on_remove)           -- must pass the same function that was registered

local task = inst:DoPeriodicTask(period, fn, initialdelay)
task:Cancel()
```

The component definition uses the base-game `Class(function(self, inst) ... end)`, and defines the lifecycle methods in the form `function Component:OnSave()`, `function Component:OnLoad(data)` and `function Component:OnRemoveFromEntity()`.

## Acceptance

- The hidden behavior tests check item by item against the formulas above: identifier and coordinate validation, the owner limit and default options, link cost rounding and the length boundary, deduplication and snapshot ordering; route selection by cost first, hops second and lexicographic order last (independent of insertion order and direction); the effect of blocking and removal on routes; request deduplication, fare rounding, the cooldown and expiry boundaries, the order and exactly-once behavior of `tick`; the idempotency of `commit`/`abort`, the three causes of `route_changed`; time validation, the freshness of returned tables and the complete save/load round trip.
- The headless dedicated server tests use `CreateEntity()` to create waystone entities with a real `Transform` and player entities with a real `inventory` (into which `SpawnPrefab("goldnugget")` is put) (some with `Physics`, some without), and assert: the 5th waystone of the same owner gets `owner_limit`, and waystones 61 apart get `link_too_long`; link costs come from the real coordinates; after `Travel` the real world coordinates of the player equal the coordinates of the destination waystone, and the gold decreases by exactly `price`; a retry, a cooldown, insufficient funds, being too far away and an unbound node all leave position and inventory unchanged; after a waystone entity is removed with `:Remove()` its node and links disappear; when a waystone on the way is removed during the deduction, `route_changed` is returned and the refund and the position reset are completed; after `OnSave`/`OnLoad` the nodes, the request history and the cooldowns are still present and `Register` is required again (`rebound = true`); before `TheWorld:RemoveComponent("waystonenetwork")` the `entity.event_listeners.onremove` of a registered entity is non-empty, and afterwards there is no longer any `onremove` listener on it (the test then calls `TheWorld:AddComponent("waystonenetwork")` again). Player entities with `Physics` are created by `MakeCharacterPhysics`; `owner_player` and `player` are both server entities with the `userid` field set.
- The static checks require that every submitted Lua file is non-empty, that the non-comment code totals at least 280 lines, and that the base-game API wiring listed in this document is satisfied: the `ismastersim` guard, `AddPrefabPostInit("world"`, `AddComponent("waystonenetwork")`, `Transform:GetWorldPosition(`, `Physics:Teleport(`, `Transform:SetPosition(`, `goldnugget`, `:Has(`, `:ConsumeByName(`, `:GiveItem(`, `AddModRPCHandler("rhenium_waystone", "travel"`, `.userid`, `:OnSave(`, `:OnLoad(`, `:OnRemoveFromEntity(`, `ListenForEvent("onremove"`, `RemoveEventCallback("onremove"`, `DoPeriodicTask(`, `:Cancel(`. The RPC handling and the cancellation of the periodic task cannot be observed in the synchronous dedicated server tests and are covered only by the static checks.

You may use only base-game APIs, prefabs and assets; you must not use placeholder implementations or hard-code against test names.
