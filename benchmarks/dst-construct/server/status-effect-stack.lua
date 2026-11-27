-- Headless dedicated-server assertions. Every case is synchronous and drives
-- the component with explicit integer-based `now` values far ahead of GetTime().

local function creature(max_health, health_only)
    local entity = CreateEntity()
    entity.entity:AddTransform()
    entity:AddComponent("health")
    entity.components.health:SetMaxHealth(max_health or 100)
    entity.components.health.nofadeout = true
    if not health_only then
        entity:AddComponent("combat")
        entity.components.combat:SetDefaultDamage(10)
        entity:AddComponent("locomotor")
    end
    return entity
end

local function base_time(offset)
    return math.floor(GetTime()) + offset
end

local function near(actual, wanted)
    return type(actual) == "number" and math.abs(actual - wanted) < 0.001
end

local function speed_of(entity)
    return entity.components.locomotor:GetSpeedMultiplier()
end

local function damage_mult_of(entity)
    return entity.components.combat.externaldamagemultipliers:Get()
end

local function listener_count(entity, event)
    local total = 0
    local by_listener = entity.event_listeners ~= nil and entity.event_listeners[event] or nil
    if by_listener ~= nil then
        for _, callbacks in pairs(by_listener) do
            total = total + #callbacks
        end
    end
    return total
end

local function pending_task_count(entity)
    local total = 0
    for _ in pairs(entity.pendingtasks or {}) do
        total = total + 1
    end
    return total
end

local function plain_copy(value, depth)
    depth = depth or 0
    assert(depth < 32, "OnSave data is too deep or cyclic")
    local kind = type(value)
    if kind == "string" or kind == "number" or kind == "boolean" then
        return value
    end
    assert(kind == "table", "OnSave data contains a " .. kind)
    local copy = {}
    for key, item in pairs(value) do
        assert(type(key) == "string" or type(key) == "number", "OnSave data has a non-plain key")
        copy[key] = plain_copy(item, depth + 1)
    end
    return copy
end

