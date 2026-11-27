local mod = RegisterMod("Construct Entity Cleanup Reference", 1)
local game = Game()

-- GetData() keys written on the entities these wrappers spawn: a tracked owner carries its own
-- token, and a tracked effect carries the token of the owner that claimed it. Ownership is never
-- decided by reading a tag back; the registry below is the only source of truth.
local OWNER_TOKEN_KEY = "gcbOwnerToken"
local EFFECT_OWNER_KEY = "gcbEffectOwner"

-- Monotonic counters of this mod instance. They are never reset, so an owner token or a
-- room-visit token cannot repeat within a run.
local ownerSerial = 0
local roomVisit = 0
local roomSpawnSeed = nil

-- Owner records in spawn order. A record keeps the owner's token, its identity (InitSeed and
-- Type), its current Index, the room visit it was spawned in and its effect records.
local owners = {}
-- Effects of owners released inside MC_POST_ENTITY_REMOVE. That callback only does bookkeeping;
-- the next sweep removes whichever of these entities still exists.
local pendingEffects = {}

local function copyList(list)
    local result = {}
    for index, value in ipairs(list) do
        result[index] = value
    end
    return result
end

local function unlist(list, item)
    for index = #list, 1, -1 do
        if list[index] == item then
            table.remove(list, index)
        end
    end
end

local function readIdentity(entity)
    local ok, seed, entityType, index = pcall(function()
        return entity.InitSeed, entity.Type, entity.Index
    end)
    if ok and seed ~= nil and entityType ~= nil then
        return seed, entityType, index
    end
    return nil
end

local function exists(entity)
    local ok, result = pcall(function()
        return entity:Exists()
    end)
    return ok and result == true
end

local function isLive(entity)
    local ok, result = pcall(function()
        return entity:Exists() and not entity:IsDead()
    end)
    return ok and result == true
end

