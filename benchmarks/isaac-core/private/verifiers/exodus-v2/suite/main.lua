local suite = RegisterMod("GameCodeBench Exodus Verifier", 1)
local game = Game()

local state = "idle"
local enteredAt = 0
local ritualEnemy = nil
local ritualHits = 0
local gridTear = nil
local gridBounceWall = nil
local gridBounceOutward = nil
local gridBounceTrace = ""
local gridCadenceTears = {}
local gridCadenceDirections = {}
local glassesEnemy = nil
local beehiveTear = nil
local beehiveVelocity = nil
local dejaTear = nil
local lovelyFly = nil
local lovelyDecoy = nil
local lovelyEnemy = nil
local baseballTear = nil
local ironLungGas = nil
local headcase = nil
local headcaseLob = nil
local leashHeld = nil
local algizShot = nil
local algizControl = nil
local useCardArgs = nil
local scissorsCreep = 0
local mantleGaper = nil
local paperGaper = nil
local aliasBall = nil
local aliasLantern = nil
local aliasBallDeath = nil
local aliasLanternDeath = nil
local matTrace = ""
local hurdleGaper = nil
local lanternPressArmed = false
local lanternRealInput = nil
local lanternUses = 0
local lanternUseFrame = -1
local lanternUseCharges = {}
local runBaseline = nil
local runBeforeRestart = nil
local passed = 0
local failed = 0
local recorded = {}
local stopped = false

local ids = {
    forbiddenFruit = Isaac.GetItemIdByName("The Forbidden Fruit"),
    tragicMushroom = Isaac.GetItemIdByName("Tragic Mushroom"),
    ritualCandle = Isaac.GetItemIdByName("Ritual Candle"),
    cursedMetronome = Isaac.GetItemIdByName("Cursed Metronome"),
    sundial = Isaac.GetItemIdByName("Sundial"),
    astroBaby = Isaac.GetItemIdByName("Astro Baby"),
    lilRune = Isaac.GetItemIdByName("Lil Rune"),
    beehive = Isaac.GetItemIdByName("Beehive"),
    dejaVu = Isaac.GetItemIdByName("Deja Vu"),
    mutantClover = Isaac.GetItemIdByName("Mutant Clover"),
    anamnesis = Isaac.GetItemIdByName("Anamnesis"),
    baseballMitt = Isaac.GetItemIdByName("Baseball Mitt"),
    ominousLantern = Isaac.GetItemIdByName("Ominous Lantern"),
    hurdleHeels = Isaac.GetItemIdByName("Hurdle Heels"),
    gridWorm = Isaac.GetTrinketIdByName("Grid Worm"),
    brokenGlasses = Isaac.GetTrinketIdByName("Broken Glasses"),
    candleVariant = Isaac.GetEntityVariantByName("Candle"),
    sunVariant = Isaac.GetEntityVariantByName("Sundial Sun"),
    shadowVariant = Isaac.GetEntityVariantByName("Sundial Shadow"),
    astroVariant = Isaac.GetEntityVariantByName("Astro Baby"),
    runeVariant = Isaac.GetEntityVariantByName("Lil Rune"),
    lovelyFlyType = Isaac.GetEntityTypeByName("Lovely Fly"),
    lovelyFlyVariant = Isaac.GetEntityVariantByName("Lovely Fly"),
    baseballVariant = Isaac.GetEntityVariantByName("Baseball"),
    baseballHitType = Isaac.GetEntityTypeByName("Baseball Hit"),
    baseballHitVariant = Isaac.GetEntityVariantByName("Baseball Hit"),
    ironLungGasType = Isaac.GetEntityTypeByName("Iron Lung Gas"),
    ironLungGasVariant = Isaac.GetEntityVariantByName("Iron Lung Gas"),
    headcaseType = Isaac.GetEntityTypeByName("Headcase"),
    headcaseVariant = Isaac.GetEntityVariantByName("Headcase"),
    hungryHippo = Isaac.GetItemIdByName("Hungry Hippo"),
    roboBaby = Isaac.GetItemIdByName("Robo-Baby 3.6.0"),
    hippoVariant = Isaac.GetEntityVariantByName("Hungry Hippo"),
    roboVariant = Isaac.GetEntityVariantByName("Robobaby 3.6.0"),
    bigScissors = Isaac.GetItemIdByName("Big Scissors"),
    unholyMantle = Isaac.GetItemIdByName("Unholy Mantle"),
    birdbath = Isaac.GetItemIdByName("Birdbath"),
    birdbathType = Isaac.GetEntityTypeByName("Birdbath"),
    birdbathVariant = Isaac.GetEntityVariantByName("Birdbath"),
    paperCut = Isaac.GetItemIdByName("Paper Cut"),
    welcomeMat = Isaac.GetItemIdByName("Welcome Mat"),
    welcomeMatType = Isaac.GetEntityTypeByName("Welcome Mat"),
    lanternTearVariant = Isaac.GetEntityVariantByName("Lantern Tear"),
    lanternFireVariant = Isaac.GetEntityVariantByName("Lantern Fire"),
}

local function debug(prefix, message)
    Isaac.DebugString(prefix .. " " .. message)
end

local function enter(nextState)
    state = nextState
    enteredAt = game:GetFrameCount()
end

local function age()
    return game:GetFrameCount() - enteredAt
end

local function detailNumber(value)
    if value == nil then return "nil" end
    return tostring(value)
end

local function record(name, ok, detail)
    if recorded[name] then return end
    recorded[name] = true
    if ok then
        passed = passed + 1
        debug("[GCB_CASE]", "PASS " .. name .. " " .. detail)
    else
        failed = failed + 1
        debug("[GCB_CASE]", "FAIL " .. name .. " " .. detail)
    end
end

local function clearPlayerHealth(player, maxHearts, hearts)
    player:AddSoulHearts(-player:GetSoulHearts())
    player:AddMaxHearts(maxHearts - player:GetMaxHearts(), false)
    player:AddHearts(-player:GetHearts())
    player:AddHearts(hearts)
end

local function removeCollectible(player, itemId)
    for _ = 1, 8 do
        if not player:HasCollectible(itemId) then break end
        player:RemoveCollectible(itemId)
    end
end

local function removeTrinket(player, trinketId)
    for _ = 1, 4 do
        if not player:HasTrinket(trinketId) then break end
        player:TryRemoveTrinket(trinketId)
    end
end

local function countFamiliarVariants()
    local counts = { candle = 0, sun = 0, shadow = 0, astro = 0, rune = 0 }
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == EntityType.ENTITY_FAMILIAR then
            if entity.Variant == ids.candleVariant then counts.candle = counts.candle + 1 end
            if entity.Variant == ids.sunVariant then counts.sun = counts.sun + 1 end
            if entity.Variant == ids.shadowVariant then counts.shadow = counts.shadow + 1 end
            if entity.Variant == ids.astroVariant then counts.astro = counts.astro + 1 end
            if entity.Variant == ids.runeVariant then counts.rune = counts.rune + 1 end
        end
    end
    return counts
end

local function familiarCountDetail(counts)
    return "candle=" .. counts.candle .. " sun=" .. counts.sun
        .. " shadow=" .. counts.shadow .. " astro=" .. counts.astro
        .. " rune=" .. counts.rune
end

local function removeVerifierFamiliars()
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == EntityType.ENTITY_FAMILIAR
            and (entity.Variant == ids.candleVariant
                or entity.Variant == ids.sunVariant
                or entity.Variant == ids.shadowVariant
                or entity.Variant == ids.astroVariant
                or entity.Variant == ids.runeVariant) then
            entity:Remove()
        end
    end
end

