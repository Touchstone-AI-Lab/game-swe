# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Server-authoritative loot roll arbitration

## Background and goal

After a boss falls it drops only one rare item, and the server must decide who gets it among the eligible players with a need / greed / pass roll. The eligible set, the item, the random seed and the deadline are all decided by the server; a client can only express its own choice. Late packets, old revisions, repeated resolution, players leaving midway, delivery failures and world reloads must not let the item be duplicated, swallowed or given to the wrong person.

The roll uses a **fully published pseudo-random number generator**: with the same seed and the same choices, every conforming implementation must obtain bit-for-bit identical roll values, winner and ranking, so the result can be recomputed by anyone.

Starting from an empty workspace, implement a DST-independent pure Lua arbiter, and a server-side world component that turns one award into a real base-game item.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/lootroll/arbiter.lua
scripts/components/lootrollarbiter.lua
```

The pure module `scripts/lootroll/arbiter.lua` returns a table and exports:

```lua
Arbiter.new(options)
Arbiter.load(data, options)

arbiter:open(roll_id, item, eligible_ids, seed, now)
arbiter:choose(roll_id, player_id, choice, revision, now)
arbiter:resolve(roll_id, now)
arbiter:mark_delivered(roll_id, ok, now)
arbiter:cancel(roll_id, now)
arbiter:tick(now)
arbiter:snapshot(now)
arbiter:save(now)
```

The pure module must not use any DST global object, `require`, `os` or `io`; all time must come only from the `now` argument. The code must be valid Lua 5.1 and valid Lua 5.4 at the same time.

`options` fields (a missing field takes its default value; the tests pass only valid values):

| Field | Meaning | Default |
| --- | --- | --- |
| `window` | Number of seconds the roll stays open, `deadline = now + window` | `30` |
| `allowed_items` | Array of item prefab strings that may be rolled for (whitelist) | `{}` |
| `max_wins_per_window` | A player who reaches this number of wins within the fairness window is demoted | `2` |
| `fairness_window` | Look-back seconds of the fairness ledger | `600` |
| `max_rounds` | Maximum number of roll rounds in one contest (including the first round) | `3` |
| `now` | Used only by `Arbiter.load`, see Core semantics 8 | none |

## Return values and data shapes

- Every method returns a **new table**; a caller modifying a returned table must not affect the arbiter or later return values.
- A failure returns `{ ok = false, code = <string> }` and **produces no side effect at all** (it does not occupy the roll id, does not record the revision, does not advance the generator).
- Every method that takes `now` checks `now` first: when it is not a finite number (`nil`, a non-number, NaN, `±math.huge`) the method returns `code = "invalid_time"`.
- When one call satisfies several failure conditions, return the first matching `code` in the order listed for that method.
- Player ids and roll ids are non-empty strings; "ascending" always means Lua string `<` comparison. In the tests the `now` values received by one arbiter instance are monotonically non-decreasing, roll ids, item names and player ids are all different from one another, `seed` is only ever an integer, and the `ok` of `mark_delivered` is only ever a boolean.
- The internal layout of the table returned by `save` is free; the tests only hand a deep copy of it to `Arbiter.load`; when `now` is invalid `save` returns the `invalid_time` failure table like the other methods.

**Result table** (returned by `resolve`, `mark_delivered` and `cancel` on success; the elements of the `resolved` array of `tick` are result tables too):

| Field | Content |
| --- | --- |
| `ok` | `true` |
| `roll_id`, `item` | Roll identifier and item |
| `status` | `"awarded"` (a winner has been selected and delivery confirmation is pending), `"delivered"`, `"unclaimed"`, `"canceled"` |
| `winner` | Id of the current winner; `nil` when `status` is `unclaimed`/`canceled` |
| `tier` | Tier of the current winner, `"need"` or `"greed"`; `nil` when there is no winner |
| `rolls` | Array in draw order, each entry `{ tier = , round = , player_id = , roll = }` |
| `demoted` | Ids of the players demoted in this resolution, array in ascending order |
| `failed` | Ids of the players whose delivery failed, array in order of failure |
| `choices` | Array in ascending player id order, each entry `{ player_id = , choice = }`, covering every player of the frozen set; `choice` is the player's **original** final choice (a player who never chose is recorded as `"pass"`, a demoted player still shows `"need"`); for a `canceled` roll this array is empty |

## Core semantics

1. **open**. Check in order: `invalid_time` (`now` or `now + window` is not a finite number); `invalid_roll_id` (`roll_id` is not a non-empty string); `duplicate_roll` (this id has been opened successfully before, whatever state it is in now); `item_not_allowed` (`item` is not a string in `allowed_items`); `invalid_eligible` (`eligible_ids` is not a table, the array `1..#eligible_ids` contains an element that is not a non-empty string, or fewer than 1 player remains after deduplication); `invalid_seed` (`seed` is not an integer-valued finite number satisfying `0 <= seed <= 4294967295`). On success, freeze the deduplicated eligible set (copied; the caller's array is not retained) and return `{ ok = true, roll_id, item, deadline = now + window, total = <size of the set>, eligible = <new array of ids in ascending order> }`; the status is `"open"`. Players who join afterwards cannot take part, and players who leave remain in the set.
2. **choose**. Check in order: `invalid_time`; `unknown_roll`; `roll_closed` (the status is not `"open"`, or `now >= deadline`); `not_eligible` (`player_id` is not in the frozen set); `invalid_choice` (`choice` is not one of `"need"`, `"greed"`, `"pass"`); `invalid_revision` (`revision` is not a non-negative integer-valued finite number; `0` is valid); `stale_revision` (`revision` is not greater than the **last accepted** revision of that player in that roll). Revisions are counted independently "per roll, per player"; a rejected call does not record a revision. On success, the new choice replaces the old choice and the call returns `{ ok = true, roll_id, player_id, revision, chosen = <number of players that have an accepted choice>, total, complete = (chosen == total) }`. The passing of the deadline does not change the status by itself; the status is changed only by `resolve`, `tick`, `cancel` and `mark_delivered`.
3. **resolve**. Check in order: `invalid_time`; `unknown_roll`; if the status is not `"open"`, directly return the **current** result table of that roll (no more values are drawn; idempotent); if some player has still not chosen and `now < deadline`, return `not_ready`; otherwise resolve. At resolution the effective choice of each player is that player's last accepted choice, and a player who never chose counts as pass; first demote according to semantics 6; if the need tier is non-empty the contest takes place within the need tier, otherwise if the greed tier is non-empty the contest takes place within the greed tier, and if both tiers are empty then `status = "unclaimed"` and `rolls` is empty.
4. **Generator and contest**. Every roll owns its own generator: `state0 = seed % 2147483646 + 1`; each draw first sets `state = (state * 48271) % 2147483647` and then takes `roll = state % 100 + 1` (`state0` itself produces no roll value). `state * 48271 < 2^53`, so using `*` and `%` directly is exact both with the doubles of Lua 5.1 and with the integers of Lua 5.4. One contest: in round 1 every player of the tier draws once in ascending id order (a single player also draws once); if several players tie for the highest roll value and the number of rounds already played is `< max_rounds`, then **only the tied leaders** enter the next round in ascending id order, using the continuing generator state; otherwise stop. Ranking within the tier: compare the roll value sequences round by round (lexicographic order, the higher roll value first; a player who did not take part in a round ranks below any roll value), and when the sequences are completely identical the smaller id comes first. The player ranked first is the winner, and `status = "awarded"`. Every draw is appended to `rolls`.
5. **mark_delivered**. Check in order: `invalid_time`; `unknown_roll`; `not_awarded` (the status is not `"awarded"`). `ok == true`: the status becomes the final `"delivered"`, and one win is recorded for `winner` in the fairness ledger, with the `now` of this call as its time. Otherwise (delivery failed): append the current `winner` to `failed`, and the award passes to the next player in the ranking of the current tier (without drawing again); when the ranking of the current tier is exhausted and the current tier is need and the greed tier is non-empty, run one new contest for the greed tier with the **continuing generator state** (its draws are appended to `rolls` with `tier = "greed"` and with `round` counted again from 1) and take its first-ranked player; when no candidate is left, `status = "unclaimed"` and `winner = nil`. Each failure call passes the award on by exactly one player, and the same player never becomes the winner twice. A successful call returns the updated result table.
6. **Fairness ledger**. At resolution take `t = math.min(now, deadline)`; for a player who chose need, count the wins in that player's ledger that satisfy `t - win_time < fairness_window`, and if the count is `>= max_wins_per_window`, that player is treated as greed in this resolution and is recorded in `demoted`. A win exactly `fairness_window` seconds ago no longer counts. Only `mark_delivered(..., true, ...)` produces a ledger record. An implementation may prune expired ledger records, but must not change any observable result (including for rolls whose deadline is earlier than the current `now` and which have not been resolved yet).
7. **cancel / tick / final states**. `cancel` checks in order `invalid_time`, `unknown_roll`, `roll_closed` (the status is not `"open"`); after success the status is the final `"canceled"`, the `winner` and `tier` of the result table are `nil`, and `rolls`, `demoted`, `failed` and `choices` are all empty arrays. `delivered`, `unclaimed` and `canceled` are final states: their roll id can never be opened again, `choose` returns `roll_closed`, `resolve` returns the same result, and `mark_delivered` returns `not_awarded`. `tick(now)` resolves every roll whose status is `"open"` and for which (every player has chosen or `now >= deadline`), and returns `{ ok = true, resolved = <array of result tables in ascending roll id order> }`; when there is no roll to resolve, `resolved` is an empty array.
8. **snapshot / save / load**. `snapshot(now)` returns `{ ok = true, rolls = , wins = }`: `rolls` covers every roll that was ever opened successfully, in ascending roll id order, and each entry contains `roll_id`, `item`, `status`, `deadline`, `remaining` (`math.max(0, deadline - now)` when `"open"`, otherwise `0`), `total`, `chosen`, `winner`, `tier` (the last two are non-`nil` only when `awarded`/`delivered`); an entry whose status is `"open"` must not contain `"need"`, `"greed"`, `"pass"` or any player id in any form (key or value). `wins` is an array of `{ player_id = , count = }` in ascending player id order, where `count` is the number of wins satisfying `now - win_time < fairness_window`, and only players with `count > 0` are listed. `save(now)` returns a new table containing only strings, numbers, booleans and nested tables without metatables (keys are strings or numbers), and records the save time `now`. `Arbiter.load(data, options)` takes its configuration from `options` and restores the entire state: eligible sets, choices, revisions, deadlines, generator states, `rolls`, tier rankings and delivery progress, `failed`, `demoted`, final results and the ledger; when `data` is not a table produced by `save`, the call is equivalent to `Arbiter.new(options)`. If `options.now` is a finite number, then `options.now - <save time>` is added to every stored absolute time (every `deadline`, every ledger time); otherwise the times are kept as they are.

