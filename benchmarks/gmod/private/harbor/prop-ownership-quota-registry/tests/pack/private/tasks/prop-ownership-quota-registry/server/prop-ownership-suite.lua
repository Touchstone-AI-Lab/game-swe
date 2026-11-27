local nonce = "__RHENIUM_NONCE__"
local run_id = "__RHENIUM_RUN_ID__"
local server_build = "__RHENIUM_SERVER_BUILD__"
local phase = "__RHENIUM_PHASE__"
local expected_state_hash = "__RHENIUM_STATE_HASH__"
local suite_id = "__RHENIUM_SUITE_ID__"
local runtime_namespace = "__RHENIUM_RUNTIME_NAMESPACE__"
local task_version = "__RHENIUM_TASK_VERSION__"
local data_directory = "__RHENIUM_DATA_DIRECTORY__"
local state_path = "__RHENIUM_STATE_PATH__"
local evidence_path = "__RHENIUM_EVIDENCE_PATH__"
local assertions = {}
local groups = { persistence = true, authority = true, quota = true, lifecycle = true, cleanup = true }

local function check(group, name, passed)
    local value = passed and true or false
    assertions[#assertions + 1] = { group = group, name = name, passed = value }
    groups[group] = groups[group] and value
    return value
end

local function all_passed()
    for _, item in ipairs(assertions) do if not item.passed then return false end end
    return #assertions > 0
end

local function emit(payload)
    print("@@RHENIUM_GMOD@@" .. nonce .. ":" .. util.TableToJSON(payload, false)
        .. "@@RHENIUM_END@@")
end

local function close_server()
    hook.Remove("InitPostEntity", "RheniumTaskPrivateSuite")
    timer.Simple(0, function() engine.CloseServer() end)
end

local function create_bot(logical_id)
    local bot = player.CreateNextBot("Rhenium Task " .. logical_id)
    check("lifecycle", logical_id .. " bot created", IsValid(bot) and bot:IsBot())
    return bot
end

local function create_prop(entity_id, revision, position)
    local entity = ents.Create("prop_physics")
    if IsValid(entity) then
        entity:SetModel("models/props_c17/oildrum001.mdl")
        entity:SetPos(position)
        entity:Spawn()
        entity:Activate()
    end
    check("lifecycle", entity_id .. " prop created",
        IsValid(entity) and entity:GetClass() == "prop_physics")
    return entity
end

local function compact_cases()
    return {
        { name = "persistence", passed = groups.persistence, message = "" },
        { name = "authority", passed = groups.authority, message = "" },
        { name = "quota", passed = groups.quota, message = "" },
        { name = "lifecycle", passed = groups.lifecycle, message = "" },
        { name = "cleanup", passed = groups.cleanup, message = "" },
    }
end

local function write_evidence(extra)
    local evidence = {
        runId = run_id, phase = phase, suiteId = suite_id, serverBuild = server_build,
        runtimeNamespace = runtime_namespace, taskVersion = task_version,
        assertions = assertions, extra = extra or {},
    }
    file.CreateDir("rhenium_runtime")
    file.CreateDir(data_directory)
    local encoded = util.TableToJSON(evidence, false)
    file.Write(evidence_path, encoded)
    local raw = file.Read(evidence_path, "DATA")
    return isstring(raw) and util.SHA256(raw) or string.rep("0", 64)
end

local function phase_a()
    local Server = include("rhenium_prop_registry/server.lua")
    check("persistence", "server module loaded", istable(Server))
    Server.Install({ max_props = 2, cleanup_delay = 5 })
    local a = create_bot("A")
    Server.BindPlayer(a, "A")
    local prop = create_prop("prop:persist", 1, Vector(0, 0, 64))
    Server.BindEntity(prop, "prop:persist", 1)
    local registered, code = Server.RegisterProp(a, prop, "persist-register")
    check("persistence", "phase a prop registered", registered and code == "registered")
    local state = Server.Save()
    local encoded = util.TableToJSON(state, false)
    file.CreateDir("rhenium_runtime")
    file.CreateDir(data_directory)
    file.Write(state_path, encoded)
    local raw = file.Read(state_path, "DATA")
    local state_hash = isstring(raw) and util.SHA256(raw) or string.rep("0", 64)
    check("persistence", "state raw round trip", raw == encoded)
    check("persistence", "state contains entity", istable(state) and #state.entities == 1)
    Server.Shutdown()
    if IsValid(prop) then prop:Remove() end
    if IsValid(a) then a:Kick("Rhenium Phase A complete") end
    local evidence_hash = write_evidence({ stateHash = state_hash })
    local passed = all_passed()
    emit({
        runId = run_id, phase = phase, status = passed and "passed" or "failed",
        cases = compact_cases(), suiteId = suite_id, serverBuild = server_build,
        runtimeNamespace = runtime_namespace, taskVersion = task_version,
        stateHash = state_hash, evidenceHash = evidence_hash, assertionCount = #assertions,
    })
    timer.Simple(0.5, close_server)
end

local function phase_b()
    local raw_state = file.Read(state_path, "DATA")
    local input_hash = isstring(raw_state) and util.SHA256(raw_state) or string.rep("0", 64)
    local state = isstring(raw_state) and util.JSONToTable(raw_state) or nil
    check("persistence", "phase a state readable", istable(state))
    check("persistence", "phase a state hash", input_hash == expected_state_hash)
    local Server = include("rhenium_prop_registry/server.lua")
    Server.Install({ max_props = 2, cleanup_delay = 5, state = state })
    local a = create_bot("A")
    local b = create_bot("B")
    Server.BindPlayer(a, "A")
    Server.BindPlayer(b, "B")

    local persistent = create_prop("prop:persist", 1, Vector(0, 0, 64))
    Server.BindEntity(persistent, "prop:persist", 1)
    local retry_ok, retry_code, retry_data = Server.RegisterProp(a, persistent, "persist-register")
    check("persistence", "register idempotency restored",
        retry_ok and retry_code == "registered" and retry_data.count == 1)
    local prefix = Server.HookPrefix
    local hook_table = hook.GetTable()
    local physgun = hook_table.PhysgunPickup[prefix .. ".PhysgunPickup"]
    local can_tool = hook_table.CanTool[prefix .. ".CanTool"]
    local can_property = hook_table.CanProperty[prefix .. ".CanProperty"]
    check("authority", "owner physgun allowed", physgun(a, persistent) == true)
    check("authority", "other physgun denied", physgun(b, persistent) == false)
    check("authority", "other tool denied", can_tool(b, { Entity = persistent }, "remover") == false)
    check("authority", "other property denied", can_property(b, "remover", persistent) == false)
    local forged = Server.HandleDeleteRequest(b, persistent, "forged-delete", "A")
    check("authority", "forged owner payload denied", forged == false and IsValid(persistent))

    local second = create_prop("prop:a2", 1, Vector(80, 0, 64))
    Server.BindEntity(second, "prop:a2", 1)
    check("quota", "second prop registered", Server.RegisterProp(a, second, "register-a2") == true)
    local third = create_prop("prop:a3", 1, Vector(160, 0, 64))
    Server.BindEntity(third, "prop:a3", 1)
    local third_ok, third_code = Server.RegisterProp(a, third, "register-a3")
    check("quota", "third prop rejected", not third_ok and third_code == "quota_exceeded")

    timer.Simple(0.25, function()
        check("quota", "third prop removed", not IsValid(third))
        if IsValid(second) then second:Remove() end
        timer.Simple(0.25, function()
            local after_remove = Server.Snapshot()
            local a_count = 0
            for _, owner in ipairs(after_remove.owners) do
                if owner.player_id == "A" then a_count = owner.count end
            end
            check("lifecycle", "EntityRemoved releases once", a_count == 1)
            if IsValid(second) then second:Remove() end

            local old = create_prop("prop:reuse", 1, Vector(240, 0, 64))
            Server.BindEntity(old, "prop:reuse", 1)
            check("lifecycle", "old generation registered",
                Server.RegisterProp(a, old, "register-old") == true)
            local old_index = old:EntIndex()
            old:Remove()
            timer.Simple(0.25, function()
                local replacement = create_prop("prop:reuse", 2, Vector(240, 0, 64))
                local replacement_index = replacement:EntIndex()
                Server.BindEntity(replacement, "prop:reuse", 2)
                check("lifecycle", "new generation registered",
                    Server.RegisterProp(b, replacement, "register-new") == true)
                check("lifecycle", "new live entity uses trusted logical revision",
                    not IsValid(old) and IsValid(replacement) and replacement ~= old
                        and type(old_index) == "number" and type(replacement_index) == "number"
                        and replacement.RheniumBenchmarkEntityRevision == 2)
                check("authority", "old owner denied on new revision", physgun(a, replacement) == false)
                check("authority", "new owner allowed", physgun(b, replacement) == true)

                b:Kick("Rhenium reconnect test")
                timer.Simple(1, function()
                    check("cleanup", "disconnect does not clean immediately", IsValid(replacement))
                    local b2 = create_bot("B reconnect")
                    Server.BindPlayer(b2, "B")
                    timer.Simple(4.5, function()
                        check("cleanup", "real Bot reconnect and trusted bind cancel cleanup", IsValid(replacement))
                        b2:Kick("Rhenium exact cleanup test")
                        timer.Simple(1, function()
                            check("cleanup", "second disconnect still delayed", IsValid(replacement))
                            timer.Simple(4.25, function()
                                check("cleanup", "five second deadline removes entity", not IsValid(replacement))
                                local final_snapshot = Server.Snapshot()
                                local stale = false
                                for _, item in ipairs(final_snapshot.entities) do
                                    if item.entity_id == "prop:reuse" then stale = true end
                                end
                                check("cleanup", "snapshot excludes invalid entity", not stale)
                                local delete_ok = false
                                if IsValid(persistent) then
                                    delete_ok = Server.HandleDeleteRequest(
                                        a, persistent, "owner-delete", "B"
                                    )
                                end
                                check("authority", "owner delete entry succeeds", delete_ok == true)
                                Server.Shutdown()
                                timer.Simple(0, function()
                                    local current = hook.GetTable()
                                    local hook_clean = true
                                    for _, event in ipairs({ "PhysgunPickup", "CanTool", "CanProperty", "EntityRemoved", "PlayerDisconnected", "PlayerInitialSpawn" }) do
                                        if current[event] and current[event][prefix .. "." .. event] then
                                            hook_clean = false
                                        end
                                    end
                                    check("cleanup", "shutdown removes hooks", hook_clean)
                                    check("cleanup", "shutdown removes timer", not timer.Exists(Server.TimerName))
                                    Server.Shutdown()
                                    if IsValid(a) then a:Kick("Rhenium task complete") end
                                    local evidence_hash = write_evidence({
                                        inputHash = input_hash,
                                        oldEntIndex = old_index,
                                        replacementEntIndex = replacement_index,
                                    })
                                    local passed = all_passed()
                                    emit({
                                        runId = run_id, phase = phase,
                                        status = passed and "passed" or "failed",
                                        cases = compact_cases(), suiteId = suite_id,
                                        serverBuild = server_build,
                                        runtimeNamespace = runtime_namespace,
                                        taskVersion = task_version, inputHash = input_hash,
                                        evidenceHash = evidence_hash, assertionCount = #assertions,
                                        oldEntIndex = old_index, replacementEntIndex = replacement_index,
                                    })
                                    timer.Simple(0.5, close_server)
                                end)
                            end)
                        end)
                    end)
                end)
            end)
        end)
    end)
end

hook.Add("InitPostEntity", "RheniumTaskPrivateSuite", function()
    timer.Simple(0.5, function()
        if phase == "A" then phase_a() elseif phase == "B" then phase_b() else close_server() end
    end)
end)