local function familiarsOfVariant(variant)
    local found = {}
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == EntityType.ENTITY_FAMILIAR and entity.Variant == variant then
            found[#found + 1] = entity:ToFamiliar()
        end
    end
    return found
end

local function removeFamiliarVariant(variant)
    for _, familiar in ipairs(familiarsOfVariant(variant)) do familiar:Remove() end
end

local function evaluateFamiliars(player)
    player:AddCacheFlags(CacheFlag.CACHE_FAMILIARS)
    player:EvaluateItems()
end

local function orbitalSnapshot(player)
    local snapshot = {}
    for _, entry in ipairs({
        { "sun", ids.sunVariant },
        { "shadow", ids.shadowVariant },
        { "hippo", ids.hippoVariant },
        { "robo", ids.roboVariant },
    }) do
        local list = familiarsOfVariant(entry[2])
        local familiar = list[1]
        if familiar then
            snapshot[entry[1]] = {
                count = #list,
                x = familiar.OrbitDistance.X,
                y = familiar.OrbitDistance.Y,
                distance = familiar.Position:Distance(player.Position),
                state = familiar.State,
            }
        else
            snapshot[entry[1]] = { count = 0 }
        end
    end
    return snapshot
end

local function orbitalDetail(snapshot)
    local parts = {}
    for _, name in ipairs({ "sun", "shadow", "hippo", "robo" }) do
        local item = snapshot[name] or { count = 0 }
        parts[#parts + 1] = name .. "{n=" .. item.count
            .. " od=" .. detailNumber(item.x) .. "," .. detailNumber(item.y)
            .. " d=" .. detailNumber(item.distance) .. " st=" .. detailNumber(item.state) .. "}"
    end
    return table.concat(parts, " ")
end

local function countEntitiesByType(entityType)
    local count = 0
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == entityType then count = count + 1 end
    end
    return count
end

local function nearestEntity(entityType, variant, origin)
    local best, bestDistance = nil, math.huge
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == entityType and entity.Variant == variant then
            local distance = entity.Position:Distance(origin)
            if distance < bestDistance then
                best = entity
                bestDistance = distance
            end
        end
    end
    return best, bestDistance
end

local function aliasMoveAway(player)
    local center = game:GetRoom():GetCenterPos()
    local entry = player:GetData().gcbAliasEntry or center
    player.Position = center + Vector(entry.X < center.X and 200 or -200, 0)
    player.Velocity = Vector(0, 0)
end

local function removeEntitiesByType(entityType)
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == entityType then entity:Remove() end
    end
end

local function removeEntitiesByTypeVariant(entityType, variant)
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == entityType and entity.Variant == variant then entity:Remove() end
    end
end

local function countEntitiesByTypeVariant(entityType, variant)
    local count = 0
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == entityType and entity.Variant == variant then count = count + 1 end
    end
    return count
end

local function removeActiveEnemies()
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity:IsActiveEnemy(false) then entity:Remove() end
    end
end

local function bookOfSecretsEffectCount()
    local level = game:GetLevel()
    local count = 0
    for _, stateFlag in ipairs({
        LevelStateFlag.STATE_COMPASS_EFFECT,
        LevelStateFlag.STATE_MAP_EFFECT,
        LevelStateFlag.STATE_BLUE_MAP_EFFECT,
    }) do
        if level:GetStateFlag(stateFlag) then count = count + 1 end
    end
    return count
end

local function statSnapshot(player)
    return {
        damage = player.Damage,
        delay = player.MaxFireDelay,
        speed = player.MoveSpeed,
        shot = player.ShotSpeed,
        luck = player.Luck,
        height = player.TearHeight,
    }
end

local function statsDiffer(left, right)
    return math.abs(left.damage - right.damage) > 0.01
        or math.abs(left.delay - right.delay) > 0.01
        or math.abs(left.speed - right.speed) > 0.01
        or math.abs(left.shot - right.shot) > 0.01
        or math.abs(left.luck - right.luck) > 0.01
        or math.abs(left.height - right.height) > 0.01
end

local function statDetail(stats)
    if stats == nil then return "nil" end
    return "damage=" .. detailNumber(stats.damage)
        .. " delay=" .. detailNumber(stats.delay)
        .. " speed=" .. detailNumber(stats.speed)
        .. " shot=" .. detailNumber(stats.shot)
        .. " luck=" .. detailNumber(stats.luck)
        .. " height=" .. detailNumber(stats.height)
end

local function hurdleCleanup(player)
    if hurdleGaper and hurdleGaper:Exists() then hurdleGaper:Remove() end
    hurdleGaper = nil
    removeCollectible(player, ids.hurdleHeels)
    player:AddCacheFlags(CacheFlag.CACHE_SPEED)
    player:EvaluateItems()
    clearPlayerHealth(player, 6, 6)
end

local function holdShootLeft(on)
    if on and lanternRealInput == nil then
        local real = Input
        lanternRealInput = real
        Input = setmetatable({
            IsActionPressed = function(action, controllerIndex)
                if action == ButtonAction.ACTION_SHOOTLEFT then return true end
                return real.IsActionPressed(action, controllerIndex)
            end,
        }, { __index = function(_, key) return real[key] end })
    elseif not on and lanternRealInput ~= nil then
        Input = lanternRealInput
        lanternRealInput = nil
    end
end

local function lanternCleanup(player)
    lanternPressArmed = false
    holdShootLeft(false)
    removeCollectible(player, ids.ominousLantern)
    removeEntitiesByTypeVariant(EntityType.ENTITY_TEAR, ids.lanternTearVariant)
    removeEntitiesByTypeVariant(EntityType.ENTITY_EFFECT, ids.lanternFireVariant)
end

local function finish()
    if stopped then return end
    stopped = true
    local total = passed + failed
    debug("[GCB_SUMMARY]", "passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed) .. " total=" .. tostring(total))
    enter("quit")
end

local function fatal(message)
    if stopped then return end
    debug("[GCB_FATAL]", tostring(message))
    finish()
end

function suite:onGameStarted(isContinued)
    if state == "run_restart_requested" then
        -- second run of this process: do not re-run the chain or touch the stat caches
        debug("[GCB_RUNTIME]", "suite_restarted continued=" .. tostring(isContinued))
        enter("run_restart_check")
        return
    end
    local ok, err = pcall(function()
        local player = Isaac.GetPlayer(0)
        for _, itemId in ipairs({
            ids.forbiddenFruit,
            ids.tragicMushroom,
            ids.ritualCandle,
            ids.cursedMetronome,
            ids.sundial,
            ids.astroBaby,
            ids.lilRune,
            ids.beehive,
            ids.dejaVu,
            ids.mutantClover,
            ids.anamnesis,
            ids.baseballMitt,
            ids.ominousLantern,
            ids.hurdleHeels,
            ids.hungryHippo,
            ids.roboBaby,
            ids.bigScissors,
            ids.unholyMantle,
            ids.birdbath,
            ids.paperCut,
            ids.welcomeMat,
        }) do
            if itemId <= 0 then error("missing collectible id") end
            removeCollectible(player, itemId)
        end
        for _, trinketId in ipairs({ ids.gridWorm, ids.brokenGlasses }) do
            if trinketId <= 0 then error("missing trinket id") end
            removeTrinket(player, trinketId)
        end
        for _, familiarVariant in ipairs({
            ids.candleVariant,
            ids.sunVariant,
            ids.shadowVariant,
            ids.astroVariant,
            ids.runeVariant,
            ids.hippoVariant,
            ids.roboVariant,
        }) do
            if familiarVariant <= 0 then error("missing familiar variant") end
        end
        if ids.lovelyFlyType <= 0 or ids.lovelyFlyVariant < 0 then
            error("missing Lovely Fly entity")
        end
        for _, entityId in ipairs({
            ids.baseballVariant,
            ids.baseballHitType,
            ids.baseballHitVariant,
            ids.ironLungGasType,
            ids.ironLungGasVariant,
            ids.headcaseType,
            ids.birdbathType,
            ids.lanternTearVariant,
            ids.lanternFireVariant,
            ids.welcomeMatType,
        }) do
            if entityId <= 0 then error("missing lifecycle regression entity id") end
        end
        if ids.headcaseVariant < 0 then
            error("missing lifecycle regression entity variant")
        end
        player:AddCacheFlags(CacheFlag.CACHE_ALL)
        player:EvaluateItems()
        runBaseline = statSnapshot(player)
        debug("[GCB_RUNTIME]", "suite_started continued=" .. tostring(isContinued))
        record("runtime_sentinel_main", true,
            "frame=" .. game:GetFrameCount() .. " player_type=" .. player:GetPlayerType())
        enter("forbidden_setup")
    end)
    if not ok then fatal(err) end
end

function suite:onEntityDamage(target)
    if ritualEnemy and target.InitSeed == ritualEnemy.InitSeed then
        ritualHits = ritualHits + 1
    end
end

local function runStep()
    local player = Isaac.GetPlayer(0)

    if state == "forbidden_setup" and age() >= 5 then
        clearPlayerHealth(player, 12, 12)
        local baseline = player.Damage
        player:AddCollectible(ids.forbiddenFruit, 0, false)
        player:UseActiveItem(ids.forbiddenFruit, false, false, false, false)
        player:GetData().gcbForbiddenBaseline = baseline
        enter("forbidden_remove")
    elseif state == "forbidden_remove" and age() >= 3 then
        local baseline = player:GetData().gcbForbiddenBaseline
        local withItem = player.Damage
        player:RemoveCollectible(ids.forbiddenFruit)
        player:AddCacheFlags(CacheFlag.CACHE_DAMAGE)
        player:EvaluateItems()
        local after = player.Damage
        record("forbidden_fruit", withItem > baseline + 0.1 and math.abs(after - withItem) < 0.05,
            "baseline=" .. detailNumber(baseline) .. " with=" .. detailNumber(withItem)
                .. " after=" .. detailNumber(after))
        enter("tragic_setup")
    elseif state == "tragic_setup" and age() >= 3 then
        clearPlayerHealth(player, 6, 1)
        player:AddCollectible(ids.tragicMushroom, 0, false)
        player:UseActiveItem(ids.tragicMushroom, false, false, false, false)
        enter("tragic_check")
    elseif state == "tragic_check" and age() >= 3 then
        local maxHearts = player:GetMaxHearts()
        local redHearts = player:GetHearts()
        local soulHearts = player:GetSoulHearts()
        record("tragic_mushroom",
            maxHearts == 2 and redHearts == 2 and soulHearts == 0 and not player:IsDead(),
            "max=" .. maxHearts .. " red=" .. redHearts .. " soul=" .. soulHearts)
        player:GetData().gcbTragicFirstDamage = player.Damage
        player:GetData().gcbTragicFirstSpeed = player.MoveSpeed
        player:GetData().gcbTragicFirstHeight = player.TearHeight
        removeCollectible(player, ids.tragicMushroom)
        enter("tragic_last_container")
    elseif state == "tragic_last_container" and age() >= 3 then
        clearPlayerHealth(player, 2, 1)
        player:AddCollectible(ids.tragicMushroom, 0, false)
        player:UseActiveItem(ids.tragicMushroom, false, false, false, false)
        local maxHearts = player:GetMaxHearts()
        local redHearts = player:GetHearts()
        local soulHearts = player:GetSoulHearts()
        record("tragic_mushroom_last_container",
            maxHearts == 2 and redHearts == 2 and soulHearts == 0 and not player:IsDead(),
            "max=" .. maxHearts .. " red=" .. redHearts .. " soul=" .. soulHearts
                .. " dead=" .. tostring(player:IsDead()))
        removeCollectible(player, ids.tragicMushroom)
        enter("tragic_repeat_check")
    elseif state == "tragic_repeat_check" and age() >= 3 then
        local firstDamage = player:GetData().gcbTragicFirstDamage or player.Damage
        local firstSpeed = player:GetData().gcbTragicFirstSpeed or player.MoveSpeed
        local firstHeight = player:GetData().gcbTragicFirstHeight or player.TearHeight
        record("tragic_mushroom_repeat",
            player.Damage > firstDamage + 0.05
                and player.MoveSpeed > firstSpeed + 0.05
                and player.TearHeight < firstHeight - 0.05,
            "first_damage=" .. detailNumber(firstDamage)
                .. " second_damage=" .. detailNumber(player.Damage)
                .. " first_speed=" .. detailNumber(firstSpeed)
                .. " second_speed=" .. detailNumber(player.MoveSpeed)
                .. " first_height=" .. detailNumber(firstHeight)
                .. " second_height=" .. detailNumber(player.TearHeight))
        player:GetData().gcbTragicSecondDamage = player.Damage
        player:GetData().gcbTragicSecondSpeed = player.MoveSpeed
        player:GetData().gcbTragicSecondHeight = player.TearHeight
        player:AddCollectible(ids.tragicMushroom, 0, false)
        player:UseActiveItem(ids.tragicMushroom, false, false, false, false)
        enter("tragic_diminishing_check")
    elseif state == "tragic_diminishing_check" and age() >= 3 then
        local firstDamage = player:GetData().gcbTragicFirstDamage or player.Damage
        local firstSpeed = player:GetData().gcbTragicFirstSpeed or player.MoveSpeed
        local firstHeight = player:GetData().gcbTragicFirstHeight or player.TearHeight
        local secondDamage = player:GetData().gcbTragicSecondDamage or player.Damage
        local secondSpeed = player:GetData().gcbTragicSecondSpeed or player.MoveSpeed
        local secondHeight = player:GetData().gcbTragicSecondHeight or player.TearHeight
        local secondDamageGain = secondDamage - firstDamage
        local thirdDamageGain = player.Damage - secondDamage
        local secondSpeedGain = secondSpeed - firstSpeed
        local thirdSpeedGain = player.MoveSpeed - secondSpeed
        local secondRangeGain = firstHeight - secondHeight
        local thirdRangeGain = secondHeight - player.TearHeight
        record("tragic_mushroom_diminishing",
            thirdDamageGain > 0.05 and thirdDamageGain < secondDamageGain
                and thirdSpeedGain > 0.05 and thirdSpeedGain < secondSpeedGain
                and thirdRangeGain > 0.05 and thirdRangeGain < secondRangeGain,
            "damage_gains=" .. detailNumber(secondDamageGain) .. ","
                .. detailNumber(thirdDamageGain)
                .. " speed_gains=" .. detailNumber(secondSpeedGain) .. ","
                .. detailNumber(thirdSpeedGain)
                .. " range_gains=" .. detailNumber(secondRangeGain) .. ","
                .. detailNumber(thirdRangeGain))
        removeCollectible(player, ids.tragicMushroom)
        enter("mutant_setup")
    elseif state == "mutant_setup" and age() >= 3 then
        removeCollectible(player, ids.mutantClover)
        player:AddCacheFlags(CacheFlag.CACHE_LUCK)
        player:EvaluateItems()
        player:GetData().gcbMutantBaseline = player.Luck
        player:AddCollectible(ids.mutantClover, 0, false)
        player:UseActiveItem(ids.mutantClover, false, false, false, false)
        enter("mutant_second")
    elseif state == "mutant_second" and age() >= 2 then
        player:GetData().gcbMutantFirst = player.Luck
        player:UseActiveItem(ids.mutantClover, false, false, false, false)
        enter("mutant_check")
    elseif state == "mutant_check" and age() >= 2 then
        local baseline = player:GetData().gcbMutantBaseline or player.Luck
        local first = player:GetData().gcbMutantFirst or player.Luck
        local second = player.Luck
        record("mutant_clover_stack",
            math.abs((first - baseline) - 10) < 0.05
                and math.abs((second - baseline) - 20) < 0.05,
            "baseline=" .. detailNumber(baseline)
                .. " first=" .. detailNumber(first)
                .. " second=" .. detailNumber(second))
        enter("anamnesis_setup")
    elseif state == "anamnesis_setup" and age() >= 3 then
        removeCollectible(player, ids.anamnesis)
        player:AddCollectible(ids.anamnesis, 6, false)
        player:SetActiveCharge(6)
        enter("anamnesis_check")
    elseif state == "anamnesis_check" and age() >= 4 then
        record("anamnesis_charge", player:GetActiveCharge() == 0,
            "fresh_charge=" .. detailNumber(player:GetActiveCharge()))
        player:SetActiveCharge(3)
        enter("anamnesis_store")
    elseif state == "anamnesis_store" and age() >= 3 then
        player:GetData().gcbAnamnesisStoredCharge = player:GetActiveCharge()
        removeCollectible(player, ids.anamnesis)
        player:AddCollectible(CollectibleType.COLLECTIBLE_BOOK_OF_BELIAL, 6, false)
        player:SetActiveCharge(6)
        enter("anamnesis_foreign")
    elseif state == "anamnesis_foreign" and age() >= 3 then
        removeCollectible(player, CollectibleType.COLLECTIBLE_BOOK_OF_BELIAL)
        player:AddCollectible(ids.anamnesis, 0, false)
        player:SetActiveCharge(0)
        enter("anamnesis_restore")
    elseif state == "anamnesis_restore" and age() >= 4 then
        local stored = player:GetData().gcbAnamnesisStoredCharge
        record("anamnesis_charge_persistence",
            stored == 3 and player:GetActiveCharge() == 3,
            "stored_before_swap=" .. detailNumber(stored)
                .. " restored=" .. detailNumber(player:GetActiveCharge()))
        removeCollectible(player, ids.anamnesis)
        enter("baseball_setup")
    elseif state == "baseball_setup" and age() >= 3 then
        removeEntitiesByType(EntityType.ENTITY_PROJECTILE)
        removeEntitiesByTypeVariant(ids.baseballHitType, ids.baseballHitVariant)
        removeCollectible(player, ids.baseballMitt)
        player:AddCollectible(ids.baseballMitt, 0, false)
        player:UseActiveItem(ids.baseballMitt, false, false, false, false)
        Isaac.Spawn(EntityType.ENTITY_PROJECTILE, 0, 0,
            player.Position, Vector(0, 0), player)
        enter("baseball_capture")
    elseif state == "baseball_capture" and age() >= 4 then
        player:GetData().gcbBaseballCaptured = countEntitiesByTypeVariant(
            EntityType.ENTITY_PROJECTILE, 0) == 0
        enter("baseball_release")
    elseif state == "baseball_release" then
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_TEAR and entity.Variant == ids.baseballVariant then
                baseballTear = entity:ToTear()
                break
            end
        end
        if baseballTear and baseballTear:Exists() then
            baseballTear.Velocity = Vector(0, 0)
            baseballTear.FallingSpeed = 0
            baseballTear.FallingAcceleration = 0
            enter("baseball_kill_arm")
        elseif age() >= 145 then
            record("baseball_mitt_delayed_hit", false,
                "captured=" .. tostring(player:GetData().gcbBaseballCaptured)
                    .. " released_ball=false")
            removeCollectible(player, ids.baseballMitt)
            enter("iron_gas_setup")
        end
    elseif state == "baseball_kill_arm" and age() >= 10 then
        record("baseball_mitt_delayed_hit", false,
            "captured=" .. tostring(player:GetData().gcbBaseballCaptured)
                .. " tear_update_seen=false")
        removeCollectible(player, ids.baseballMitt)
        enter("iron_gas_setup")
    elseif state == "baseball_hit_check" and age() >= 2 then
        local hitCount = countEntitiesByTypeVariant(ids.baseballHitType, ids.baseballHitVariant)
        record("baseball_mitt_delayed_hit",
            player:GetData().gcbBaseballCaptured == true and hitCount >= 1,
            "captured=" .. tostring(player:GetData().gcbBaseballCaptured)
                .. " hit_effects=" .. hitCount)
        removeCollectible(player, ids.baseballMitt)
        removeEntitiesByTypeVariant(ids.baseballHitType, ids.baseballHitVariant)
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        baseballTear = nil
        enter("iron_gas_setup")
    elseif state == "iron_gas_setup" and age() >= 3 then
        removeActiveEnemies()
        removeEntitiesByTypeVariant(ids.ironLungGasType, ids.ironLungGasVariant)
        ironLungGas = Isaac.Spawn(ids.ironLungGasType, ids.ironLungGasVariant, 0,
            player.Position + Vector(90, 0), Vector(0, 0), nil)
        ironLungGas:GetSprite():Play("Pyroclastic Flow", true)
        enter("iron_gas_check")
    elseif state == "iron_gas_check" and age() >= 240 then
        local exists = ironLungGas and ironLungGas:Exists()
        record("iron_lung_orphan_gas", not exists,
            "exists=" .. tostring(exists))
        if exists then ironLungGas:Remove() end
        ironLungGas = nil
        enter("headcase_setup")
    elseif state == "headcase_setup" and age() >= 3 then
        removeActiveEnemies()
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        clearPlayerHealth(player, 12, 12)
        headcase = Isaac.Spawn(ids.headcaseType, ids.headcaseVariant, 0,
            player.Position + Vector(80, 0), Vector(0, 0), nil):ToNPC()
        headcase.State = 2
        headcase.EntityCollisionClass = EntityCollisionClass.ENTCOLL_NONE
        headcase:GetSprite():Play("Stomp", true)
        enter("headcase_wait")
    elseif state == "headcase_wait" then
        if age() >= 160 then
            record("headcase_orphan_lob", false, "lob_spawned=false")
            if headcase and headcase:Exists() then headcase:Remove() end
            enter("ritual_setup")
        end
    elseif state == "headcase_check" and age() >= 3 then
        local before = player:GetData().gcbHeadcaseHealth or player:GetHearts()
        local after = player:GetHearts()
        record("headcase_orphan_lob", after < before,
            "before_red=" .. detailNumber(before)
                .. " after_red=" .. detailNumber(after)
                .. " lob_exists=" .. tostring(headcaseLob and headcaseLob:Exists()))
        if headcaseLob and headcaseLob:Exists() then headcaseLob:Remove() end
        headcase = nil
        headcaseLob = nil
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        enter("ritual_setup")
    elseif state == "ritual_setup" and age() >= 3 then
        player:AddCollectible(ids.ritualCandle, 0, false)
        player:AddCacheFlags(CacheFlag.CACHE_FAMILIARS)
        player:EvaluateItems()
        enter("ritual_light")
    elseif state == "ritual_light" and age() >= 5 then
        local candles = 0
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_FAMILIAR and entity.Variant == ids.candleVariant then
                candles = candles + 1
                entity:GetData().IsLit = true
                entity:GetData().LitTimer = 600
            end
        end
        player:GetData().gcbCandleCount = candles
        player.MaxFireDelay = 2
        ritualEnemy = Isaac.Spawn(EntityType.ENTITY_GAPER, 0, 0,
            player.Position + Vector(40, 0), Vector(0, 0), nil):ToNPC()
        ritualEnemy.MaxHitPoints = 100
        ritualEnemy.HitPoints = 100
        ritualEnemy:AddEntityFlags(EntityFlag.FLAG_FREEZE)
        ritualHits = 0
        enter("ritual_check")
    elseif state == "ritual_check" then
        player.MaxFireDelay = 2
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_FAMILIAR and entity.Variant == ids.candleVariant then
                entity:GetData().IsLit = true
                entity:GetData().LitTimer = 600
            end
        end
        if age() >= 8 then
            local hp = ritualEnemy and ritualEnemy.HitPoints or 100
            local candles = player:GetData().gcbCandleCount or 0
            record("ritual_candle", candles >= 5 and hp < 99 and ritualHits > 0,
                "candles=" .. candles .. " enemy_hp=" .. detailNumber(hp)
                    .. " hits=" .. ritualHits)
            ritualEnemy.HitPoints = 100
            ritualHits = 0
            player.MaxFireDelay = 4
            enter("ritual_cadence")
        end
    elseif state == "ritual_cadence" then
        player.MaxFireDelay = 4
        if age() >= 8 then
            record("ritual_candle_cadence", ritualHits == 4,
                "delay=4 hits=" .. ritualHits)
            if ritualEnemy and ritualEnemy:Exists() then ritualEnemy:Remove() end
            ritualEnemy = nil
            player:AddCollectible(ids.sundial, 0, false)
            player:AddCollectible(ids.astroBaby, 0, false)
            player:AddCollectible(ids.lilRune, 0, false)
            player:AddCacheFlags(CacheFlag.CACHE_FAMILIARS)
            player:EvaluateItems()
            enter("familiar_spawn")
        end
    elseif state == "familiar_spawn" and age() >= 8 then
        local counts = countFamiliarVariants()
        player:GetData().gcbFamiliarsSpawned = counts.candle >= 5
            and counts.sun >= 1 and counts.shadow >= 1
            and counts.astro >= 1 and counts.rune >= 1
        player:GetData().gcbFamiliarSpawnDetail = familiarCountDetail(counts)
        for _, itemId in ipairs({ ids.ritualCandle, ids.sundial, ids.astroBaby, ids.lilRune }) do
            removeCollectible(player, itemId)
        end
        player:AddCacheFlags(CacheFlag.CACHE_ALL)
        player:EvaluateItems()
        enter("familiar_cleanup")
    elseif state == "familiar_cleanup" and age() >= 5 then
        local counts = countFamiliarVariants()
        local remaining = counts.candle + counts.sun + counts.shadow + counts.astro + counts.rune
        local spawned = player:GetData().gcbFamiliarsSpawned == true
        record("familiar_cleanup", spawned and remaining == 0,
            "spawned=" .. tostring(spawned)
                .. " before={" .. tostring(player:GetData().gcbFamiliarSpawnDetail) .. "}"
                .. " after={" .. familiarCountDetail(counts) .. "}")
        removeVerifierFamiliars()
        enter("beehive_setup")
    elseif state == "beehive_setup" and age() >= 3 then
        removeCollectible(player, ids.beehive)
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        player:GetData().gcbBeehiveHadSpoonBender = player:GetEffects():HasCollectibleEffect(
            CollectibleType.COLLECTIBLE_SPOON_BENDER)
        player:GetData().gcbBeehiveFallingAcceleration = player.TearFallingAcceleration
        player:AddCollectible(ids.beehive, 0, false)
        beehiveTear = player:FireTear(player.Position, Vector(7, 0),
            false, true, false):ToTear()
        enter("beehive_settle")
    elseif state == "beehive_settle" and age() >= 3 then
        if beehiveTear and beehiveTear:Exists() then
            beehiveVelocity = Vector(beehiveTear.Velocity.X, beehiveTear.Velocity.Y)
            enter("beehive_check")
        else
            record("beehive_early_wobble", false, "tear disappeared before measurement")
            removeCollectible(player, ids.beehive)
            if not player:GetData().gcbBeehiveHadSpoonBender then
                player:GetEffects():RemoveCollectibleEffect(CollectibleType.COLLECTIBLE_SPOON_BENDER)
            end
            player.TearFallingAcceleration = player:GetData().gcbBeehiveFallingAcceleration
            player:AddCacheFlags(CacheFlag.CACHE_ALL)
            player:EvaluateItems()
            enter("deja_setup")
        end
    elseif state == "beehive_check" and age() >= 1 then
        local exists = beehiveTear and beehiveTear:Exists()
        local delta = exists and beehiveTear.Velocity:Distance(beehiveVelocity) or -1
        record("beehive_early_wobble", exists and delta >= 0.35 and delta <= 0.65,
            "exists=" .. tostring(exists) .. " velocity_delta=" .. detailNumber(delta))
        if exists then beehiveTear:Remove() end
        beehiveTear = nil
        beehiveVelocity = nil
        beehiveTear = player:FireTear(game:GetRoom():GetCenterPos(), Vector(0, 0),
            false, true, false):ToTear()
        beehiveTear.Position = game:GetRoom():GetCenterPos()
        beehiveTear.GridCollisionClass = GridCollisionClass.COLLISION_NONE
        beehiveTear.FallingSpeed = 0
        beehiveTear.FallingAcceleration = 0
        enter("beehive_mature_age")
    elseif state == "beehive_mature_age" then
        local exists = beehiveTear and beehiveTear:Exists()
        if exists then
            beehiveTear.Position = game:GetRoom():GetCenterPos()
            beehiveTear.GridCollisionClass = GridCollisionClass.COLLISION_NONE
        end
        if not exists then
            record("beehive_mature_wobble", false,
                "tear disappeared before frame 21")
            enter("beehive_cleanup")
        elseif beehiveTear.FrameCount >= 22 then
            beehiveVelocity = Vector(beehiveTear.Velocity.X, beehiveTear.Velocity.Y)
            enter("beehive_mature_check")
        end
    elseif state == "beehive_mature_check" and age() >= 1 then
        local exists = beehiveTear and beehiveTear:Exists()
        local delta = exists and beehiveTear.Velocity:Distance(beehiveVelocity) or -1
        record("beehive_mature_wobble", exists and delta >= 0.85 and delta <= 1.15,
            "exists=" .. tostring(exists) .. " frame="
                .. (exists and detailNumber(beehiveTear.FrameCount) or "nil")
                .. " velocity_delta=" .. detailNumber(delta))
        enter("beehive_cleanup")
    elseif state == "beehive_cleanup" then
        if beehiveTear and beehiveTear:Exists() then beehiveTear:Remove() end
        beehiveTear = nil
        beehiveVelocity = nil
        removeCollectible(player, ids.beehive)
        if not player:GetData().gcbBeehiveHadSpoonBender then
            player:GetEffects():RemoveCollectibleEffect(CollectibleType.COLLECTIBLE_SPOON_BENDER)
        end
        player.TearFallingAcceleration = player:GetData().gcbBeehiveFallingAcceleration
        player:AddCacheFlags(CacheFlag.CACHE_ALL)
        player:EvaluateItems()
        enter("deja_setup")
    elseif state == "deja_setup" and age() >= 3 then
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        player:AddCollectible(ids.dejaVu, 0, false)
        player:GetData().gcbSavedLuck = player.Luck
        player.Luck = 100
        dejaTear = player:FireTear(player.Position, Vector(8, 0),
            false, true, false):ToTear()
        dejaTear.TearFlags = dejaTear.TearFlags | TearFlags.TEAR_SPLIT
        enter("deja_arm")
    elseif state == "deja_check" then
        local marked = 0
        local livingMarked = 0
        local tears = 0
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_TEAR then
                tears = tears + 1
                if entity:GetData().ReturnChance ~= nil then
                    marked = marked + 1
                    if not entity:IsDead() then livingMarked = livingMarked + 1 end
                end
            end
        end
        record("deja_vu_split_guard", marked == 0,
            "tears=" .. tears .. " return_marked=" .. marked
                .. " living_returned=" .. livingMarked)
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        dejaTear = player:FireTear(player.Position, Vector(8, 0),
            false, true, false):ToTear()
        enter("deja_normal_arm")
    elseif state == "deja_normal_check" and age() >= 2 then
        local marked = 0
        local livingMarked = 0
        local tears = 0
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_TEAR then
                tears = tears + 1
                if entity:GetData().ReturnChance ~= nil then
                    marked = marked + 1
                    if not entity:IsDead() then livingMarked = livingMarked + 1 end
                end
            end
        end
        record("deja_vu_normal_return", livingMarked >= 1,
            "tears=" .. tears .. " return_marked=" .. marked
                .. " living_returned=" .. livingMarked)
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        dejaTear = nil
        removeCollectible(player, ids.dejaVu)
        player.Luck = player:GetData().gcbSavedLuck or player.Luck
        enter("jera_setup")
    elseif state == "jera_setup" and age() >= 3 then
        removeEntitiesByType(EntityType.ENTITY_HORF)
        player:AddCollectible(ids.lilRune, 0, false)
        player:AddCacheFlags(CacheFlag.CACHE_FAMILIARS)
        player:EvaluateItems()
        player:UseCard(Card.RUNE_JERA)
        player:GetData().gcbJeraAttempts = 0
        enter("jera_spawn")
    elseif state == "jera_spawn" and age() >= 1 then
        removeEntitiesByType(EntityType.ENTITY_HORF)
        player:GetData().gcbJeraAttempts = (player:GetData().gcbJeraAttempts or 0) + 1
        for index = 1, 8 do
            local angle = index * 45
            local radius = 38
            local npc = Isaac.Spawn(EntityType.ENTITY_HORF, 0, 0,
                player.Position + Vector.FromAngle(angle) * radius,
                Vector(0, 0), nil):ToNPC()
            npc.MaxHitPoints = 20
            npc.HitPoints = 1
            npc:AddEntityFlags(EntityFlag.FLAG_FREEZE)
            npc:Kill()
        end
        enter("jera_check")
    elseif state == "jera_check" and age() >= 1 then
        local clones = 0
        local overfull = 0
        local healthDetail = ""
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_HORF and not entity:IsDead()
                and entity:ToNPC().Scale < 0.9 then
                clones = clones + 1
                if entity.HitPoints > entity.MaxHitPoints + 0.01 then
                    overfull = overfull + 1
                end
                if clones <= 4 then
                    healthDetail = healthDetail .. " [hp=" .. detailNumber(entity.HitPoints)
                        .. " max=" .. detailNumber(entity.MaxHitPoints) .. "]"
                end
            end
        end
        if clones >= 2 or (player:GetData().gcbJeraAttempts or 0) >= 16 then
            record("lil_rune_jera_health", clones >= 2 and overfull == 0,
                "attempts=" .. tostring(player:GetData().gcbJeraAttempts)
                    .. " clones=" .. clones .. " overfull=" .. overfull .. healthDetail)
            removeEntitiesByType(EntityType.ENTITY_HORF)
            removeCollectible(player, ids.lilRune)
            player:AddCacheFlags(CacheFlag.CACHE_FAMILIARS)
            player:EvaluateItems()
            removeVerifierFamiliars()
            removeActiveEnemies()
            enter("lovely_setup")
        else
            removeEntitiesByType(EntityType.ENTITY_HORF)
            enter("jera_spawn")
        end
    elseif state == "lovely_setup" and age() >= 3 then
        removeActiveEnemies()
        lovelyDecoy = Isaac.Spawn(EntityType.ENTITY_SHOPKEEPER, 0, 0,
            player.Position + Vector(25, 0), Vector(0, 0), nil):ToNPC()
        player:GetData().gcbLovelyDecoyVulnerableAtSpawn = lovelyDecoy:IsVulnerableEnemy()
        player:GetData().gcbLovelyDecoyActiveAtSpawn = lovelyDecoy:IsActiveEnemy(false)
        lovelyEnemy = Isaac.Spawn(EntityType.ENTITY_HORF, 0, 0,
            player.Position + Vector(120, 0), Vector(0, 0), nil):ToNPC()
        lovelyEnemy:AddEntityFlags(EntityFlag.FLAG_FREEZE)
        lovelyFly = Isaac.Spawn(ids.lovelyFlyType, ids.lovelyFlyVariant, 0,
            player.Position, Vector(0, 0), nil):ToNPC()
        enter("lovely_check")
    elseif state == "lovely_check" and age() >= 8 then
        local flyExists = lovelyFly and lovelyFly:Exists()
        local parent = flyExists and lovelyFly:GetData().parentEnemy or nil
        local parentSeed = type(parent) ~= "string" and parent and parent.InitSeed or nil
        local parentType = type(parent) ~= "string" and parent and parent.Type or nil
        local parentVariant = type(parent) ~= "string" and parent and parent.Variant or nil
        local expectedSeed = lovelyEnemy and lovelyEnemy.InitSeed or nil
        local decoySeed = lovelyDecoy and lovelyDecoy.InitSeed or nil
        local decoyVulnerable = lovelyDecoy and lovelyDecoy:IsVulnerableEnemy() or false
        local decoyActive = lovelyDecoy and lovelyDecoy:IsActiveEnemy(false) or false
        record("lovely_fly_target", flyExists and parentSeed == expectedSeed,
            "fly_exists=" .. tostring(flyExists)
                .. " parent_seed=" .. detailNumber(parentSeed)
                .. " parent_type=" .. detailNumber(parentType)
                .. " parent_variant=" .. detailNumber(parentVariant)
                .. " enemy_seed=" .. detailNumber(expectedSeed)
                .. " decoy_seed=" .. detailNumber(decoySeed)
                .. " decoy_spawn_vulnerable="
                    .. tostring(player:GetData().gcbLovelyDecoyVulnerableAtSpawn)
                .. " decoy_spawn_active="
                    .. tostring(player:GetData().gcbLovelyDecoyActiveAtSpawn)
                .. " decoy_vulnerable=" .. tostring(decoyVulnerable)
                .. " decoy_active=" .. tostring(decoyActive))
        if lovelyFly and lovelyFly:Exists() then lovelyFly:Remove() end
        if lovelyDecoy and lovelyDecoy:Exists() then lovelyDecoy:Remove() end
        if lovelyEnemy and lovelyEnemy:Exists() then lovelyEnemy:Remove() end
        lovelyFly = nil
        lovelyDecoy = nil
        lovelyEnemy = nil
        removeActiveEnemies()
        enter("cursed_setup")
    elseif state == "grid_setup" and age() >= 3 then
        removeTrinket(player, ids.gridWorm)
        local activeEnemies = 0
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity:IsActiveEnemy(false) then activeEnemies = activeEnemies + 1 end
        end
        player:GetData().gcbGridIsolation = "active_enemies=" .. activeEnemies
            .. " spoon_effect=" .. tostring(player:GetEffects():HasCollectibleEffect(
                CollectibleType.COLLECTIBLE_SPOON_BENDER))
        player:AddTrinket(ids.gridWorm, true)
        player:GetData().gcbGridHeadDirection = player:GetHeadDirection()
        gridTear = player:FireTear(player.Position, Vector(3, 4), false, true, false):ToTear()
        enter("grid_check")
    elseif state == "grid_check" and age() >= 2 then
        local x = gridTear and gridTear.Velocity.X or 0
        local y = gridTear and gridTear.Velocity.Y or 0
        local axisLocked = (math.abs(x) < 0.01 and math.abs(y) > 0.01)
            or (math.abs(y) < 0.01 and math.abs(x) > 0.01)
        local head = player:GetData().gcbGridHeadDirection
        local headingLocked = (head == Direction.DOWN and math.abs(x) < 0.01 and y > 0)
            or (head == Direction.LEFT and x < 0 and math.abs(y) < 0.01)
            or (head == Direction.RIGHT and x > 0 and math.abs(y) < 0.01)
            or (head == Direction.UP and math.abs(x) < 0.01 and y < 0)
        record("grid_worm", axisLocked,
            "velocity=" .. detailNumber(x) .. "," .. detailNumber(y)
                .. " " .. tostring(player:GetData().gcbGridIsolation))
        record("grid_worm_heading", headingLocked,
            "head=" .. detailNumber(head) .. " velocity=" .. detailNumber(x)
                .. "," .. detailNumber(y))
        if gridTear and gridTear:Exists() then gridTear:Remove() end
        gridTear = nil
        enter("grid_cross_setup")
    elseif state == "grid_cross_setup" and age() >= 1 then
        -- A diagonal whose dominant axis is perpendicular to the facing axis: the first
        -- snap must follow the facing direction, not the tear's own dominant axis.
        local head = player:GetHeadDirection()
        local crossVelocity = (head == Direction.LEFT or head == Direction.RIGHT)
            and Vector(3, -4) or Vector(4, -3)
        player:GetData().gcbGridCrossHead = head
        player:GetData().gcbGridCrossFire = player:GetFireDirection()
        gridTear = player:FireTear(player.Position, crossVelocity, false, true, false):ToTear()
        enter("grid_cross_check")
    elseif state == "grid_cross_check" and age() >= 2 then
        local x = gridTear and gridTear.Velocity.X or 0
        local y = gridTear and gridTear.Velocity.Y or 0
        local head = player:GetData().gcbGridCrossHead
        local headingLocked = (head == Direction.DOWN and math.abs(x) < 0.01 and y > 0)
            or (head == Direction.LEFT and x < 0 and math.abs(y) < 0.01)
            or (head == Direction.RIGHT and x > 0 and math.abs(y) < 0.01)
            or (head == Direction.UP and math.abs(x) < 0.01 and y < 0)
        record("grid_worm_heading_cross_axis", headingLocked,
            "head=" .. detailNumber(head)
                .. " fire=" .. detailNumber(player:GetData().gcbGridCrossFire)
                .. " velocity=" .. detailNumber(x) .. "," .. detailNumber(y))
        if gridTear and gridTear:Exists() then gridTear:Remove() end
        gridTear = nil
        gridCadenceTears = {}
        gridCadenceDirections = {}
        local room = game:GetRoom()
        for index = 1, 12 do
            local tear = player:FireTear(room:GetCenterPos(), Vector(5, 0),
                false, true, false):ToTear()
            tear.Position = room:GetCenterPos()
            tear.GridCollisionClass = GridCollisionClass.COLLISION_NONE
            gridCadenceTears[index] = tear
        end
        enter("grid_cadence_capture")
    elseif state == "grid_cadence_capture" and age() >= 2 then
        local captured = 0
        for index, tear in ipairs(gridCadenceTears) do
            if tear and tear:Exists() and tear.Velocity:Length() > 0.01 then
                gridCadenceDirections[index] = tear.Velocity:Normalized()
                tear.Position = game:GetRoom():GetCenterPos()
                captured = captured + 1
            end
        end
        player:GetData().gcbGridCadenceCaptured = captured
        enter("grid_cadence_check")
    elseif state == "grid_cadence_check" then
        for _, tear in ipairs(gridCadenceTears) do
            if tear and tear:Exists() then
                tear.Position = game:GetRoom():GetCenterPos()
                tear.GridCollisionClass = GridCollisionClass.COLLISION_NONE
            end
        end
        if age() >= 10 then
            local observed = 0
            local unchanged = 0
            local minimumDot = 1
            for index, tear in ipairs(gridCadenceTears) do
                local initial = gridCadenceDirections[index]
                if tear and tear:Exists() and initial and tear.Velocity:Length() > 0.01 then
                    local dot = tear.Velocity:Normalized():Dot(initial)
                    observed = observed + 1
                    minimumDot = math.min(minimumDot, dot)
                    if dot > 0.99 then unchanged = unchanged + 1 end
                end
            end
            record("grid_worm_cadence_regression",
                (player:GetData().gcbGridCadenceCaptured or 0) == 12
                    and observed == 12 and unchanged == 12,
                "captured=" .. detailNumber(player:GetData().gcbGridCadenceCaptured)
                    .. " observed=" .. observed .. " unchanged=" .. unchanged
                    .. " minimum_dot=" .. detailNumber(minimumDot))
            for _, tear in ipairs(gridCadenceTears) do
                if tear and tear:Exists() then tear:Remove() end
            end
            gridCadenceTears = {}
            gridCadenceDirections = {}
            enter("grid_bounce_setup")
        end
    elseif state == "grid_bounce_setup" then
        local room = game:GetRoom()
        local collisionPos = nil
        for index = 0, room:GetGridSize() - 1 do
            local grid = room:GetGridEntity(index)
            if grid and grid:GetType() == GridEntityType.GRID_WALL then
                collisionPos = room:GetGridPosition(index)
                break
            end
        end
        if not collisionPos then error("no wall grid position for Grid Worm bounce") end
        local outward = (collisionPos - room:GetCenterPos()):Normalized() * 10
        gridTear = player:FireTear(room:GetCenterPos(), Vector(0, 0),
            false, true, false):ToTear()
        gridTear.Position = room:GetCenterPos()
        gridTear.Velocity = Vector(0, 0)
        gridBounceWall = Vector(collisionPos.X, collisionPos.Y)
        gridBounceOutward = outward:Normalized()
        gridBounceTrace = ""
        enter("grid_bounce_arm")
    elseif state == "grid_bounce_arm" and age() >= 3 then
        local exists = gridTear and gridTear:Exists()
        gridBounceTrace = gridBounceTrace .. " [arm_exists=" .. tostring(exists)
            .. " frame=" .. (exists and detailNumber(gridTear.FrameCount) or "nil")
            .. " height=" .. (exists and detailNumber(gridTear.Height) or "nil") .. "]"
        if exists then
            gridTear.Position = gridBounceWall - gridBounceOutward * 30
            gridTear.Velocity = gridBounceOutward * 10
        end
        enter("grid_bounce_check")
    elseif state == "grid_bounce_check" then
        local exists = gridTear and gridTear:Exists()
        local dot = exists and (gridTear.Velocity.X * gridBounceOutward.X
            + gridTear.Velocity.Y * gridBounceOutward.Y) or 0
        local wallDistance = exists and gridTear.Position:Distance(gridBounceWall) or 0
        local colliding = exists and gridTear:CollidesWithGrid() or false
        gridBounceTrace = gridBounceTrace .. " [age=" .. age()
            .. " dot=" .. detailNumber(dot)
            .. " distance=" .. detailNumber(wallDistance)
            .. " colliding=" .. tostring(colliding) .. "]"
        if exists and dot < 0 then
            record("grid_worm_bounce", wallDistance >= 35,
                "reversed=true distance=" .. detailNumber(wallDistance)
                    .. " trace=" .. gridBounceTrace)
        elseif not exists or age() >= 8 then
            record("grid_worm_bounce", false,
                "reversed=false trace=" .. gridBounceTrace)
        end
        if recorded.grid_worm_bounce then
            if exists then gridTear:Remove() end
            removeTrinket(player, ids.gridWorm)
            enter("hurdle_setup")
        end
    elseif state == "glasses_hold" and age() >= 3 then
        removeTrinket(player, ids.brokenGlasses)
        player:AddTrinket(ids.brokenGlasses, true)
        enter("glasses_drop")
    elseif state == "glasses_drop" and age() >= 3 then
        removeTrinket(player, ids.brokenGlasses)
        glassesEnemy = Isaac.Spawn(EntityType.ENTITY_GAPER, 0, 0,
            player.Position + Vector(60, 0), Vector(0, 0), nil):ToNPC()
        glassesEnemy:AddEntityFlags(EntityFlag.FLAG_FREEZE)
        enter("glasses_check")
    elseif state == "glasses_check" and age() >= 4 then
        local exists = glassesEnemy and glassesEnemy:Exists()
        local colour = exists and glassesEnemy:GetSprite().Color or nil
        local black = colour and colour.R < 0.05 and colour.G < 0.05 and colour.B < 0.05
        record("broken_glasses", black == true,
            "exists=" .. tostring(exists)
                .. " rgb=" .. (colour and (detailNumber(colour.R) .. ","
                    .. detailNumber(colour.G) .. "," .. detailNumber(colour.B)) or "nil"))
        if exists then glassesEnemy:Remove() end
        enter("james_stage_setup")
    elseif state == "james_stage_setup" and age() >= 3 then
        player:GetData().gcbBookOfSecretsBaseline = bookOfSecretsEffectCount()
        enter("james_stage_check")
        Isaac.ExecuteCommand("stage 1")
    elseif state == "james_stage_check" and age() >= 10 then
        local baseline = player:GetData().gcbBookOfSecretsBaseline or 0
        local after = bookOfSecretsEffectCount()
        record("james_book_of_secrets_scope", after == 0,
            "player_type=" .. player:GetPlayerType()
                .. " before_effects=" .. baseline .. " after_effects=" .. after)
        local mutantBaseline = player:GetData().gcbMutantBaseline or player.Luck
        record("mutant_clover_room_reset", math.abs(player.Luck - mutantBaseline) < 0.05,
            "baseline=" .. detailNumber(mutantBaseline)
                .. " after_new_floor=" .. detailNumber(player.Luck))
        removeCollectible(player, ids.mutantClover)
        player:AddCacheFlags(CacheFlag.CACHE_LUCK)
        player:EvaluateItems()
        glassesEnemy = Isaac.Spawn(EntityType.ENTITY_GAPER, 0, 0,
            player.Position + Vector(60, 0), Vector(0, 0), nil):ToNPC()
        glassesEnemy:AddEntityFlags(EntityFlag.FLAG_FREEZE)
        enter("glasses_floor_reset_check")
    elseif state == "glasses_floor_reset_check" and age() >= 4 then
        local exists = glassesEnemy and glassesEnemy:Exists()
        local colour = exists and glassesEnemy:GetSprite().Color or nil
        local black = colour and colour.R < 0.05 and colour.G < 0.05 and colour.B < 0.05
        record("broken_glasses_floor_reset", exists and black ~= true,
            "exists=" .. tostring(exists)
                .. " rgb=" .. (colour and (detailNumber(colour.R) .. ","
                    .. detailNumber(colour.G) .. "," .. detailNumber(colour.B)) or "nil"))
        if exists then glassesEnemy:Remove() end
        glassesEnemy = nil
        enter("grid_setup")
    elseif state == "cursed_setup" and age() >= 5 then
        clearPlayerHealth(player, 12, 4)
        player:AddCollectible(ids.cursedMetronome, 0, false)
        enter("cursed_check")
    elseif state == "cursed_check" and age() >= 3 then
        local maxHearts = player:GetMaxHearts()
        local redHearts = player:GetHearts()
        record("cursed_metronome", maxHearts == 12 and redHearts == 0,
            "max=" .. maxHearts .. " red=" .. redHearts)
        removeCollectible(player, ids.cursedMetronome)
        enter("glasses_hold")
    -- C2: Hurdle Heels landing stomp and Isaac's own protection ------------------------------
    elseif state == "hurdle_setup" and age() >= 3 then
        removeActiveEnemies()
        removeEntitiesByType(EntityType.ENTITY_PROJECTILE)
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        clearPlayerHealth(player, 6, 6)
        removeCollectible(player, ids.hurdleHeels)
        player:AddCollectible(ids.hurdleHeels, 2, false)
        hurdleGaper = Isaac.Spawn(EntityType.ENTITY_GAPER, 0, 0,
            player.Position + Vector(36, 0), Vector(0, 0), nil):ToNPC()
        hurdleGaper.MaxHitPoints = 1000
        hurdleGaper.HitPoints = 1000
        hurdleGaper:AddEntityFlags(EntityFlag.FLAG_FREEZE)
        enter("hurdle_jump")
    elseif state == "hurdle_jump" and age() >= 3 then
        player:GetData().gcbHurdleDamage = player.Damage
        player:UseActiveItem(ids.hurdleHeels, false, false, false, false)
        enter("hurdle_airborne")
    elseif state == "hurdle_airborne" then
        -- airborne: the jump hides Isaac and keeps a landing marker (effect variant 30, as in the mod)
        if countEntitiesByTypeVariant(EntityType.ENTITY_EFFECT, 30) > 0 or not player.Visible then
            player:GetData().gcbHurdleDetail = "airborne_after=" .. age()
                .. " visible_in_air=" .. tostring(player.Visible)
            enter("hurdle_midair")
        elseif age() >= 40 then
            local detail = "airborne=false visible=" .. tostring(player.Visible)
            record("hurdle_heels_landing_stomp", false, detail)
            record("hurdle_heels_player_protected", false, detail)
            hurdleCleanup(player)
            enter("lantern_setup")
        end
    elseif state == "hurdle_midair" and age() >= 15 then
        player:GetData().gcbHurdleHeartsMid = player:GetHearts()
        player:GetData().gcbHurdleStompBase = hurdleGaper.HitPoints
        player:TakeDamage(2, 0, EntityRef(hurdleGaper), 0)
        enter("hurdle_midair_check")
    elseif state == "hurdle_midair_check" and age() >= 1 then
        player:GetData().gcbHurdleMidSafe =
            player:GetHearts() == player:GetData().gcbHurdleHeartsMid
        enter("hurdle_land")
    elseif state == "hurdle_land" then
        if countEntitiesByTypeVariant(EntityType.ENTITY_EFFECT, 30) == 0 and player.Visible then
            player:GetData().gcbHurdleDetail = player:GetData().gcbHurdleDetail
                .. " landed_after=" .. age()
            enter("hurdle_stomp_check")
        elseif age() >= 120 then
            local detail = player:GetData().gcbHurdleDetail .. " landed=false"
            record("hurdle_heels_landing_stomp", false, detail)
            record("hurdle_heels_player_protected", false, detail)
            hurdleCleanup(player)
            enter("lantern_setup")
        end
    elseif state == "hurdle_stomp_check" and age() >= 2 then
        local loss = player:GetData().gcbHurdleStompBase - hurdleGaper.HitPoints
        local expected = 4 * player:GetData().gcbHurdleDamage - 0.5
        record("hurdle_heels_landing_stomp", loss >= expected,
            player:GetData().gcbHurdleDetail .. " stomp_hp_loss=" .. detailNumber(loss)
                .. " expected_at_least=" .. detailNumber(expected))
        player:GetData().gcbHurdleHeartsGrace = player:GetHearts()
        player:TakeDamage(2, 0, EntityRef(hurdleGaper), 0)
        enter("hurdle_grace_check")
    elseif state == "hurdle_grace_check" and age() >= 1 then
        player:GetData().gcbHurdleGraceSafe =
            player:GetHearts() == player:GetData().gcbHurdleHeartsGrace
        enter("hurdle_after")
    elseif state == "hurdle_after" and age() >= 40 then
        player:GetData().gcbHurdleHeartsAfter = player:GetHearts()
        player:TakeDamage(2, 0, EntityRef(hurdleGaper), 0)
        enter("hurdle_after_check")
    elseif state == "hurdle_after_check" and age() >= 1 then
        local midSafe = player:GetData().gcbHurdleMidSafe == true
        local graceSafe = player:GetData().gcbHurdleGraceSafe == true
        local hurtAfter = player:GetHearts() < player:GetData().gcbHurdleHeartsAfter
        record("hurdle_heels_player_protected", midSafe and graceSafe and hurtAfter,
            "mid_air_safe=" .. tostring(midSafe)
                .. " landing_window_safe=" .. tostring(graceSafe)
                .. " hurt_after_jump=" .. tostring(hurtAfter)
                .. " red=" .. player:GetHearts())
        hurdleCleanup(player)
        enter("lantern_setup")
    -- C1: Ominous Lantern put away without a throw ---------------------------------------------
    elseif state == "lantern_setup" and age() >= 3 then
        removeCollectible(player, ids.ominousLantern)
        player:AddCollectible(ids.ominousLantern, 1, false)
        player:SetActiveCharge(1)
        lanternUses = 0
        lanternUseFrame = -1
        lanternUseCharges = {}
        enter("lantern_raise")
    elseif state == "lantern_raise" and age() >= 5 then
        player:GetData().gcbLanternStart = player:GetActiveCharge()
        lanternPressArmed = true
        enter("lantern_raise_wait")
    elseif state == "lantern_raise_wait" then
        if lanternUses >= 1 and game:GetFrameCount() >= lanternUseFrame + 20 then
            player:GetData().gcbLanternRaised = player:GetActiveCharge()
            lanternPressArmed = true
            enter("lantern_lower_wait")
        elseif lanternUses == 0 and age() >= 30 then
            local detail = "real_use=false start_charge="
                .. detailNumber(player:GetData().gcbLanternStart)
            record("ominous_lantern_put_away", false, detail)
            record("ominous_lantern_throw_recharge", false, detail)
            lanternCleanup(player)
            enter("leash_setup")
        end
    elseif state == "lantern_lower_wait" then
        if lanternUses >= 2 and game:GetFrameCount() >= lanternUseFrame + 3 then
            local raised = player:GetData().gcbLanternRaised
            local lowered = player:GetActiveCharge()
            record("ominous_lantern_put_away", raised == 1 and lowered == 1,
                "uses=" .. lanternUses
                    .. " charge_in_use_callback=" .. table.concat(lanternUseCharges, ",")
                    .. " raised_charge=" .. detailNumber(raised)
                    .. " lowered_charge=" .. detailNumber(lowered))
            player:SetActiveCharge(1)
            enter("lantern_reraise")
        elseif age() >= 30 then
            local detail = "second_use=false uses=" .. lanternUses
            record("ominous_lantern_put_away", false, detail)
            record("ominous_lantern_throw_recharge", false, detail)
            lanternCleanup(player)
            enter("leash_setup")
        end
    elseif state == "lantern_reraise" and game:GetFrameCount() >= lanternUseFrame + 20 then
        lanternPressArmed = true
        enter("lantern_reraise_wait")
    elseif state == "lantern_reraise_wait" then
        if lanternUses >= 3 and game:GetFrameCount() >= lanternUseFrame + 20 then
            holdShootLeft(true)
            enter("lantern_throw_wait")
        elseif lanternUses < 3 and age() >= 30 then
            record("ominous_lantern_throw_recharge", false,
                "raised_again=false uses=" .. lanternUses
                    .. " charge=" .. detailNumber(player:GetActiveCharge()))
            lanternCleanup(player)
            enter("leash_setup")
        end
    elseif state == "lantern_throw_wait" then
        if countEntitiesByTypeVariant(EntityType.ENTITY_TEAR, ids.lanternTearVariant) > 0 then
            holdShootLeft(false)
            player:GetData().gcbLanternEarly = nil
            enter("lantern_recharge")
        elseif age() >= 30 then
            record("ominous_lantern_throw_recharge", false,
                "thrown=false charge=" .. detailNumber(player:GetActiveCharge()))
            lanternCleanup(player)
            enter("leash_setup")
        end
    elseif state == "lantern_recharge" then
        if age() == 3 then
            player:GetData().gcbLanternEarly = player:GetActiveCharge()
        end
        if age() > 3 and player:GetActiveCharge() >= 1 then
            local early = player:GetData().gcbLanternEarly
            record("ominous_lantern_throw_recharge", early == 0 and age() <= 330,
                "early_charge=" .. detailNumber(early) .. " recharged_after=" .. age())
            lanternCleanup(player)
            enter("leash_setup")
        elseif age() >= 360 then
            record("ominous_lantern_throw_recharge", false,
                "early_charge=" .. detailNumber(player:GetData().gcbLanternEarly)
                    .. " recharged=false charge=" .. detailNumber(player:GetActiveCharge()))
            lanternCleanup(player)
            enter("leash_setup")
        end
    -- EX-436: Child's Leash on Exodus orbitals -------------------------------------------------
    elseif state == "leash_setup" and age() >= 3 then
        removeActiveEnemies()
        for _, itemId in ipairs({ ids.sundial, ids.hungryHippo, ids.roboBaby }) do
            removeCollectible(player, itemId)
        end
        removeTrinket(player, TrinketType.TRINKET_CHILD_LEASH)
        removeVerifierFamiliars()
        removeFamiliarVariant(ids.hippoVariant)
        removeFamiliarVariant(ids.roboVariant)
        player:AddCollectible(ids.sundial, 0, false)
        player:AddCollectible(ids.hungryHippo, 0, false)
        player:AddCollectible(ids.roboBaby, 0, false)
        player:AddTrinket(TrinketType.TRINKET_CHILD_LEASH)
        evaluateFamiliars(player)
        enter("leash_held")
    elseif state == "leash_held" and age() >= 10 then
        leashHeld = orbitalSnapshot(player)
        removeTrinket(player, TrinketType.TRINKET_CHILD_LEASH)
        enter("leash_dropped")
    elseif state == "leash_dropped" and age() >= 10 then
        local free = orbitalSnapshot(player)
        local ratios = {}
        local ratiosOk = true
        for _, name in ipairs({ "sun", "shadow", "hippo", "robo" }) do
            local held = leashHeld[name]
            local loose = free[name]
            local ratio = -1
            if held.count == 1 and loose.count == 1 and loose.distance > 0 then
                ratio = held.distance / loose.distance
            end
            ratios[#ratios + 1] = name .. "=" .. detailNumber(ratio)
            if ratio < 0.35 or ratio > 0.65 then ratiosOk = false end
        end
        record("childs_leash_orbitals", ratiosOk,
            "ratios={" .. table.concat(ratios, " ") .. "} held={" .. orbitalDetail(leashHeld)
                .. "} free={" .. orbitalDetail(free) .. "}")
        for _, itemId in ipairs({ ids.sundial, ids.hungryHippo, ids.roboBaby }) do
            removeCollectible(player, itemId)
        end
        evaluateFamiliars(player)
        removeVerifierFamiliars()
        removeFamiliarVariant(ids.hippoVariant)
        removeFamiliarVariant(ids.roboVariant)
        leashHeld = nil
        enter("scissors_setup")
    -- EX-427: a rune used while holding Lil Rune empowers it -----------------------------------
    elseif state == "algiz_setup" and age() >= 3 then
        removeCollectible(player, ids.lilRune)
        removeVerifierFamiliars()
        removeEntitiesByType(EntityType.ENTITY_PROJECTILE)
        player:AddCollectible(ids.lilRune, 0, false)
        evaluateFamiliars(player)
        enter("algiz_use")
    elseif state == "algiz_use" and age() >= 5 then
        local rune = familiarsOfVariant(ids.runeVariant)[1]
        if not rune then
            record("lil_rune_algiz_rune", false, "rune_familiar=false")
            enter("algiz_cleanup")
        else
            useCardArgs = nil
            player:UseCard(Card.RUNE_ALGIZ)
            local center = game:GetRoom():GetCenterPos()
            local left = center + Vector(-100, 0)
            local right = center + Vector(100, 0)
            local controlPos = left
            if right:Distance(rune.Position) > left:Distance(rune.Position) then controlPos = right end
            algizShot = Isaac.Spawn(EntityType.ENTITY_PROJECTILE, 0, 0, rune.Position,
                Vector(0, 0), nil)
            algizShot.EntityCollisionClass = EntityCollisionClass.ENTCOLL_NONE
            algizControl = Isaac.Spawn(EntityType.ENTITY_PROJECTILE, 0, 0, controlPos,
                Vector(0, 0), nil)
            algizControl.EntityCollisionClass = EntityCollisionClass.ENTCOLL_NONE
            enter("algiz_track")
        end
    elseif state == "algiz_track" then
        local rune = familiarsOfVariant(ids.runeVariant)[1]
        local shotAlive = algizShot ~= nil and algizShot:Exists() and not algizShot:IsDead()
        if rune and shotAlive then
            algizShot.Position = rune.Position
            algizShot.Velocity = Vector(0, 0)
        end
        if algizControl and algizControl:Exists() then algizControl.Velocity = Vector(0, 0) end
        if age() >= 4 then
            local controlAlive = algizControl ~= nil and algizControl:Exists()
                and not algizControl:IsDead()
            local controlDistance = -1
            if rune and algizControl then
                controlDistance = algizControl.Position:Distance(rune.Position)
            end
            record("lil_rune_algiz_rune", (not shotAlive) and controlAlive and controlDistance > 32,
                "shot_alive=" .. tostring(shotAlive) .. " control_alive=" .. tostring(controlAlive)
                    .. " control_distance=" .. detailNumber(controlDistance)
                    .. " use_card_args=" .. detailNumber(useCardArgs)
                    .. " runes=" .. #familiarsOfVariant(ids.runeVariant))
            enter("algiz_cleanup")
        end
    elseif state == "algiz_cleanup" then
        if algizShot and algizShot:Exists() then algizShot:Remove() end
        if algizControl and algizControl:Exists() then algizControl:Remove() end
        algizShot = nil
        algizControl = nil
        removeCollectible(player, ids.lilRune)
        evaluateFamiliars(player)
        removeVerifierFamiliars()
        enter("alias_setup")
    -- EX-461: Big Scissors leaves a creep trail after Isaac is hurt ----------------------------
    elseif state == "scissors_setup" and age() >= 3 then
        removeActiveEnemies()
        removeEntitiesByTypeVariant(EntityType.ENTITY_EFFECT, EffectVariant.PLAYER_CREEP_RED)
        clearPlayerHealth(player, 6, 6)
        removeCollectible(player, ids.bigScissors)
        player:AddCollectible(ids.bigScissors, 0, false)
        enter("scissors_hit")
    elseif state == "scissors_hit" and age() >= 60 then
        scissorsCreep = 0
        player:TakeDamage(1, 0, EntityRef(player), 0)
        enter("scissors_trail")
    elseif state == "scissors_trail" and age() >= 30 then
        record("big_scissors_trail", scissorsCreep >= 3,
            "creep_spawned=" .. scissorsCreep .. " red=" .. player:GetHearts())
        removeCollectible(player, ids.bigScissors)
        removeEntitiesByTypeVariant(EntityType.ENTITY_EFFECT, EffectVariant.PLAYER_CREEP_RED)
        clearPlayerHealth(player, 6, 6)
        enter("mantle_setup")
    -- EX-463: Unholy Mantle bursts once per floor -----------------------------------------------
    elseif state == "mantle_setup" and age() >= 60 then
        removeActiveEnemies()
        clearPlayerHealth(player, 6, 6)
        removeCollectible(player, ids.unholyMantle)
        player:AddCollectible(ids.unholyMantle, 0, false)
        mantleGaper = Isaac.Spawn(EntityType.ENTITY_GAPER, 0, 0,
            player.Position + Vector(120, 0), Vector(0, 0), nil):ToNPC()
        mantleGaper:AddEntityFlags(EntityFlag.FLAG_FREEZE)
        enter("mantle_hit")
    elseif state == "mantle_hit" and age() >= 5 then
        player:GetData().gcbMantleHp = mantleGaper and mantleGaper.HitPoints or nil
        player:TakeDamage(1, 0, EntityRef(player), 0)
        enter("mantle_check")
    elseif state == "mantle_check" and age() >= 5 then
        local alive = mantleGaper ~= nil and mantleGaper:Exists() and not mantleGaper:IsDead()
        local before = player:GetData().gcbMantleHp
        local after = alive and mantleGaper.HitPoints or 0
        record("unholy_mantle_burst", before ~= nil and (not alive or after <= before - 50),
            "before=" .. detailNumber(before) .. " alive=" .. tostring(alive)
                .. " after=" .. detailNumber(after) .. " stage=" .. game:GetLevel():GetAbsoluteStage())
        if mantleGaper and mantleGaper:Exists() then mantleGaper:Remove() end
        mantleGaper = Isaac.Spawn(EntityType.ENTITY_GAPER, 0, 0,
            player.Position + Vector(120, 0), Vector(0, 0), nil):ToNPC()
        mantleGaper:AddEntityFlags(EntityFlag.FLAG_FREEZE)
        enter("mantle_second_hit")
    elseif state == "mantle_second_hit" and age() >= 90 then
        player:GetData().gcbMantleHp = mantleGaper and mantleGaper.HitPoints or nil
        player:GetData().gcbMantleRedBefore = player:GetHearts()
        player:TakeDamage(1, 0, EntityRef(player), 0)
        enter("mantle_second_check")
    elseif state == "mantle_second_check" and age() >= 5 then
        local alive = mantleGaper ~= nil and mantleGaper:Exists() and not mantleGaper:IsDead()
        local before = player:GetData().gcbMantleHp
        local after = alive and mantleGaper.HitPoints or 0
        local redBefore = player:GetData().gcbMantleRedBefore
        record("unholy_mantle_once",
            alive and before ~= nil and math.abs(after - before) < 0.01 and player:GetHearts() < redBefore,
            "before=" .. detailNumber(before) .. " alive=" .. tostring(alive) .. " after=" .. detailNumber(after)
                .. " red_before=" .. detailNumber(redBefore) .. " red_after=" .. player:GetHearts())
        if mantleGaper and mantleGaper:Exists() then mantleGaper:Remove() end
        mantleGaper = nil
        removeCollectible(player, ids.unholyMantle)
        clearPlayerHealth(player, 6, 6)
        enter("bath_setup")
    -- EX-465: Birdbath places a bath when used --------------------------------------------------
    elseif state == "bath_setup" and age() >= 3 then
        removeActiveEnemies()
        removeEntitiesByTypeVariant(ids.birdbathType, ids.birdbathVariant)
        removeCollectible(player, ids.birdbath)
        player:AddCollectible(ids.birdbath, 0, false)
        player:UseActiveItem(ids.birdbath, false, false, false, false)
        enter("bath_check")
    elseif state == "bath_check" and age() >= 5 then
        local baths = countEntitiesByTypeVariant(ids.birdbathType, ids.birdbathVariant)
        record("birdbath_use_spawns", baths == 1, "baths=" .. baths)
        removeEntitiesByTypeVariant(ids.birdbathType, ids.birdbathVariant)
        removeCollectible(player, ids.birdbath)
        enter("paper_setup")
    -- EX-467: Paper Cut makes cards hurt enemies -------------------------------------------------
    elseif state == "paper_setup" and age() >= 3 then
        removeActiveEnemies()
        removeCollectible(player, ids.paperCut)
        player:AddCollectible(ids.paperCut, 0, false)
        paperGaper = Isaac.Spawn(EntityType.ENTITY_GAPER, 0, 0,
            player.Position + Vector(120, 0), Vector(0, 0), nil):ToNPC()
        paperGaper:AddEntityFlags(EntityFlag.FLAG_FREEZE)
        enter("paper_use")
    elseif state == "paper_use" and age() >= 5 then
        player:GetData().gcbPaperHp = paperGaper and paperGaper.HitPoints or nil
        player:UseCard(Card.CARD_JUSTICE)
        enter("paper_check")
    elseif state == "paper_check" and age() >= 3 then
        local alive = paperGaper ~= nil and paperGaper:Exists() and not paperGaper:IsDead()
        local before = player:GetData().gcbPaperHp
        local after = alive and paperGaper.HitPoints or 0
        record("paper_cut_card_damage", before ~= nil and (not alive or after <= before - 9),
            "before=" .. detailNumber(before) .. " alive=" .. tostring(alive) .. " after=" .. detailNumber(after))
        if paperGaper and paperGaper:Exists() then paperGaper:Remove() end
        paperGaper = nil
        removeCollectible(player, ids.paperCut)
        removeEntitiesByType(EntityType.ENTITY_PICKUP)
        enter("mitt_flags_setup")
    -- EX-469: balls returned by Baseball Mitt keep their bounce, confusion and damage ------------
    elseif state == "mitt_flags_setup" and age() >= 3 then
        removeActiveEnemies()
        removeEntitiesByType(EntityType.ENTITY_PROJECTILE)
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        removeCollectible(player, ids.baseballMitt)
        player:AddCollectible(ids.baseballMitt, 0, false)
        player:UseActiveItem(ids.baseballMitt, false, false, false, false)
        for _ = 1, 2 do
            Isaac.Spawn(EntityType.ENTITY_PROJECTILE, 0, 0, player.Position, Vector(0, 0), player)
        end
        enter("mitt_flags_wait")
    elseif state == "mitt_flags_wait" then
        local balls = {}
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_TEAR and entity.Variant == ids.baseballVariant then
                balls[#balls + 1] = entity:ToTear()
            end
        end
        if #balls > 0 or age() >= 170 then
            local flagged = 0
            local strong = 0
            for _, ball in ipairs(balls) do
                if ball.TearFlags & TearFlags.TEAR_BOUNCE ~= 0
                    and ball.TearFlags & TearFlags.TEAR_CONFUSION ~= 0 then
                    flagged = flagged + 1
                end
                if math.abs(ball.CollisionDamage - player.Damage * 3) < 0.05 then
                    strong = strong + 1
                end
            end
            record("baseball_mitt_return_flags", #balls == 2 and flagged == 2 and strong == 2,
                "balls=" .. #balls .. " flagged=" .. flagged .. " strong=" .. strong
                    .. " damage=" .. detailNumber(player.Damage) .. " age=" .. age())
            removeEntitiesByType(EntityType.ENTITY_TEAR)
            removeCollectible(player, ids.baseballMitt)
            enter("algiz_setup")
        end
    -- EX-406: Welcome Mat must not corrupt the mod's shared zero vector -----------------------
    elseif state == "alias_setup" and age() >= 3 then
        removeActiveEnemies()
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        removeCollectible(player, ids.welcomeMat)
        removeCollectible(player, ids.ominousLantern)
        player:AddCollectible(ids.welcomeMat, 0, false)
        player:AddCollectible(ids.ominousLantern, 0, false)
        enter("alias_room")
        Isaac.ExecuteCommand("goto s.secret.1")
    elseif state == "alias_room" and age() >= 20 then
        local room = game:GetRoom()
        local center = room:GetCenterPos()
        local ballPos = center + Vector(-120, 0)
        local lanternPos = center + Vector(120, 0)
        player:GetData().gcbAliasEntry = Vector(player.Position.X, player.Position.Y)
        player:GetData().gcbAliasNearDelay = player.MaxFireDelay
        player:GetData().gcbAliasShape = room:GetRoomShape()
        aliasBall = player:FireTear(ballPos, Vector(0, 0), false, true, false):ToTear()
        aliasBall:ChangeVariant(ids.baseballVariant)
        aliasLantern = Isaac.Spawn(EntityType.ENTITY_TEAR, ids.lanternTearVariant, 0,
            lanternPos, Vector(0, 0), player):ToTear()
        for _, pair in ipairs({ { aliasBall, ballPos }, { aliasLantern, lanternPos } }) do
            local tear = pair[1]
            tear.Position = pair[2]
            tear.Velocity = Vector(0, 0)
            tear.GridCollisionClass = GridCollisionClass.COLLISION_NONE
            tear.FallingSpeed = 0
            tear.FallingAcceleration = 0
        end
        aliasBallDeath = nil
        aliasLanternDeath = nil
        enter("alias_kill")
    elseif state == "alias_kill" then
        if aliasBallDeath and aliasLanternDeath then
            enter("alias_check")
        elseif age() >= 10 then
            record("welcome_mat_poof_at_rest", false,
                "ball_killed=" .. tostring(aliasBallDeath ~= nil))
            record("welcome_mat_flame_at_rest", false,
                "lantern_killed=" .. tostring(aliasLanternDeath ~= nil))
            aliasMoveAway(player)
            enter("alias_far")
        end
    elseif state == "alias_check" and age() >= 3 then
        local hit, hitDistance = nearestEntity(ids.baseballHitType, ids.baseballHitVariant,
            aliasBallDeath)
        local hitSpeed = hit and hit.Velocity:Length() or -1
        record("welcome_mat_poof_at_rest", hit ~= nil and hitDistance < 8 and hitSpeed < 0.5,
            "found=" .. tostring(hit ~= nil)
                .. " distance=" .. detailNumber(hit and hitDistance or nil)
                .. " speed=" .. detailNumber(hitSpeed)
                .. " shape=" .. detailNumber(player:GetData().gcbAliasShape))
        local flame, flameDistance = nearestEntity(EntityType.ENTITY_EFFECT, ids.lanternFireVariant,
            aliasLanternDeath)
        local flameSpeed = flame and flame.Velocity:Length() or -1
        record("welcome_mat_flame_at_rest", flame ~= nil and flameDistance < 8 and flameSpeed < 0.5,
            "found=" .. tostring(flame ~= nil)
                .. " distance=" .. detailNumber(flame and flameDistance or nil)
                .. " speed=" .. detailNumber(flameSpeed))
        aliasMoveAway(player)
        enter("alias_far")
    elseif state == "alias_far" and age() >= 3 then
        local entry = player:GetData().gcbAliasEntry
        local nearDelay = player:GetData().gcbAliasNearDelay
        record("welcome_mat_bonus_kept",
            nearDelay ~= nil and player.MaxFireDelay - nearDelay == 3,
            "near_delay=" .. detailNumber(nearDelay)
                .. " far_delay=" .. detailNumber(player.MaxFireDelay)
                .. " entry=" .. (entry and (detailNumber(entry.X) .. "," .. detailNumber(entry.Y)) or "nil"))
        removeEntitiesByTypeVariant(ids.baseballHitType, ids.baseballHitVariant)
        removeEntitiesByTypeVariant(EntityType.ENTITY_EFFECT, ids.lanternFireVariant)
        removeEntitiesByType(EntityType.ENTITY_TEAR)
        removeCollectible(player, ids.welcomeMat)
        removeCollectible(player, ids.ominousLantern)
        aliasBall = nil
        aliasLantern = nil
        enter("mat_setup")
    -- EX-412: Welcome Mat floor boundary ----------------------------------------------------------
    elseif state == "mat_setup" and age() >= 3 then
        removeActiveEnemies()
        removeCollectible(player, ids.welcomeMat)
        removeEntitiesByType(ids.welcomeMatType)
        player:AddCollectible(ids.welcomeMat, 0, false)
        matTrace = ""
        enter("mat_corner")
        Isaac.ExecuteCommand("goto s.treasure.1")
    elseif state == "mat_corner" and age() >= 60 then
        record("welcome_mat_floor_start", false, "room_transition=timeout")
        record("welcome_mat_next_room", false, "room_transition=timeout")
        removeCollectible(player, ids.welcomeMat)
        enter("run_restart_setup")
    elseif state == "mat_corner_room" and age() >= 15 then
        local stage = game:GetLevel():GetStage()
        player:GetData().gcbMatStageBefore = stage
        enter("mat_floor_check")
        Isaac.ExecuteCommand("stage " .. tostring(stage % 6 + 1))
    elseif state == "mat_floor_check" and age() >= 20 then
        player:GetData().gcbMatStartDelay = player.MaxFireDelay
        player:GetData().gcbMatStartPos = Vector(player.Position.X, player.Position.Y)
        player.Position = player.Position + Vector(200, 0)
        player.Velocity = Vector(0, 0)
        enter("mat_floor_far")
    elseif state == "mat_floor_far" and age() >= 3 then
        local startDelay = player:GetData().gcbMatStartDelay
        local startPos = player:GetData().gcbMatStartPos
        local stage = game:GetLevel():GetStage()
        record("welcome_mat_floor_start",
            stage ~= player:GetData().gcbMatStageBefore and startDelay ~= nil
                and math.abs(player.MaxFireDelay - startDelay) < 0.01,
            "stage=" .. stage .. " trace=" .. matTrace
                .. " start_delay=" .. detailNumber(startDelay)
                .. " far_delay=" .. detailNumber(player.MaxFireDelay)
                .. " start_pos=" .. (startPos and (detailNumber(startPos.X) .. "," .. detailNumber(startPos.Y)) or "nil"))
        enter("mat_next_room")
        Isaac.ExecuteCommand("goto s.secret.1")
    elseif state == "mat_next_room" and age() >= 20 then
        player:GetData().gcbMatNearDelay = player.MaxFireDelay
        player:GetData().gcbMatNearPos = Vector(player.Position.X, player.Position.Y)
        player.Position = game:GetRoom():GetCenterPos() + Vector(170, 0)
        player.Velocity = Vector(0, 0)
        enter("mat_next_far")
    elseif state == "mat_next_far" and age() >= 3 then
        local nearDelay = player:GetData().gcbMatNearDelay
        local bonus = nearDelay and (player.MaxFireDelay - nearDelay) or 0
        local nearPos = player:GetData().gcbMatNearPos
        record("welcome_mat_next_room", bonus == 3,
            "trace=" .. matTrace .. " bonus=" .. detailNumber(bonus)
                .. " near_pos=" .. (nearPos and (detailNumber(nearPos.X) .. "," .. detailNumber(nearPos.Y)) or "nil"))
        removeCollectible(player, ids.welcomeMat)
        enter("run_restart_setup")
    -- C3: a second run in the same process starts from base stats (must be the LAST block) -------
    elseif state == "run_restart_setup" and age() >= 3 then
        clearPlayerHealth(player, 12, 12)
        player:AddCollectible(ids.forbiddenFruit, 0, false)
        player:UseActiveItem(ids.forbiddenFruit, false, false, false, false)
        removeCollectible(player, ids.forbiddenFruit)
        player:AddCollectible(ids.tragicMushroom, 0, false)
        player:UseActiveItem(ids.tragicMushroom, false, false, false, false)
        removeCollectible(player, ids.tragicMushroom)
        enter("run_restart_go")
    elseif state == "run_restart_go" and age() >= 3 then
        runBeforeRestart = statSnapshot(player)
        enter("run_restart_requested")
        Isaac.ExecuteCommand("restart 0")
    elseif state == "run_restart_check" and age() >= 5 then
        local now = statSnapshot(player)
        local boosted = runBaseline ~= nil and runBeforeRestart ~= nil
            and statsDiffer(runBaseline, runBeforeRestart)
        record("new_run_starts_with_base_stats",
            boosted and not statsDiffer(runBaseline, now),
            "player_type=" .. player:GetPlayerType()
                .. " room_frame=" .. game:GetRoom():GetFrameCount()
                .. " baseline={" .. statDetail(runBaseline) .. "}"
                .. " previous_run={" .. statDetail(runBeforeRestart) .. "}"
                .. " new_run={" .. statDetail(now) .. "}")
        finish()
    elseif state == "quit" and age() >= 5 then
        state = "exiting"
        Isaac.ExecuteCommand("quit")
    end
end

function suite:onNpcUpdate(npc)
    if state == "lovely_check" and lovelyDecoy
        and npc.InitSeed == lovelyDecoy.InitSeed then
        npc.State = 1
        npc.Velocity = Vector(0, 0)
        return true
    end
end

function suite:onHeadcaseUpdate(npc)
    if state ~= "headcase_wait" or npc.Variant ~= ids.headcaseVariant then return end
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == EntityType.ENTITY_TEAR
            and entity:GetData().IsExodusLobbed == true then
            local player = Isaac.GetPlayer(0)
            headcaseLob = entity:ToTear()
            player:GetData().gcbHeadcaseHealth = player:GetHearts()
            entity.Position = Vector(player.Position.X, player.Position.Y)
            entity.Velocity = Vector(0, 0)
            headcaseLob.Height = 4
            headcaseLob.FallingSpeed = 0
            headcaseLob.FallingAcceleration = 0
            if headcase and headcase:Exists() then headcase:Remove() end
            enter("headcase_check")
            return
        end
    end
end

function suite:onTearUpdate(tear)
    if state == "deja_arm" and dejaTear
        and tear.InitSeed == dejaTear.InitSeed and tear.FrameCount >= 1 then
        tear:Die()
        enter("deja_check")
    elseif state == "deja_normal_arm" and dejaTear
        and tear.InitSeed == dejaTear.InitSeed and tear.FrameCount >= 1 then
        tear:Die()
        enter("deja_normal_check")
    elseif state == "baseball_kill_arm" and baseballTear
        and tear.InitSeed == baseballTear.InitSeed then
        tear:Die()
        enter("baseball_hit_check")
    elseif state == "alias_kill" and aliasBall and not aliasBallDeath
        and tear.InitSeed == aliasBall.InitSeed and tear.FrameCount >= 1 then
        aliasBallDeath = Vector(tear.Position.X, tear.Position.Y)
        tear:Die()
    elseif state == "alias_kill" and aliasLantern and not aliasLanternDeath
        and tear.InitSeed == aliasLantern.InitSeed and tear.FrameCount >= 1 then
        aliasLanternDeath = Vector(tear.Position.X, tear.Position.Y)
        tear:Die()
    elseif state == "headcase_wait" and tear:GetData().IsExodusLobbed == true then
        local player = Isaac.GetPlayer(0)
        headcaseLob = tear
        player:GetData().gcbHeadcaseHealth = player:GetHearts()
        if headcase and headcase:Exists() then headcase:Remove() end
        tear.Position = Vector(player.Position.X, player.Position.Y)
        tear.Velocity = Vector(0, 0)
        tear.Height = 4
        tear.FallingSpeed = 0
        tear.FallingAcceleration = 0
        enter("headcase_check")
    end
end

function suite:onUseCard(...)
    useCardArgs = select("#", ...)
end

function suite:onCreepInit(effect)
    if state == "scissors_trail" then scissorsCreep = scissorsCreep + 1 end
end

function suite:onNewRoom()
    if state == "mat_corner" then
        local player = Isaac.GetPlayer(0)
        player.Position = game:GetRoom():GetCenterPos() + Vector(-200, -100)
        player.Velocity = Vector(0, 0)
        enter("mat_corner_room")
    end
    if state == "mat_floor_check" or state == "mat_next_room" then
        matTrace = matTrace .. "R"
    end
    if state == "mat_next_room" then
        local player = Isaac.GetPlayer(0)
        player.Position = game:GetRoom():GetCenterPos() + Vector(-170, 0)
        player.Velocity = Vector(0, 0)
    end
end

function suite:onNewLevel()
    if state == "mat_floor_check" or state == "mat_next_room" then
        matTrace = matTrace .. "L"
    end
end

function suite:onUpdate()
    if state == "idle" or state == "exiting" or state == "run_restart_requested" then return end
    local ok, err = pcall(runStep)
    if not ok then fatal(err) end
end

function suite:onInputAction(entity, inputHook, buttonAction)
    if not lanternPressArmed or buttonAction ~= ButtonAction.ACTION_ITEM then return nil end
    if entity ~= nil and entity.Type ~= EntityType.ENTITY_PLAYER then return nil end
    if inputHook == InputHook.GET_ACTION_VALUE then return 1.0 end
    return true
end

function suite:onLanternUse()
    lanternUses = lanternUses + 1
    lanternUseFrame = game:GetFrameCount()
    lanternUseCharges[#lanternUseCharges + 1] = Isaac.GetPlayer(0):GetActiveCharge()
    lanternPressArmed = false
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, suite.onGameStarted)
suite:AddCallback(ModCallbacks.MC_POST_UPDATE, suite.onUpdate)
suite:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, suite.onEntityDamage)
suite:AddCallback(ModCallbacks.MC_PRE_NPC_UPDATE, suite.onNpcUpdate, EntityType.ENTITY_SHOPKEEPER)
suite:AddCallback(ModCallbacks.MC_NPC_UPDATE, suite.onHeadcaseUpdate, ids.headcaseType)
suite:AddCallback(ModCallbacks.MC_POST_TEAR_UPDATE, suite.onTearUpdate)
suite:AddCallback(ModCallbacks.MC_INPUT_ACTION, suite.onInputAction)
suite:AddCallback(ModCallbacks.MC_USE_ITEM, suite.onLanternUse, ids.ominousLantern)
suite:AddCallback(ModCallbacks.MC_USE_CARD, suite.onUseCard)
suite:AddCallback(ModCallbacks.MC_POST_EFFECT_INIT, suite.onCreepInit, EffectVariant.PLAYER_CREEP_RED)
suite:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, suite.onNewRoom)
suite:AddCallback(ModCallbacks.MC_POST_NEW_LEVEL, suite.onNewLevel)
