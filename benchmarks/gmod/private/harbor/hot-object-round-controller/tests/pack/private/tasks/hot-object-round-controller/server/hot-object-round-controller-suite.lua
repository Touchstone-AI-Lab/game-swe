local nonce = "__RHENIUM_NONCE__"
local run_id = "__RHENIUM_RUN_ID__"
local build = "__RHENIUM_SERVER_BUILD__"
local phase = "__RHENIUM_PHASE__"
local expected = "__RHENIUM_STATE_HASH__"
local suite_id = "__RHENIUM_SUITE_ID__"
local namespace = "__RHENIUM_RUNTIME_NAMESPACE__"
local version = "__RHENIUM_TASK_VERSION__"
local data_dir = "__RHENIUM_DATA_DIRECTORY__"
local state_path = "__RHENIUM_STATE_PATH__"
local evidence_path = "__RHENIUM_EVIDENCE_PATH__"

local groups = {
    "physical-touch", "three-bot", "lifecycle", "variants",
    "deadline", "exactly-once", "persistence", "cleanup",
}
local good, assertions, observations = {}, {}, {}
for _, group in ipairs(groups) do good[group] = true end
local function check(group, name, value)
    assertions[#assertions + 1] = { group = group, name = name, passed = value and true or false }
    if not value then good[group] = false end
end
local function finish(raw, input)
    local cases, status = {}, "passed"
    for _, group in ipairs(groups) do
        cases[#cases + 1] = { name = group, passed = good[group], message = good[group] and "ok" or "failed" }
        if not good[group] then status = "failed" end
    end
    local evidence_raw = util.TableToJSON({
        runId = run_id, phase = phase, suiteId = suite_id,
        runtimeNamespace = namespace, taskVersion = version,
        assertions = assertions, observations = observations,
    }, false)
    file.Write(evidence_path, evidence_raw)
    local payload = {
        runId = run_id, phase = phase, serverBuild = build,
        suiteId = suite_id, runtimeNamespace = namespace, taskVersion = version,
        status = status, cases = cases, evidenceHash = util.SHA256(evidence_raw),
    }
    if phase == "A" then payload.stateHash = util.SHA256(raw) else payload.inputHash = input end
    print("@@RHENIUM_GMOD@@" .. nonce .. ":" .. util.TableToJSON(payload, false) .. "@@RHENIUM_END@@")
    engine.CloseServer()
end
local function bots()
    return {
        player.CreateNextBot("Rhenium Hot A"),
        player.CreateNextBot("Rhenium Hot B"),
        player.CreateNextBot("Rhenium Hot C"),
    }
end
local function bind_players(server, list)
    for index, bot in ipairs(list) do
        check("three-bot", "Bot " .. index .. " is a real valid Player", IsValid(bot) and bot:IsPlayer() and bot:IsBot())
        if IsValid(bot) then server.BindPlayer(bot, string.char(64 + index), 1) end
    end
end
local function clean(server, list, trigger, original_start, original_touch, raw, input)
    server.Shutdown()
    timer.Simple(.05, function()
        check("cleanup", "submission Timer is removed", not timer.Exists(server.TimerName))
        check("cleanup", "submission lifecycle Hook is removed",
            not ((hook.GetTable().PlayerDeath or {})[server.HookPrefix .. ".Death"]))
        if trigger then
            check("cleanup", "bound entity callbacks are restored exactly",
                trigger.StartTouch == original_start and trigger.Touch == original_touch)
            if IsValid(trigger) then trigger:Remove() end
        end
        for _, bot in ipairs(list) do if IsValid(bot) then bot:Kick("done") end end
        finish(raw, input)
    end)
end

hook.Add("InitPostEntity", "RheniumHotPrivate", function()
    hook.Remove("InitPostEntity", "RheniumHotPrivate")
    timer.Simple(.2, function()
        file.CreateDir(data_dir)
        local raw, input, state = nil, "", nil
        if phase == "B" then
            raw = file.Read(state_path, "DATA")
            input = raw and util.SHA256(raw) or ""
            state = raw and util.JSONToTable(raw) or nil
            check("persistence", "Phase B reads exact Phase A state", raw ~= nil and input == expected)
        end
        local list = bots()
        local Server = include("rhenium_hot_object_round/server.lua")
        Server.Install({ object_id = "hot:1", object_revision = 1, state = state })
        bind_players(Server, list)

        if phase == "A" then
            local callbacks = { start = 0, touch = 0 }
            local definition = { Type = "anim", Base = "base_anim" }
            function definition:Initialize()
                self:SetMoveType(MOVETYPE_NONE)
                self:SetSolid(SOLID_BBOX)
                self:SetCollisionBounds(Vector(-48, -48, 0), Vector(48, 48, 96))
                self:SetTrigger(true)
                self:SetNoDraw(true)
            end
            function definition:StartTouch() callbacks.start = callbacks.start + 1 end
            function definition:Touch() callbacks.touch = callbacks.touch + 1 end
            scripted_ents.Register(definition, "rhenium_hot_player_trigger")
            local trigger = ents.Create("rhenium_hot_player_trigger")
            trigger:SetPos(Vector(450, 0, 64))
            trigger:Spawn()
            local original_start, original_touch = trigger.StartTouch, trigger.Touch
            check("physical-touch", "hot object is bound once", Server.BindObject(trigger, "hot:1", 1))
            check("physical-touch", "duplicate BindObject is rejected", not Server.BindObject(trigger, "hot:1", 1))
            for index, bot in ipairs(list) do
                if IsValid(bot) then bot:SetPos(Vector(650 + index * 80, 0, 64)) end
            end
            local deadline = CurTime() + 4
            assert(Server.StartRound("start", "round:infectious", "infectious", list, list[1], deadline))
            timer.Simple(.2, function()
                if IsValid(list[2]) then list[2]:SetPos(Vector(450, 0, 64)) end
            end)
            local waited = 0
            timer.Create("RheniumHotPrivate.WaitTouch", .05, 50, function()
                waited = waited + 1
                local snapshot = Server.Snapshot()
                if snapshot.holder == "B" or waited == 50 then
                    timer.Remove("RheniumHotPrivate.WaitTouch")
                    check("physical-touch", "engine Player StartTouch/Touch changes holder",
                        snapshot.holder == "B" and callbacks.start >= 1 and callbacks.touch >= 1)
                    check("variants", "infectious physical touch records infection",
                        snapshot.players and snapshot.players.B and snapshot.players.B.infected
                            or snapshot.player_rows and snapshot.player_rows[2] and snapshot.player_rows[2].infected)
                    if IsValid(list[2]) then list[2]:Kill() end
                    timer.Simple(.2, function()
                        local after_death = Server.Snapshot()
                        check("lifecycle", "real Bot Kill triggers PlayerDeath successor", after_death.holder == "A")
                        if IsValid(list[2]) then list[2]:Spawn() end
                        timer.Simple(.2, function()
                            local after_spawn = Server.Snapshot()
                            local revision = after_spawn.players and after_spawn.players.B.revision
                                or after_spawn.player_rows and after_spawn.player_rows[2].revision
                            check("lifecycle", "real Bot Spawn triggers revision increment", revision == 2)
                            if IsValid(list[2]) then
                                list[2]:SetPos(Vector(700, 0, 64))
                                timer.Simple(.1, function()
                                    if IsValid(list[2]) then list[2]:SetPos(Vector(450, 0, 64)) end
                                end)
                            end
                            timer.Simple(.35, function()
                                local after_touch = Server.Snapshot()
                                check("lifecycle", "physical touch uses new revision", after_touch.holder == "B")
                                if IsValid(list[2]) then list[2]:Kick("lifecycle") end
                                timer.Simple(.2, function()
                                    local after_disconnect = Server.Snapshot()
                                    check("lifecycle", "real Bot Kick triggers PlayerDisconnected successor",
                                        after_disconnect.holder == "A")
                                    local remaining = math.max(0, deadline - CurTime() + .15)
                                    timer.Simple(remaining, function()
                                        local final = Server.Snapshot()
                                        check("deadline", "fixed deadline reaches finished", final.status == "finished")
                                        check("exactly-once", "deadline settles exactly once",
                                            final.settlements == 1 and final.result ~= nil)
                                        check("variants", "infectious excludes infected B from winners",
                                            final.result and not table.HasValue(final.result.winners or {}, "B"))
                                        observations.phaseA = {
                                            audit = final.audit, players = final.players or final.player_rows,
                                            result = final.result, physicalCallbacks = callbacks,
                                        }
                                        raw = util.TableToJSON(Server.Save(), false)
                                        file.Write(state_path, raw)
                                        check("persistence", "finished lifecycle state written",
                                            file.Read(state_path, "DATA") == raw)
                                        clean(Server, list, trigger, original_start, original_touch, raw, input)
                                    end)
                                end)
                            end)
                        end)
                    end)
                end
            end)
        else
            local restored = Server.Snapshot()
            check("persistence", "infectious result and lifecycle audit restore",
                restored.result and restored.result.variant == "infectious" and #restored.audit >= 6)
            check("exactly-once", "restart does not repeat settlement", restored.settlements == 1)
            observations.restored = { audit = restored.audit, result = restored.result }
            Server.Shutdown()
            Server.Install({ object_id = "hot:1", object_revision = 1 })
            bind_players(Server, list)
            local deadline = CurTime() + .35
            assert(Server.StartRound("start:exploding", "round:exploding", "exploding", list, list[1], deadline))
            timer.Simple(.45, function()
                local exploding = Server.Snapshot()
                check("variants", "exploding settles without infecting survivors",
                    exploding.result and exploding.result.variant == "exploding"
                        and #exploding.result.winners == 2)
                check("deadline", "fresh exploding round reaches its deadline", exploding.status == "finished")
                check("physical-touch", "physical touch evidence is confined to Phase A", true)
                check("lifecycle", "Phase A real lifecycle evidence restored", restored.audit and #restored.audit >= 6)
                observations.exploding = { result = exploding.result, players = exploding.players or exploding.player_rows }
                clean(Server, list, nil, nil, nil, raw, input)
            end)
        end
    end)
end)
