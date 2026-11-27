# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Server-authoritative camp fuel ration allocator

## Background and goal

A multiplayer base has a shared fuel depot: players deposit fuel items such as logs and twigs into it, and at intervals the server distributes the stock, by "priority classes + max-min fairness within a class", to the registered fires (campfires, stone fire pits, etc.). A client can only express "which item I deposit, and how many"; it cannot decide fuel units, stock, fire levels or allocation results. Network retries, a full depot, a fire being dismantled before settlement, the `fueled` component actually accepting less than the planned amount, and world reloads must not let fuel units appear out of nothing, disappear or be delivered twice.

Starting from an empty mod workspace, implement a DST-independent pure Lua integer rationing core, and a master simulation world component that uses the base-game `fueled` and `inventory` components. Only base-game APIs, prefabs, components and assets may be used.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/fuelration/allocator.lua
scripts/components/fuelration.lua
```

The core module `scripts/fuelration/allocator.lua` must be able to run in a plain Lua environment without `GLOBAL`, `TheWorld`, `GetTime`, `require`, `os` (the code must be compatible with both Lua 5.1 and 5.4), must `return` a table, and must export:

```lua
Allocator.new(options)
Allocator.load(data, options)

allocator:deposit(request_id, player_id, units, now)
allocator:lookup(request_id, player_id)
allocator:register(consumer_id, priority, capacity, now)
allocator:unregister(consumer_id, now)
allocator:report(consumer_id, level, now)
allocator:plan(round_id, now)
allocator:commit(round_id, consumer_id, delivered_units, now)
allocator:abort(round_id, consumer_id, now)
allocator:close(round_id, now)
allocator:snapshot(now)
allocator:save(now)
```

`options` is always supplied by the caller with three valid integers, and no default values need to be defined: `options.depot_capacity` (>= 1, the maximum number of units the fuel depot can hold), `options.max_units_per_round` (>= 1, the maximum number of units a single consumer can be allocated in a single round), `options.reserve_floor` (>= 0, the number of reserve units that no plan may touch). The core must not read any clock; all times come from the `now` parameter.

## Core semantics

### 1. Return values and validation

1. Except for `lookup`, `snapshot`, `save`, every method returns a new table containing a boolean field `ok`. On failure `ok == false` and `code` is a string given below; on success `ok == true` and `status` is a string given below.
2. Validation proceeds in a fixed order, and the first failure decides `code`:
   (1) `now` must be a number, finite (not NaN, not +/-inf) and `>= 0`, otherwise `invalid_time`;
   (2) except for `report`, a `now` less than the core clock gives `time_regressed` (equal to the clock is valid);
   (3) identifiers are checked in signature order (`request_id` before `player_id`, `round_id` before `consumer_id`): each must be a string of length 1 to 64 (`#id`, both ends inclusive), otherwise `invalid_id`;
   (4) quantities are checked in signature order: each must be of type number, finite, integer-valued and not less than its lower bound, otherwise `priority` reports `invalid_priority` and the others (`units`, `capacity`, `level`, `delivered_units`) report `invalid_units`. Lower bounds: `units >= 1`, `capacity >= 1`, `priority >= 0`, `level >= 0`, `delivered_units >= 0`. Fractions, NaN, infinities, negative numbers, numbers in string form and `nil` are all rejected.
3. The core clock starts at 0. A call that fails at any of steps (1)-(4) must not change any state, must not advance the clock, and must not write to the request history. A call that passes (1)-(4) (except `report`) immediately advances the clock to `max(clock, now)`, even if it then fails for a business reason (such as `unknown_consumer`).
4. `snapshot(now)` and `save(now)` are read-only operations: `now` is kept only for signature symmetry; it is not validated and does not advance the clock.

### 2. Deposits

5. `deposit` uses the pair `(player_id, request_id)` as its idempotency key (the same `request_id` coming from different players is a different request). When validation passes and the key has not appeared before: let `free = depot_capacity - available - reserved` (reserved units occupy capacity as well).
   - `free == 0`: return `{ ok = false, code = "depot_full", accepted = 0 }`;
   - `units <= free`: deposit everything, return `status = "accepted"`, `accepted = units`;
   - otherwise deposit only `free` units, return `status = "partial"`, `accepted = free`.
   All three outcomes are written to the request history, and the first result carries `duplicate = false`. The deposited amount is added to `available`, `deposited_total` and that player's cumulative contribution.
