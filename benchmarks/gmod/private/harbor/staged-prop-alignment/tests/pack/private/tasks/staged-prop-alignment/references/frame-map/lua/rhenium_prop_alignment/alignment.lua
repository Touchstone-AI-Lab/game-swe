local Alignment = {}
Alignment.__index = Alignment

local function copy(v)
    if type(v) ~= "table" then return v end
    local out = {}
    for k, x in pairs(v) do out[copy(k)] = copy(x) end
    return out
end
local function finite(n) return type(n) == "number" and n == n and n < math.huge and n > -math.huge end
local function valid_id(v) return type(v) == "string" and #v > 0 and #v <= 128 and v:match("^[%w][%w_.:%-]*$") ~= nil end
local function point(v) return type(v) == "table" and finite(v.x) and finite(v.y) and finite(v.z) end
local function q(n)
    local scaled = n * 1000000
    return (scaled >= 0 and math.floor(scaled + 0.5) or math.ceil(scaled - 0.5)) / 1000000
end
local function sub(a,b) return {x=a.x-b.x,y=a.y-b.y,z=a.z-b.z} end
local function add(a,b) return {x=a.x+b.x,y=a.y+b.y,z=a.z+b.z} end
local function mul(a,n) return {x=a.x*n,y=a.y*n,z=a.z*n} end
local function dot(a,b) return a.x*b.x+a.y*b.y+a.z*b.z end
local function cross(a,b) return {x=a.y*b.z-a.z*b.y,y=a.z*b.x-a.x*b.z,z=a.x*b.y-a.y*b.x} end
local function norm(a) local n=math.sqrt(dot(a,a)); if n < 0.000001 then return nil end; return mul(a,1/n) end
local function frame(p)
    local x=norm(sub(p.x,p.origin)); if not x then return nil,"degenerate_frame" end
    local z=norm(cross(x,sub(p.y,p.origin))); if not z then return nil,"collinear_frame" end
    local y=norm(cross(z,x)); return {origin=copy(p.origin),x=x,y=y,z=z}