### Recomputation examples

- `seed = 1`: `state0 = 2`, the `state` of the first five draws is `96542`, `365211588`, `435306125`, `1681957627`, `2009854435`, and the roll values are `43`, `89`, `26`, `28`, `36`.
- `seed = 313`, p1, p2 and p3 all choose need, `max_rounds = 3`: round 1 gives p1=95, p2=95, p3=69; p1 and p2 tie and enter round 2, which gives p1=6, p2=34. The ranking is p2, p1, p3 (p1's sequence `95,6` is higher than p3's `69`). `rolls` has 5 entries in total. If `max_rounds = 1`, there are only the 3 entries of round 1, and the ranking is p1, p2, p3.
- `seed = 2147483652` is equivalent to `seed = 6` (`2147483652 % 2147483646 = 6`, `state0 = 7`); the roll value of the first draw is `98` for both.

## DST integration

- In `modmain.lua`, handle the world entity with `AddPrefabPostInit("world", ...)`: first create `inst._lootroll_state = net_string(inst.GUID, "lootrollarbiter.state", "lootrolldirty")`, then return early when not on the master simulation, and finally call `inst:AddComponent("lootrollarbiter")` only on the master simulation.
- The arbiter configuration inside the component is fixed: `window = 30`, `max_wins_per_window = 2`, `fairness_window = 600`, `max_rounds = 3`, and the whitelist is fixed to these 10 prefabs: `goldnugget`, `gears`, `redgem`, `bluegem`, `purplegem`, `deerclops_eyeball`, `bearger_fur`, `dragon_scales`, `goose_feather`, `minotaurhorn`; any other prefab (for example `log`) is rejected with `item_not_allowed`. All time uses `GetTime()`.
- `Open(item_prefab, player_entities, seed)` may only be called by server-side code: it builds the eligible set by taking the `player.userid` of every entity in the `player_entities` array (skipping entries that have no non-empty string `userid`), the component generates the roll id (a non-empty string, unique over the whole lifetime of the save, and not to be reused after `OnLoad` either), and when `seed` is `nil` the server generates one itself. It returns the result table of the arbiter's `open` (on success it contains `ok = true` and `roll_id`, on failure it contains `ok = false` and `code`, for example `item_not_allowed` or `invalid_eligible`). A rejected `Open` must not spawn any item.
- The identity in `Choose(player, roll_id, choice, revision)` comes only from `player.userid` (when there is none, return `{ ok = false, code = "not_eligible" }`); it returns the result table of the arbiter's `choose`. When the returned `complete == true`, the component must resolve and deliver **immediately**, without waiting for the deadline.
- `Resolve(roll_id)` resolves the roll and completes the delivery, and returns the final result table (`status` is `"delivered"` or `"unclaimed"`); when the roll cannot be resolved yet it returns `{ ok = false, code = "not_ready" }`; calling it again for a roll that has already been resolved returns the same result and must not spawn the item again.
- Delivery: find the player entity by `userid` - prefer the entity that was passed to `Open` and cached at that time (it must still be `IsValid()`), otherwise iterate over the global `AllPlayers` to find an entity with the same `userid`. If no entity is found, or the entity has no `inventory` component, the delivery counts as failed and **no item is spawned**. Otherwise call `inventory:GiveItem(item)` after `SpawnPrefab(item_prefab)`; the delivery counts as successful only when a truthy value is returned and, in addition, the item has been merged into a stack the player already had (`not item:IsValid()`) or `item.components.inventoryitem:GetGrandOwner() == player`. In every other case (for example when no slot is available, `GiveItem` returns `false` and drops the item on the ground) you must `item:Remove()` and treat the delivery as failed. Call `mark_delivered` after every attempt; on failure continue with the new winner, until `delivered` or `unclaimed`. One award leaves at most one item, and failed attempts must not leave items behind in the world.
- Every `"open"` roll keeps **exactly one** `inst:DoTaskInTime(deadline - GetTime(), ...)` deadline task on the world entity, which resolves the roll when it fires; you must `Cancel` it when the roll is resolved (including the immediate resolution triggered by the last player's choice, and any cancel entry point the implementation provides on its own) and in `OnRemoveFromEntity`. Apart from these deadline tasks, the component must not keep any other unfinished `DoTaskInTime`/`DoPeriodicTask` task on the world entity: the dedicated server tests count the world entity's `inst.pendingtasks` (the table in which the engine records unfinished tasks) and require that it grows by exactly 1 after a successful `Open`, returns to its original value after the roll is resolved, still has exactly 1 task per open roll after `OnLoad`, and is 0 after the component is removed.
- Listen for `ms_playerleft` on `inst` itself, the entity the component lives on (`inst:ListenForEvent("ms_playerleft", fn)`; for a world component `inst` is the world; do not hard-code `TheWorld`): only discard the entity cache of that player, and you **must not** shrink any frozen set - a player who has left is still counted as a member of the set afterwards, but the reward can only be delivered to that player after the entity has been found again through `AllPlayers`; in `OnRemoveFromEntity` call `RemoveEventCallback` with the same callback.
- The component must not assume that `inst` is always `TheWorld`: the dedicated server tests also `CreateEntity()` a standalone entity and `AddComponent("lootrollarbiter")`, push `ms_playerleft` on it, open rolls, then `RemoveComponent("lootrollarbiter")`, and check that both that entity's `pendingtasks` and its number of `ms_playerleft` listeners drop to zero. When `inst._lootroll_state` does not exist, skip the network publication; the rest of the behavior is unchanged.
- After a resolution or a cancellation, announce the result with `TheNet:Announce` (the text is free, but it must not contain the choices of any unresolved roll). After every state change, encode **all `"open"` rolls** in ascending roll id order as `roll_id|item|chosen|total` (`chosen` and `total` are decimal integers), join them with `;` and write the result to `inst._lootroll_state` (an empty string when there is no open roll). The network state must not contain any choice or player id, and resolved rolls must disappear from it.
- `OnSave()` returns a plain table that the game can serialize (containing the result of the arbiter's `save` and the roll id counter); `OnLoad(data)` first cancels the old tasks, calls `Arbiter.load` with `options.now = GetTime()`, reschedules the deadline task of every roll that is still open and republishes the network state. Loading itself must not spawn items.

## Base-game API contract

```lua
AddPrefabPostInit("world", function(inst)
    inst._lootroll_state = net_string(inst.GUID, "lootrollarbiter.state", "lootrolldirty")   -- written as GLOBAL.net_string in modmain
    if not inst.ismastersim then   -- or TheWorld.ismastersim
        return inst
    end
    inst:AddComponent("lootrollarbiter")
end)

AddModRPCHandler("rhenium_lootroll", "choose", function(player, roll_id, choice, revision)
    local userid = player ~= nil and player.userid or nil
    -- validate the argument types, then forward to TheWorld.components.lootrollarbiter:Choose(player, roll_id, choice, revision)
end)

local task = inst:DoTaskInTime(delay, function() component:Resolve(roll_id) end)
if task ~= nil then task:Cancel() end

inst:ListenForEvent("ms_playerleft", on_player_left)      -- callback arguments (world, player)
inst:RemoveEventCallback("ms_playerleft", on_player_left)

local item = SpawnPrefab("goldnugget")
local accepted = player.components.inventory:GiveItem(item)   -- returns the slot or true on success; returns false/nil on failure, and the item may already have been dropped
local owner = item.components.inventoryitem:GetGrandOwner()
local has, count = player.components.inventory:Has("goldnugget", 1)

TheNet:Announce(message)
inst._lootroll_state:set(encoded)      -- the client reads :value() in the "lootrolldirty" event
```

The RPC handler receives only the roll id, the choice and the revision, and its return value is ignored; it must not call `Open`, and it must not accept an item, a seed, a player id or a deadline. Once `AddModRPCHandler` has registered it, the server can obtain the handler through `MOD_RPC_HANDLERS["rhenium_lootroll"][MOD_RPC["rhenium_lootroll"]["choose"].id]`, and the dedicated server tests call it directly in the form `handler(player, roll_id, choice, revision)`.

The world component must expose `Open(item_prefab, player_entities, seed)`, `Choose(player, roll_id, choice, revision)`, `Resolve(roll_id)`, `OnSave()`, `OnLoad(data)` and `OnRemoveFromEntity()`.

## Acceptance

- With the same seed and the same choices, the roll values, the winner, the ranking and the `rolls` record agree bit for bit with the published generator.
- Old revisions, late choices, players outside the eligible set, reused roll ids and repeated resolution all have no side effect.
- Fairness demotion and the deadline boundary strictly follow the published formulas; after save and load all state and all time relations remain unchanged.
- Delivery failures pass the award on by exactly one player each time, ending in `unclaimed` when no candidate is left; the item is never duplicated or left behind.
- The headless dedicated server tests open `goldnugget` rolls with entities that have a real `inventory` component and different `userid` values, and verify that the predicted winner has exactly one more item in the real inventory, that nobody else has one, that a repeated `Resolve` does not duplicate the item, that on a delivery failure (no `inventory` component, or `inventory.maxslots = 0` causing the item to be dropped) the item passes to the next player and nothing is left behind in the world; they also verify the RPC identity entry point, the network state and `OnSave/OnLoad`.

Use only base-game APIs and assets; copying individual choices to clients is forbidden.