6. When the key has appeared before (decided after validation): do not change the stock, and return the same `ok`, `status` or `code`, and `accepted` as the first time, with `duplicate = true`. Even if the depot has gained space later, a recorded `depot_full` is still replayed as `depot_full`.
7. `lookup(request_id, player_id)` is read-only: it returns a new table with the result recorded for that key (same fields as above, `duplicate = true`), and returns `nil` when there is no record or an identifier is invalid.

### 3. Consumers and levels

8. `register` returns `status = "registered"` on success; the new consumer's `level` equals `capacity` (i.e. its demand is 0 before the first report), its last report time is recorded as this call's `now`, and `received = 0`. When a consumer with the same name already exists, return `duplicate_consumer` and do not change the original record. Demand is defined as `demand = capacity - level`.
9. The `now` of `report` is a "measurement time": it is not compared with the core clock and does not advance the core clock. If the consumer does not exist, return `unknown_consumer`. If `now` is strictly less than that consumer's last report time, return `{ ok = true, status = "stale", level, demand }` and change no state; otherwise (including equal) accept it: `level = min(level, capacity)`, the last report time is updated to `now`, and return `{ ok = true, status = "reported", level, demand }` (the returned values are the stored values).
10. `unregister`: if the consumer does not exist, return `unknown_consumer`; otherwise delete it and return `{ ok = true, status = "unregistered", returned = n }`. If it has a `pending` share in the open round, that share immediately becomes `aborted`, all of its units go back to `available`, and `n` is that number of units; otherwise `n = 0`. After unregistering, a consumer with the same name can `register` again (it is treated as a brand-new consumer and does not inherit the old share).

### 4. Planning

11. After passing validation, `plan(round_id, now)` decides in order: (1) an open round exists and its id equals `round_id`: replay, see item 14; (2) some other open round exists: `round_open`; (3) `round_id` has been closed before: `round_closed`; (4) otherwise create a new round. There is at most one open round at any time; even when there are no shares at all, the new round is still created and must be closed with `close`.
12. The allocation budget is `budget = max(0, available - reserve_floor)`. Each consumer's demand cap is `want = min(demand, max_units_per_round)`; a consumer with `want == 0` does not take part and does not appear in the result. Classes are processed one by one in ascending `priority` order (the smaller the number the earlier; the next class gets its turn only after the higher-priority class has fully satisfied its `want`). Within a class do integer water-filling: repeatedly give 1 unit to the consumer that "currently has the fewest allocated units and has not yet reached `want`", breaking ties by the smallest `consumer_id` (plain Lua string `<` comparison, i.e. `"f10" < "f2"`), until the budget is exhausted or the whole class has reached `want`. Any closed-form algorithm with the same result may be used. Example: budget 8, same class `a` (want 5), `b` (want 1), `c` (want 5) yields `a = 4, b = 1, c = 3`.
13. On success return `{ ok = true, status = "planned", round_id, shares, total, duplicate = false }`. `shares` is an array whose entries are `{ consumer_id, priority, units }`; it contains only shares with `units >= 1`, ordered by ascending `priority` and then by ascending `consumer_id`; `total` is the sum of the shares. These units move from `available` to `reserved`, and the status of each share is `pending`.
14. Replay: return exactly the same `round_id`, `shares`, `total` as the first time, with `duplicate = true`; do not recompute and do not reserve again, no matter whether settlements, deposits, reports or unregistrations happened in between.

### 5. Settlement and closing

