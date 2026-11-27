# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Server-authoritative status effect stack manager

## Background and goal

Timed status effects (buffs/debuffs) such as slow, poison, frenzy and regeneration must be adjudicated in one place by the server: a retry of the same request must not stack two layers; different effects have different stacking and refresh policies; the expiry boundary must be exact; damage over time must not deduct more or less because the tick frequency differs; dispelling must follow a deterministic priority; after the target dies or is removed no modifier may be left behind, and a late request must not "revive" an effect; after a save and reload the remaining time, the stack counts and the unsettled damage must all be preserved.

Implement a DST-independent pure Lua status effect manager, and a world component that runs only on the master simulation and writes the aggregated result into the base-game `locomotor`, `combat` and `health` components.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/statuseffects/stack.lua
scripts/components/statuseffects.lua
```

The pure module `scripts/statuseffects/stack.lua` returns a table and exports:

```lua
Stack.new(options)
Stack.load(data, options, now)

stack:add_target(target_id, now)
stack:remove_target(target_id, now)
stack:apply(request_id, target_id, effect_id, source_id, now)
stack:dispel(target_id, tag, max_count, now)
stack:tick(now)
stack:modifiers(target_id, now)
stack:snapshot(now)
stack:save(now)
```

The pure module must not use any DST global object, `require`, `os` or `io`; all time may come only from the `now` argument. The code must be valid Lua 5.1 and valid Lua 5.4 at the same time.

`options` is supplied by the server and may be assumed valid; `Stack.new` does not need to validate it:

```lua
options = {
    extend_cap = 3,            -- optional, a finite number >= 1, defaults to 3
    effects = {
        [effect_id] = {
            duration = 8,          -- positive finite number of seconds
            max_stacks = 3,        -- positive integer
            policy = "refresh",    -- "refresh" | "extend" | "independent"
            tags = { "debuff" },   -- list of non-empty strings
            priority = 2,          -- integer; larger values are dispelled first
            speed_mult = 0.5,      -- positive number or nil
            damage_mult = nil,     -- positive number or nil
            tick_health = nil,     -- health change per second (may be negative) or nil
        },
    },
}
```

## Core semantics

Below, an "identifier" means a non-empty string. An "instance" means one copy of an effect on a target, with the fields `effect_id`, `seq`, `stacks`, `applied_at`, `expires_at`, `source_id`.

1. **Time and clock.** The manager holds a clock, which is `0` after `Stack.new`. Every method that takes `now` validates the time first: when `now` is not a number, is NaN, is negative or is infinite, the call is rejected with code `invalid_time`; when `now` is less than the clock, the call is rejected with code `stale_time` (`now` equal to the clock is valid). A call rejected because of its time has no side effect at all and is not written into the request history. A call that passes the time validation sets the clock to `now`, even if it is subsequently rejected for another reason; apart from the clock (and the request history as described in item 4), a rejected call must not change any instance, target or sequence number.
2. **Return convention.** `add_target`, `remove_target`, `apply`, `dispel` and `modifiers` always return a new table: `ok == true` on success, and `{ ok = false, code = <code> }` on failure. `tick`, `snapshot` and `save` return the new table specified below on success, and return the two values `nil, code` when the time is rejected. A wrong argument shape (an argument that should be an identifier is not a non-empty string; `source_id` is neither nil nor an identifier; `max_count` is neither nil nor an integer `>= 1`) has code `invalid_argument`. The validation order of all methods is always: time -> argument shape -> (`apply` only: request history) -> `unknown_effect` -> `unknown_target`, and the code of the first check that is not satisfied is returned. A caller modifying any returned table must not affect the internal state of the manager or any later return value.
3. **Targets.** Only a registered target can have effects. `add_target` returns `{ ok = true, code = "tracked", target_id = ... }` on success; when the target is already registered it likewise returns success and does not change the effects the target already has. `remove_target` returns code `unknown_target` for an unregistered target; otherwise it clears all instances of that target and all health changes of that target that have not yet been collected by `tick`, turns the target back into an unregistered one, and returns `{ ok = true, code = "removed", target_id = ..., count = <number of live instances cleared> }`. The request history is not deleted because of `remove_target`.
4. **Validation order and idempotency of apply.** In order: time validation; if `request_id` is not an identifier then `invalid_argument` (not written into the history); if `request_id` is already in the history, return a field-by-field copy of the first result (a new table), produce no other side effect, and ignore the remaining arguments of this call; otherwise the result of this call, whether success or failure, is written into the history under that `request_id`, and the following are validated in order: a wrong shape of `target_id`, `effect_id` or `source_id` is `invalid_argument`; `effect_id` not being in `options.effects` is `unknown_effect`; the target not being registered is `unknown_target`; then the call takes effect according to item 5. The fields of a successful result are `ok = true`, `code`, `target_id`, `effect_id`, `seq`, `stacks`, `expires_at`.
5. **Stacking policies.** Let `D = duration` and `M = max_stacks`; a "live instance" means an instance of that effect on that target that is live according to item 6. A newly created instance has `stacks = 1`, `applied_at = now`, `expires_at = now + D`, and its `seq` is taken from a manager-wide integer sequence that starts at `1` and increases by one for every newly created instance.
   - `refresh`: if there is no live instance, create one, with code `applied`; otherwise that single instance gets `stacks = min(stacks + 1, M)` and `expires_at = now + D`, with code `refreshed`.
   - `extend`: if there is no live instance, create one, with code `applied`; otherwise `stacks = min(stacks + 1, M)` and `expires_at = now + min((expires_at - now) + D, extend_cap * D)`, with code `extended`.
   - `independent`: every call creates a new independent instance with `stacks = 1`. When the number of live instances is 0 the code is `applied`; when it is greater than 0 and less than `M` the code is `stacked`; when it has already reached `M`, the live instance with the smallest `seq` is removed first, and the code is `replaced`.
   - When `refresh`/`extend` acts on an existing instance, it does not change that instance's `seq` or `applied_at`, and it updates the instance's `source_id` to the `source_id` of this call (which may be nil). The `seq` and `expires_at` in the result belong to the instance that this call created or acted on; `stacks` is, for `refresh`/`extend`, the stack count of that instance, and for `independent`, the number of live instances of that effect on that target after the call completes.
6. **Exact expiry.** An instance is expired if and only if `now >= expires_at`. An expired instance is treated as non-existent by `apply`, `dispel`, `modifiers`, `snapshot` and the `count` of `remove_target`, regardless of whether `tick` was called beforehand; it remains effective only in the settlement of item 8.
7. **Aggregation.** `modifiers(target_id, now)` returns `unknown_target` for an unregistered target, and otherwise returns `{ ok = true, code = "ok", target_id, speed_mult, damage_mult, tick_health, count }`: `count` is the number of live instances; `speed_mult` is the product of `speed_mult ^ stacks` over all live instances whose effect defines `speed_mult` (each stack multiplies once), or `1` if there are none; `damage_mult` is computed in the same way; `tick_health` is the sum of `tick_health * stacks` over all live instances whose effect defines `tick_health`, or `0` if there are none. The result depends only on `now`; no prior call to `tick` is needed.
8. **Health change settlement.** An instance is alive from `applied_at` until the moment `end` at which it expires, is removed by `dispel`, or is `replaced`; at any moment its rate is `tick_health * the stacks at that moment` (after `refresh`/`extend` adds a stack at moment `u`, the old stack count applies before `u` and the new stack count applies after `u`). `tick(now)` returns the health changes newly added since the previous successful `tick` (treated as moment `0` if `tick` was never called; after a reload see item 11): for each (target, effect), `amount` equals the sum, over all of its instances, of the integral of the rate over "the intersection of (the moment of the previous tick, now] and [applied_at, end)". The total therefore does not depend on how often `tick` or any other method is called, and the changes produced before `end` by an instance that was dispelled, replaced or has expired are still returned by a later `tick`; only `remove_target` discards the changes of that target that have not yet been collected. The return value is a new list whose elements are `{ target_id, effect_id, amount }`, in ascending `target_id` order and then ascending `effect_id` order (both by string `<` comparison); entries with `amount == 0` and effects without `tick_health` do not appear; when there is no change an empty table is returned. Example: an effect with `tick_health = -2` and `duration = 6` is applied at `now = 1`; `tick(3)` returns `-4`, and a following `tick(10)` returns `-8`; if only a single `tick(10)` is called it returns `-12`. The hidden tests use only times and values that are exactly representable in binary floating point, and compare the results for exact equality; integrating the piecewise-constant rate directly by the formula above (instead of simulating with a fixed step) yields the exact result.
9. **Dispel.** `dispel(target_id, tag, max_count, now)` returns `unknown_target` for an unregistered target. Among the live instances of that target it selects the instances whose effect definition's `tags` contain `tag`, sorted by: `priority` descending, `applied_at` ascending, `effect_id` ascending, `seq` ascending; it removes the first `max_count` of them (all of them when `max_count` is nil). An instance with multiple stacks counts as one as a whole. It returns `{ ok = true, code = "dispelled", target_id, count, removed }`, where `removed` is a list of `{ effect_id, seq, stacks }` in removal order and `count == #removed`; when nothing matches it likewise succeeds, with `count == 0`.
10. **Snapshot.** `snapshot(now)` returns a new list with one row per live instance: `{ target_id, effect_id, seq, stacks, applied_at, expires_at, remaining, source_id }`, where `remaining = expires_at - now`; the rows are ordered by ascending `target_id`, then ascending `effect_id`, then ascending `seq`.
11. **Saving.** `save(now)` returns a new table that contains only strings, numbers, booleans and nested tables (with string or number keys), and no functions, userdata, metatables or circular references; later modifications of the manager must not affect a save that has already been returned. `Stack.load(data, options, now)` returns a manager whose clock is `now`, and shifts all saved timestamps by `now - the now at save time`: the remaining time of every instance, the relative order of `applied_at` (which may be negative after the shift), `seq`, `stacks`, `source_id`, the registered targets, the `seq` counter (after a reload the `seq` of a new instance is greater than any `seq` allocated before the save) and the request history all remain unchanged; the health changes that had not yet been collected by `tick` at save time are returned in the first `tick` after the reload together with the newly added amount. The results in the request history are kept as they are, and the `expires_at` inside them is not shifted. For an effect that no longer exists in `options.effects`, its instances and its uncollected changes are discarded at reload. When `data` is not a table produced by `save` (for example nil), a manager equivalent to `Stack.new(options)` but with its clock at `now` is returned.

