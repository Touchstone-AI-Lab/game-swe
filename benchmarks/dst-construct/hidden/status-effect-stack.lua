local loaded, Stack = pcall(load_submission, "scripts/statuseffects/stack.lua")
if not loaded or type(Stack) ~= "table" then Stack = {} end
local cases = {}
local function expect(value, message) if not value then error(message or "expectation failed", 0) end end
local function run(name, body)
    local ok, message = pcall(body)
    cases[#cases + 1] = { name = name, passed = ok, message = ok and "ok" or tostring(message) }
end

local function effects()
    return {
        chill = { duration = 8, max_stacks = 3, policy = "refresh", tags = { "debuff", "cold" }, priority = 2, speed_mult = 0.5 },
        venom = { duration = 6, max_stacks = 2, policy = "independent", tags = { "debuff", "poison" }, priority = 3, tick_health = -2 },
        frenzy = { duration = 10, max_stacks = 2, policy = "extend", tags = { "buff" }, priority = 1, speed_mult = 1.25, damage_mult = 1.5 },
        regen = { duration = 4, max_stacks = 1, policy = "refresh", tags = { "buff", "heal" }, priority = 1, tick_health = 1 },
        curse = { duration = 20, max_stacks = 1, policy = "refresh", tags = { "debuff" }, priority = 3, damage_mult = 0.5 },
        bleed = { duration = 4, max_stacks = 3, policy = "refresh", tags = { "debuff" }, priority = 2, tick_health = -1.5 },
        hex = { duration = 12, max_stacks = 1, policy = "refresh", tags = { "debuff" }, priority = 2, speed_mult = 0.75 },
    }
end
local options = { extend_cap = 3, effects = effects() }

local function fresh(targets, custom)
    expect(type(Stack.new) == "function", "module must export Stack.new")
    local stack = Stack.new(custom or options)
    expect(type(stack) == "table", "Stack.new must return a manager")
    for _, id in ipairs(targets or { "a" }) do
        local added = stack:add_target(id, 0)
        expect(type(added) == "table" and added.ok == true and added.code == "tracked", "add_target failed")
    end
    return stack
end

local function rejected(result, code, label)
    expect(type(result) == "table", label .. ": result must be a table")
    expect(result.ok == false, label .. ": ok must be false")
    expect(result.code == code, label .. ": expected code " .. code .. ", got " .. tostring(result.code))
end

local function applied(result, code, stacks, expires_at, label)
    expect(type(result) == "table" and result.ok == true, label .. ": apply was not ok")
    expect(result.code == code, label .. ": expected code " .. code .. ", got " .. tostring(result.code))
    expect(result.stacks == stacks, label .. ": expected stacks " .. stacks .. ", got " .. tostring(result.stacks))
    expect(result.expires_at == expires_at, label .. ": expected expires_at " .. expires_at .. ", got " .. tostring(result.expires_at))
    return result
end

local function rows(stack, now)
    local snapshot = stack:snapshot(now)
    expect(type(snapshot) == "table", "snapshot must return a list")
    return snapshot
end

local function deep_copy(value, depth)
    depth = depth or 0
    expect(depth < 32, "saved data is too deep or cyclic")
    local kind = type(value)
    if kind == "string" or kind == "number" or kind == "boolean" then
        return value
    end
    expect(kind == "table", "saved data contains a " .. kind)
    expect(getmetatable(value) == nil, "saved data contains a metatable")
    local copy = {}
    for key, item in pairs(value) do
        expect(type(key) == "string" or type(key) == "number", "saved data has a non-plain key")
        copy[key] = deep_copy(item, depth + 1)
    end
    return copy
end

run("validation and request dedupe leave no side effects", function()
    expect(type(Stack.new) == "function", "module must export Stack.new")
    local s = Stack.new(options)
    expect(s:add_target("a", 5).ok == true)
    local nan = 0 / 0
    rejected(s:apply("r0", "a", "chill", nil, -1), "invalid_time", "negative time")
    rejected(s:apply("r0", "a", "chill", nil, nan), "invalid_time", "nan time")
    rejected(s:apply("r0", "a", "chill", nil, math.huge), "invalid_time", "infinite time")
    rejected(s:apply("r0", "a", "chill", nil, "6"), "invalid_time", "string time")
    rejected(s:apply("r0", "a", "chill", nil, nil), "invalid_time", "missing time")
    rejected(s:apply("r0", "a", "chill", nil, 4), "stale_time", "time behind the clock")
    rejected(s:apply("", "a", "chill", nil, 5), "invalid_argument", "empty request id")
    rejected(s:apply(7, "a", "chill", nil, 5), "invalid_argument", "numeric request id")
    rejected(s:apply("r1", "a", "chill", 42, 5), "invalid_argument", "numeric source id")
    rejected(s:apply("r2", "a", "nope", nil, 5), "unknown_effect", "unknown effect")
    rejected(s:apply("r3", "ghost", "chill", nil, 5), "unknown_target", "unknown target")
    rejected(s:apply("r4", "ghost", "nope", nil, 5), "unknown_effect", "unknown effect is reported before unknown target")
    expect(#rows(s, 5) == 0, "a rejected call created an instance")

    -- "r0" was only ever rejected for its time, so it is still unused.
    local first = applied(s:apply("r0", "a", "chill", "src", 5), "applied", 1, 13, "first apply")
    expect(first.target_id == "a" and first.effect_id == "chill" and type(first.seq) == "number")
    local retry = s:apply("r0", "a", "venom", nil, 6)
    applied(retry, "applied", 1, 13, "retry")
    expect(retry ~= first and retry.effect_id == "chill" and retry.seq == first.seq, "retry must copy the first result")
    retry.code = "mutated"
    applied(s:apply("r0", "a", "chill", nil, 6), "applied", 1, 13, "second retry")
    local snap = rows(s, 6)
    expect(#snap == 1 and snap[1].effect_id == "chill" and snap[1].stacks == 1, "retry had a side effect")
    expect(snap[1].target_id == "a" and snap[1].source_id == "src" and snap[1].seq == first.seq)
    expect(snap[1].applied_at == 5 and snap[1].expires_at == 13 and snap[1].remaining == 7)
    snap[1].stacks = 99
    snap[1] = nil
    expect(#rows(s, 6) == 1 and rows(s, 6)[1].stacks == 1, "snapshot must be a fresh copy")

    -- Failures reached after the dedupe step are recorded as well.
    expect(s:add_target("ghost", 6).ok == true)
    rejected(s:apply("r3", "ghost", "chill", nil, 6), "unknown_target", "recorded unknown target")
    rejected(s:apply("r2", "a", "chill", nil, 6), "unknown_effect", "recorded unknown effect")
    rejected(s:apply("r1", "a", "chill", nil, 6), "invalid_argument", "recorded invalid argument")
    expect(#rows(s, 6) == 1, "a recorded failure was re-executed")

    -- A call that passes the time check moves the clock even when rejected later.
    rejected(s:apply("", "a", "chill", nil, 9), "invalid_argument", "empty request id at 9")
    rejected(s:apply("r9", "a", "chill", nil, 8), "stale_time", "clock must have advanced to 9")
    applied(s:apply("r9", "a", "chill", nil, 9), "refreshed", 2, 17, "stale call must not be recorded")

    local removed = s:remove_target("a", 9)
    expect(removed.ok == true and removed.code == "removed" and removed.count == 1, "remove_target result")
    applied(s:apply("r0", "a", "chill", nil, 9), "applied", 1, 13, "history survives remove_target")
    rejected(s:apply("r10", "a", "chill", nil, 9), "unknown_target", "removed target")
    rejected(s:remove_target("a", 9), "unknown_target", "second remove_target")
    rejected(s:remove_target("a", 8), "stale_time", "stale remove_target")
    local no_rows, why = s:snapshot(8)
    expect(no_rows == nil and why == "stale_time", "stale snapshot must return nil, stale_time")
    rejected(s:add_target("", 9), "invalid_argument", "empty target id")
    expect(s:add_target("a", 10).ok == true)
    expect(#rows(s, 10) == 0, "re-added target must start empty")
    local aggregate = s:modifiers("a", 10)
    expect(aggregate.ok == true and aggregate.count == 0 and aggregate.speed_mult == 1)
end)

run("stacking policies honor caps and the exact expiry boundary", function()
    local s = fresh()
    local c1 = applied(s:apply("c1", "a", "chill", nil, 0), "applied", 1, 8, "c1")
    expect(c1.seq == 1, "the first instance of a manager has seq 1")
    local c2 = applied(s:apply("c2", "a", "chill", nil, 5), "refreshed", 2, 13, "c2")
    expect(c2.seq == c1.seq, "refresh must keep the instance")
    applied(s:apply("c3", "a", "chill", nil, 6), "refreshed", 3, 14, "c3")
    applied(s:apply("c4", "a", "chill", nil, 7), "refreshed", 3, 15, "c4 at max stacks")
    local live = s:modifiers("a", 14.5)
    expect(live.speed_mult == 0.125 and live.count == 1, "three chill stacks must be live at 14.5")
    local snap = rows(s, 14.5)
    expect(#snap == 1 and snap[1].applied_at == 0 and snap[1].remaining == 0.5 and snap[1].stacks == 3)
    local gone = s:modifiers("a", 15)
    expect(gone.speed_mult == 1 and gone.count == 0, "instance must be expired at now == expires_at")
    expect(#rows(s, 15) == 0, "expired instance listed")
    local c5 = applied(s:apply("c5", "a", "chill", nil, 15), "applied", 1, 23, "c5 after expiry")
    expect(c5.seq > c1.seq, "a new instance needs a new seq")

    local e = fresh(nil, { effects = effects() })
    applied(e:apply("f1", "a", "frenzy", nil, 0), "applied", 1, 10, "f1")
    applied(e:apply("f2", "a", "frenzy", nil, 4), "extended", 2, 20, "f2")
    applied(e:apply("f3", "a", "frenzy", nil, 4), "extended", 2, 30, "f3")
    applied(e:apply("f4", "a", "frenzy", nil, 5), "extended", 2, 35, "f4 capped at 3 * duration")
    expect(e:modifiers("a", 34.5).count == 1)
    applied(e:apply("f5", "a", "frenzy", nil, 35), "applied", 1, 45, "f5 after expiry")

    local capped = fresh(nil, { extend_cap = 2, effects = effects() })
    applied(capped:apply("f1", "a", "frenzy", nil, 0), "applied", 1, 10, "cap2 f1")
    applied(capped:apply("f2", "a", "frenzy", nil, 4), "extended", 2, 20, "cap2 f2")
    applied(capped:apply("f3", "a", "frenzy", nil, 4), "extended", 2, 24, "cap2 f3")

    local v = fresh()
    local v1 = applied(v:apply("v1", "a", "venom", nil, 0), "applied", 1, 6, "v1")
    local v2 = applied(v:apply("v2", "a", "venom", nil, 1), "stacked", 2, 7, "v2")
    local v3 = applied(v:apply("v3", "a", "venom", nil, 2), "replaced", 2, 8, "v3")
    expect(v1.seq < v2.seq and v2.seq < v3.seq, "seq must increase")
    snap = rows(v, 2)
    expect(#snap == 2 and snap[1].seq == v2.seq and snap[2].seq == v3.seq, "oldest instance must be replaced")
    expect(snap[1].stacks == 1 and snap[1].expires_at == 7 and snap[2].expires_at == 8)
    local v4 = applied(v:apply("v4", "a", "venom", nil, 7), "stacked", 2, 13, "v4 after v2 expired")
    snap = rows(v, 7)
    expect(#snap == 2 and snap[1].seq == v3.seq and snap[2].seq == v4.seq, "expired instance must not be replaced")
    applied(v:apply("v5", "a", "venom", nil, 13), "applied", 1, 19, "v5 after all expired")
end)

run("modifiers aggregate live stacks without any tick", function()
    local s = fresh({ "a", "b" })
    expect(s:apply("m1", "a", "chill", nil, 0).ok)
    expect(s:apply("m2", "a", "chill", nil, 1).ok)
    expect(s:apply("m3", "a", "frenzy", nil, 1).ok)
    expect(s:apply("m4", "a", "curse", nil, 1).ok)
    expect(s:apply("m5", "a", "venom", nil, 2).ok)
    expect(s:apply("m6", "a", "venom", nil, 2).ok)
    expect(s:apply("m7", "a", "regen", nil, 2).ok)
    expect(s:apply("m8", "b", "hex", nil, 2).ok)
    local function check(target, now, speed, damage, health, count)
        local m = s:modifiers(target, now)
        local label = target .. "@" .. now
        expect(type(m) == "table" and m.ok == true and m.code == "ok" and m.target_id == target, label .. ": result shape")
        expect(m.speed_mult == speed, label .. ": speed_mult " .. tostring(m.speed_mult))
        expect(m.damage_mult == damage, label .. ": damage_mult " .. tostring(m.damage_mult))
        expect(m.tick_health == health, label .. ": tick_health " .. tostring(m.tick_health))
        expect(m.count == count, label .. ": count " .. tostring(m.count))
        return m
    end
    local first = check("a", 3, 0.3125, 0.75, -3, 6)
    first.speed_mult = 99
    expect(s:add_target("a", 3).ok == true, "add_target of a known target must succeed")
    check("a", 3, 0.3125, 0.75, -3, 6)
    check("b", 3, 0.75, 1, 0, 1)
    check("a", 6, 0.3125, 0.75, -4, 5)
    check("a", 8, 0.3125, 0.75, 0, 3)
    check("a", 9, 1.25, 0.75, 0, 2)
    check("a", 11, 1, 0.5, 0, 1)
    check("a", 21, 1, 1, 0, 0)
    rejected(s:modifiers("nobody", 21), "unknown_target", "modifiers of unknown target")
    rejected(s:modifiers("a", 20), "stale_time", "stale modifiers")
    rejected(s:modifiers(5, 21), "invalid_argument", "numeric target id")
    expect(s:apply("m9", "b", "frenzy", nil, 21).ok)
    expect(s:apply("m10", "b", "frenzy", nil, 21).ok)
    check("b", 21, 1.5625, 2.25, 0, 1)
end)

run("tick accrual is exact and independent of tick frequency", function()
    local function play(extra_ticks)
        local s = fresh({ "a", "b", "c" })
        local totals, lists = {}, {}
        local function collect(now)
            local list, code = s:tick(now)
            expect(type(list) == "table", "tick must return a list, got " .. tostring(code))
            for index, delta in ipairs(list) do
                local key = delta.target_id .. "/" .. delta.effect_id
                expect(type(delta.amount) == "number" and delta.amount ~= 0, "zero amounts must be omitted")
                totals[key] = (totals[key] or 0) + delta.amount
                if index > 1 then
                    local before = list[index - 1]
                    expect(before.target_id < delta.target_id
                        or (before.target_id == delta.target_id and before.effect_id < delta.effect_id),
                        "tick rows must be ordered by target id then effect id")
                end
            end
            lists[#lists + 1] = { now = now, list = list }
            return list
        end
        local function maybe(now) if extra_ticks then collect(now) end end
        expect(s:apply("t1", "a", "bleed", nil, 0).ok and s:apply("t2", "a", "regen", nil, 0).ok)
        expect(s:apply("t3", "a", "chill", nil, 0).ok)
        expect(s:apply("t4", "b", "venom", nil, 0).ok and s:apply("t5", "c", "venom", nil, 0).ok)
        maybe(0.5); maybe(1)
        expect(s:apply("t6", "a", "venom", nil, 1).ok)
        expect(s:apply("t7", "a", "bleed", nil, 2).stacks == 2)
        expect(s:remove_target("c", 2).ok)
        maybe(2.5)
        expect(s:dispel("b", "poison", nil, 3).count == 1)
        maybe(3)
        expect(s:apply("t8", "b", "venom", nil, 4).ok and s:apply("t9", "b", "venom", nil, 4).ok)
        maybe(4.5)
        expect(s:apply("t10", "b", "venom", nil, 5).code == "replaced")
        maybe(6); maybe(7)
        local final = collect(12)
        expect(#collect(12) == 0, "a second tick at the same time must be empty")
        local stale, code = s:tick(11)
        expect(stale == nil and code == "stale_time", "stale tick must return nil, stale_time")
        stale, code = s:tick(-1)
        expect(stale == nil and code == "invalid_time", "invalid tick must return nil, invalid_time")
        return totals, lists, final
    end

    local totals, _, final = play(false)
    expect(#final == 4, "single tick must report four rows, got " .. #final)
    local want = { { "a", "bleed", -15 }, { "a", "regen", 4 }, { "a", "venom", -12 }, { "b", "venom", -32 } }
    for index, row in ipairs(want) do
        local got = final[index]
        expect(got.target_id == row[1] and got.effect_id == row[2], "row " .. index .. " is out of order")
        expect(got.amount == row[3], row[1] .. "/" .. row[2] .. " amount " .. tostring(got.amount))
    end
    expect(totals["c/venom"] == nil, "remove_target must drop unreported health changes")

    local frequent, lists = play(true)
    for _, row in ipairs(want) do
        local key = row[1] .. "/" .. row[2]
        expect(frequent[key] == row[3], key .. " depends on tick frequency: " .. tostring(frequent[key]))
    end
    expect(frequent["c/venom"] == -2, "c/venom reported before removal must be -2")
    local early = lists[1].list
    expect(#early == 4 and early[1].effect_id == "bleed" and early[1].amount == -0.75, "tick(0.5) bleed")
    expect(early[2].effect_id == "regen" and early[2].amount == 0.5, "tick(0.5) regen")
    expect(early[3].target_id == "b" and early[3].amount == -1 and early[4].target_id == "c", "tick(0.5) venom rows")
    for _, entry in ipairs(lists) do
        if entry.now > 2 then
            for _, delta in ipairs(entry.list) do
                expect(delta.target_id ~= "c", "removed target reported at " .. entry.now)
            end
        end
    end
end)

run("dispel orders by priority age effect id and sequence", function()
    local s = fresh({ "a" })
    local v1 = s:apply("d1", "a", "venom", nil, 0)
    local v2 = s:apply("d2", "a", "venom", nil, 0)
    local k = s:apply("d3", "a", "curse", nil, 0)
    local c = s:apply("d4", "a", "chill", nil, 0)
    local h = s:apply("d5", "a", "hex", nil, 3)
    expect(v1.ok and v2.ok and k.ok and c.ok and h.ok)
    expect(s:apply("d6", "a", "chill", nil, 4).stacks == 2)
    expect(s:apply("d7", "a", "frenzy", nil, 4).ok)
    rejected(s:dispel("a", "debuff", 0, 4), "invalid_argument", "zero max_count")
    rejected(s:dispel("a", "debuff", 1.5, 4), "invalid_argument", "fractional max_count")
    rejected(s:dispel("a", "debuff", -1, 4), "invalid_argument", "negative max_count")
    rejected(s:dispel("a", "debuff", "2", 4), "invalid_argument", "string max_count")
    rejected(s:dispel("a", "", 1, 4), "invalid_argument", "empty tag")
    rejected(s:dispel("zz", "debuff", 1, 4), "unknown_target", "unknown dispel target")
    rejected(s:dispel("a", "debuff", 1, 3), "stale_time", "stale dispel")
    expect(#rows(s, 4) == 6, "rejected dispel removed something")

    local first = s:dispel("a", "debuff", 2, 4)
    expect(first.ok == true and first.code == "dispelled" and first.count == 2 and #first.removed == 2, "first dispel result")
    expect(first.removed[1].effect_id == "curse" and first.removed[1].seq == k.seq, "equal priority and age must fall back to effect id")
    expect(first.removed[2].effect_id == "venom" and first.removed[2].seq == v1.seq, "equal effect id must fall back to seq")
    local second = s:dispel("a", "debuff", nil, 4)
    expect(second.count == 3 and #second.removed == 3, "nil max_count removes every match")
    expect(second.removed[1].seq == v2.seq, "priority 3 goes first")
    expect(second.removed[2].effect_id == "chill" and second.removed[2].stacks == 2, "refresh must keep applied_at, so chill is older than hex")
    expect(second.removed[3].effect_id == "hex" and second.removed[3].seq == h.seq)
    local snap = rows(s, 4)
    expect(#snap == 1 and snap[1].effect_id == "frenzy", "only the buff may remain")
    expect(s:modifiers("a", 4).speed_mult == 1.25)
    local none = s:dispel("a", "cold", 1, 4)
    expect(none.ok == true and none.code == "dispelled" and none.count == 0 and #none.removed == 0, "empty dispel")

    expect(s:apply("d8", "a", "venom", nil, 4).ok)
    expect(s:dispel("a", "poison", nil, 10).count == 0, "an expired instance must not be dispelled")

    expect(s:add_target("b", 10).ok)
    expect(s:apply("d9", "b", "hex", nil, 10).ok)
    local young = s:apply("d10", "b", "curse", nil, 11)
    local top = s:dispel("b", "debuff", 1, 11)
    expect(top.count == 1 and top.removed[1].seq == young.seq, "higher priority beats older age")
    snap = rows(s, 11)
    expect(#snap == 2 and snap[1].target_id == "a" and snap[1].effect_id == "frenzy", "snapshot rows are ordered by target id")
    expect(snap[2].target_id == "b" and snap[2].effect_id == "hex", "the older low-priority instance must remain")
end)

run("save load rebases time and keeps history and accrual cursor", function()
    expect(type(Stack.load) == "function", "module must export Stack.load")
    local s = fresh({ "a", "b" })
    local q1 = s:apply("q1", "a", "venom", nil, 0)
    local q2 = s:apply("q2", "a", "chill", nil, 2)
    local q3 = s:apply("q3", "a", "chill", "b", 4)
    local q4 = s:apply("q4", "b", "bleed", nil, 4)
    expect(q1.ok and q2.ok and q3.ok and q4.ok)
    local ticked = s:tick(5)
    expect(#ticked == 2 and ticked[1].amount == -10 and ticked[2].amount == -1.5, "tick(5) before save")
    expect(s:add_target("c", 5).ok)
    local q5 = s:apply("q5", "c", "regen", nil, 5)
    expect(q5.ok and s:remove_target("c", 6).ok)
    local stale, code = s:save(1)
    expect(stale == nil and code == "stale_time", "stale save must return nil, stale_time")
    local data = s:save(7)
    expect(type(data) == "table", "save must return a table")
    local copy = deep_copy(data)
    expect(s:dispel("a", "cold", nil, 7).count == 1)
    expect(s:apply("q6", "a", "curse", nil, 7).ok)

    local r = Stack.load(deep_copy(data), options, 100)
    expect(type(r) == "table", "load must return a manager")
    rejected(r:apply("zz", "a", "chill", nil, 99), "stale_time", "loaded clock must be 100")
    local snap = rows(r, 100)
    expect(#snap == 2, "loaded snapshot must hold two live instances, got " .. #snap)
    expect(snap[1].target_id == "a" and snap[1].effect_id == "chill" and snap[1].seq == q2.seq)
    expect(snap[1].stacks == 2 and snap[1].source_id == "b", "stacks and source must survive")
    expect(snap[1].expires_at == 105 and snap[1].remaining == 5 and snap[1].applied_at == 95, "chill must be rebased by 93")
    expect(snap[2].target_id == "b" and snap[2].effect_id == "bleed" and snap[2].seq == q4.seq)
    expect(snap[2].expires_at == 101 and snap[2].remaining == 1)

    local retry = applied(r:apply("q3", "a", "venom", nil, 100), "refreshed", 2, 12, "history is returned verbatim")
    expect(retry.effect_id == "chill" and retry.seq == q2.seq)
    local old = r:apply("q5", "c", "regen", nil, 100)
    expect(old.ok == true and old.code == "applied" and old.effect_id == "regen", "history of a removed target survives")
    rejected(r:apply("q7", "c", "regen", nil, 100), "unknown_target", "removed target stays removed")
    expect(#rows(r, 100) == 2, "retries after load had side effects")
    local fresh_instance = applied(r:apply("q6", "a", "curse", nil, 100), "applied", 1, 120, "q6 is new for the loaded manager")
    expect(fresh_instance.seq > q5.seq, "the seq counter must survive a reload")

    local list = r:tick(101)
    expect(#list == 2, "tick after load must report two rows, got " .. #list)
    expect(list[1].target_id == "a" and list[1].effect_id == "venom" and list[1].amount == -2, "unreported venom must survive")
    expect(list[2].target_id == "b" and list[2].effect_id == "bleed" and list[2].amount == -4.5, "bleed cursor must survive")
    expect(r:modifiers("a", 104.5).speed_mult == 0.25)
    local after = r:modifiers("a", 105)
    expect(after.speed_mult == 1 and after.damage_mult == 0.5 and after.count == 1)

    local reduced = Stack.load(copy, { effects = { chill = effects().chill } }, 50)
    snap = rows(reduced, 50)
    expect(#snap == 1 and snap[1].effect_id == "chill" and snap[1].expires_at == 55, "unknown effects must be dropped")
    expect(#reduced:tick(60) == 0, "health changes of dropped effects must be dropped")

    local empty = Stack.load(nil, options, 4)
    expect(type(empty) == "table" and #rows(empty, 4) == 0)
    rejected(empty:add_target("a", 3), "stale_time", "empty load must start at the supplied now")
    expect(empty:add_target("a", 4).ok == true)
end)

return { cases = cases }
