# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Crash-safe container transfer transaction

## Background and goal

Players need to move a specified count of items of the same kind from one base-game container to another. The destination capacity may be insufficient, an adapter operation may fail midway, and the world may be saved and reloaded after the source items have been removed. The system must conserve items: it must not duplicate items, swallow items, or execute an already completed request again.

Starting from an empty workspace, implement a DST-independent transaction state machine and a server-side adapter layer that uses the base-game `container` component.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/containertransfer/transaction.lua
scripts/components/containertransfer.lua
```

The pure module exports:

```lua
Transaction.new(adapter, persisted)
Transaction.load(adapter, data)

transaction:transfer(request)
transaction:recover()
transaction:status(request_id)
transaction:save()
```

`request` contains `request_id`, `source_id`, `destination_id`, `prefab` and a positive integer `count`. The adapter contract is:

```lua
adapter:snapshot(container_id)
adapter:capacity(container_id, prefab)
adapter:remove(container_id, prefab, count)
adapter:add(container_id, items)
adapter:restore(container_id, snapshot)
```

## Core semantics

1. Validate all fields and reject an identical source and destination before any adapter call.
2. Snapshot entries contain at least `slot`, `prefab` and `count`, and may carry `perish_percent` and `finite_uses_percent`; source items are selected in ascending slot order.
3. Obtain the source and destination snapshots first, then preflight the source total and the destination capacity. On failure, `remove` and `add` must not be called.
4. Before the first destructive call, write a `prepared` intent containing both snapshots and the selected items into the saveable state; the phases are, in order, `prepared`, `source_removed`, `destination_added`, `committed`.
5. When `add` fails, restore the destination snapshot first, then restore the source snapshot. When the compensation itself fails, keep an explicit recoverable phase; completion must not be falsely reported.
6. `recover` completes the commit or compensates in reverse order, depending on the saved phase; repeated recovery must be idempotent.
7. The successful, failed or pending result for the same `request_id` must be stable. A retry of an already committed request must not call the adapter again.
8. `save` returns a new table and must not expose the adapter, functions or mutable internal tables to the caller.

## Return values and data shapes

The hidden tests depend only on the following public shapes:

- `transfer` returns a new table containing a boolean `ok` and a string `status`; on success and on a retry of that success `status = "committed"`, and on any failure `ok = false`.
- On success `adapter:remove` returns an array of the removed entries, each containing the source `slot`, `prefab`, `count` and optional metadata; on failure it returns `nil` and a reason. The core must pass these entries to `adapter:add(destination_id, items)` in ascending source slot order, keeping `slot` and the other fields.
- `adapter:add` and `adapter:restore` return `true` on success, and `false` and a reason on failure; `adapter:capacity` returns how many more of that prefab the destination can still accept.
- The first two adapter calls of a transfer are, in order, the source snapshot and the destination snapshot.

## DST integration

- Attach the `containertransfer` world component only on the master simulation.
- The server looks up entities by stable ID; the client may only send the source ID, destination ID, prefab, count and request ID, and must not send entities, slot snapshots or capacities.
- The adapter uses the slots of the base-game `components.container`, `RemoveItem`/`RemoveItemBySlot` and `GiveItem`, and preserves stacking, perish percentage and finite-use durability.
- Register a custom Action, a Component Action, a stategraph Action Handler and a server-side Mod RPC.
- Track the `itemget`, `itemlose` and `onremove` events of the containers; every listener registration must be paired with its removal.
- The world component saves its state through `OnSave/OnLoad` and calls `recover` after loading.

## Base-game API contract

The key calls and event shapes of the base-game container are as follows:

```lua
local container = entity.components.container
local item = container:GetItemInSlot(slot)
local removed = container:RemoveItemBySlot(slot)
local accepted = container:GiveItem(item, slot, source_position, false)

entity:ListenForEvent("itemget", on_item_get)   -- data.item, data.slot, data.src_pos
entity:ListenForEvent("itemlose", on_item_lose) -- data.prev_item, data.slot
entity:RemoveEventCallback("itemget", on_item_get)
entity:RemoveEventCallback("itemlose", on_item_lose)
```

`Container:GiveItem(item, slot, src_pos, drop_on_fail)` returns a boolean; transaction code should pass `drop_on_fail = false`, otherwise a capacity failure may drop the item into the world. Stack counts use `item.components.stackable:StackSize()` / `SetStackSize(count)`; the perish and durability percentages can be saved through `perishable:GetPercent()/SetPercent()` and `finiteuses:GetPercent()/SetPercent()` respectively.

The Action wiring uses the base-game signatures:

```lua
local ACTION = AddAction("RHENIUM_TRANSFER", "Transfer", action_fn)
AddComponentAction("SCENE", "container", function(inst, doer, actions, right)
    -- when the public interaction conditions are met: actions[#actions + 1] = ACTION
end)
AddStategraphActionHandler("wilson", ActionHandler(ACTION, "doshortaction"))
AddStategraphActionHandler("wilson_client", ActionHandler(ACTION, "doshortaction"))
AddModRPCHandler("rhenium_transfer", "request", function(player, ...)
end)
```

The world component must expose `Track(entity, stable_id)`, `Transfer(request)` and `Recover()`, for use by the normal gameplay wiring and by the headless dedicated server verification.

## Acceptance

- Insufficient capacity does not change either container.
- A partial failure is restored in the order destination first, then source, and the total item count is unchanged.
- Any persisted phase can be completed or safely rolled back after a reload.
- A retry does not transfer again.
- The headless dedicated server test creates two base-game chests and real item stacks, and asserts that after a successful transfer the counts at both ends are conserved, and that `Recover` can still be called after the component state makes an `OnSave/OnLoad` round trip; capacity failure, compensation order and recovery are covered by the pure-module tests, and event cleanup is covered by the static integration check.
- The static check requires that all submitted Lua files are non-empty, that the non-comment code totals at least 260 lines, and that the base-game API wiring listed in this document is satisfied.

Only base-game APIs, prefabs and assets may be used; placeholder implementations and hard-coding against test names are forbidden.
