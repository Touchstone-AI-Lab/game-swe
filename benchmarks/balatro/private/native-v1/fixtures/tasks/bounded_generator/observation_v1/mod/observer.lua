-- Observation only. Never invokes a business callback outside its engine caller.
local function pack(...) return {n=select('#',...),...} end
local frames, changed, errors, dropped = 0,0,0,0
local serial, origin, action_seq = 0,nil,0
local ids, objects, tracked, event_rows, rows, actions = {},{},{},{},{},{}
local function identity(card)
    if not card then return false end
    if not ids[card] then serial=serial+1;ids[card]=serial;objects[serial]=card end
    return ids[card]
end
local function safe(fn,...)
    local r=pack(pcall(fn,...))
    if not r[1] then errors=errors+1 end
    return unpack(r,2,r.n)
end
local function state_name()
    for k,v in pairs(G.STATES) do if G.STATE==v then return k end end
    return tostring(G.STATE)
end
local function small()
    return {frame=frames,time=G.TIMERS.TOTAL,state=state_name(),
        count=G.consumeables and #G.consumeables.cards or 0,
        capacity=G.consumeables and G.consumeables.config.card_limit or 0,
        buffer=G.GAME.consumeable_buffer or 0,use_lock=G.CONTROLLER.locks.use==true,
        locked=G.CONTROLLER.locked==true,stop_use=G.GAME.STOP_USE or 0}
end
local function log(kind,extra)
    if #rows>=256 then dropped=dropped+1;return end
    local row=small();row.kind=kind;row.action=origin or 0
    for k,v in pairs(extra or {}) do row[k]=v end
    rows[#rows+1]=row
end
local function card_info(card)
    return {id=identity(card),sort_id=card.sort_id,key=card.config.center.key,set=card.ability.set,
        hand_type=(card.ability.consumeable or {}).hand_type or false,
        removed=card.REMOVED==true,in_inventory=card.area==G.consumeables,
        edition=card.edition~=nil,debuff=card.debuff==true}
end
local function inventory()
    local out={};for _,c in ipairs(G.consumeables and G.consumeables.cards or {}) do out[#out+1]=card_info(c) end
    return out
end
local old_add=EventManager.add_event
EventManager.add_event=function(self,event,...)
    safe(function()
        if origin and not tracked[event] then
            if #event_rows>=512 then dropped=dropped+1;return end
            local row={id=#event_rows+1,action=origin,trigger=event.trigger,delay=event.delay,timer=event.timer,
                registered_frame=frames,registered_time=G.TIMERS.TOTAL,calls=0,finished=false}
            tracked[event]=row;event_rows[#event_rows+1]=row
            local callback=event.func
            event.func=function(...)
                local prior=origin;origin=row.action
                safe(function()
                    row.calls=row.calls+1
                    if row.calls==1 then row.first_frame=frames;row.first_time=G.TIMERS.TOTAL end
                end)
                local r=pack(callback(...)) -- original exception propagates unchanged
                safe(function()
                    row.last_frame=frames;row.last_time=G.TIMERS.TOTAL
                    if r[1] then row.finished=true end
                end)
                origin=prior
                return unpack(r,1,r.n)
            end
        end
    end)
    return old_add(self,event,...)
end
local old_emplace=CardArea.emplace
CardArea.emplace=function(self,card,...)
    local r=pack(old_emplace(self,card,...))
    if self==G.consumeables then safe(log,'emplace',{id=identity(card),key=card.config.center.key}) end
    return unpack(r,1,r.n)
end
local old_leave=CardArea.remove_card
CardArea.remove_card=function(self,card,...)
    local relevant=self==G.consumeables
    local r=pack(old_leave(self,card,...))
    if relevant then safe(log,'leave',{id=identity(r[1] or card)}) end
    return unpack(r,1,r.n)
end
local old_remove=Card.remove
Card.remove=function(self,...)
    local r=pack(old_remove(self,...))
    if ids[self] then safe(log,'destroy',{id=ids[self],removed=self.REMOVED==true}) end
    return unpack(r,1,r.n)
end
for _,name in ipairs({'can_use_consumeable','check_use','use_consumeable'}) do
    local original=Card[name]
    Card[name]=function(self,...)
        if origin and name=='use_consumeable' then safe(log,'effect_enter',{id=identity(self),key=self.config.center.key}) end
        local r=pack(original(self,...))
        if origin then safe(log,name,{id=identity(self),value_type=type(r[1]),value=r[1] or false}) end
        return unpack(r,1,r.n)
    end
end
local endpoint=assert(BB_DISPATCHER.endpoints.use)
local execute=endpoint.execute
endpoint.execute=function(args,respond,...)
    action_seq=action_seq+1
    local index=action_seq
    local action={id=index,request_id=BB_DISPATCHER.Server.current_request_id,
        target=identity(G.consumeables.cards[args.consumable+1]),started_frame=frames}
    actions[#actions+1]=action
    local before=origin;origin=index
    safe(log,'request',{id=action.target})
    local function response(...)
        local values=pack(...)
        safe(function()
            action.response_frame=frames;action.response_time=G.TIMERS.TOTAL
            action.response=values[1].message and values[1].name or 'success'
            action.response_inventory=inventory();action.response_buffer=G.GAME.consumeable_buffer or 0
            log('response',{response=action.response})
        end)
        return respond(unpack(values,1,values.n))
    end
    local r=pack(execute(args,response,...))
    origin=before
    return unpack(r,1,r.n)
end
local previous_signature=''
local update=love.update
love.update=function(...)
    frames=frames+1
    local r=pack(update(...))
    safe(function()
        local s=small();local parts={s.state,s.count,s.capacity,s.buffer,tostring(s.use_lock),tostring(s.locked),s.stop_use}
        for _,c in ipairs(G.consumeables and G.consumeables.cards or {}) do parts[#parts+1]=identity(c) end
        local signature=table.concat(parts,':')
        if signature~=previous_signature then changed=frames;previous_signature=signature;log('state_change') end
    end)
    return unpack(r,1,r.n)
end
assert(BB_DISPATCHER.register({name='poc.bg.observe',description='Read-only bounded inventory and real event lifecycle',schema={},
    execute=function(args,respond)
        local s=small();s.inventory=inventory();s.objects={}
        for i,c in ipairs(objects) do s.objects[#s.objects+1]=card_info(c) end
        s.pending_events=0
        for _,q in pairs(G.E_MANAGER.queues) do for _,e in ipairs(q) do
            if tracked[e] then s.pending_events=s.pending_events+1 end
        end end
        s.events=event_rows;s.rows=rows;s.actions=actions;s.observer_errors=errors;s.dropped=dropped
        s.quiet_frames=frames-changed;s.state_complete=G.STATE_COMPLETE==true
        s.paused=G.SETTINGS.paused==true;s.play_count=G.play and #G.play.cards or 0
        s.hand_levels={};for k,v in pairs(G.GAME.hands or {}) do s.hand_levels[k]=v.level end
        s.usage={};for k,v in pairs(G.GAME.consumeable_usage or {}) do s.usage[k]=v.count end
        s.dollars=G.GAME.dollars or 0;s.last_tarot_planet=G.GAME.last_tarot_planet or false
        respond(s)
    end}))
