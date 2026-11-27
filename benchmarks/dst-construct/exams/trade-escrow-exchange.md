---
difficulty: hard
estimated_minutes: 390
domains:
  - trading
  - transactions
  - inventory
  - persistence
---

# Server-authoritative two-player trade escrow

## Background and goal

Two players want to exchange base-game items face to face. Each side puts items into an escrowed offer, and after each has confirmed the other side's **current** offer, the server completes the exchange in one step. A client can only express "what I offer" and "which revision of the other side's offer I have seen and agree to"; whether the items really exist, whether the exchange happens and when the trade expires are decided only by the server. Swapping an offer after a change, duplicate packets, expiry, insufficient inventory, a full inventory, a player leaving and a world reload must not duplicate items, swallow items or leave the trade stuck.

Starting from an empty mod workspace, implement a plain Lua escrow state machine that is independent of DST, and a master simulation world component that operates on the base-game `inventory` component. Only the game's base-game APIs, prefabs, components and assets may be used.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/tradeescrow/escrow.lua
scripts/components/tradeescrow.lua
```

The core module must be able to run in a plain Lua environment without objects such as `GLOBAL`, `TheWorld`, `GetTime`, `require` and `os` (the code must be compatible with both Lua 5.1 and 5.4), and all time is passed in only through the `now` parameter. The module returns a table and exports:

```lua
Escrow.new(options)
Escrow.load(data, options)