15. After passing validation, `commit` and `abort` decide in order: (1) `round_id` is not the current open round: return `round_closed` if it has been closed, otherwise `unknown_round`; (2) the round has no share for this `consumer_id`: `unknown_share`; (3) the share is already settled: change no state and replay the first settlement result with `duplicate = true` (no matter whether this call is `commit` or `abort`, and no matter what `delivered_units` is); (4) `commit` only: `delivered_units` greater than the share's units returns `over_delivery`, and the share stays `pending`; (5) settle.
16. The settlement result is `{ ok = true, status, units, delivered, returned, duplicate = false }`. `commit`: `status = "committed"`, `delivered = delivered_units` (0 is valid), `returned = units - delivered`; `abort`: `status = "aborted"`, `delivered = 0`, `returned = units`. On settlement `reserved` decreases by `units`, `available` increases by `returned`, and `delivered_total` increases by `delivered`. `commit` also updates the consumer, if it is still registered, to `level = min(capacity, level + delivered)`, `received = received + delivered`.
17. `close(round_id, now)`: if `round_id` is already closed, replay the first close result with `duplicate = true`; if it is the current open round, settle all `pending` shares as `abort` and then close it; otherwise `unknown_round`. The result is `{ ok = true, status = "closed", round_id, total, delivered, returned, duplicate }`, where `delivered` is the sum delivered in this round and `returned = total - delivered`. A `round_id` that has been closed can never again be used for `plan`, `commit`, `abort`.
18. Conservation: at any moment `deposited_total == available + reserved + delivered_total`, and none of the three is negative.

### 6. Snapshot and persistence

19. `snapshot` returns a brand-new table (modifying it must not affect the core, and the same holds for any result table returned to the caller) with the fields: `clock` (the core clock), `available`, `reserved`, `free` (`depot_capacity - available - reserved`), `deposited_total`, `delivered_total`, `consumers`, `contributors`, `round`.
    - `consumers`: an array in ascending `consumer_id` order, each entry `{ consumer_id, priority, capacity, level, demand, received }`;
    - `contributors`: an array in ascending `player_id` order, each entry `{ player_id, units }`, where `units` is the cumulative number of units accepted from that player;
    - `round`: `nil` when there is no open round, otherwise `{ round_id, total, shares }`, where `shares` is in the same order as the plan, each entry `{ consumer_id, priority, units, status, delivered, returned }`, `status` is `pending`, `committed` or `aborted`, and `delivered` and `returned` of a `pending` share are 0.
    The snapshot does not expose the request history.
20. `save` returns a new table containing only string/number keys and strings, finite numbers, booleans and nested tables (no functions, no metatables, no circular references). `Allocator.load(data, options)` restores the full semantics: the clock, the stock and totals, the consumers (including last report times), player contributions, the request history, closed round ids and their close results, and an open round containing partially settled shares. `load` must not keep a reference to any table inside `data`; when `data` is not a table it is equivalent to `Allocator.new(options)`.

## DST integration

The server configuration is fixed as follows (the hidden dedicated server tests depend on these values):

```lua
local OPTIONS = { unit_size = 15, depot_capacity = 60, max_units_per_round = 6, reserve_floor = 2 }
local FUEL_UNITS = { log = 3, twigs = 1, cutgrass = 1 }   -- whitelist: prefab -> fuel units per item
local ROUND_PERIOD = 30                                    -- seconds
```