local function with_entities(body)
    local created = {}
    local function make(max_health, health_only)
        local entity = creature(max_health, health_only)
        created[#created + 1] = entity
        return entity
    end
    local ok, message = pcall(body, make)
    for _, entity in ipairs(created) do
        if entity:IsValid() then
            entity:Remove()
        end
    end
    if not ok then
        error(message, 0)
    end
end

return function(ctx)
    ctx:case("status effect component is attached and authoritative", function()
        assert(TheWorld.ismastersim, "suite must run on the master simulation")
        local service = TheWorld.components.statuseffects
        assert(service ~= nil, "world is missing the statuseffects component")
        for _, method in ipairs({ "Track", "Apply", "Dispel", "Cleanse", "Reconcile", "Tick", "OnSave", "OnLoad", "OnRemoveFromEntity" }) do
            assert(type(service[method]) == "function", "statuseffects is missing " .. method)
        end
        with_entities(function(make)
            local now = base_time(1000)
            local bare = CreateEntity()
            local tracked_bare = service:Track(bare, "sfx-bare")
            bare:Remove()
            assert(tracked_bare == false, "an entity without health must not be tracked")
            local corpse = make(50)
            corpse.components.health:DoDelta(-50)
            assert(corpse.components.health:IsDead() and service:Track(corpse, "sfx-corpse") == false, "a dead entity must not be tracked")

            local player, other, stranger = make(), make(), make()
            player.userid = "KU_sfxsuite"
            other.userid = "KU_sfxsuite"
            assert(service:Track(player, "") == false, "an empty stable id must be rejected")
            assert(service:Track(player, "KU_sfxsuite") == true)
            assert(service:Track(player, "KU_sfxsuite") == true, "tracking the same pair again must succeed")
            assert(service:Track(other, "KU_sfxsuite") == false, "a bound id must not move to another entity")
            assert(service:Track(player, "sfx-second-id") == false, "a bound entity must not take a second id")

            local result = service:Apply("sfx-auth-1", stranger, "chill", nil, now)
            assert(type(result) == "table" and result.ok == false and result.code == "unknown_target")
            result = service:Apply("sfx-auth-2", player, "chill", stranger, now)
            assert(result.ok == false and result.code == "unknown_source", "an untracked source must be rejected")
            assert(service:Reconcile(stranger, now) == nil, "Reconcile of an untracked entity must return nil")

            local plain = make(100, true)
            assert(service:Track(plain, "sfx-plain") == true, "health alone is enough to be tracked")
            result = service:Apply("sfx-auth-plain", plain, "frenzy", nil, now)
            assert(result.ok == true and result.code == "applied" and result.expires_at == now + 10, "missing locomotor and combat must be skipped")
            assert(type(service:Reconcile(plain, now)) == "table")
            result = service:Apply("sfx-auth-plain-2", plain, "frenzy", nil, now)
            assert(result.code == "extended" and result.stacks == 2 and result.expires_at == now + 20)
            result = service:Apply("sfx-auth-plain-3", plain, "frenzy", nil, now)
            assert(result.stacks == 2 and result.expires_at == now + 30, "frenzy has max_stacks = 2")
            result = service:Apply("sfx-auth-plain-4", plain, "frenzy", nil, now)
            assert(result.expires_at == now + 30, "the component must use extend_cap = 3")

            local baseline = speed_of(player)
            result = service:Apply("sfx-auth-3", player, "chill", nil, now)
            assert(result.ok == true and result.code == "applied")
            service:Reconcile(player, now)
            assert(near(speed_of(player), baseline * 0.5), "chill must halve the real speed multiplier")
            result = service:Cleanse(player, "buff", now)
            assert(result.ok == false and result.code == "forbidden_tag", "only whitelisted tags may be cleansed")
            result = service:Cleanse(other, "cold", now)
            assert(result.ok == false and result.code == "unknown_target", "identity must come from the tracked player entity")
            assert(near(speed_of(player), baseline * 0.5), "a rejected cleanse changed the player")
            result = service:Cleanse(player, "cold", now)
            assert(result.ok == true and result.code == "dispelled" and result.count == 1)
            assert(near(speed_of(player), baseline), "a successful cleanse must reconcile the real speed multiplier at once")

            assert(service:Apply("sfx-auth-4", player, "chill", nil, now).ok == true)
            assert(service:Apply("sfx-auth-5", player, "venom", nil, now + 1).ok == true)
            assert(service:Apply("sfx-auth-6", player, "venom", nil, now + 1).ok == true)
            result = service:Cleanse(player, "poison", now + 1)
            assert(result.ok == true and result.count == 1, "a cleanse removes exactly one instance")
            result = service:Dispel(player, "debuff", 1, now + 1)
            assert(result.count == 1 and result.removed[1].effect_id == "venom", "venom has the higher dispel priority")
            result = service:Dispel(player, "debuff", nil, now + 1)
            assert(result.count == 1 and result.removed[1].effect_id == "chill")
        end)
    end)

    ctx:case("real locomotor and combat modifiers follow stacks dispel and expiry", function()
        local service = assert(TheWorld.components.statuseffects)
        with_entities(function(make)
            local now = base_time(2000)
            local entity, source, dummy = make(), make(), make()
            assert(service:Track(entity, "sfx-mods") == true and service:Track(source, "sfx-mods-source") == true)
            local baseline = speed_of(entity)
            assert(near(damage_mult_of(entity), 1) and near(entity.components.combat:CalcDamage(dummy), 10))

            local result = service:Apply("sfx-mods-1", entity, "chill", source, now)
            assert(result.ok == true and result.code == "applied" and result.stacks == 1)
            local aggregate = service:Reconcile(entity, now)
            assert(type(aggregate) == "table" and aggregate.speed_mult == 0.5, "Reconcile must return the aggregate")
            assert(near(speed_of(entity), baseline * 0.5), "one chill stack must halve the speed")
            result = service:Apply("sfx-mods-1", entity, "chill", source, now + 1)
            assert(result.code == "applied" and result.stacks == 1, "a retried request must return the first result")
            service:Reconcile(entity, now + 1)
            assert(near(speed_of(entity), baseline * 0.5), "a retried request must not add a stack")

            result = service:Apply("sfx-mods-2", entity, "chill", nil, now + 1)
            assert(result.code == "refreshed" and result.stacks == 2)
            result = service:Apply("sfx-mods-3", entity, "frenzy", nil, now + 1)
            assert(result.code == "applied" and result.expires_at == now + 11)
            service:Reconcile(entity, now + 1)
            assert(near(speed_of(entity), baseline * 0.3125), "two chill stacks and frenzy must give 0.3125")
            assert(near(damage_mult_of(entity), 1.5), "frenzy must set the real damage multiplier")
            assert(near(entity.components.combat:CalcDamage(dummy), 15), "real damage must be scaled by frenzy")

            -- A modifier owned by somebody else must survive every reconcile.
            entity.components.locomotor:SetExternalSpeedMultiplier(dummy, "sfx-suite-foreign", 2)
            result = service:Dispel(entity, "cold", nil, now + 2)
            assert(result.ok == true and result.count == 1 and result.removed[1].effect_id == "chill" and result.removed[1].stacks == 2)
            service:Reconcile(entity, now + 2)
            assert(near(speed_of(entity), baseline * 2.5), "dispel must leave frenzy and the foreign modifier")
            service:Reconcile(entity, now + 10.5)
            assert(near(damage_mult_of(entity), 1.5), "frenzy must still be live just before its expiry")
            service:Reconcile(entity, now + 11)
            assert(near(damage_mult_of(entity), 1), "frenzy must be gone at now == expires_at")
            assert(near(entity.components.combat:CalcDamage(dummy), 10))
            assert(near(speed_of(entity), baseline * 2), "only the foreign modifier may remain")
            entity.components.locomotor:RemoveExternalSpeedMultiplier(dummy, "sfx-suite-foreign")

            assert(service:Apply("sfx-mods-4", entity, "chill", nil, now + 11).ok == true)
            assert(near(speed_of(entity), baseline * 0.5), "Apply must reconcile the entity at once")
            assert(service:Tick(now + 19) == true)
            assert(near(speed_of(entity), baseline), "Tick must reconcile expired effects")

            assert(service:Apply("sfx-mods-5", entity, "chill", nil, now + 19).ok == true)
            entity:Remove()
            result = service:Apply("sfx-mods-6", entity, "chill", nil, now + 19)
            assert(result.ok == false and result.code == "unknown_target", "a removed entity must be forgotten")
            local successor = make()
            assert(service:Track(successor, "sfx-mods") == true, "the id of a removed entity must be free again")
            service:Reconcile(successor, now + 19)
            assert(near(speed_of(successor), baseline), "effects of the removed entity leaked to its successor")
        end)
    end)

    ctx:case("damage over time changes real health and death clears everything", function()
        local service = assert(TheWorld.components.statuseffects)
        with_entities(function(make)
            local now = base_time(3000)
            local entity = make(100)
            local health = entity.components.health
            local death_before, remove_before = listener_count(entity, "death"), listener_count(entity, "onremove")
            assert(service:Track(entity, "sfx-dot") == true)
            assert(listener_count(entity, "death") > death_before, "death must be listened for on the tracked entity")
            assert(listener_count(entity, "onremove") > remove_before, "onremove must be listened for on the tracked entity")
            local death_tracked, remove_tracked = listener_count(entity, "death"), listener_count(entity, "onremove")
            assert(service:Track(entity, "sfx-dot") == true)
            assert(listener_count(entity, "death") == death_tracked and listener_count(entity, "onremove") == remove_tracked,
                "tracking the same pair again must not register listeners twice")
            local baseline = speed_of(entity)

            assert(service:Apply("sfx-dot-1", entity, "venom", nil, now).ok == true)
            assert(service:Apply("sfx-dot-2", entity, "venom", nil, now + 1).code == "stacked")
            assert(service:Tick(now + 3) == true)
            assert(near(health.currenthealth, 90), "two venom instances must cost 10 by now+3, health is " .. tostring(health.currenthealth))
            assert(service:Tick(now + 2) == false, "a stale Tick must be rejected")
            assert(near(health.currenthealth, 90), "a stale Tick changed health")
            assert(service:Tick(now + 10) == true)
            assert(near(health.currenthealth, 76), "venom must be clipped to its expiry, health is " .. tostring(health.currenthealth))
            assert(service:Apply("sfx-dot-3", entity, "regen", nil, now + 10).ok == true)
            assert(service:Tick(now + 12) == true)
            assert(near(health.currenthealth, 78), "regen must heal 2 by now+12")
            assert(service:Tick(now + 20) == true)
            assert(near(health.currenthealth, 80), "regen must stop at its expiry")

            assert(service:Apply("sfx-dot-4", entity, "chill", nil, now + 20).ok == true)
            assert(service:Apply("sfx-dot-5", entity, "frenzy", nil, now + 20).ok == true)
            assert(service:Apply("sfx-dot-6", entity, "regen", nil, now + 20).ok == true)
            service:Reconcile(entity, now + 20)
            assert(near(speed_of(entity), baseline * 0.625) and near(damage_mult_of(entity), 1.5))
            health:DoDelta(-1000)
            assert(health:IsDead(), "the entity must really be dead")
            assert(near(speed_of(entity), baseline), "death must remove the speed modifier")
            assert(near(damage_mult_of(entity), 1), "death must remove the damage modifier")
            assert(listener_count(entity, "death") == death_before, "the death listener must be removed")
            assert(listener_count(entity, "onremove") == remove_before, "the onremove listener must be removed")
            local late = service:Apply("sfx-dot-7", entity, "regen", nil, now + 21)
            assert(late.ok == false and late.code == "unknown_target", "a dead entity must not receive effects")
            assert(service:Tick(now + 23) == true)
            assert(health:IsDead() and health.currenthealth <= 0, "regen must never revive a dead entity")

            -- Death caused by the Tick itself re-enters the death callback.
            local frail = make(5)
            assert(service:Track(frail, "sfx-frail") == true)
            assert(service:Apply("sfx-frail-1", frail, "chill", nil, now + 23).ok == true)
            assert(service:Apply("sfx-frail-2", frail, "venom", nil, now + 23).ok == true)
            service:Reconcile(frail, now + 23)
            assert(near(speed_of(frail), baseline * 0.5))
            assert(service:Tick(now + 26) == true)
            assert(frail.components.health:IsDead(), "venom must kill the frail entity through health:DoDelta")
            assert(near(speed_of(frail), baseline), "death inside Tick must clear the modifiers")
            assert(service:Apply("sfx-frail-3", frail, "chill", nil, now + 26).code == "unknown_target")
        end)
    end)

    ctx:case("effects survive OnSave and OnLoad and component removal cleans up", function()
        local service = assert(TheWorld.components.statuseffects)
        with_entities(function(make)
            local now = base_time(4000)
            local entity = make(100)
            local health = entity.components.health
            assert(service:Track(entity, "sfx-persist") == true)
            local baseline = speed_of(entity)
            assert(service:Apply("sfx-persist-1", entity, "chill", nil, now).ok == true)
            assert(service:Apply("sfx-persist-2", entity, "venom", nil, now).ok == true)
            assert(service:Tick(now + 3) == true)
            assert(near(health.currenthealth, 94))
            local data = service:OnSave()
            assert(type(data) == "table", "OnSave must return a table")
            local copy = plain_copy(data)
            assert(service:Dispel(entity, "debuff", nil, now + 3).count == 2)
            service:Reconcile(entity, now + 3)
            assert(near(speed_of(entity), baseline))

            local reload_time = GetTime()
            service:OnLoad(copy)
            assert(near(speed_of(entity), baseline * 0.5), "OnLoad must reconcile entities that are still tracked")
            assert(service:Tick(reload_time + 2) == true)
            assert(near(health.currenthealth, 90), "venom must continue from the reload time, health is " .. tostring(health.currenthealth))
            service:Reconcile(entity, reload_time + 4.5)
            assert(near(speed_of(entity), baseline * 0.5), "chill must keep 5 seconds after the reload")
            assert(service:Tick(reload_time + 5.5) == true)
            assert(near(health.currenthealth, 88), "venom must keep 3 seconds after the reload, health is " .. tostring(health.currenthealth))
            assert(near(speed_of(entity), baseline), "chill must expire 5 seconds after the reload")

            local retry = service:Apply("sfx-persist-1", entity, "venom", nil, reload_time + 6)
            assert(retry.ok == true and retry.code == "applied" and retry.effect_id == "chill", "request history must survive the reload")
            assert(service:Tick(reload_time + 9) == true)
            assert(near(health.currenthealth, 88) and near(speed_of(entity), baseline), "a retried request had side effects after the reload")

            assert(service:Apply("sfx-persist-3", entity, "chill", nil, reload_time + 9).ok == true)
            service:Reconcile(entity, reload_time + 9)
            assert(near(speed_of(entity), baseline * 0.5))
            service:OnLoad(nil)
            assert(near(speed_of(entity), baseline), "loading empty data must clear the modifiers of tracked entities")
            local again = service:Apply("sfx-persist-4", entity, "chill", nil, GetTime() + 1)
            assert(again.ok == true and again.code == "applied", "tracked entities must stay registered after OnLoad")
            assert(type(service:OnSave()) == "table")

            -- A saved target that has no entity yet keeps its effects for the next Track.
            local leaver = make(100)
            assert(service:Track(leaver, "sfx-rejoin") == true)
            assert(service:Apply("sfx-rejoin-1", leaver, "chill", nil, GetTime() + 2).ok == true)
            local parked = plain_copy(service:OnSave())
            leaver:Remove()
            service:OnLoad(parked)
            local rejoiner = make(100)
            assert(near(speed_of(rejoiner), baseline))
            assert(service:Track(rejoiner, "sfx-rejoin") == true)
            assert(near(speed_of(rejoiner), baseline * 0.5), "restored effects must reach the entity that takes the id")

            -- Removing the component must cancel its task and release every entity.
            local mortal = make(100)
            local death_before, remove_before = listener_count(mortal, "death"), listener_count(mortal, "onremove")
            assert(service:Track(mortal, "sfx-teardown") == true)
            assert(service:Apply("sfx-teardown-1", mortal, "frenzy", nil, GetTime() + 2).ok == true)
            service:Reconcile(mortal, GetTime() + 2)
            assert(near(speed_of(mortal), baseline * 1.25) and near(damage_mult_of(mortal), 1.5))
            local tasks_before = pending_task_count(TheWorld)
            TheWorld:RemoveComponent("statuseffects")
            local removed_ok, removed_message = pcall(function()
                assert(TheWorld.components.statuseffects == nil)
                assert(pending_task_count(TheWorld) < tasks_before, "OnRemoveFromEntity must cancel the periodic task")
                assert(near(speed_of(mortal), baseline) and near(damage_mult_of(mortal), 1), "OnRemoveFromEntity must remove the modifiers")
                assert(listener_count(mortal, "death") == death_before, "OnRemoveFromEntity must remove the death listener")
                assert(listener_count(mortal, "onremove") == remove_before, "OnRemoveFromEntity must remove the onremove listener")
            end)
            TheWorld:AddComponent("statuseffects")
            assert(removed_ok, removed_message)
            assert(TheWorld.components.statuseffects ~= nil, "the component must attach again")
            assert(TheWorld.components.statuseffects:Track(mortal, "sfx-teardown") == true, "a fresh component must accept the entity")
        end)
    end)
end
