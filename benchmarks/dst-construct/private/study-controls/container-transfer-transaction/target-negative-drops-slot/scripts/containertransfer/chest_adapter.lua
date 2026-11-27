-- Adapter between the pure transaction and base-game `container` components.
--
-- Strategy: items are handled by description, never by entity identity. What
-- `remove` takes out of the source is destroyed after it has been described,
-- and `add` spawns fresh base-game items from the descriptions. A reload can
-- therefore always rebuild either container from its persisted snapshot,
-- because no step depends on an entity that only lived in memory.

local function stack_of(item)
    local stackable = item.components.stackable
    return stackable ~= nil and stackable:StackSize() or 1
end

local function describe_item(item, slot)
    local perishable = item.components.perishable
    local finiteuses = item.components.finiteuses
    return {
        slot = slot,
        prefab = item.prefab,
        count = stack_of(item),
        perish_percent = perishable ~= nil and perishable:GetPercent() or nil,
        finite_uses_percent = finiteuses ~= nil and finiteuses:GetPercent() or nil,
    }
end

local function apply_metadata(item, row)
    if item.components.perishable ~= nil and type(row.perish_percent) == "number" then
        item.components.perishable:SetPercent(row.perish_percent)
    end
    if item.components.finiteuses ~= nil and type(row.finite_uses_percent) == "number" then
        item.components.finiteuses:SetPercent(row.finite_uses_percent)
    end
end

-- resolve(stable_id) -> container component or nil
-- scratch is a list owned by the world component; every entity that exists
-- only for the duration of one adapter call is registered there so the
-- component can clean it up if it is removed mid-call.
local function MakeChestAdapter(resolve, scratch)
    local adapter = {}

    local function hold(entity)
        scratch[#scratch + 1] = entity
        return entity
    end

    local function release(entity)
        for index = #scratch, 1, -1 do
            if scratch[index] == entity then
                table.remove(scratch, index)
            end
        end
        if entity:IsValid() then
            entity:Remove()
        end
    end

    local function forget(entity)
        for index = #scratch, 1, -1 do
            if scratch[index] == entity then
                table.remove(scratch, index)
            end
        end
    end

    -- Largest stack the prefab supports, learned from a short-lived probe.
    local function stack_limit(prefab)
        local probe = SpawnPrefab(prefab)
        if probe == nil then
            return 0
        end
        hold(probe)
        local limit = 1
        if probe.components.inventoryitem == nil then
            limit = 0
        elseif probe.components.stackable ~= nil then
            limit = probe.components.stackable.maxsize or 1
        end
        release(probe)
        return limit
    end

    function adapter:snapshot(stable_id)
        local rows = {}
        local container = resolve(stable_id)
        if container == nil then
            return rows
        end
        for slot = 1, container:GetNumSlots() do
            local item = container:GetItemInSlot(slot)
            if item ~= nil then
                rows[#rows + 1] = describe_item(item, slot)
            end
        end
        return rows
    end

    function adapter:capacity(stable_id, prefab)
        local container = resolve(stable_id)
        if container == nil then
            return 0
        end
        local limit = stack_limit(prefab)
        if limit <= 0 then
            return 0
        end
        local total = 0
        for slot = 1, container:GetNumSlots() do
            local item = container:GetItemInSlot(slot)
            if item == nil then
                total = total + limit
            elseif item.prefab == prefab and container.acceptsstacks ~= false
                and item.components.stackable ~= nil then
                total = total + math.max(0, limit - stack_of(item))
            end
        end
        return total
    end

    function adapter:remove(stable_id, prefab, count)
        local container = resolve(stable_id)
        if container == nil then
            return nil, "unknown_container"
        end
        local taken, left = {}, count
        for slot = 1, container:GetNumSlots() do
            local item = left > 0 and container:GetItemInSlot(slot) or nil
            if item ~= nil and item.prefab == prefab then
                local piece
                if stack_of(item) <= left then
                    piece = container:RemoveItemBySlot(slot)
                else
                    piece = item.components.stackable:Get(left)
                end
                if piece == nil then
                    return nil, "remove_failed"
                end
                hold(piece)
                taken[#taken + 1] = describe_item(piece, slot)
                left = left - stack_of(piece)
                release(piece)
            end
        end
        if left > 0 then
            return nil, "source_short"
        end
        return taken
    end

    function adapter:add(stable_id, rows)
        local container = resolve(stable_id)
        if container == nil or type(rows) ~= "table" then
            return false, "unknown_container"
        end
        for index = 1, #rows do
            local row = rows[index]
            local limit = math.max(1, stack_limit(row.prefab))
            local left = row.count
            while left > 0 do
                local item = SpawnPrefab(row.prefab)
                if item == nil then
                    return false, "spawn_failed"
                end
                hold(item)
                local part = math.min(left, limit)
                if item.components.stackable ~= nil then
                    item.components.stackable:SetStackSize(part)
                else
                    part = 1
                end
                apply_metadata(item, row)
                -- drop_on_fail = false: a full container must not spill the
                -- item into the world.
                if not container:GiveItem(item, nil, nil, false) then
                    release(item)
                    return false, "give_failed"
                end
                forget(item)
                left = left - part
            end
        end
        return true
    end

    -- Converges the container onto the snapshot slot by slot. A stack of the
    -- right prefab is resized in place; anything else is replaced.
    function adapter:restore(stable_id, snapshot)
        local container = resolve(stable_id)
        if container == nil or type(snapshot) ~= "table" then
            return false, "unknown_container"
        end
        local wanted = {}
        for index = 1, #snapshot do
            wanted[snapshot[index].slot] = snapshot[index]
        end
        for slot = 1, container:GetNumSlots() do
            local row = wanted[slot]
            local item = container:GetItemInSlot(slot)
            local keep = item ~= nil and row ~= nil and item.prefab == row.prefab
            if keep and stack_of(item) ~= row.count then
                if item.components.stackable ~= nil then
                    item.components.stackable:SetStackSize(row.count)
                    apply_metadata(item, row)
                else
                    keep = false
                end
            end
            if not keep then
                if item ~= nil then
                    local old = container:RemoveItemBySlot(slot)
                    if old ~= nil then
                        release(hold(old))
                    end
                end
                if row ~= nil then
                    local fresh = SpawnPrefab(row.prefab)
                    if fresh == nil then
                        return false, "spawn_failed"
                    end
                    hold(fresh)
                    if fresh.components.stackable ~= nil then
                        fresh.components.stackable:SetStackSize(row.count)
                    end
                    apply_metadata(fresh, row)
                    if not container:GiveItem(fresh, slot, nil, false) then
                        release(fresh)
                        return false, "give_failed"
                    end
                    forget(fresh)
                end
            end
        end
        return true
    end

    return adapter
end

return MakeChestAdapter