## DST integration

- In `modmain.lua`, use `AddPrefabPostInit("world", ...)` to attach the world component `statuseffects` (`scripts/components/statuseffects.lua`) only on the master simulation (`inst.ismastersim`).
- The component must use the effect table below, and must create the manager with `extend_cap = 3`:

```lua
local EFFECTS = {
    chill  = { duration = 8,  max_stacks = 3, policy = "refresh",     tags = { "debuff", "cold" },   priority = 2, speed_mult = 0.5 },
    venom  = { duration = 6,  max_stacks = 2, policy = "independent", tags = { "debuff", "poison" }, priority = 3, tick_health = -2 },
    frenzy = { duration = 10, max_stacks = 2, policy = "extend",      tags = { "buff" },             priority = 1, speed_mult = 1.25, damage_mult = 1.5 },
    regen  = { duration = 4,  max_stacks = 1, policy = "refresh",     tags = { "buff", "heal" },     priority = 1, tick_health = 1 },
}
```

- The component exposes the following methods (all called as `component:Method(...)`):

```lua
Track(entity, stable_id)
Apply(request_id, entity, effect_id, source_entity, now)
Dispel(entity, tag, max_count, now)
Cleanse(player, tag, now)
Reconcile(entity, now)
Tick(now)
OnSave()
OnLoad(data)
OnRemoveFromEntity()
```