- Attach the world component `fuelration` through `AddPrefabPostInit("world", ...)` on the master simulation only (return immediately when `inst.ismastersim` is false).
- The component exposes `Track(entity, consumer_id, priority)`, `Untrack(consumer_id)`, `Deposit(player, request_id, item_prefab, count)`, `RunRound(round_id)`, `Snapshot()`, `OnSave()`, `OnLoad(data)`, `OnRemoveFromEntity()`. `Snapshot()` returns the result of the core `snapshot`.
- **Time**: the `now` that the component passes to the core is based on `GetTime()`. `GetTime()` restarts from 0 in every server session, whereas the core clock is restored with the save, so the component must guarantee that the time passed to the core after `OnLoad` is not less than the restored `snapshot().clock` (for example by maintaining an offset, or by taking the larger of the two); otherwise every call after a reload would get `time_regressed`.
- **Track**: decide in order: (1) `entity` is invalid, has no real `entity.components.fueled`, or the converted capacity is less than 1: `{ ok = false, code = "not_fueled" }`; (2) the entity is already tracked: `already_tracked`; (3) call the core `register`, and on failure (`invalid_id`, `invalid_priority`, `duplicate_consumer`) return the result as is and leave no listener behind. Capacity and level are taken from the real component: `capacity = math.floor(fueled.maxfuel / unit_size)`, `level = math.min(capacity, math.ceil(fueled.currentfuel / unit_size))` (capacity rounds down and level rounds up, which guarantees that the demand never exceeds the fuel the real component can still accept). After success, immediately `report` the level once, listen for the entity's `onremove`, and return `{ ok = true, status = "registered", consumer_id, capacity, level }`.
- **Untrack**: if not tracked, return `{ ok = false, code = "unknown_consumer" }`; otherwise unregister the `onremove` listener with the same function object, call the core `unregister` and return its result. When a tracked entity fires `onremove`, the same Untrack must be performed (so a removed fire no longer takes part in later allocations, and its unsettled share returns to the stock).
- **Deposit**: the client is untrusted. Decide in order: (1) `player.userid` is not a non-empty string: `invalid_player`; (2) there is no `player.components.inventory`: `no_inventory`; (3) `item_prefab` is not in the whitelist: `not_fuel`; (4) `count` is not an integer-valued number `>= 1`: `invalid_units`; (5) `request_id` is not a string of 1 to 64 characters: `invalid_id`; (6) the core `lookup(request_id, player.userid)` already has a record: return that record directly (`duplicate = true`) without touching the inventory again; (7) `units = count * FUEL_UNITS[item_prefab]` is greater than the core `snapshot().free`: `depot_full` (the component layer does not do partial deposits); (8) `inventory:Has(item_prefab, count)` is false: `insufficient_items`. None of the rejections in (1)-(8) removes any item or writes to the request history. After that, remove exactly `count` items from the real inventory and re-check that the quantity really decreased by `count` (otherwise return `removal_failed` and do not credit anything); only after the removal has succeeded, call the core `deposit(request_id, player.userid, units, now)` and return its result.
- **RunRound(round_id)**: (1) for each tracked entity: if the entity is no longer valid or has lost its `fueled` component, Untrack it, otherwise `report` the latest level to the core using the formula above; (2) call the core `plan`, and on failure return the result as is (for example `round_closed`) without adding any fuel; (3) process each share in plan order: when the entity is still valid, record `before = fueled.currentfuel`, call `fueled:DoDelta(units * unit_size)`, and then call the core `commit` with `delivered = clamp(math.floor((fueled.currentfuel - before) / unit_size), 0, units)`; when the entity is unavailable, call `abort`; (4) call the core `close`. Return `{ ok = true, status = "closed", round_id, shares, total, delivered, returned }`, where the last three fields are taken from the result of `close`, and `shares` is an array in the same order as the plan, each entry `{ consumer_id, units, delivered, status }` (`status` is `committed` or `aborted`).
- The component uses `self.inst:DoPeriodicTask(ROUND_PERIOD, ...)` to periodically execute `RunRound` with `"auto-" .. n` as the `round_id` (`n` is an incrementing integer counter that is saved with the save data).
- `AddModRPCHandler("rhenium_fuel", "deposit", function(player, request_id, item_prefab, count) ... end)`: the RPC payload consists only of the request ID, the prefab name and the count; `player` is passed in by the server, and a player, userid, fuel units or stock values sent by the client must not be accepted. The handler hands these three values to `Deposit(player, request_id, item_prefab, count)`; payloads of the wrong type (for example `request_id`/`item_prefab` is not a string, `count` is not a number) must be silently ignored or rejected by `Deposit`, must not raise an error, and must not remove items.
- **OnSave / OnLoad**: `OnSave()` returns a table containing the core `save` result and the automatic round counter. `OnLoad(data)` restores the core with `Allocator.load` and then reconciles: (1) if the restored state contains an open round, `close` it immediately (fuel delivery is synchronous, so no fuel is in flight after a reload); (2) the entity-to-consumer mapping exists only in the memory of the current session: a consumer that exists in the core but for which the component currently tracks no entity must be removed with `unregister`; (3) a consumer that the component is tracking but that does not exist in the restored core must be registered again with `register` using its original `priority`, and the latest level must be sent with `report` for all entities that are still tracked.
- **OnRemoveFromEntity**: cancel the periodic task (`task:Cancel()`), and unregister the `onremove` listeners on all tracked entities with the same function object.