end
local function same(a,b) return a == b or (type(a)=="table" and type(b)=="table" and a.x==b.x and a.y==b.y and a.z==b.z) end
local function signature(method,args)
    local parts={method}; for _,v in ipairs(args) do
        if type(v)=="table" then parts[#parts+1]=tostring(v.x)..","..tostring(v.y)..","..tostring(v.z) else parts[#parts+1]=tostring(v) end
    end; return table.concat(parts,"|")
end

local function valid_session(player_id, session)
    if not valid_id(player_id) or type(session) ~= "table" or not valid_id(session.entity_id)
        or type(session.revision) ~= "number" or session.revision < 1
        or session.revision % 1 ~= 0 or type(session.source) ~= "table"
        or type(session.target) ~= "table" then return false end
    local expected = { {"source","origin"}, {"source","x"}, {"source","y"},
        {"target","origin"}, {"target","x"}, {"target","y"} }
    local missing = false
    for _, pair in ipairs(expected) do
        local value = session[pair[1]][pair[2]]
        if value == nil then missing = true
        elseif missing or not point(value) then return false end
    end
    for _, frame_name in ipairs({"source", "target"}) do
        for key in pairs(session[frame_name]) do
            if key ~= "origin" and key ~= "x" and key ~= "y" then return false end
        end
        if session[frame_name].y and not frame(session[frame_name]) then return false end
    end
    return true
end

local function restore(self, state)
    if type(state) ~= "table" or state.schema_version ~= 1
        or type(state.sessions) ~= "table" or type(state.requests) ~= "table"
        or type(state.spent) ~= "table" then return false end
    for player_id, session in pairs(state.sessions) do
        if not valid_session(player_id, session) then return false end
    end
    for player_id, count in pairs(state.spent) do
        if not valid_id(player_id) or type(count) ~= "number" or count % 1 ~= 0
            or count < 0 or count > self.max_operations then return false end
    end
    for request_id, request in pairs(state.requests) do
        if not valid_id(request_id) or type(request) ~= "table"
            or type(request.signature) ~= "string" or request.signature == ""
            or type(request.ok) ~= "boolean" or type(request.code) ~= "string"
            or request.code == "" or type(request.data) ~= "table" then return false end
    end
    self.sessions=copy(state.sessions); self.requests=copy(state.requests); self.spent=copy(state.spent)
    return true
end

function Alignment.new(options)
    options=options or {}; if options.max_operations ~= 2 then return nil,"invalid_options" end
    local self=setmetatable({max_operations=2,sessions={},requests={},spent={},stopped=false},Alignment)
    local state=options.state
    if state ~= nil and not restore(self, state) then return nil,"invalid_state" end
    return self
end
function Alignment:_prior(id,method,args)
    local old=self.requests[id]; if not old then return nil end
    if old.signature~=signature(method,args) then return false,"request_conflict",{} end
    return old.ok,old.code,copy(old.data)
end
function Alignment:_record(id,method,args,ok,code,data)
    self.requests[id]={signature=signature(method,args),ok=ok,code=code,data=copy(data or {})}; return ok,code,copy(data or {})
end
function Alignment:stage(request_id,player_id,entity_id,revision,which,slot,value)
    if self.stopped then return false,"shutdown",{} end
    local args={player_id,entity_id,revision,which,slot,value}; local a,b,c=self:_prior(request_id,"stage",args); if a~=nil then return a,b,c end
    if not valid_id(request_id) or not valid_id(player_id) or not valid_id(entity_id) or type(revision)~="number" or revision<1 or revision%1~=0 or (which~="source" and which~="target") or (slot~="origin" and slot~="x" and slot~="y") or not point(value) then return false,"invalid_stage",{} end
    local s=self.sessions[player_id]
    if not s then s={entity_id=entity_id,revision=revision,source={},target={}};self.sessions[player_id]=s end
    if s.entity_id~=entity_id or s.revision~=revision then return self:_record(request_id,"stage",args,false,"stage_identity_mismatch",{}) end
    local order={source={origin=1,x=2,y=3},target={origin=4,x=5,y=6}}; local count=0;for _,f in ipairs({"source","target"})do for _,k in ipairs({"origin","x","y"})do if s[f][k]then count=count+1 end end end
    if order[which][slot]~=count+1 then return self:_record(request_id,"stage",args,false,"bad_stage_order",{}) end
    s[which][slot]=copy(value)
    if slot=="y" then local _,err=frame(s[which]);if err then s[which][slot]=nil;return self:_record(request_id,"stage",args,false,err,{}) end end
    return self:_record(request_id,"stage",args,true,"staged",{stage=count+1})
end
function Alignment:solve(request_id,player_id,entity_id,revision,probe)
    if self.stopped then return false,"shutdown",{} end
    local args={player_id,entity_id,revision,probe};local a,b,c=self:_prior(request_id,"solve",args);if a~=nil then return a,b,c end
    if not valid_id(request_id) or not valid_id(player_id) or not valid_id(entity_id)
        or type(revision) ~= "number" or revision < 1 or revision % 1 ~= 0
        or not point(probe) then return false,"invalid_request",{} end
    local s=self.sessions[player_id];if not s or s.entity_id~=entity_id or s.revision~=revision then return self:_record(request_id,"solve",args,false,"incomplete_stage",{}) end
    local sf,se=frame(s.source);local tf,te=frame(s.target);if not sf or not tf then return self:_record(request_id,"solve",args,false,se or te,{}) end
    if (self.spent[player_id] or 0)>=self.max_operations then return self:_record(request_id,"solve",args,false,"budget_exceeded",{}) end
    local d=sub(probe,sf.origin);local mapped=add(tf.origin,add(mul(tf.x,dot(d,sf.x)),add(mul(tf.y,dot(d,sf.y)),mul(tf.z,dot(d,sf.z)))))
    local data={position={x=q(mapped.x),y=q(mapped.y),z=q(mapped.z)},basis={x={x=q(tf.x.x),y=q(tf.x.y),z=q(tf.x.z)},y={x=q(tf.y.x),y=q(tf.y.y),z=q(tf.y.z)},z={x=q(tf.z.x),y=q(tf.z.y),z=q(tf.z.z)}}}
    self.spent[player_id]=(self.spent[player_id] or 0)+1;self.sessions[player_id]=nil
    return self:_record(request_id,"solve",args,true,"solved",data)
end
function Alignment:clear(request_id,player_id)
    if self.stopped then return false,"shutdown",{} end
    if not valid_id(request_id) or not valid_id(player_id) then return false,"invalid_request",{} end
    local args={player_id};local a,b,c=self:_prior(request_id,"clear",args);if a~=nil then return a,b,c end
    self.sessions[player_id]=nil;return self:_record(request_id,"clear",args,true,"cleared",{})
end
function Alignment:snapshot() return copy({sessions=self.sessions,spent=self.spent}) end
function Alignment:save() return {schema_version=1,sessions=copy(self.sessions),requests=copy(self.requests),spent=copy(self.spent)} end
function Alignment:shutdown() self.stopped=true;return true,"shutdown" end
return Alignment