- **Component time.** `now` is an optional argument: when it is passed, it is handed to the manager as is; when it is nil, `math.max(GetTime(), the largest time the component has previously handed to the manager successfully)` is used. `Track`, `OnSave` and the `death`/`onremove` callbacks also use this default time. `OnLoad` is the exception: it uses `GetTime()` as the `now` of `Stack.load`, and from then on the component's time base returns to `GetTime()`. A periodic call whose time is rejected by the manager must fail quietly and must not raise an error.
- `Track(entity, stable_id)`: the entity must be valid, have a `health` component and not be dead, and `stable_id` must be a non-empty string; otherwise return `false`. On success, register the target in the manager and return `true`; calling `Track` again for the same entity with the same id returns `true` and must not register the listeners a second time; when the id is already bound to another entity, or the entity is already bound to another id, return `false`. If effects for that id already exist in the manager (for example after a reload), they are kept and are applied to the entity immediately.
- `Apply`: when `entity` is not tracked, return `{ ok = false, code = "unknown_target" }`; when `source_entity` is non-nil and not tracked, return `{ ok = false, code = "unknown_source" }`; otherwise call `apply` with the stable ids of the two entities and return its result. `Dispel` likewise returns the result of `dispel`, and `unknown_target` when the entity is not tracked. After the manager has accepted the time, both must immediately run `Reconcile` on that entity.
- `Cleanse(player, tag, now)` is the only player-facing entry point: when `tag` is not in the whitelist `{ cold = true, poison = true }`, return `{ ok = false, code = "forbidden_tag" }` (before any other check); the target can only be the entity that is tracked with `player.userid` as its stable id and that is exactly `player` itself, otherwise return `{ ok = false, code = "unknown_target" }`; once these checks pass, the call is equivalent to `Dispel(player, tag, 1, now)`.
- `Reconcile(entity, now)`: when the entity is not tracked or the time is rejected, return nil and do nothing; otherwise obtain the `modifiers` aggregate, write it into the base-game components, and then return that aggregate table. When `speed_mult ~= 1`, call `locomotor:SetExternalSpeedMultiplier(source, key, speed_mult)`, and when it equals `1`, call `locomotor:RemoveExternalSpeedMultiplier(source, key)`; when `damage_mult ~= 1`, call `combat.externaldamagemultipliers:SetModifier(source, damage_mult, key)`, and when it equals `1`, call `combat.externaldamagemultipliers:RemoveModifier(source, key)`. When the entity lacks `locomotor` or `combat`, skip the corresponding part. Modifiers set by other sources must not be touched.
- `Tick(now)`: when the time is rejected, return `false` and do not change any health value; otherwise, in the order returned by `tick`, for each change, call `health:DoDelta(amount, true, effect_id)` only if the corresponding entity is still tracked, is valid and `health:IsDead()` is false, then run `Reconcile` on all tracked entities, and return `true`. A dead or removed entity must never be healed, damaged or revived.
- Listen for `death` and `onremove` on every tracked entity. When either event occurs: call `remove_target` for that id, remove the speed and damage modifiers set by this component, unregister both listeners using the same callback that was used at registration, and forget the binding between the entity and the id (afterwards the id can be passed to `Track` again, and `Apply` on that entity returns `unknown_target`).
- On the world entity that owns the component, use `self.inst:DoPeriodicTask(period, fn)` to call `Tick()` periodically; `OnRemoveFromEntity` must cancel that task with `task:Cancel()`, and must perform the same cleanup as in the previous item for all tracked entities (remove the modifiers, unregister the listeners, clear the targets). After the component has been removed with `TheWorld:RemoveComponent("statuseffects")`, it must be possible to attach it again with `TheWorld:AddComponent("statuseffects")`.
- `OnSave()` returns a table that contains the `save` result (likewise containing only serializable plain data); `OnLoad(data)` rebuilds the manager with `Stack.load` (an empty manager results when `data` is nil or malformed), keeps the entities already tracked in this process and their listeners, registers their ids again, and immediately runs `Reconcile` on them.
- Players are tracked by `player.userid` through `ms_playerjoined`. The RPC exposes only self-cleansing: `AddModRPCHandler("rhenium_statuseffects", "cleanse", function(player, tag) ... end)`; the handler passes only the real `player` supplied by the framework and `tag` to `Cleanse`; the client cannot specify the target, the count, the effect or the time.

