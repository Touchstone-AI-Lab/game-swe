# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Deterministic combat target arbiter

## Background and goal

A server-side creature receives damage and taunt events from multiple targets. Duplicate or out-of-order events must not add threat again; threat decays over time; a temporary taunt overrides the normal ranking until an exact boundary; a target that has died or been removed must not be resurrected by late messages.

Implement a DST-independent threat arbiter and a master simulation component.

## Required deliverables

```text
modinfo.lua
modmain.lua
scripts/combatarbiter/arbiter.lua
scripts/components/combattargetarbiter.lua
```

The pure module exports:

```lua
Arbiter.new(options)
Arbiter.load(data, options, now)

arbiter:observe(entity, now)
arbiter:add_threat(source_id, target_id, amount, seq, now)
arbiter:taunt(request_id, source_id, target_id, duration, now)
arbiter:remove(target_id, now)
arbiter:choose(source_id, now)
arbiter:tick(now)
arbiter:snapshot(now)
arbiter:save(now)
```

## Core semantics

1. Validate all identifiers, finite non-negative times, positive and finite threat amounts, positive duration, and a strictly increasing integer seq for each source/target stream.
2. `observe` records the entity's `id`, `alive` and monotonic `revision`. An old revision must not change the life state.
3. Each source->target threat entry decays independently: the entry's threat at `now` is `max(0, value - options.decay_per_second * (now - updated_at))`, where `updated_at` is the time of the most recently accepted threat event of that entry. A new threat event first decays that entry to the event time, then adds `amount`, and does not affect other entries; an entry whose threat drops to zero is removed. The result must not depend on how often `tick` is called.
4. Normal selection orders by current threat descending, then first-seen time ascending, then target ID in lexical order.
5. A valid taunt overrides normal selection while `now < expires_at`; it lapses as soon as the boundary is reached. A retry with the same `request_id` must return the original result.
6. Death or `remove` immediately clears the threat and taunts that the target takes part in, but keeps the seq anti-replay state; delayed old events must not resurrect the target.
7. `choose` and `snapshot` return new tables with a stable ordering. `save/load` preserve, as of the given now, the effective threat, the first-seen order, leases, request history and anti-replay state.

## Return values and data shapes

The hidden tests rely only on the following public shapes:

- `observe` and `add_threat` return `false` when rejected, and any non-`false` value on success.
- `choose` returns `nil` when there is no selectable target; otherwise it returns a new table containing `target_id` and `threat`, the current threat of that target at `now`.
- `taunt` returns a new table containing a boolean `ok` and `expires_at = now + duration`; a retry with the same `request_id` returns the first result and does not change the lease.
- `snapshot(now)` returns an array in which every row contains at least `threat`.

## DST integration

- Attach `combattargetarbiter` only on the master simulation.
- Derive the attacker, the target and the damage from the real `attacked` event; damage, entities or seq submitted by a client must not be trusted.
- Track the entity's `health` and `combat` components, listen for `attacked`, `death` and `onremove`, and unregister them in matching pairs. As soon as a `death` event is received the entity is treated as dead; the clearing must not wait until `health:IsDead()` changes.
- Use `DoPeriodicTask` to reconcile targets; call `components.combat:SetTarget` only when the target is alive and can be attacked.
- The component saves its state through `OnSave/OnLoad`; on removal it cancels the periodic task and all callbacks.
- If the taunt entry point is exposed through an RPC, only the server may construct the request, from the real player and the distance.

## Base-game API contract

The base-game combat events and component calls are as follows:

```lua
entity:ListenForEvent("attacked", function(inst, data)
    local attacker = data ~= nil and data.attacker or nil
    local damage = data ~= nil and data.damage or nil
end)
entity:ListenForEvent("death", on_death)
entity:ListenForEvent("onremove", on_remove)

local alive = target.components.health ~= nil
    and not target.components.health:IsDead()
if alive and source.components.combat ~= nil then
    source.components.combat:SetTarget(target)
end
```

The base-game `attacked` payload contains fields such as `attacker`, `damage`, `weapon` and `stimuli`; you must not assume that an attacker is always present. `Combat:SetTarget` still runs the base-game `IsValidTarget/ShouldAggro` validation, so you should check `combat.target` after the call and must not treat a single call as success in itself.

Periodic reconciliation uses `inst:DoPeriodicTask(period, fn, initialdelay)`, with `task:Cancel()` on removal. The server-side component must expose `Track(entity, stable_id)`, `ObserveDamage(source, target, amount, seq)`, `Taunt(...)` and `Reconcile(source)`, and must store the corresponding callback for every tracked entity so that it can unregister with the same function object.

## Acceptance

- Duplicate and out-of-order damage does not change threat.
- Decay, ties and first-seen order do not depend on table traversal or on tick frequency.
- A taunt lapses at the exact boundary.
- A dead or removed target is not resurrected by old events.
- The headless dedicated server tests create entities with the base-game health/combat components and assert that `combat:SetTarget` is really applied, that the target is no longer selected after a `death` event, and the `OnSave/OnLoad` round trip; lease expiry is covered by the pure-module tests, and listener cleanup is covered by the static integration checks.
- The static checks require that every submitted Lua file is non-empty, that the non-comment code totals at least 240 lines, and that the base-game API wiring listed in this document is satisfied.

Only base-game APIs, components, prefabs and assets may be used; placeholders and client-authoritative implementations are forbidden.
