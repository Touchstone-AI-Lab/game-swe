-- The component tracks joining players by itself; modmain only attaches it
-- and wires the single player-facing RPC.

local RPC_NAMESPACE = "rhenium_statuseffects"

AddPrefabPostInit("world", function(inst)
    if inst.ismastersim and inst.components.statuseffects == nil then
        inst:AddComponent("statuseffects")
    end
end)

-- Self-cleanse only. `player` is supplied by the RPC framework; the component
-- resolves the target from player.userid and refuses tags off its whitelist.
AddModRPCHandler("rhenium_statuseffects", "cleanse", function(player, tag)
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim or player == nil or GLOBAL.type(tag) ~= "string" then
        return
    end
    local component = world.components.statuseffects
    if component ~= nil and GLOBAL.type(player.userid) == "string" then
        component:Cleanse(player, tag)
    end
end)
