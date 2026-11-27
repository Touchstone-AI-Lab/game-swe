local suite = RegisterMod("Construct Entity Cleanup Verifier", 1)
local game = Game()
local json = require("json")

-- Every fixture is a plain Fly (13.0). The suite makes each one inert as soon as it exists and
-- keeps it so on every frame (no entity collision, frozen, at rest): no fixture can touch the
-- player, and only the scripted Remove()/Kill() calls and the submission remove fixtures.
local FLY = EntityType.ENTITY_FLY
-- A GetData() tag value that no owner token can be equal to.
local FOREIGN_TOKEN = "gcb-foreign-token"
-- Update frames a cleanup gets before its result is asserted. The contract sweeps on every
-- MC_POST_UPDATE, so one or two frames suffice whichever mod's callbacks run first.
local SETTLE = 10
-- Update frames between the kills and the check of the post-update sweep case.
local SWEEP_DEADLINE = 3
-- Update frames a room transition may take before its cases fail.
local TRANSITION_BUDGET = 150
-- The public acceptance cases; only used to report the cases an aborted suite never reached.
local CASES = {
    "created_effect_is_tracked",
    "foreign_entity_is_not_tracked",
    "live_owner_keeps_effect",
    "dead_owner_removes_effect",
    "removed_owner_removes_effect",
    "owner_missing_clears_reference",
    "room_change_removes_old_owned_effect",
    "room_change_keeps_foreign_effect",
    "reentry_does_not_restore_old_owner",
    "repeated_cleanup_is_idempotent",
    "duplicate_remove_callback_is_safe",
    "already_removed_entity_is_safe",
    "nil_owner_is_safe",
    "effect_removed_once",
    "registry_entry_removed_once",
    "reused_entity_index_not_reused",
    "ownership_token_matches_entity",
    "ownership_token_survives_update",
    "ownership_token_cleared_on_room_change",
    "new_owner_does_not_adopt_stale_effect",
    "two_owners_clean_independently",
    "multiple_effects_per_owner_clean",
    "foreign_sibling_effect_survives_cleanup",
    "entity_removed_callback_scoped",
    "partial_effect_remove_clears_only_one",
    "post_update_catches_missing_remove_event",
    "room_identity_prevents_cross_room_cleanup",
    "cleanup_order_does_not_skip_entries",
    "cleanup_after_owner_death",
    "cleanup_after_owner_remove",
    "cleanup_after_transition_then_remove",
    "no_double_free_on_transition",
    "foreign_entity_untouched_on_bulk_scan",
    "registry_empty_after_all_owners_removed",
    "reused_index_does_not_adopt_new_entity",
}
-- Owners each scripted round removes or kills; registry samples must never list them again.
local RELEASED_FIRST = {
    "dead.owner", "removed.owner", "missing.owner", "multi.owner", "two.first",
    "scoped.removed", "sibling.owner", "order.o1", "order.o2", "order.o3", "dup.owner",
    "idem.owner", "once.owner", "reuse.owner", "adopt.owner", "stale.owner",
}
local RELEASED_SECOND = { "two.second", "stale.next" }
local RELEASED_THIRD = { "sweep.owner" }
local RELEASED_FOURTH = { "already.owner" }

local passed = 0
local failed = 0
local recorded = {}
local finished = false
local started = false
-- Update frames since the run started. The plan runs one entry per frame from the first one,
-- when every mod's MC_POST_GAME_STARTED handler has run whatever the mod load order.
local frame = 0
local slotCounter = 0

local ctx = {
    epoch = 0,        -- bumped by every MC_POST_NEW_ROOM; stored entity references die with it
    handles = {},     -- fixture name -> handle
    groupErrors = {}, -- fixture group -> first error
    owners = {},      -- tracked owner handles in spawn order
    acted = {},       -- fixture name -> true once its scripted Remove()/Kill() happened
    samples = {},     -- registry samples for registry_entry_removed_once
    visits = {},      -- spawn seed of each visited room, in visit order
    ownerKeys = {},   -- GetData() keys holding an owner's own token
    effectKeys = {},  -- GetData() keys holding an effect's owner token
    allKeys = {},
}

local function log(text)
    Isaac.DebugString(text)
end

local function oneLine(value)
    return (tostring(value):gsub("[\r\n]+", " "))
end

local function equal(actual, expected, label)
    if actual ~= expected then
        error((label or "value") .. ": expected " .. tostring(expected)
            .. ", received " .. tostring(actual), 2)
    end
end

local function truthy(value, label)
    if not value then
        error(label or "expected truthy value", 2)
    end
    return value
end

local function record(name, ok, detail)
    if recorded[name] then
        return
    end
    recorded[name] = true
    if ok then
        passed = passed + 1
        log("[GCB_CASE] PASS " .. name .. " " .. oneLine(detail or "ok"))
    else
        failed = failed + 1
        log("[GCB_CASE] FAIL " .. name .. " " .. oneLine(detail or "failed"))
    end
end

local function run(name, fn)
    local ok, result = pcall(fn)
    record(name, ok, result)
end

-- pcall that keeps the outcome for a case recorded on a later frame.
local function capture(fn)
    local ok, value = pcall(fn)
    return { ok = ok, value = value }
end

local function captured(result, label)
    truthy(result ~= nil, label .. " was never checked")
    truthy(result.ok, label .. ": " .. oneLine(result.value))
    return result.value
end

local function finish()
    if finished then
        return
    end
    finished = true
    log("[GCB_SUMMARY] passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed)
        .. " total=" .. tostring(passed + failed))
end

-- The suite body itself crashed: report it, fail every unreached case once, and stop.
local function abort(err)
    if finished then
        return
    end
    log("[GCB_FATAL] " .. oneLine(err))
    for _, name in ipairs(CASES) do
        record(name, false, "suite aborted before this case: " .. oneLine(err))
    end
    finish()
end

local function api()
    local exported = IsaacConstructEntities
    truthy(type(exported) == "table", "IsaacConstructEntities is not exported")
    return exported
end

local function need(name)
    local handle = ctx.handles[name]
    if handle == nil then
        local group = name:match("^([^.]+)")
        error("fixture " .. name .. " unavailable: "
            .. tostring(ctx.groupErrors[group] or "it was never spawned"), 0)
    end
    return handle
end

-- Creates a group of fixtures; a submission error keeps the group's first error for its cases.
local function group(name, fn)
    local ok, err = pcall(fn)
    if not ok and ctx.groupErrors[name] == nil then
        ctx.groupErrors[name] = oneLine(err)
    end
end

local function acted(name)
    truthy(ctx.acted[name], name .. " was not removed or killed as scripted")
end

local function nextPosition()
    slotCounter = slotCounter + 1
    local column = (slotCounter % 9) - 4
    local row = (math.floor(slotCounter / 9) % 5) - 2
    return game:GetRoom():GetCenterPos() + Vector(column * 32 + 16, row * 36)
end

local function roomSeed()
    return game:GetRoom():GetSpawnSeed()
end

local function pacify(entity)
    entity.EntityCollisionClass = EntityCollisionClass.ENTCOLL_NONE
    entity:AddEntityFlags(EntityFlag.FLAG_FREEZE)
    entity.Velocity = Vector(0, 0)
end

