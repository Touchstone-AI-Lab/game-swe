local TheWorldOrNil = function()
    return GLOBAL.rawget(GLOBAL, "TheWorld")
end

local MAX_FIELD = 96

local function plain_text(value)
    return GLOBAL.type(value) == "string" and #value > 0 and #value <= MAX_FIELD
end

-- The world owns the ledger, and only on the master simulation. Clients and
-- secondary shards' client sims never get the component.
AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return
    end
    if inst.components.campsupplyledger == nil then
        inst:AddComponent("campsupplyledger")
    end
end)

-- Wire format: (request_id, bundle_id). The sender is supplied by the server's
-- RPC layer. Anything else a client appends is dropped here and never read.
AddModRPCHandler("rhenium_supply", "claim", function(player, request_id, bundle_id)
    if player == nil or not plain_text(request_id) or not plain_text(bundle_id) then
        return
    end
    local world = TheWorldOrNil()
    if world == nil or not world.ismastersim then
        return
    end
    local desk = world.components.campsupplyledger
    if desk ~= nil then
        desk:Claim(player, request_id, bundle_id)
    end
end)

-- Convenience for clients (console or another mod): ask for a bundle by name.
-- A fresh request id is generated per call; callers that want retry safety can
-- pass their own id and reuse it.
local request_counter = 0
GLOBAL.CampSupplyRequest = function(bundle_id, request_id)
    if not plain_text(bundle_id) then
        return nil
    end
    if not plain_text(request_id) then
        request_counter = request_counter + 1
        request_id = "c" .. GLOBAL.tostring(GLOBAL.os.time()) .. "-" .. GLOBAL.tostring(request_counter)
    end
    SendModRPCToServer(GetModRPC("rhenium_supply", "claim"), request_id, bundle_id)
    return request_id
end