escrow:open(trade_id, a_id, b_id, now)
escrow:offer(trade_id, party_id, items, revision, now)
escrow:confirm(trade_id, party_id, seen_revision, now)
escrow:cancel(trade_id, party_id, now)
escrow:begin_settle(trade_id, now)
escrow:finish_settle(trade_id, ok, now)
escrow:tick(now)
escrow:snapshot(now)
escrow:save(now)
```

`options` is provided by the server, and the tests always pass valid values:

```lua
options = {
    allowed_prefabs = { twigs = true, cutgrass = true }, -- whitelist: prefab -> true
    max_distinct = 2,                                     -- maximum number of distinct prefabs in one offer (positive integer)
    ttl = 30,                                             -- trade time to live (positive number)
}
```

Other helper methods may be added, but the names and argument order above and the field names below are the public contract.

## Return values and data shapes

The trade phase `phase` takes the values `"open"`, `"settling"`, `"settled"`, `"canceled"`, `"expired"`; the last three are called **closed**, and `open` and `settling` are called **in progress**.

Except for `snapshot` and `save`, every method returns a **newly created** result table that contains at least a boolean `ok` and a string `code`. Whenever `trade_id` refers to an existing trade (including failure results, for example `not_a_party`, `trade_closed`, `trade_exists`), the result must also contain `phase`, whose value is the phase of that trade after this call has finished. Additional fields of each method on success:

| Method | Success `code` | Additional fields |
| --- | --- | --- |
| `open` | `"opened"` | `trade_id`, `expires_at` |
| `offer` | `"offered"` | `revision` (that party's current revision) |
| `confirm` | `"confirmed"` | `ready` (boolean: whether both parties' confirmations are valid at this moment) |
| `cancel` | `"canceled"` | none |
| `begin_settle` | `"settling"` | `plan` (the transfer plan, see core semantics 9) |
| `finish_settle` | `"settled"` or `"reopened"` | none |
| `tick` | `"ticked"` | `expired` (array of the `trade_id` values newly expired by this call, ascending) |

On failure `ok = false` and `code` is one of the following: `"invalid_argument"`, `"unknown_trade"`, `"not_a_party"`, `"trade_closed"`, `"trade_locked"`, `"trade_exists"`, `"party_busy"`, `"prefab_not_allowed"`, `"invalid_count"`, `"too_many_prefabs"`, `"stale_revision"`, `"revision_conflict"`, `"stale_confirmation"`, `"not_ready"`, `"not_settling"`.

`snapshot(now)` returns `{ trades = { ... } }`. `trades` is an array in ascending `trade_id` order that **includes closed trades**, and each element is:

```lua
{
    trade_id = "t1", phase = "open", opened_at = 10, expires_at = 40,
    parties = {                      -- exactly two entries, ascending by party id
        { id = "alice", revision = 2, confirmed = false,
          items = { { prefab = "cutgrass", count = 1 }, { prefab = "twigs", count = 3 } } }, -- ascending by prefab
        { id = "bob", revision = 0, confirmed = false, items = {} },
    },
}
```

Every "ascending" in this document means Lua string `<` comparison.

## Core semantics

1. **Argument validation.** `trade_id`, `a_id`, `b_id` and `party_id` must be non-empty strings and `a_id ~= b_id`; `now` must be a number; `revision` must be an integer not less than 1; `seen_revision` must be an integer not less than 0; `items` must be a table; the `ok` of `finish_settle` must be a boolean. When any one of these is not satisfied, return `invalid_argument` and **do nothing at all** (not even expiry processing).
2. **Fixed processing order.** `open`, `offer`, `confirm`, `cancel`, `begin_settle` and `finish_settle` all process in the following order and return at the first hit: (1) `invalid_argument`; (2) perform exactly the same expiry processing as `tick(now)` (trades expired this way never appear again in the `expired` of any later `tick`); (3) the trade does not exist -> `unknown_trade` (`open` uses semantics 3 instead); (4) in methods that take a `party_id`, `party_id` is not one of the two parties of that trade -> `not_a_party`; (5) the phase table below; (6) the method's own rules. Apart from the expiry in step (2), a failed call must not change any state. `snapshot(now)` and `save(now)` likewise perform step (2) first, before reading.

   | Method \ current phase | `open` | `settling` | `settled` | `canceled` | `expired` |
   | --- | --- | --- | --- | --- | --- |
   | `offer`, `confirm` | continue with step (6) | `trade_locked` | `trade_closed` | `trade_closed` | `trade_closed` |
   | `cancel` | closes as `canceled`, success | `trade_locked` | `trade_closed` | idempotent success `canceled` (either party may call) | `trade_closed` |
   | `begin_settle` | see semantics 9 | idempotent success (semantics 9) | `trade_closed` | `trade_closed` | `trade_closed` |
   | `finish_settle(ok = true)` | `not_settling` | becomes `settled`, success `settled` | idempotent success `settled` | `trade_closed` | `trade_closed` |
   | `finish_settle(ok = false)` | `not_settling` | returns to `open`, success `reopened` | `trade_closed` | `trade_closed` | `trade_closed` |

3. **Opening.** `open`, after steps (1) and (2): if `trade_id` already exists - when it is closed, `trade_closed` (a closed id can never be reused); when it is not closed and the parties are the same pair (regardless of the order of a and b), idempotent success `opened`, changing no state and returning the original `expires_at`; otherwise `trade_exists`. If `trade_id` does not exist but `a_id` or `b_id` is currently in another in-progress trade -> `party_busy` (each party takes part in at most one in-progress trade at a time; the party is released immediately when the trade closes). Otherwise create the trade: phase `open`, `opened_at = now`, `expires_at = now + options.ttl`, and for both parties `revision = 0`, empty `items` and `confirmed = false`.
4. **Expiry boundary.** Only the `open` phase expires: a trade expires if and only if `now >= expires_at` (`now == expires_at` is expired, `now < expires_at` is not expired). `settling` never expires. After `finish_settle(false)` returns a trade to `open`, the original `expires_at` stays in force and later calls judge it by the same rule. Each call judges only by the `now` passed to that call (the `now` values that hidden tests pass to one instance are monotonically non-decreasing). `tick(now)` turns every trade that satisfies the condition into `expired`; the `expired` array lists only the ids newly expired by this call, in ascending order; when `now` is not a number it returns `invalid_argument`.
5. **Offer revision.** Step (6) of `offer` first compares `revision` with that party's current revision: smaller -> `stale_revision`; equal and `items` exactly identical to the stored offer (the same set of prefabs and the same count for each) -> idempotent success `offered`, **with no side effect at all** (no confirmation is cleared); equal but with different content -> `revision_conflict`; only a larger revision proceeds to semantics 6. Revisions only have to be strictly increasing; they need not be consecutive.
6. **Offer validation.** `items` is a `prefab -> count` table and may be an empty table. More distinct prefabs than `options.max_distinct` -> `too_many_prefabs`; a prefab that is not in `options.allowed_prefabs` (or a key that is not a non-empty string) -> `prefab_not_allowed`; a count that is not a positive integer (0, negative, fractional, non-number) -> `invalid_count`. Every call in the hidden tests contains at most one kind of violation. A rejected offer does not consume a revision and does not clear any confirmation.
7. **An accepted offer invalidates both parties' confirmations.** An accepted new revision (even when its content is identical to the old offer) stores a copy of `items`, updates the revision, and sets the `confirmed` of **both parties** to `false`.
8. **Confirmation.** Step (6) of `confirm`: `seen_revision` must equal the **other party's** current revision (0 when the other party has never offered), otherwise `stale_confirmation` and no confirmation is changed; when it is equal, set that party's `confirmed` to `true` and return `ready`. Confirming again after having confirmed, with a `seen_revision` that is still correct, is an idempotent success.
9. **Beginning settlement.** `begin_settle` in the `open` phase: the two parties' `confirmed` are not both `true` -> `not_ready`; otherwise the phase becomes `settling` and `plan` is returned. `plan` is an array in which every row is `{ from = giver id, to = receiver id, prefab = ..., count = ... }`, sorted by `from` ascending and then by `prefab` ascending, covering every prefab of both parties' offers. Calling it again on a `settling` trade returns a `plan` with the same content; every returned `plan` is a new table, and modifying it must not affect internal state.
10. **Finishing settlement.** `finish_settle(trade_id, true, now)` turns `settling` into `settled`; `finish_settle(trade_id, false, now)` turns `settling` back into `open` and clears both parties' confirmations (offers and revisions are kept), and after both parties confirm again the trade can be settled again.
11. **Snapshot.** `snapshot(now)` returns a completely new table on every call (including all nested tables), with the shape and ordering given in the previous section; modifying the returned value must not affect internal state.
12. **Save and load.** `save(now)` returns a new table made up only of tables, strings, numbers and booleans (no functions, no metatable, no circular references); its internal format is up to the implementation. `Escrow.load(save_data, options)` must fully restore all trades (phases including `settling`, offers, revisions, confirmations, `opened_at`, `expires_at`, the tombstones of closed ids and the party occupancy relation), so that the `snapshot` after loading is identical to the one before saving and the idempotence and rejection rules continue to hold; modifying `save_data` after loading must not affect the loaded instance. `Escrow.load(nil, options)` returns an empty, usable instance.

## DST integration

1. Attach the world component `tradeescrow` only on the master simulation, through `AddPrefabPostInit("world", ...)` (guarded by `inst.ismastersim` / `TheWorld.ismastersim`).
2. The component stores the core instance in the field `self.escrow` (after `OnLoad` it points to the restored instance) and uses a fixed server configuration: `allowed_prefabs` is exactly `twigs`, `cutgrass`, `flint`, `log`, `rocks`, `max_distinct = 4`, `ttl = 120`.
3. The component clock `Now()` returns `saved clock offset + GetTime()`: `OnSave` saves the current `Now()`, and after `OnLoad`, `Now()` must continue from the saved value instead of going back to 0 (`GetTime()` resets to zero after a server restart). All core calls use `self:Now()`.
4. Player identity comes only from `player.userid`. Component methods (all called with `:`):
   - `Open(player_a, player_b)`: when either argument is not an entity with a non-empty string `userid` and `components.inventory`, return `{ ok = false, code = "invalid_player" }`; otherwise the server generates a non-empty string `trade_id` that does not repeat during the whole lifetime of the save (including after save and load) and calls the core `open`, returning a table containing `ok`, `code` and `trade_id` (when the core fails, its `ok`/`code` are returned unchanged).
   - `Offer(player, trade_id, items)`: the server takes that player's current revision plus 1 as the new revision and calls the core `offer`, returning the core result (containing `ok`, `code`, `revision`). `Offer` does not check inventory.
   - `Confirm(player, trade_id, seen_revision)`: when `seen_revision` is `nil`, use the other party's revision as the server currently sees it (for calls from server code); otherwise pass it to the core unchanged. When the core fails, return its result unchanged. On success with `ready == false`, return the core result. With `ready == true`, perform settlement synchronously **within the same call** (see 6) and return a table containing `ok`, `code` and `phase`.
   - `Cancel(player, trade_id)`: call the core `cancel` and return its result.
   - `OnPlayerLeft(player)`: cancel the `open` trade that the player is in and forget the player's entity.
   - `Recover()`: call `finish_settle(id, false, now)` for every `settling` trade (an exchange of unknown progress is never replayed; both parties must confirm again), and return `{ ok = true, recovered = { trade_id values in ascending order } }`.
   - `OnSave()` returns a serializable table; `OnLoad(data)` restores the core, the `trade_id` generator and the clock, and performs the same recovery as `Recover()`; for `OnRemoveFromEntity()` see 9.
5. The component must remember, by `userid`, the player entity that most recently appeared in `Open`/`Offer`/`Confirm`/`Cancel`, and use it at settlement to obtain both parties' `inventory` (it may additionally fall back to `AllPlayers`).
6. Settlement order: (1) either party's entity is missing or `not entity:IsValid()` -> do not call `begin_settle`, return `{ ok = false, code = "counterparty_unavailable", phase = "open" }`, and confirmations stay unchanged; (2) `begin_settle` obtains `plan`; (3) for every row of `plan`, verify holdings with the giver's `inventory:Has(prefab, count)`; if any is insufficient -> `finish_settle(false)`, return `{ ok = false, code = "insufficient_items", phase = "open" }`, and both inventories are unchanged; (4) take the items out of both inventories, then hand them to the other party with `inventory:GiveItem`; (5) any item cannot fully enter the receiver's inventory (for example it is dropped on the ground because the inventory is full) -> restore the quantity of every prefab of both parties to what it was before settlement (including picking up items that were dropped on the ground), `finish_settle(false)`, return `{ ok = false, code = "delivery_failed", phase = "open" }`; (6) everything succeeded -> `finish_settle(true)`, return `{ ok = true, code = "settled", phase = "settled" }`.
7. Item quantities must be strictly conserved and exact: an offered quantity may span multiple item stacks, and only the offered quantity is taken. Real item entities must be moved (`RemoveItem` / `stackable:Get`); they must not be destroyed and then regenerated with `SpawnPrefab`; when a whole stack is transferred and the receiver previously had no item of the same kind, what is in the receiver's inventory is that original entity.
8. Register four server-side Mod RPCs in the namespace `rhenium_trade`: `open(player, target_userid)`, `offer(player, trade_id, prefab1, count1, prefab2, count2, ...)`, `confirm(player, trade_id, seen_revision)`, `cancel(player, trade_id)`. The payload contains only strings and numbers; for `open`, the server uses `target_userid` to look up the other party in `AllPlayers`. The variadic arguments of `offer` must be pairs of "string prefab, number count"; when any other type appears (including an entity or a table), the number of arguments is odd, or a prefab is repeated, the whole request is dropped and state is unchanged; a valid request is equivalent to calling `Offer(player, trade_id, { [prefab] = count, ... })`. When the `seen_revision` of `confirm` is not a number, the request is dropped.
9. On `self.inst` (the world entity), listen for the world event `ms_playerleft` and call `self:OnPlayerLeft(player)` in the callback; on `self.inst`, use `DoPeriodicTask` to periodically call the core `tick(self:Now())`. `OnRemoveFromEntity` must `RemoveEventCallback` with the same function object and `Cancel()` the periodic task. The dedicated server tests execute `TheWorld:RemoveComponent("tradeescrow")`, assert that the number of listener callbacks for `ms_playerleft` on the world (`TheWorld.event_listeners["ms_playerleft"]`) and the number of pending tasks of the world entity (`TheWorld.pendingtasks`) both decrease as a result, and then `TheWorld:AddComponent("tradeescrow")` again; the component must be able to attach normally again.
10. The mod must not print to the log any line containing the words `error`, `failed` or `missing`; it must not leave `TODO`, `IMPLEMENT ME` or placeholder implementations.

## Base-game API contract

The following signatures have been checked against the current official scripts and can be used directly:

```lua
AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return
    end
    inst:AddComponent("tradeescrow")
