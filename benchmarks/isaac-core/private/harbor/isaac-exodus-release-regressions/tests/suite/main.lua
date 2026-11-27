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
        }) do
            if entityId <= 0 then error("missing lifecycle regression entity id") end
        end
        if ids.headcaseVariant < 0 then
            error("missing lifecycle regression entity variant")
        end
        player:AddCacheFlags(CacheFlag.CACHE_ALL)
        player:EvaluateItems()
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
            finish()
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

function suite:onUpdate()
    if state == "idle" or state == "exiting" then return end
    local ok, err = pcall(runStep)
    if not ok then fatal(err) end
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, suite.onGameStarted)
suite:AddCallback(ModCallbacks.MC_POST_UPDATE, suite.onUpdate)
suite:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, suite.onEntityDamage)
suite:AddCallback(ModCallbacks.MC_PRE_NPC_UPDATE, suite.onNpcUpdate, EntityType.ENTITY_SHOPKEEPER)
suite:AddCallback(ModCallbacks.MC_NPC_UPDATE, suite.onHeadcaseUpdate, ids.headcaseType)
suite:AddCallback(ModCallbacks.MC_POST_TEAR_UPDATE, suite.onTearUpdate)
