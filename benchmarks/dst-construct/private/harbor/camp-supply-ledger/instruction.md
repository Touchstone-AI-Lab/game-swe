# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Server-authoritative camp supply ledger

## Background and goal

A multiplayer server wants to provide a limited amount of basic supplies to every active player each day. The client can only express "which preconfigured supply bundle to claim"; it cannot decide the item prefab, the count, the day or the remaining quota. Network retries, a full inventory, a failure to spawn an item and a world reload must not cause duplicate issuance or loss of quota.

Starting from an empty mod workspace, implement a plain Lua ledger and a master simulation world component. You may use only base-game APIs, prefabs, components and assets; you must not ship custom art.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/campsupply/ledger.lua
scripts/components/campsupplyledger.lua
```

The core module must be able to run in a plain Lua environment that has no `GLOBAL`, `TheWorld`, `TheNet`, `SpawnPrefab` or similar objects, and must export:

```lua
Ledger.new(options)
Ledger.load(data, options)

ledger:begin_day(day)
ledger:set_player(player_id, active)
ledger:claim(player_id, request_id, bundle_id, day)
ledger:commit(token)
ledger:rollback(token)
ledger:snapshot()
ledger:save()
```

`options.bundles` is the table of supply bundles configured by the server; each bundle lists base-game item prefabs and positive integer counts. `options.daily_limits` gives the per-player, per-day limit for each prefab.

## Core semantics

1. All IDs must be strings that are non-empty, bounded in length and free of control characters. `day` must be a non-negative integer and strictly monotonic; an old day must not change any state.
2. `set_player` controls whether a player may claim. An unknown bundle, an inactive player, an illegal count or insufficient quota must be rejected before a reservation is created.
3. `player_id + request_id` uniquely identifies one request. The idempotency record must be looked up before any quota is modified; a retry returns the first pending, committed, rolled_back or rejected result.
4. A successful `claim` creates a unique token and immediately reduces the available quota, but does not count it as issued. The return value contains at least `ok`, `token` and the list of items to create, resolved from the server-side configuration.
5. `commit` may only turn a pending token into committed; a repeated commit returns the same final state and must not deduct quota again. `rollback` may release a pending quota only once; a committed token cannot be rolled back.
6. When `begin_day` moves to a newer day it resets the current day's consumption, but keeps the idempotency history and the outstanding reservations; an old token that is committed or rolled back on a new day must still settle the quota of its original day correctly.
7. `snapshot` returns a new table stably sorted by player ID, item prefab and token, and must not expose mutable internal tables. `save/load` round-trips the day, the quotas, the request states, the reservations and the token sequence completely.

## Return values and data shapes

The hidden tests depend only on the following public shapes:

- `options.bundles[bundle_id]` may be written as an array of records `{ { prefab = "twigs", count = 2 }, { prefab = "cutgrass", count = 1 } }` or as a map `{ twigs = 2, cutgrass = 1 }`; both forms must be accepted. `options.daily_limits[prefab]` is the per-player, per-day limit for that prefab.
- `begin_day` and `set_player` return `false` when rejected and any non-`false` value on success.
- `claim` returns a new table. On success `ok = true`, `status = "pending"`, `token` is a string and `items` is an array in which each prefab of the bundle has one `{ prefab = ..., count = ... }` record. On rejection `ok = false` and `status = "rejected"`. A retry with the same `player_id + request_id` returns the first result (including the same `token`), even if the retry carries a different `bundle_id`.
- `commit(token)` returns `{ ok = true, status = "committed" }`, and a repeated commit returns the same content. `rollback(token)` returns `{ ok = true, status = "rolled_back" }` the first time it releases a pending reservation; a repeated call on an already rolled-back token returns `status = "rolled_back"` and must not release quota again; on a committed token it returns `ok = false`.
- The top level of `snapshot()` contains at least the current `day` and `players`.
- The world component's `Claim` returns a table with a boolean field `ok`.

## DST integration

- Attach `campsupplyledger` only on `TheWorld.ismastersim`.
- The component exposes `Claim(player, request_id, bundle_id)` and obtains the identity from `player.userid`.
- Use `AddModRPCHandler`; the RPC payload must not contain a prefab, a count, the day, the remaining quota or a player object.
- Call the core `claim` first, then deliver the base-game items through `SpawnPrefab` and the player's `inventory:GiveItem`. `commit` is allowed only after every delivery has succeeded.
- If any spawn or delivery fails, remove the items already delivered for this request and `rollback`. Partial items must not be left with the player.
- Listen for `ms_cyclecomplete` to advance the day; persist through the component's `OnSave/OnLoad`.
- Every long-lived `ListenForEvent` must have a matching `RemoveEventCallback`; when the component is removed it must cancel its own tasks and clean up temporary entities.

## Base-game API contract

The following forms come from the current base-game Lua interface and can be used directly in the integration layer; the task does not ask you to guess signatures:

```lua
AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return
    end
    inst:AddComponent("campsupplyledger")
end)

AddModRPCHandler("rhenium_supply", "claim", function(player, request_id, bundle_id)
    -- player is passed in by the server; do not accept a player/userid sent by the client.
end)

local item = SpawnPrefab(prefab)
local accepted = item ~= nil
    and player.components.inventory ~= nil
    and player.components.inventory:GiveItem(item)
```

`Inventory:GiveItem(item, slot, src_pos)` returns a slot or a truthy value on success; on failure it may return `false/nil`, and it may put the item into the active item or drop it, so a failure rollback must also confirm the item's actual owner. Event listening must keep the same function object:

```lua
inst:ListenForEvent("ms_cyclecomplete", on_cycle_complete, TheWorld)
inst:RemoveEventCallback("ms_cyclecomplete", on_cycle_complete, TheWorld)
```

The component uses the base-game `Class` form and hooks into the lifecycle with `function Component:OnSave()`, `function Component:OnLoad(data)` and `function Component:OnRemoveFromEntity()`. The dedicated server configuration must provide at least `basic = { twigs = 2, cutgrass = 1 }`, so that the public functionality and the server assertions can use it; other bundles may be added.

## Acceptance

- Network retries do not duplicate items or consume quota twice.
- An inventory failure and a spawn failure restore the quota and the item state exactly once.
- Semantics stay consistent after a day change and after a save reload.
- Items, counts and days forged by the client do not affect server-side decisions.
- The mod can be loaded on a headless dedicated server. The hidden dedicated server tests create a server entity with a base-game `inventory`, assert that the `basic` bundle really enters the inventory, that the component state can round-trip through `OnSave/OnLoad`, and that the component can still save after `ms_cyclecomplete` is triggered; the rollback of a failed delivery is covered by the pure-module tests and the static integration checks.
- The static checks require that every submitted Lua file is non-empty, that the non-comment code totals at least 220 lines, and that the base-game API wiring listed in this document is satisfied.

You must not leave `TODO`, `IMPLEMENT ME`, a deliberately raised "not implemented" error, or hollow code that exists only to match the static checks.