end)

AddModRPCHandler("rhenium_trade", "offer", function(player, trade_id, ...)
    -- player is passed in by the server; do not accept an entity or userid sent by the client.
end)
-- The registered handler can be retrieved with GetModRPCHandler("rhenium_trade", "offer").

local inventory = player.components.inventory
local enough, found = inventory:Has(prefab, count)        -- whether there is enough, total actually held (including the active item)
local stacks = inventory:GetItemByName(prefab, count)     -- { [item] = amount to take from that stack }
local whole = inventory:RemoveItem(item, true)            -- takes out the whole stack and returns that entity
local part = item.components.stackable:Get(n)             -- splits off a new entity when n is less than the stack size, otherwise returns item itself (still in its slot)
local size = item.components.stackable:StackSize()
local slot = other.components.inventory:GiveItem(item)    -- returns the slot or true on success
local owner = item.components.inventoryitem:GetGrandOwner()
```

`Inventory:GiveItem(item, slot, src_pos)` automatically merges into a non-full stack of the same kind (the merged entity is removed and `item:IsValid()` becomes false). When the inventory is full, it may put the item into the active item and return `true`, or it may drop the item on the ground and return `false`/`nil`, so the actual ownership of the item must be determined by combining the return value, `item:IsValid()` and `GetGrandOwner()`. The new entity split off by `stackable:Get(n)` is still registered under its original owner; no other handling is needed before handing it to the other party, and `GiveItem` releases it by itself.

Events and tasks must keep the same function object / task handle:

```lua
inst:ListenForEvent("ms_playerleft", on_player_left)      -- callback signature (world, player)
inst:RemoveEventCallback("ms_playerleft", on_player_left)
local task = inst:DoPeriodicTask(period, fn)
task:Cancel()
```

The component uses the base-game `Class` form and hooks into the lifecycle with `function Component:OnSave()`, `function Component:OnLoad(data)` and `function Component:OnRemoveFromEntity()`.

## Acceptance

- An offer change by either party invalidates both parties' confirmations; only a trade in which both parties have confirmed the other party's current revision is settled.
- The expiry boundary is exact at `now >= expires_at`, and the behavior of duplicate packets, old packets and closed ids is deterministic and free of side effects.
- When inventory is insufficient or delivery fails, both parties' inventory quantities are exactly the same as before settlement, and the trade returns to `open` and can be confirmed again.
- The `settling` phase can be saved, loaded and recovered; after loading, an exchange of unknown progress is not replayed.
- The headless dedicated server tests create two entities with the base-game `inventory` component and different `userid` values, put in real `twigs`, `cutgrass` and `flint` item stacks, complete trades through the component methods and the registered RPC handlers, and use `inventory:Has` to assert that both parties' quantities change exactly and stay unchanged on failure, as well as the leave, save/load and recovery behavior.

Hard-coding against test names or fixed ids is forbidden.