## Base-game API contract

The following usages come from the current base-game Lua interface and can be used directly in the integration layer; the task will not require you to guess signatures:

```lua
AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return
    end
    inst:AddComponent("fuelration")
end)

-- fueled component (campfire (campfire): maxfuel = 270; stone fire pit (firepit): maxfuel = 360)
local fueled = entity.components.fueled
fueled.maxfuel                 -- number, fuel limit (seconds)
fueled.currentfuel             -- number, current fuel (seconds)
fueled:DoDelta(amount, doer)   -- currentfuel = clamp(currentfuel + amount, 0, maxfuel), and triggers the base-game section callbacks

-- inventory component
local enough, found = inventory:Has(prefab, count)  -- enough: boolean; found: quantity actually held (including stacks)
inventory:ConsumeByName(prefab, count)              -- removes and destroys count items of this prefab (across stacks)
local stacks = inventory:GetItemByName(prefab, count) -- table: item entity -> quantity taken from that stack (total not exceeding count)
local taken = inventory:RemoveItem(item, true)      -- moves the whole stack out of the inventory and returns that entity (you must call taken:Remove() yourself)
local part = item.components.stackable:Get(n)       -- splits n off the stack as a new entity (the original stack decreases by n; you must call part:Remove() yourself)

-- a listener can only be unregistered if the same function object was kept
self.inst:ListenForEvent("onremove", on_remove, entity)
self.inst:RemoveEventCallback("onremove", on_remove, entity)

local task = self.inst:DoPeriodicTask(period, fn)
task:Cancel()

-- The base game registers the handler as MOD_RPC_HANDLERS[namespace][MOD_RPC[namespace][name].id];
-- the dedicated server tests call this registered function directly as (player, request_id, item_prefab, count).
AddModRPCHandler("rhenium_fuel", "deposit", function(player, request_id, item_prefab, count)
    -- player is passed in by the server; do not accept a player/userid sent by the client.
end)
```

`entity:IsValid()` tells whether the entity still exists. `GetTime()` returns the simulation time of the current session (seconds). The component uses the base-game `Class` form and hooks into the lifecycle with `function Component:OnSave()`, `function Component:OnLoad(data)`, `function Component:OnRemoveFromEntity()`; removing the world component through `TheWorld:RemoveComponent("fuelration")` triggers `OnRemoveFromEntity`.

## Acceptance

- Units are conserved and the stock never goes negative; retried deposits, plans, settlements and closes do not move units twice.
- Priority, within-class fairness, the per-round cap and the reserve floor show up in exact integer shares.
- An open round containing partially settled shares, the request history, closed rounds and player contributions keep their semantics after `save/load`.
- Items, counts and player identities forged by a client do not affect server-side decisions; a rejected deposit removes no items.
- The mod can be loaded on a headless dedicated server. The hidden dedicated server tests really spawn `campfire` and `firepit`, set a known fuel level through the `fueled` component, create entities that have a real `inventory` and `userid` and hold real `log` and `twigs`, and assert that the `fueled.currentfuel` of each fire rises exactly by its share, that the inventory loses exactly the deposited items, that a fire removed with `:Remove()` before the round no longer holds a share, that when the real `fueled.maxfuel` is lowered after `Track` so that `DoDelta` actually accepts less than the planned amount, `commit` uses only the measured amount and the remaining units return to the depot, that the semantics stay consistent after `OnSave/OnLoad` (including the case where `GetTime()` resets to zero), and that listeners and the periodic task are cleaned up after `Untrack` and after component removal.

The submission must not leave behind `TODO`, `IMPLEMENT ME`, deliberately raised "not implemented" errors, or hollow shell code that exists only to match the static checks.