## Base-game API contract

The shapes of the base-game interfaces in this build are as follows (`source` must be an entity, and the base game listens for `onremove` on it; `key` is a fixed string of your choice):

```lua
-- components/locomotor.lua
locomotor:SetExternalSpeedMultiplier(source, key, mult)   -- a mult of nil or 1 is equivalent to removal
locomotor:RemoveExternalSpeedMultiplier(source, key)
locomotor:GetSpeedMultiplier()                             -- total multiplier including the external multipliers

-- components/combat.lua: self.externaldamagemultipliers = SourceModifierList(self.inst)
combat.externaldamagemultipliers:SetModifier(source, mult, key)
combat.externaldamagemultipliers:RemoveModifier(source, key)
combat.externaldamagemultipliers:Get()
combat:CalcDamage(target)                                  -- defaultdamage * multiplier

-- components/health.lua
health:DoDelta(amount, overtime, cause, ignore_invincible, afflicter, ignore_absorb)
health:IsDead()                                            -- currenthealth <= 0

entity:ListenForEvent("death", on_death)
entity:ListenForEvent("onremove", on_remove)
entity:RemoveEventCallback("death", on_death)              -- must be the same function object that was registered
local task = inst:DoPeriodicTask(period, fn, initialdelay)
task:Cancel()
```

When `health:DoDelta` brings the health down to 0, the base game pushes `death` synchronously, so your death callback may be re-entered from inside `Tick`. The first argument of the RPC handler is the real `player` passed in by the base-game framework, and the identity may be read only from `player.userid`.

## Acceptance

- Retries, malformed arguments and stale times produce no side effects; the three stacking policies and the `now >= expires_at` expiry boundary hold exactly.
- Aggregation and settlement do not depend on the `tick` frequency or on table traversal order; the dispel order and the snapshot order are deterministic.
- After a save and reload the remaining time, stack counts, instance order, request history, sequence numbers and unsettled changes are all preserved.
- The headless dedicated server test uses `CreateEntity()` to create entities with the base-game `health`, `combat` and `locomotor`, drives the component through a controllable `now`, and asserts the changes of the real `locomotor:GetSpeedMultiplier()`, `combat.externaldamagemultipliers:Get()`, `combat:CalcDamage` and `health.currenthealth`, the cleanup after a real death and after removal (including the number of `death`/`onremove` listeners on the entity returning to what it was before `Track`), the preservation of remaining time after `OnSave`/`OnLoad`, and that after `TheWorld:RemoveComponent("statuseffects")` the modifiers and listeners are cleaned up and the number of pending tasks on the world entity decreases, followed by a fresh `AddComponent`.

Only base-game APIs, components, prefabs and assets may be used; placeholder implementations and client-authoritative implementations are forbidden.