-- Existing room entities grouped by InitSeed. Entities are always taken from this fresh list,
-- never from a reference kept across frames, whose object may since belong to another entity.
local function roomEntitiesBySeed()
    local bySeed = {}
    local ok, entities = pcall(Isaac.GetRoomEntities)
    if not ok or type(entities) ~= "table" then
        return bySeed
    end
    for _, entity in ipairs(entities) do
        local seed = readIdentity(entity)
        if seed ~= nil and exists(entity) then
            local list = bySeed[seed]
            if list == nil then
                list = {}
                bySeed[seed] = list
            end
            list[#list + 1] = entity
        end
    end
    return bySeed
end

-- The existing entity of a record, matched by InitSeed and Type, never by the reusable Index. An
-- entity spawned during the current frame may not be listed yet, so its own reference is trusted
-- during that frame only.
local function locate(bySeed, record, allowSpawnFrame)
    local candidates = bySeed[record.initSeed]
    if candidates ~= nil then
        for _, entity in ipairs(candidates) do
            local seed, entityType = readIdentity(entity)
            if seed == record.initSeed and entityType == record.type and exists(entity) then
                return entity
            end
        end
    end
    if allowSpawnFrame and record.spawnFrame == game:GetFrameCount() and exists(record.entity) then
        return record.entity
    end
    return nil
end

local function clearTag(entity, key, token)
    pcall(function()
        local data = entity:GetData()
        if data[key] == token then
            data[key] = nil
        end
    end)
end

-- Removes the entity of a released record if it still exists, at most once.
local function removeOnce(bySeed, record, key, allowSpawnFrame)
    if record.removed then
        return
    end
    record.removed = true
    local entity = locate(bySeed, record, allowSpawnFrame)
    if entity ~= nil then
        clearTag(entity, key, record.token)
        pcall(function()
            entity:Remove()
        end)
    end
end

-- Clears one owner's registry entry and removes each of its still-existing effects once. With a
-- fresh room list (bySeed) the effects are removed now; without one (inside the removal
-- callback) they wait for the next sweep. Leaving a room also removes an owner entity that is
-- still around.
local function releaseOwner(record, bySeed, removeOwnerEntity, allowSpawnFrame)
    if record.released then
        return
    end
    record.released = true
    unlist(owners, record)
    local effects = record.effects
    record.effects = {}
    for _, effect in ipairs(effects) do
        if bySeed ~= nil then
            removeOnce(bySeed, effect, EFFECT_OWNER_KEY, allowSpawnFrame)
        else
            pendingEffects[#pendingEffects + 1] = effect
        end
    end
    if removeOwnerEntity and bySeed ~= nil then
        removeOnce(bySeed, record, OWNER_TOKEN_KEY, allowSpawnFrame)
    end
end

local function flushPendingEffects(bySeed, allowSpawnFrame)
    local pending = pendingEffects
    pendingEffects = {}
    for _, effect in ipairs(pending) do
        removeOnce(bySeed, effect, EFFECT_OWNER_KEY, allowSpawnFrame)
    end
end

-- Clears one effect reference whose entity was removed (or killed) elsewhere.
local function dropEffect(record, effect)
    effect.removed = true
    unlist(record.effects, effect)
end

local function ownerRecordOf(seed, entityType)
    for _, record in ipairs(owners) do
        if record.initSeed == seed and record.type == entityType then
            return record
        end
    end
    return nil
end

-- MC_POST_UPDATE: reconcile a snapshot of the registry with the room. Entries released during
-- the pass are skipped through their flags, so no later owner or effect is missed.
local function sweep()
    if #owners == 0 and #pendingEffects == 0 then
        return
    end
    local bySeed = roomEntitiesBySeed()
    flushPendingEffects(bySeed, true)
    for _, record in ipairs(copyList(owners)) do
        if not record.released then
            local entity = locate(bySeed, record, true)
            if entity == nil or not isLive(entity) then
                releaseOwner(record, bySeed, false, true)
            else
                local _, _, index = readIdentity(entity)
                record.index = index
                for _, effect in ipairs(copyList(record.effects)) do
                    local effectEntity = locate(bySeed, effect, true)
                    if effectEntity == nil or not isLive(effectEntity) then
                        dropEffect(record, effect)
                    else
                        local _, _, effectIndex = readIdentity(effectEntity)
                        effect.index = effectIndex
                    end
                end
            end
        end
    end
end

-- MC_POST_ENTITY_REMOVE: bookkeeping only. A repeated, late or foreign event finds no record.
local function onEntityRemoved(entity)
    local seed, entityType = readIdentity(entity)
    if seed == nil then
        return
    end
    local owner = ownerRecordOf(seed, entityType)
    if owner ~= nil then
        clearTag(entity, OWNER_TOKEN_KEY, owner.token)
        releaseOwner(owner, nil, false, false)
        return
    end
    for _, record in ipairs(owners) do
        for _, effect in ipairs(record.effects) do
            if effect.initSeed == seed and effect.type == entityType then
                clearTag(entity, EFFECT_OWNER_KEY, effect.token)
                dropEffect(record, effect)
                return
            end
        end
    end
    for _, effect in ipairs(pendingEffects) do
        if not effect.removed and effect.initSeed == seed and effect.type == entityType then
            effect.removed = true
            return
        end
    end
end

local function recordRoomVisit()
    roomVisit = roomVisit + 1
    roomSpawnSeed = game:GetRoom():GetSpawnSeed()
end

-- MC_POST_NEW_ROOM: everything still registered belongs to the room being left. Only entities
-- matched to those records are touched; tags on other room entities are never read.
local function enterRoom()
    local bySeed = roomEntitiesBySeed()
    flushPendingEffects(bySeed, false)
    for _, record in ipairs(copyList(owners)) do
        releaseOwner(record, bySeed, true, false)
    end
    recordRoomVisit()
end

local function currentVisit()
    if roomVisit == 0 then
        -- Loaded inside a room whose MC_POST_NEW_ROOM this mod never saw.
        recordRoomVisit()
    end
    return roomSpawnSeed, roomVisit
end

-- Isaac.Spawn, accepting only an entity that still exists when the call returns.
local function spawnEntity(entityType, variant, subType, position, velocity, spawner)
    local ok, entity = pcall(Isaac.Spawn, entityType, variant, subType, position, velocity, spawner)
    if not ok or entity == nil or not exists(entity) or readIdentity(entity) == nil then
        return nil
    end
    return entity
end

local function spawnTrackedOwner(entityType, variant, subType, position, velocity, spawner)
    local entity = spawnEntity(entityType, variant, subType, position, velocity, spawner)
    if entity == nil then
        return nil
    end
    local seed, spawnedType, index = readIdentity(entity)
    local spawnSeed, visit = currentVisit()
    ownerSerial = ownerSerial + 1
    local record = {
        token = tostring(seed) .. ":" .. tostring(ownerSerial),
        initSeed = seed,
        type = spawnedType,
        index = index,
        roomSpawnSeed = spawnSeed,
        roomVisit = visit,
        effects = {},
        entity = entity,
        spawnFrame = game:GetFrameCount(),
    }
    pcall(function()
        entity:GetData()[OWNER_TOKEN_KEY] = record.token
    end)
    owners[#owners + 1] = record
    return entity
end

-- The registry record of a live owner, matched by identity; a tag alone never makes an owner.
local function trackedOwnerOf(owner)
    if owner == nil or not isLive(owner) then
        return nil
    end
    local seed, entityType = readIdentity(owner)
    if seed == nil then
        return nil
    end
    return ownerRecordOf(seed, entityType)
end

local function spawnTrackedEffect(owner, entityType, variant, subType, position, velocity, spawner)
    local record = trackedOwnerOf(owner)
    if record == nil then
        return nil
    end
    local entity = spawnEntity(entityType, variant, subType, position, velocity, spawner)
    if entity == nil then
        return nil
    end
    if record.released then
        -- The owner went away while the effect spawned; nothing may claim this entity.
        pcall(function()
            entity:Remove()
        end)
        return nil
    end
    local seed, spawnedType, index = readIdentity(entity)
    local effect = {
        token = record.token,
        initSeed = seed,
        type = spawnedType,
        index = index,
        entity = entity,
        spawnFrame = game:GetFrameCount(),
    }
    pcall(function()
        entity:GetData()[EFFECT_OWNER_KEY] = record.token
    end)
    record.effects[#record.effects + 1] = effect
    return entity
end

local function snapshot()
    local records = {}
    for _, record in ipairs(owners) do
        local effects = {}
        for _, effect in ipairs(record.effects) do
            effects[#effects + 1] = {
                token = effect.token,
                initSeed = effect.initSeed,
                index = effect.index,
            }
        end
        records[#records + 1] = {
            token = record.token,
            initSeed = record.initSeed,
            index = record.index,
            roomSpawnSeed = record.roomSpawnSeed,
            roomVisit = record.roomVisit,
            effects = effects,
        }
    end
    return { owners = records }
end

IsaacConstructEntities = {
    SpawnTrackedOwner = spawnTrackedOwner,
    SpawnTrackedEffect = spawnTrackedEffect,
    Snapshot = snapshot,
}

mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, enterRoom)
mod:AddCallback(ModCallbacks.MC_POST_UPDATE, sweep)
mod:AddCallback(ModCallbacks.MC_POST_ENTITY_REMOVE, function(_, entity)
    onEntityRemoved(entity)
end)