local function remember(name, entity, isOwner)
    truthy(entity ~= nil, name .. ": the spawn returned nil")
    local ok, live = pcall(function()
        return entity:Exists() and not entity:IsDead()
    end)
    truthy(ok and live, name .. ": the spawn did not return a live entity")
    pacify(entity)
    local handle = {
        name = name,
        entity = entity,
        seed = entity.InitSeed,
        index = entity.Index,
        epoch = ctx.epoch,
        isOwner = isOwner == true,
    }
    ctx.handles[name] = handle
    if handle.isOwner then
        ctx.owners[#ctx.owners + 1] = handle
    end
    return handle
end

-- A stored reference is only used inside the room it was spawned in.
local function entityOf(handle)
    truthy(handle.epoch == ctx.epoch, handle.name .. " belongs to a room that was left")
    return handle.entity
end

local function spawnForeign(name)
    return remember(name, Isaac.Spawn(FLY, 0, 0, nextPosition(), Vector(0, 0), nil), false)
end

local function spawnOwner(name)
    local entity = api().SpawnTrackedOwner(FLY, 0, 0, nextPosition(), Vector(0, 0), nil)
    return remember(name, entity, true)
end

local function spawnEffect(name, ownerName)
    local owner = need(ownerName)
    local entity = api().SpawnTrackedEffect(entityOf(owner), FLY, 0, 0, nextPosition(),
        Vector(0, 0), nil)
    local handle = remember(name, entity, false)
    handle.ownerName = ownerName
    return handle
end

-- GetData() keys of an entity whose value is exactly the given token.
local function keysHolding(entity, token)
    local keys = {}
    if token == nil then
        return keys
    end
    for key, value in pairs(entity:GetData()) do
        if value == token then
            keys[#keys + 1] = key
        end
    end
    return keys
end

-- Writes a tag under the submission's own keys onto a suite-spawned foreign fly.
local function forge(handle, keys, value)
    if value == nil then
        return handle
    end
    local data = handle.entity:GetData()
    for _, key in ipairs(keys) do
        data[key] = value
    end
    handle.forged = { keys = keys, value = value }
    return handle
end

local function dataHolds(entity, token)
    if token == nil then
        return false
    end
    for _, value in pairs(entity:GetData()) do
        if value == token then
            return true
        end
        if type(value) == "table" then
            for _, inner in pairs(value) do
                if inner == token then
                    return true
                end
            end
        end
    end
    return false
end

local function pick(source, names)
    for _, name in ipairs(names) do
        local value = source[name]
        if value ~= nil then
            return value
        end
    end
    return nil
end

local OWNER_TOKEN_FIELDS = { "token", "ownerToken" }
local EFFECT_TOKEN_FIELDS = { "ownerToken", "token" }
local SEED_FIELDS = { "initSeed", "InitSeed" }
local INDEX_FIELDS = { "index", "Index" }
local ROOM_SEED_FIELDS = { "roomSpawnSeed", "spawnSeed" }
local ROOM_VISIT_FIELDS = { "roomVisit", "roomVisitToken", "visitToken", "visit" }
local EFFECT_FIELDS = { "effects", "ownedEffects" }

-- A suite-owned copy of Snapshot(): owner records with their effect records. The field names
-- follow the statement's wording (token, initSeed, index, roomSpawnSeed, roomVisit, effects);
-- a few spellings of the same fields are accepted. The returned tables are never written.
local function readRegistry()
    local raw = api().Snapshot()
    truthy(type(raw) == "table", "Snapshot() did not return a table")
    local list = raw.owners
    if type(list) ~= "table" then
        list = raw
    end
    local registry = {}
    for _, source in pairs(list) do
        if type(source) == "table" then
            local owner = {
                token = pick(source, OWNER_TOKEN_FIELDS),
                initSeed = pick(source, SEED_FIELDS),
                index = pick(source, INDEX_FIELDS),
                roomSpawnSeed = pick(source, ROOM_SEED_FIELDS),
                roomVisit = pick(source, ROOM_VISIT_FIELDS),
                effects = {},
            }
            local effects = pick(source, EFFECT_FIELDS)
            if type(effects) == "table" then
                for _, effect in pairs(effects) do
                    if type(effect) == "table" then
                        owner.effects[#owner.effects + 1] = {
                            token = pick(effect, EFFECT_TOKEN_FIELDS),
                            initSeed = pick(effect, SEED_FIELDS),
                            index = pick(effect, INDEX_FIELDS),
                        }
                    end
                end
            end
            registry[#registry + 1] = owner
        end
    end
    return registry
end

local function describe(registry)
    local ok, text = pcall(json.encode, registry)
    if not ok or type(text) ~= "string" then
        return "?"
    end
    if #text > 240 then
        text = text:sub(1, 240) .. "..."
    end
    return text
end

local function ownerRecord(registry, handle)
    for _, owner in ipairs(registry) do
        if owner.initSeed == handle.seed then
            return owner
        end
    end
    return nil
end

local function effectRecord(registry, handle)
    for _, owner in ipairs(registry) do
        for _, effect in ipairs(owner.effects) do
            if effect.initSeed == handle.seed then
                return effect, owner
            end
        end
    end
    return nil
end

local function tokenListed(registry, token)
    if token == nil then
        return false
    end
    for _, owner in ipairs(registry) do
        if owner.token == token then
            return true
        end
        for _, effect in ipairs(owner.effects) do
            if effect.token == token then
                return true
            end
        end
    end
    return false
end

local function seedListed(registry, seed)
    for _, owner in ipairs(registry) do
        if owner.initSeed == seed then
            return true
        end
        for _, effect in ipairs(owner.effects) do
            if effect.initSeed == seed then
                return true
            end
        end
    end
    return false
end

-- The owner is tracked with exactly the named effects.
local function expectTracked(registry, handle, effectNames)
    local owner = ownerRecord(registry, handle)
    truthy(owner, handle.name .. " is not tracked; registry=" .. describe(registry))
    local expected = {}
    for _, name in ipairs(effectNames) do
        expected[need(name).seed] = name
    end
    for _, effect in ipairs(owner.effects) do
        truthy(expected[effect.initSeed], handle.name .. " lists an unexpected effect "
            .. tostring(effect.initSeed))
    end
    equal(#owner.effects, #effectNames, handle.name .. " effect count")
    return owner
end

local function expectUntracked(registry, handle)
    truthy(not seedListed(registry, handle.seed), handle.name .. " is listed in the registry")
end

-- The owner's entry is gone and its token is listed nowhere.
local function expectReleased(registry, handle)
    truthy(not ownerRecord(registry, handle), handle.name .. " is still tracked")
    if handle.token ~= nil then
        truthy(not tokenListed(registry, handle.token), handle.name .. " token is still listed")
    end
end

local function expectUnique(registry, label)
    local tokens, seeds, effectSeeds = {}, {}, {}
    for _, owner in ipairs(registry) do
        truthy(owner.token ~= nil, label .. ": an owner record has no token")
        truthy(owner.initSeed ~= nil, label .. ": an owner record has no InitSeed")
        truthy(not tokens[owner.token],
            label .. ": owner token listed twice: " .. tostring(owner.token))
        truthy(not seeds[owner.initSeed], label .. ": owner InitSeed listed twice")
        tokens[owner.token] = true
        seeds[owner.initSeed] = true
        for _, effect in ipairs(owner.effects) do
            truthy(effect.initSeed ~= nil, label .. ": an effect record has no InitSeed")
            truthy(not effectSeeds[effect.initSeed], label .. ": effect InitSeed listed twice")
            effectSeeds[effect.initSeed] = true
        end
    end
end

local function signature(registry)
    local parts = {}
    for _, owner in ipairs(registry) do
        local seeds = {}
        for _, effect in ipairs(owner.effects) do
            seeds[#seeds + 1] = tostring(effect.initSeed)
        end
        table.sort(seeds)
        parts[#parts + 1] = tostring(owner.token) .. "@" .. tostring(owner.initSeed)
            .. "[" .. table.concat(seeds, ",") .. "]"
    end
    table.sort(parts)
    return table.concat(parts, ";")
end

-- Existing flies of the current room grouped by InitSeed, from a fresh entity list.
local function scanRoom()
    local bySeed = {}
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == FLY and entity:Exists() then
            local list = bySeed[entity.InitSeed]
            if list == nil then
                list = {}
                bySeed[entity.InitSeed] = list
            end
            list[#list + 1] = entity
        end
    end
    return bySeed
end

local function existingOf(bySeed, handle)
    for _, entity in ipairs(bySeed[handle.seed] or {}) do
        if entity:Exists() then
            return entity
        end
    end
    return nil
end

local function liveOf(bySeed, handle)
    for _, entity in ipairs(bySeed[handle.seed] or {}) do
        if entity:Exists() and not entity:IsDead() then
            return entity
        end
    end
    return nil
end

local function expectPresent(bySeed, handle)
    return truthy(liveOf(bySeed, handle), handle.name .. " no longer exists")
end

local function expectGone(bySeed, handle)
    truthy(not existingOf(bySeed, handle), handle.name .. " still exists")
end

local function flyCount()
    local count = 0
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == FLY and entity:Exists() then
            count = count + 1
        end
    end
    return count
end

-- SpawnTrackedEffect(owner, ...) for an owner that must be refused: nil, and nothing spawned.
local function expectRefused(owner, label)
    local before = flyCount()
    local result = api().SpawnTrackedEffect(owner, FLY, 0, 0, nextPosition(), Vector(0, 0), nil)
    if result ~= nil then
        pcall(function()
            result:Remove()
        end)
        error(label .. ": SpawnTrackedEffect returned an entity", 0)
    end
    equal(flyCount(), before, label .. ": flies after the refused claim")
end

-- Removes or kills a fixture through a fresh room entity, never through a stored reference.
local function act(bySeed, name, method)
    local handle = ctx.handles[name]
    if handle == nil then
        return nil
    end
    local entity = liveOf(bySeed, handle)
    if entity == nil then
        return nil
    end
    if method == "Kill" then
        entity:Kill()
    else
        entity:Remove()
    end
    ctx.acted[name] = true
    return entity
end

-- The owner tokens and their visit fields, read right after the owners spawned.
local function learnTokens()
    local ok, registry = pcall(readRegistry)
    if not ok then
        ctx.tokenError = oneLine(registry)
        return
    end
    for _, handle in ipairs(ctx.owners) do
        if handle.token == nil then
            local owner = ownerRecord(registry, handle)
            if owner ~= nil and owner.token ~= nil then
                handle.token = owner.token
                handle.roomVisit = owner.roomVisit
                handle.roomSpawnSeed = owner.roomSpawnSeed
            end
        end
    end
end

local function tokenOf(handle)
    if handle.token == nil then
        error(handle.name .. " has no observed token"
            .. (ctx.tokenError and (": " .. ctx.tokenError) or ""), 0)
    end
    return handle.token
end

local function seedTexts(seed)
    local texts = { tostring(seed) }
    local integer = type(seed) == "number" and math.tointeger and math.tointeger(seed) or nil
    if integer ~= nil and tostring(integer) ~= texts[1] then
        texts[#texts + 1] = tostring(integer)
    end
    return texts
end

local function tokenMentionsSeed(token, seed)
    local text = tostring(token)
    for _, seedText in ipairs(seedTexts(seed)) do
        if text:find(seedText, 1, true) then
            return true
        end
    end
    return false
end

-- The mod serial inside a token: the first integer left once the InitSeed text is taken out.
local function tokenSerial(token, seed)
    local text = tostring(token)
    for _, seedText in ipairs(seedTexts(seed)) do
        local first, last = text:find(seedText, 1, true)
        if first then
            local digits = (text:sub(1, first - 1) .. " " .. text:sub(last + 1)):match("%d+")
            if digits then
                return tonumber(digits)
            end
        end
    end
    return nil
end

-- Tokens never repeat and their mod serial grows in spawn order, across rooms too.
local function expectIncreasingSerials(handles)
    local seen = {}
    local previous = nil
    for _, handle in ipairs(handles) do
        local token = tokenOf(handle)
        truthy(not seen[token], "token issued twice: " .. tostring(token))
        seen[token] = true
        local serial = tokenSerial(token, handle.seed)
        truthy(serial ~= nil, handle.name .. " token " .. tostring(token)
            .. " has no mod serial besides InitSeed " .. tostring(handle.seed))
        if previous ~= nil then
            truthy(serial > previous.serial, "token serial did not increase from "
                .. previous.name .. " to " .. handle.name)
        end
        previous = { name = handle.name, serial = serial }
    end
end

local function sample(label, releasedLists)
    local released = {}
    for _, list in ipairs(releasedLists) do
        for _, name in ipairs(list) do
            released[#released + 1] = name
        end
    end
    local ok, registry = pcall(readRegistry)
    ctx.samples[#ctx.samples + 1] = {
        label = label,
        registry = ok and registry or nil,
        err = (not ok) and oneLine(registry) or nil,
        released = released,
    }
end

-- Runs a call with Isaac.Spawn replaced by patch(original, ...), then restores it.
local function patchSpawn(patch, call)
    local original = Isaac.Spawn
    local result = { calls = 0, restored = true }
    local installed = false
    if Isaac.Spawn == original then
        installed = pcall(function()
            Isaac.Spawn = function(...)
                result.calls = result.calls + 1
                return patch(original, ...)
            end
        end)
        installed = installed and Isaac.Spawn ~= original
    end
    result.ok, result.value = pcall(call)
    if installed then
        pcall(function()
            Isaac.Spawn = original
        end)
        result.restored = Isaac.Spawn == original
    end
    return result
end

-- A wrapper call during which Isaac.Spawn hands back an entity removed before it returned.
local function probeRemovedSpawn(call)
    local removed = nil
    local probe = {}
    local patched = patchSpawn(function(original, ...)
        local entity = original(...)
        if entity ~= nil then
            removed = entity
            probe.removedSeed = entity.InitSeed
            entity:Remove()
        end
        return entity
    end, call)
    probe.calls = patched.calls
    probe.restored = patched.restored
    if not patched.ok then
        probe.error = oneLine(patched.value)
        return probe
    end
    probe.returnedNil = patched.value == nil
    if removed ~= nil then
        local ok, alive = pcall(function()
            return removed:Exists()
        end)
        probe.goneAtReturn = ok and alive == false
    end
    if patched.value ~= nil then
        local ok, seed = pcall(function()
            return patched.value.InitSeed
        end)
        if not ok or seed ~= probe.removedSeed then
            -- The wrapper spawned through another path; drop that stray entity.
            pcall(function()
                patched.value:Remove()
            end)
        end
    end
    return probe
end

local function requireRestored(probe)
    if not probe.restored then
        error("Isaac.Spawn could not be restored after a probe")
    end
end

local function transitionOk(transition)
    truthy(transition ~= nil, "room transition was never started")
    truthy(transition.seen, "room transition " .. transition.label .. " failed: "
        .. tostring(transition.failure or "no MC_POST_NEW_ROOM was observed"))
end

-- The registry around a room change, independent of callback order. When the suite's
-- MC_POST_NEW_ROOM runs, the submission's has run too (nothing may remain) or not yet (only
-- entries from before the change may remain); nothing else may appear. At the first update
-- after the change the submission's MC_POST_NEW_ROOM has run, so nothing may remain at all.
local function expectCleanTransition(transition)
    transitionOk(transition)
    local before = captured(transition.before, "registry before the room change")
    local atEnter = captured(transition.atEnter, "registry in MC_POST_NEW_ROOM")
    for _, owner in ipairs(atEnter) do
        truthy(owner.token ~= nil and before[owner.token],
            "an entry that did not exist before the room change appeared in MC_POST_NEW_ROOM: "
            .. tostring(owner.token))
    end
    local atUpdate = captured(transition.atUpdate, "registry at the first update after the change")
    equal(#atUpdate, 0, "entries left at the first update after the room change")
end

-- Starts a real room change through the console command the Exodus verifiers use. The state is
-- armed before the command because the game may run MC_POST_NEW_ROOM inside the call.
local function beginTransition(label, command, onEnter)
    local transition = { label = label, command = command, onEnter = onEnter, seen = false }
    ctx.transition = transition
    if type(IsaacConstructEntities) ~= "table" then
        transition.failure = "not attempted: IsaacConstructEntities is not exported"
        return
    end
    transition.before = capture(function()
        local tokens = {}
        for _, owner in ipairs(readRegistry()) do
            if owner.token ~= nil then
                tokens[owner.token] = true
            end
        end
        return tokens
    end)
    transition.armed = true
    transition.armedFrame = frame
    Isaac.ExecuteCommand(command)
end

local function transitionSettled()
    local transition = ctx.transition
    if transition == nil or not transition.armed then
        return true
    end
    if transition.seen and transition.atUpdate == nil then
        transition.atUpdate = capture(readRegistry)
    end
    return transition.seen and frame - transition.seenFrame >= SETTLE
end

local function transitionTimedOut()
    local transition = ctx.transition
    if transition ~= nil and not transition.seen then
        transition.failure = transition.failure
            or ("no MC_POST_NEW_ROOM within " .. TRANSITION_BUDGET .. " update frames")
    end
end

-- Every fly in these rooms exists because the suite asked for it, including any a faulty
-- submission spawned on its own; none may reach the player.
local function pacifyAll()
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == FLY and entity:Exists() and not entity:IsDead() then
            pacify(entity)
        end
    end
end

-- The plan: one entry per update frame. A step runs once; a wait holds for a number of frames;
-- an await holds until its condition or its frame budget.
local plan = {}
local cursor = 1
local cursorAge = 0

local function step(fn)
    plan[#plan + 1] = { kind = "step", fn = fn }
end

local function wait(frames)
    plan[#plan + 1] = { kind = "wait", frames = frames }
end

local function await(condition, budget, onTimeout)
    plan[#plan + 1] = { kind = "await", condition = condition, budget = budget,
        onTimeout = onTimeout }
end

local function tick()
    local entry = plan[cursor]
    if entry == nil then
        finish()
        return
    end
    cursorAge = cursorAge + 1
    local advance = false
    if entry.kind == "step" then
        entry.fn()
        advance = true
    elseif entry.kind == "wait" then
        advance = cursorAge >= entry.frames
    elseif entry.condition() then
        advance = true
    elseif cursorAge >= entry.budget then
        entry.onTimeout()
        advance = true
    end
    if advance then
        cursor = cursor + 1
        cursorAge = 0
    end
end

-- Frame 1: every same-room fixture, and the cases that only need the spawns themselves.
step(function()
    ctx.visits[1] = { seed = roomSeed() }
    group("basic", function()
        spawnOwner("basic.owner")
        spawnEffect("basic.effect", "basic.owner")
    end)
    group("partial", function()
        spawnOwner("partial.owner")
        spawnEffect("partial.a", "partial.owner")
        spawnEffect("partial.b", "partial.owner")
        spawnEffect("partial.c", "partial.owner")
    end)
    group("dead", function()
        spawnOwner("dead.owner")
        spawnEffect("dead.effect", "dead.owner")
    end)
    group("removed", function()
        spawnOwner("removed.owner")
        spawnEffect("removed.effect", "removed.owner")
    end)
    group("missing", function()
        spawnOwner("missing.owner")
        spawnEffect("missing.a", "missing.owner")
        spawnEffect("missing.b", "missing.owner")
    end)
    group("multi", function()
        spawnOwner("multi.owner")
        spawnEffect("multi.a", "multi.owner")
        spawnEffect("multi.b", "multi.owner")
        spawnEffect("multi.c", "multi.owner")
    end)
    group("two", function()
        spawnOwner("two.first")
        spawnEffect("two.firstEffect", "two.first")
        spawnOwner("two.second")
        spawnEffect("two.secondEffect", "two.second")
    end)
    group("scoped", function()
        spawnOwner("scoped.removed")
        spawnEffect("scoped.removedA", "scoped.removed")
        spawnEffect("scoped.removedB", "scoped.removed")
        spawnOwner("scoped.kept")
        spawnEffect("scoped.keptEffect", "scoped.kept")
    end)
    group("sibling", function()
        spawnOwner("sibling.owner")
        spawnEffect("sibling.effect", "sibling.owner")
    end)
    group("order", function()
        for _, name in ipairs({ "order.o1", "order.o2", "order.o3", "order.o4" }) do
            spawnOwner(name)
            spawnEffect(name .. "a", name)
            spawnEffect(name .. "b", name)
        end
    end)
    group("dup", function()
        spawnOwner("dup.owner")
        spawnEffect("dup.a", "dup.owner")
        spawnEffect("dup.b", "dup.owner")
    end)
    group("idem", function()
        spawnOwner("idem.owner")
        spawnEffect("idem.effect", "idem.owner")
    end)
    group("once", function()
        spawnOwner("once.owner")
        spawnEffect("once.effect", "once.owner")
    end)
    group("reuse", function()
        spawnOwner("reuse.owner")
        spawnEffect("reuse.effect", "reuse.owner")
    end)
    group("adopt", function()
        spawnOwner("adopt.owner")
        spawnEffect("adopt.effect", "adopt.owner")
    end)
    group("stale", function()
        spawnOwner("stale.owner")
        spawnEffect("stale.effect", "stale.owner")
    end)
    group("already", function()
        spawnOwner("already.owner")
    end)
    group("sweep", function()
        spawnOwner("sweep.owner")
        spawnEffect("sweep.a", "sweep.owner")
        spawnEffect("sweep.b", "sweep.owner")
        spawnEffect("sweep.c", "sweep.owner")
        spawnOwner("sweep.peer")
        spawnEffect("sweep.peerA", "sweep.peer")
        spawnEffect("sweep.peerB", "sweep.peer")
    end)
    learnTokens()
    -- The submission's own tag keys, so foreign flies can carry look-alike tags.
    pcall(function()
        local owner = need("basic.owner")
        ctx.ownerKeys = keysHolding(entityOf(owner), tokenOf(owner))
        ctx.effectKeys = keysHolding(entityOf(need("basic.effect")), tokenOf(owner))
    end)
    local seenKeys = {}
    for _, list in ipairs({ ctx.ownerKeys, ctx.effectKeys }) do
        for _, key in ipairs(list) do
            if not seenKeys[key] then
                seenKeys[key] = true
                ctx.allKeys[#ctx.allKeys + 1] = key
            end
        end
    end
    group("foreign", function()
        local basicOwner = ctx.handles["basic.owner"]
        spawnForeign("foreign.plain")
        -- A fly carrying a live owner's token under the submission's own owner-tag keys.
        forge(spawnForeign("foreign.forged"), ctx.ownerKeys, basicOwner and basicOwner.token)
        forge(spawnForeign("foreign.token"), ctx.allKeys, FOREIGN_TOKEN)
    end)
    group("sibling", function()
        spawnForeign("sibling.plain")
        forge(spawnForeign("sibling.token"), ctx.allKeys, FOREIGN_TOKEN)
    end)
    group("stale", function()
        local owner = need("stale.owner")
        local keys = keysHolding(entityOf(need("stale.effect")), tokenOf(owner))
        ctx.staleKeys = #keys
        forge(spawnForeign("stale.tag"), keys, owner.token)
    end)

    run("created_effect_is_tracked", function()
        local owner = need("basic.owner")
        local effect = need("basic.effect")
        local registry = readRegistry()
        local ownerEntry = expectTracked(registry, owner, { "basic.effect" })
        equal(ownerEntry.index, owner.index, "owner Index in the registry")
        local effectEntry = effectRecord(registry, effect)
        equal(effectEntry.index, effect.index, "effect Index in the registry")
        truthy(ownerEntry.token ~= nil, "owner token missing")
        equal(ownerEntry.roomSpawnSeed, ctx.visits[1].seed, "owner room spawn seed")
        truthy(ownerEntry.roomVisit ~= nil, "owner room-visit token missing")
        return "token=" .. tostring(ownerEntry.token) .. " visit=" .. tostring(ownerEntry.roomVisit)
    end)

    run("ownership_token_matches_entity", function()
        local registry = readRegistry()
        local families = {
            { owner = "basic.owner", effects = { "basic.effect" } },
            { owner = "partial.owner", effects = { "partial.a", "partial.b", "partial.c" } },
        }
        local tokens = {}
        for _, family in ipairs(families) do
            local owner = need(family.owner)
            local ownerEntry = expectTracked(registry, owner, family.effects)
            local token = ownerEntry.token
            equal(ownerEntry.index, owner.index, family.owner .. " Index")
            truthy(type(token) == "string" or type(token) == "number",
                family.owner .. " token is not a string or number")
            truthy(tokenMentionsSeed(token, owner.seed), family.owner .. " token "
                .. tostring(token) .. " is not based on InitSeed " .. tostring(owner.seed))
            for _, other in ipairs(tokens) do
                truthy(other.token ~= token, "two owners share token " .. tostring(token))
            end
            for _, effectName in ipairs(family.effects) do
                local effect = need(effectName)
                local effectEntry = effectRecord(registry, effect)
                equal(effectEntry.index, effect.index, effectName .. " Index")
                equal(effectEntry.token, token, effectName .. " owner token in the registry")
                truthy(dataHolds(entityOf(effect), token),
                    effectName .. " GetData() does not hold its owner's exact token")
            end
            tokens[#tokens + 1] = { token = token, effects = family.effects }
        end
        -- No effect carries the other owner's token.
        for _, family in ipairs(tokens) do
            for _, other in ipairs(tokens) do
                if other ~= family then
                    for _, effectName in ipairs(family.effects) do
                        truthy(not dataHolds(entityOf(need(effectName)), other.token),
                            effectName .. " also holds another owner's token")
                    end
                end
            end
        end
        return "tokens=" .. tostring(tokens[1].token) .. "," .. tostring(tokens[2].token)
    end)

    local nilClaim = capture(function()
        local before = #readRegistry()
        expectRefused(nil, "nil owner")
        equal(#readRegistry(), before, "tracked owners after a nil-owner claim")
        return before
    end)
    local nilProbe = patchSpawn(function()
        return nil
    end, function()
        return api().SpawnTrackedOwner(FLY, 0, 0, nextPosition(), Vector(0, 0), nil)
    end)
    requireRestored(nilProbe)
    run("nil_owner_is_safe", function()
        local before = captured(nilClaim, "nil owner claim")
        truthy(nilProbe.ok, "SpawnTrackedOwner raised an error when Isaac.Spawn returned nil: "
            .. oneLine(nilProbe.value))
        if nilProbe.calls == 0 then
            -- The wrapper did not reach the patched Isaac.Spawn; drop what it spawned.
            if nilProbe.value ~= nil then
                pcall(function()
                    nilProbe.value:Remove()
                end)
            end
            return "nil_owner_refused=true spawn_nil_path=not_exercised"
        end
        equal(nilProbe.value, nil, "SpawnTrackedOwner result when Isaac.Spawn returned nil")
        equal(#readRegistry(), before, "tracked owners after Isaac.Spawn returned nil")
        expectRefused(nilProbe.value, "owner of a failed spawn")
        return "nil_owner_refused=true spawn_nil_path=exercised"
    end)
end)

wait(19)

-- Frame 21: foreign flies after twenty sweeps, then the first scripted round of removals.
step(function()
    run("foreign_entity_is_not_tracked", function()
        local registry = readRegistry()
        for _, name in ipairs({ "foreign.plain", "foreign.forged", "foreign.token" }) do
            local handle = need(name)
            expectUntracked(registry, handle)
            expectRefused(entityOf(handle), name)
        end
        equal(#readRegistry(), #registry, "tracked owners after the refused claims")
        return "forged_owner_keys=" .. #ctx.ownerKeys .. " foreign_token_keys=" .. #ctx.allKeys
    end)
    ctx.staleBefore = capture(function()
        expectUntracked(readRegistry(), need("stale.tag"))
    end)

    local bySeed = scanRoom()
    local deadOwner = act(bySeed, "dead.owner", "Kill")
    if deadOwner then
        -- The object SpawnTrackedOwner returned, now dead: it may not claim an effect.
        ctx.deadClaim = capture(function()
            local stored = entityOf(need("dead.owner"))
            if stored:Exists() and not stored:IsDead() then
                return "not_dead_at_claim"
            end
            expectRefused(stored, "dead owner")
            return "refused"
        end)
    end
    act(bySeed, "removed.owner", "Remove")
    act(bySeed, "missing.a", "Remove")
    act(bySeed, "missing.owner", "Remove")
    act(bySeed, "partial.b", "Remove")
    act(bySeed, "multi.owner", "Remove")
    act(bySeed, "two.first", "Remove")
    act(bySeed, "scoped.removed", "Remove")
    act(bySeed, "sibling.owner", "Remove")
    act(bySeed, "order.o1", "Remove")
    act(bySeed, "order.o2", "Kill")
    act(bySeed, "order.o3", "Remove")
    act(bySeed, "order.o4a", "Remove")
    -- Duplicate and out-of-order removals of one family within one frame.
    local dupEffect = act(bySeed, "dup.a", "Remove")
    local dupOwner = act(bySeed, "dup.owner", "Remove")
    if dupOwner then
        dupOwner:Remove()
    end
    if dupEffect then
        dupEffect:Remove()
    end
    -- Two cleanup triggers for one owner: death, then removal.
    local idemOwner = act(bySeed, "idem.owner", "Kill")
    if idemOwner then
        idemOwner:Remove()
    end
    act(bySeed, "once.owner", "Remove")
    act(bySeed, "reuse.owner", "Remove")
    act(bySeed, "adopt.owner", "Remove")
    act(bySeed, "stale.owner", "Remove")
end)

wait(1)

-- Frame 23: two updates after the removals the adjacent owners must all be cleaned (a sweep that
-- skips an entry it just removed leaves the next one behind); then new entities, which may take
-- over freed indexes.
step(function()
    ctx.orderEarly = capture(function()
        local registry = readRegistry()
        local bySeed = scanRoom()
        for _, name in ipairs({ "order.o1", "order.o2", "order.o3" }) do
            expectReleased(registry, need(name))
            for _, suffix in ipairs({ "a", "b" }) do
                expectGone(bySeed, need(name .. suffix))
                expectUntracked(registry, need(name .. suffix))
            end
        end
        expectTracked(registry, need("order.o4"), { "order.o4b" })
    end)
    group("reuseNext", function()
        spawnOwner("reuse.next")
    end)
    group("adoptNext", function()
        spawnForeign("adopt.next")
    end)
    group("staleNext", function()
        spawnOwner("stale.next")
    end)
    group("onceNext", function()
        spawnForeign("once.r1")
        spawnForeign("once.r2")
        spawnForeign("once.r3")
    end)
    learnTokens()
end)

wait(9)

-- Frame 33: results of the first round.
step(function()
    run("dead_owner_removes_effect", function()
        acted("dead.owner")
        expectGone(scanRoom(), need("dead.effect"))
        local claim = captured(ctx.deadClaim, "dead owner claim")
        return "effect_removed=true dead_owner_claim=" .. tostring(claim)
    end)

    run("cleanup_after_owner_death", function()
        acted("dead.owner")
        local registry = readRegistry()
        expectReleased(registry, need("dead.owner"))
        expectUntracked(registry, need("dead.effect"))
    end)

    run("removed_owner_removes_effect", function()
        acted("removed.owner")
        expectGone(scanRoom(), need("removed.effect"))
    end)

    run("cleanup_after_owner_remove", function()
        acted("removed.owner")
        local registry = readRegistry()
        expectReleased(registry, need("removed.owner"))
        expectUntracked(registry, need("removed.effect"))
    end)

    run("owner_missing_clears_reference", function()
        acted("missing.a")
        acted("missing.owner")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("missing.owner"))
        for _, name in ipairs({ "missing.a", "missing.b" }) do
            expectGone(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
    end)

    run("partial_effect_remove_clears_only_one", function()
        acted("partial.b")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectTracked(registry, need("partial.owner"), { "partial.a", "partial.c" })
        expectPresent(bySeed, need("partial.owner"))
        expectPresent(bySeed, need("partial.a"))
        expectPresent(bySeed, need("partial.c"))
        expectGone(bySeed, need("partial.b"))
    end)

    run("multiple_effects_per_owner_clean", function()
        acted("multi.owner")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("multi.owner"))
        for _, name in ipairs({ "multi.a", "multi.b", "multi.c" }) do
            expectGone(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
        return "effects_removed=3"
    end)

    run("entity_removed_callback_scoped", function()
        acted("scoped.removed")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("scoped.removed"))
        for _, name in ipairs({ "scoped.removedA", "scoped.removedB" }) do
            expectGone(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
        local kept = expectTracked(registry, need("scoped.kept"), { "scoped.keptEffect" })
        equal(kept.token, tokenOf(need("scoped.kept")), "scoped.kept token")
        expectPresent(bySeed, need("scoped.kept"))
        expectPresent(bySeed, need("scoped.keptEffect"))
    end)

    run("foreign_sibling_effect_survives_cleanup", function()
        acted("sibling.owner")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("sibling.owner"))
        expectGone(bySeed, need("sibling.effect"))
        expectUntracked(registry, need("sibling.effect"))
        for _, name in ipairs({ "sibling.plain", "sibling.token" }) do
            expectPresent(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
        return "foreign_token_keys=" .. #ctx.allKeys
    end)

    run("cleanup_order_does_not_skip_entries", function()
        for _, name in ipairs({ "order.o1", "order.o2", "order.o3", "order.o4a" }) do
            acted(name)
        end
        captured(ctx.orderEarly, "two update frames after the removals")
        local registry = readRegistry()
        local bySeed = scanRoom()
        for _, name in ipairs({ "order.o1", "order.o2", "order.o3" }) do
            expectReleased(registry, need(name))
            for _, suffix in ipairs({ "a", "b" }) do
                expectGone(bySeed, need(name .. suffix))
                expectUntracked(registry, need(name .. suffix))
            end
        end
        expectTracked(registry, need("order.o4"), { "order.o4b" })
        expectPresent(bySeed, need("order.o4"))
        expectPresent(bySeed, need("order.o4b"))
        expectGone(bySeed, need("order.o4a"))
    end)

    run("duplicate_remove_callback_is_safe", function()
        acted("dup.a")
        acted("dup.owner")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("dup.owner"))
        for _, name in ipairs({ "dup.a", "dup.b" }) do
            expectGone(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
        expectTracked(registry, need("basic.owner"), { "basic.effect" })
        expectPresent(bySeed, need("basic.effect"))
        expectUnique(registry, "registry after duplicate removals")
    end)

    run("effect_removed_once", function()
        acted("once.owner")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("once.owner"))
        expectGone(bySeed, need("once.effect"))
        expectUntracked(registry, need("once.effect"))
        for _, name in ipairs({ "once.r1", "once.r2", "once.r3" }) do
            expectPresent(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
        return "later_entities_kept=3"
    end)

    run("reused_entity_index_not_reused", function()
        acted("reuse.owner")
        local old = need("reuse.owner")
        local new = need("reuse.next")
        local registry = readRegistry()
        truthy(tokenOf(new) ~= tokenOf(old), "a new owner received the removed owner's token")
        expectReleased(registry, old)
        local newEntry = expectTracked(registry, new, {})
        local bySeed = scanRoom()
        equal(newEntry.index, expectPresent(bySeed, new).Index, "new owner current Index")
        expectGone(bySeed, need("reuse.effect"))
        expectUntracked(registry, need("reuse.effect"))
        expectIncreasingSerials(ctx.owners)
        return "index_reused=" .. tostring(new.index == old.index)
            .. " old_index=" .. tostring(old.index) .. " new_index=" .. tostring(new.index)
    end)

    run("reused_index_does_not_adopt_new_entity", function()
        acted("adopt.owner")
        local newcomer = need("adopt.next")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("adopt.owner"))
        expectGone(bySeed, need("adopt.effect"))
        expectUntracked(registry, need("adopt.effect"))
        expectPresent(bySeed, newcomer)
        expectUntracked(registry, newcomer)
        expectRefused(entityOf(newcomer), "foreign entity spawned after an owner was removed")
        local reused = newcomer.index == need("adopt.owner").index
            or newcomer.index == need("adopt.effect").index
        return "index_reused=" .. tostring(reused)
    end)

    ctx.twoFirst = capture(function()
        acted("two.first")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("two.first"))
        expectGone(bySeed, need("two.firstEffect"))
        expectUntracked(registry, need("two.firstEffect"))
        expectTracked(registry, need("two.second"), { "two.secondEffect" })
        expectPresent(bySeed, need("two.second"))
        expectPresent(bySeed, need("two.secondEffect"))
    end)
    ctx.staleFirst = capture(function()
        acted("stale.owner")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("stale.owner"))
        expectGone(bySeed, need("stale.effect"))
        local newOwner = need("stale.next")
        truthy(tokenOf(newOwner) ~= tokenOf(need("stale.owner")),
            "the new owner received the removed owner's token")
        expectTracked(registry, newOwner, {})
        expectUntracked(registry, need("stale.tag"))
        return liveOf(bySeed, need("stale.tag")) ~= nil
    end)
    sample("first round", { RELEASED_FIRST })

    local bySeed = scanRoom()
    act(bySeed, "two.second", "Kill")
    act(bySeed, "stale.next", "Remove")
end)

wait(10)

-- Frame 44: second removals, then the kills the post-update sweep must catch.
step(function()
    run("two_owners_clean_independently", function()
        captured(ctx.twoFirst, "first owner cleanup")
        acted("two.second")
        local registry = readRegistry()
        expectReleased(registry, need("two.second"))
        expectGone(scanRoom(), need("two.secondEffect"))
        expectUntracked(registry, need("two.secondEffect"))
    end)

    run("new_owner_does_not_adopt_stale_effect", function()
        captured(ctx.staleBefore, "stale-tagged fly before the owner was removed")
        local staleKept = captured(ctx.staleFirst, "stale owner cleanup")
        acted("stale.next")
        local registry = readRegistry()
        local tag = need("stale.tag")
        expectReleased(registry, need("stale.next"))
        expectUntracked(registry, tag)
        if staleKept then
            -- It carries the removed owner's token, so the new owner's cleanup leaves it alone.
            expectPresent(scanRoom(), tag)
        end
        return "stale_tag_keys=" .. tostring(ctx.staleKeys)
            .. " stale_fly_kept=" .. tostring(staleKept)
    end)
    sample("second round", { RELEASED_FIRST, RELEASED_SECOND })

    local bySeed = scanRoom()
    act(bySeed, "sweep.owner", "Kill")
    act(bySeed, "sweep.peerA", "Kill")
end)

wait(SWEEP_DEADLINE - 1)

-- Frame 47: the sweep has had its frames; then a quiet removal for the already-removed probes.
step(function()
    run("post_update_catches_missing_remove_event", function()
        acted("sweep.owner")
        acted("sweep.peerA")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("sweep.owner"))
        for _, name in ipairs({ "sweep.a", "sweep.b", "sweep.c" }) do
            expectGone(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
        expectUntracked(registry, need("sweep.peerA"))
        expectTracked(registry, need("sweep.peer"), { "sweep.peerB" })
        expectPresent(bySeed, need("sweep.peer"))
        expectPresent(bySeed, need("sweep.peerB"))
        return "update_frames_after_kills=" .. SWEEP_DEADLINE
    end)
    sample("sweep round", { RELEASED_FIRST, RELEASED_SECOND, RELEASED_THIRD })
    act(scanRoom(), "already.owner", "Remove")
end)

wait(1)

-- Frame 49: a removed owner, and an Isaac.Spawn result that no longer exists.
step(function()
    ctx.alreadyStale = capture(function()
        expectRefused(entityOf(need("already.owner")), "removed owner")
    end)
    ctx.alreadyOwnerProbe = probeRemovedSpawn(function()
        return api().SpawnTrackedOwner(FLY, 0, 0, nextPosition(), Vector(0, 0), nil)
    end)
    requireRestored(ctx.alreadyOwnerProbe)
    if ctx.alreadyOwnerProbe.goneAtReturn and ctx.alreadyOwnerProbe.returnedNil then
        ctx.alreadyOwnerProbe.immediate = capture(function()
            expectUntracked(readRegistry(), { name = "removed spawn",
                seed = ctx.alreadyOwnerProbe.removedSeed })
        end)
    end
end)

-- Frame 50: the same for an effect claimed by a live owner.
step(function()
    local before = capture(function()
        return #expectTracked(readRegistry(), need("basic.owner"), { "basic.effect" }).effects
    end)
    ctx.alreadyEffectProbe = probeRemovedSpawn(function()
        return api().SpawnTrackedEffect(entityOf(need("basic.owner")), FLY, 0, 0,
            nextPosition(), Vector(0, 0), nil)
    end)
    requireRestored(ctx.alreadyEffectProbe)
    if ctx.alreadyEffectProbe.goneAtReturn and ctx.alreadyEffectProbe.returnedNil then
        ctx.alreadyEffectProbe.immediate = capture(function()
            captured(before, "basic.owner before the probe")
            expectTracked(readRegistry(), need("basic.owner"), { "basic.effect" })
        end)
    end
end)

wait(9)

-- Frame 60: the already-removed results, then the baseline for the idempotency case.
step(function()
    run("already_removed_entity_is_safe", function()
        acted("already.owner")
        captured(ctx.alreadyStale, "removed owner claim")
        local registry = readRegistry()
        expectReleased(registry, need("already.owner"))
        local notes = {}
        for _, key in ipairs({ "alreadyOwnerProbe", "alreadyEffectProbe" }) do
            local probe = ctx[key]
            truthy(probe ~= nil, key .. " did not run")
            truthy(probe.error == nil,
                key .. ": the wrapper raised an error: " .. tostring(probe.error))
            if probe.calls == 0 then
                notes[#notes + 1] = key .. "=not_exercised"
            else
                truthy(probe.removedSeed ~= nil, key .. ": Isaac.Spawn produced no entity")
                truthy(not seedListed(registry, probe.removedSeed),
                    key .. ": the removed entity is listed in the registry")
                if probe.goneAtReturn then
                    truthy(probe.returnedNil,
                        key .. ": the wrapper returned an entity that no longer existed")
                    captured(probe.immediate, key .. " registry right after the call")
                end
                notes[#notes + 1] = key .. "=" .. (probe.goneAtReturn and "refused" or "cleaned")
            end
        end
        expectTracked(registry, need("basic.owner"), { "basic.effect" })
        return table.concat(notes, " ")
    end)
    sample("already round", { RELEASED_FIRST, RELEASED_SECOND, RELEASED_THIRD, RELEASED_FOURTH })
    ctx.idempotentBase = capture(function()
        return signature(readRegistry())
    end)
end)

wait(15)

-- Frame 76: nothing changed for fifteen more sweeps; the long-lived fixtures are intact.
step(function()
    run("repeated_cleanup_is_idempotent", function()
        acted("idem.owner")
        local base = captured(ctx.idempotentBase, "registry baseline")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("idem.owner"))
        expectGone(bySeed, need("idem.effect"))
        expectUntracked(registry, need("idem.effect"))
        equal(signature(registry), base, "registry after fifteen more sweeps")
        return "tracked_owners=" .. #registry
    end)

    sample("idle round", { RELEASED_FIRST, RELEASED_SECOND, RELEASED_THIRD, RELEASED_FOURTH })
    run("registry_entry_removed_once", function()
        truthy(#ctx.samples >= 5, "registry samples missing")
        for _, entry in ipairs(ctx.samples) do
            truthy(entry.registry ~= nil,
                entry.label .. ": Snapshot failed: " .. tostring(entry.err))
            expectUnique(entry.registry, entry.label)
            for _, name in ipairs(entry.released) do
                acted(name)
                local handle = need(name)
                truthy(not ownerRecord(entry.registry, handle),
                    entry.label .. ": " .. name .. " is tracked again")
                truthy(not tokenListed(entry.registry, tokenOf(handle)),
                    entry.label .. ": " .. name .. " token is listed again")
            end
        end
        return "samples=" .. #ctx.samples
    end)

    run("foreign_entity_untouched_on_bulk_scan", function()
        local registry = readRegistry()
        local bySeed = scanRoom()
        local names = { "foreign.plain", "foreign.forged", "foreign.token", "sibling.plain",
            "sibling.token", "adopt.next", "once.r1", "once.r2", "once.r3" }
        for _, name in ipairs(names) do
            local handle = need(name)
            local live = expectPresent(bySeed, handle)
            expectUntracked(registry, handle)
            if handle.forged then
                local data = live:GetData()
                for _, key in ipairs(handle.forged.keys) do
                    equal(data[key], handle.forged.value, name .. " tag " .. tostring(key))
                end
            end
        end
        return "foreign_flies=" .. #names .. " tag_keys=" .. #ctx.allKeys
    end)

    run("live_owner_keeps_effect", function()
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectTracked(registry, need("basic.owner"), { "basic.effect" })
        expectPresent(bySeed, need("basic.owner"))
        expectPresent(bySeed, need("basic.effect"))
        return "update_frames_alive=" .. tostring(frame - 1)
    end)

    run("ownership_token_survives_update", function()
        local owner = need("basic.owner")
        local token = tokenOf(owner)
        local registry = readRegistry()
        local ownerEntry = expectTracked(registry, owner, { "basic.effect" })
        equal(ownerEntry.token, token, "owner token after " .. tostring(frame - 1) .. " updates")
        equal(effectRecord(registry, need("basic.effect")).token, token, "effect owner token")
        local live = expectPresent(scanRoom(), need("basic.effect"))
        truthy(dataHolds(live, token), "basic.effect GetData() no longer holds its owner's token")
        return "token=" .. tostring(token)
    end)
end)

-- Frame 77: leave the room for a secret room, as the Exodus secret-room verifier does.
step(function()
    ctx.firstRoom = { owners = {}, effects = {} }
    for _, handle in pairs(ctx.handles) do
        if handle.epoch == ctx.epoch then
            if handle.isOwner then
                ctx.firstRoom.owners[#ctx.firstRoom.owners + 1] = handle
            elseif handle.ownerName ~= nil then
                ctx.firstRoom.effects[#ctx.firstRoom.effects + 1] = handle
            end
        end
    end
    beginTransition("first", "goto s.secret.1", function()
        group("t1", function()
            spawnForeign("t1.plain")
            forge(spawnForeign("t1.token"), ctx.allKeys, FOREIGN_TOKEN)
        end)
    end)
end)

await(transitionSettled, TRANSITION_BUDGET, transitionTimedOut)

-- The first room is gone: its owners and effects must be too.
step(function()
    ctx.t1 = ctx.transition
    ctx.visits[2] = { seed = roomSeed() }
    run("room_change_removes_old_owned_effect", function()
        transitionOk(ctx.t1)
        local registry = readRegistry()
        local bySeed = scanRoom()
        truthy(#ctx.firstRoom.effects > 0, "no effects were spawned in the first room")
        for _, handle in ipairs(ctx.firstRoom.effects) do
            expectUntracked(registry, handle)
            expectGone(bySeed, handle)
        end
        return "first_room_effects=" .. #ctx.firstRoom.effects
    end)

    run("ownership_token_cleared_on_room_change", function()
        expectCleanTransition(ctx.t1)
        local registry = readRegistry()
        truthy(#ctx.firstRoom.owners > 0, "no owners were spawned in the first room")
        for _, handle in ipairs(ctx.firstRoom.owners) do
            truthy(not tokenListed(registry, tokenOf(handle)),
                handle.name .. " token is still listed after the room change")
            expectUntracked(registry, handle)
        end
        equal(#registry, 0, "tracked owners right after the room change")
        return "first_room_tokens=" .. #ctx.firstRoom.owners
    end)

    run("room_change_keeps_foreign_effect", function()
        transitionOk(ctx.t1)
        local registry = readRegistry()
        local bySeed = scanRoom()
        for _, name in ipairs({ "t1.plain", "t1.token" }) do
            local handle = need(name)
            local live = expectPresent(bySeed, handle)
            expectUntracked(registry, handle)
            if handle.forged then
                local data = live:GetData()
                for _, key in ipairs(handle.forged.keys) do
                    equal(data[key], FOREIGN_TOKEN, name .. " tag " .. tostring(key))
                end
            end
        end
        return "spawned_in_new_room_callback=2"
    end)

    group("x", function()
        spawnOwner("x.removed")
        spawnEffect("x.removedA", "x.removed")
        spawnEffect("x.removedB", "x.removed")
        spawnOwner("x.kept")
        spawnEffect("x.keptEffect", "x.kept")
    end)
    group("xForeign", function()
        spawnForeign("x.r1")
        spawnForeign("x.r2")
        spawnForeign("x.r3")
    end)
    learnTokens()
end)

step(function()
    act(scanRoom(), "x.removed", "Remove")
end)

wait(SETTLE)

-- Cleanup in the second room, then a new floor: the Exodus main verifier's stage command.
step(function()
    run("cleanup_after_transition_then_remove", function()
        transitionOk(ctx.t1)
        acted("x.removed")
        local registry = readRegistry()
        local bySeed = scanRoom()
        expectReleased(registry, need("x.removed"))
        for _, name in ipairs({ "x.removedA", "x.removedB" }) do
            expectGone(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
        local kept = expectTracked(registry, need("x.kept"), { "x.keptEffect" })
        expectPresent(bySeed, need("x.kept"))
        expectPresent(bySeed, need("x.keptEffect"))
        equal(kept.roomSpawnSeed, ctx.visits[2].seed, "x.kept room spawn seed")
    end)

    run("no_double_free_on_transition", function()
        transitionOk(ctx.t1)
        local registry = readRegistry()
        local bySeed = scanRoom()
        for _, name in ipairs({ "t1.plain", "t1.token", "x.r1", "x.r2", "x.r3" }) do
            expectPresent(bySeed, need(name))
            expectUntracked(registry, need(name))
        end
        expectUnique(registry, "second-room registry")
        equal(#registry, 1, "tracked owners in the second room")
        for _, handle in ipairs(ctx.firstRoom.owners) do
            truthy(not tokenListed(registry, tokenOf(handle)),
                handle.name .. " token is listed in the second room")
        end
        return "new_room_flies_kept=5"
    end)

    beginTransition("second", "stage 1", function()
        group("t2", function()
            spawnForeign("t2.plain")
        end)
    end)
end)

await(transitionSettled, TRANSITION_BUDGET, transitionTimedOut)

-- A fresh starting room: nothing from earlier visits may come back.
step(function()
    ctx.t2 = ctx.transition
    ctx.visits[3] = { seed = roomSeed() }
    ctx.reentryBefore = capture(function()
        transitionOk(ctx.t2)
        local registry = readRegistry()
        equal(#registry, 0, "tracked owners right after entering the new floor")
        for _, handle in ipairs(ctx.owners) do
            truthy(not tokenListed(registry, tokenOf(handle)),
                handle.name .. " token is listed after re-entry")
            expectUntracked(registry, handle)
        end
    end)
    group("s2", function()
        spawnOwner("s2.owner")
        spawnEffect("s2.effect", "s2.owner")
    end)
    learnTokens()

    run("reentry_does_not_restore_old_owner", function()
        expectCleanTransition(ctx.t2)
        captured(ctx.reentryBefore, "registry after re-entry")
        local owner = need("s2.owner")
        local token = tokenOf(owner)
        for _, handle in ipairs(ctx.owners) do
            if handle ~= owner and handle.token ~= nil then
                truthy(handle.token ~= token, "the new room reissued token " .. tostring(token))
            end
        end
        -- The run's serial keeps growing through both room changes.
        expectIncreasingSerials(ctx.owners)
        local registry = readRegistry()
        expectTracked(registry, owner, { "s2.effect" })
        equal(#registry, 1, "tracked owners after the new owner spawned")
        local plain = need("t2.plain")
        expectUntracked(registry, plain)
        expectRefused(expectPresent(scanRoom(), plain), "foreign fly of the re-entered room")
        return "same_spawn_seed_as_first_room="
            .. tostring(ctx.visits[3].seed == ctx.visits[1].seed)
    end)
end)

wait(SETTLE)

-- Visits never alias, even when the new floor's starting room repeats the first spawn seed.
step(function()
    run("room_identity_prevents_cross_room_cleanup", function()
        transitionOk(ctx.t1)
        transitionOk(ctx.t2)
        local registry = readRegistry()
        local bySeed = scanRoom()
        local owner = need("s2.owner")
        local ownerEntry = expectTracked(registry, owner, { "s2.effect" })
        expectPresent(bySeed, owner)
        expectPresent(bySeed, need("s2.effect"))
        expectReleased(registry, need("x.kept"))
        equal(ownerEntry.roomVisit, owner.roomVisit, "s2.owner room-visit token after sweeps")
        local visits = { need("basic.owner"), need("x.kept"), owner }
        for position, handle in ipairs(visits) do
            truthy(handle.roomVisit ~= nil, handle.name .. " has no room-visit token")
            equal(handle.roomSpawnSeed, ctx.visits[position].seed,
                handle.name .. " room spawn seed")
            if position > 1 then
                local before = visits[position - 1].roomVisit
                if type(before) == "number" and type(handle.roomVisit) == "number" then
                    truthy(handle.roomVisit > before, "room-visit token did not increase: "
                        .. tostring(before) .. " -> " .. tostring(handle.roomVisit))
                else
                    truthy(handle.roomVisit ~= before, "room-visit token repeated: "
                        .. tostring(before))
                end
            end
        end
        -- Every owner carries the visit and spawn seed of the room it was spawned in.
        for _, handle in ipairs(ctx.owners) do
            local reference = handle.epoch == visits[1].epoch and visits[1]
                or handle.epoch == visits[2].epoch and visits[2]
                or handle.epoch == owner.epoch and owner or nil
            if reference ~= nil then
                equal(handle.roomVisit, reference.roomVisit, handle.name .. " room-visit token")
                equal(handle.roomSpawnSeed, reference.roomSpawnSeed,
                    handle.name .. " room spawn seed")
            end
        end
        return "same_spawn_seed_as_first_room="
            .. tostring(ctx.visits[3].seed == ctx.visits[1].seed)
            .. " visits=" .. tostring(visits[1].roomVisit) .. "," .. tostring(visits[2].roomVisit)
            .. "," .. tostring(owner.roomVisit)
    end)

    local bySeed = scanRoom()
    for _, handle in ipairs(ctx.owners) do
        act(bySeed, handle.name, "Remove")
    end
end)

wait(SETTLE)

step(function()
    run("registry_empty_after_all_owners_removed", function()
        local registry = readRegistry()
        equal(#registry, 0, "tracked owners after every owner was removed")
        expectGone(scanRoom(), need("s2.effect"))
        return "tracked_owners=0"
    end)
end)

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
    if started then
        return
    end
    started = true
    log("[GCB_RUNTIME] suite_started")
end)

suite:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, function()
    if not started or finished then
        return
    end
    ctx.epoch = ctx.epoch + 1
    local transition = ctx.transition
    if transition ~= nil and transition.armed and not transition.seen then
        transition.seen = true
        transition.seenFrame = frame
        transition.atEnter = capture(readRegistry)
        local ok, err = pcall(transition.onEnter)
        if not ok then
            transition.enterError = oneLine(err)
        end
    end
end)

suite:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if not started or finished then
        return
    end
    frame = frame + 1
    pcall(pacifyAll)
    local ok, err = pcall(tick)
    if not ok then
        abort(err)
    end
end)
