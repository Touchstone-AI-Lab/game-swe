local Profiles={};Profiles.__index=Profiles
local WEAPONS={weapon_crowbar=true,weapon_pistol=true,weapon_smg1=true,weapon_shotgun=true};local CAPS={Pistol=200,SMG1=120,Buckshot=32}
local function cp(v)if type(v)~="table"then return v end;local o={};for k,x in pairs(v)do o[cp(k)]=cp(x)end;return o end
local function id(v)return type(v)=="string"and#v>0 and#v<=128 and v:match("^[%w][%w_.:%-]*$")~=nil end
local function name(v)return type(v)=="string"and#v>0 and#v<=32 and v:match("^[%w_-]+$")~=nil end
local function integer(v)return type(v)=="number"and v>=0 and v%1==0 and v<math.huge end
local function encode(v)
 if type(v)~="table"then return type(v)..":"..tostring(v)end
 local keys={};for k in pairs(v)do keys[#keys+1]=k end;table.sort(keys,function(a,b)return tostring(a)<tostring(b)end)
 local out={"{"};for _,k in ipairs(keys)do out[#out+1]=encode(k).."="..encode(v[k])..";"end;out[#out+1]="}";return table.concat(out)
end
local function sig(method,args)local p={method};for _,v in ipairs(args)do p[#p+1]=encode(v)end;return table.concat(p,"|")end
local function normalize(spec)
 if type(spec)~="table"or type(spec.weapons)~="table"or#spec.weapons<1 or#spec.weapons>4 then return nil,"invalid_profile"end;local list,seen,ammo={},{},{}
 for _,w in ipairs(spec.weapons)do if type(w)~="table"or not WEAPONS[w.class]or seen[w.class]then return nil,"invalid_weapon"end;seen[w.class]=true;local row={class=w.class}
  for _,slot in ipairs({"primary","secondary"})do local a=w[slot];if a~=nil then if type(a)~="table"or not CAPS[a.type]or not integer(a.amount)then return nil,"invalid_ammo"end;ammo[a.type]=(ammo[a.type]or 0)+a.amount;row[slot]={type=a.type,amount=a.amount}end end;list[#list+1]=row
 end;for t,n in pairs(ammo)do if n>CAPS[t]then return nil,"ammo_cap_exceeded"end end;table.sort(list,function(a,b)return a.class<b.class end);local rounds={};for t,n in pairs(ammo)do rounds[#rounds+1]={type=t,amount=n}end;table.sort(rounds,function(a,b)return a.type<b.type end);return{weapons=list,ammo=rounds}
end
local function fields(v,allowed)local n=0;for k in pairs(v)do if not allowed[k]then return false end;n=n+1 end;return n end
local function serial(v,seen)local t=type(v);if t=="nil"or t=="string"or t=="boolean"then return true end;if t=="number"then return v==v and v<math.huge and v>-math.huge end;if t~="table"then return false end;seen=seen or{};if seen[v]then return false end;seen[v]=true;for k,x in pairs(v)do if(type(k)~="string"and type(k)~="number")or not serial(k,seen)or not serial(x,seen)then return false end end;seen[v]=nil;return true end
local function restore(self,s)
 if type(s)~="table"or s.schema_version~=1 or fields(s,{schema_version=1,last_now=1,players=1,requests=1})~=4 or type(s.last_now)~="number"or s.last_now~=s.last_now or s.last_now<0 or s.last_now>=math.huge or type(s.players)~="table"or type(s.requests)~="table"then return false end
 for player_id,player in pairs(s.players)do
  local field_count=type(player)=="table"and fields(player,{profiles=1,preferred=1,select_revision=1})or false
  if not id(player_id)or type(player)~="table"or not field_count or field_count<2 or type(player.profiles)~="table"or not integer(player.select_revision)then return false end
  local count=0
  for profile_name,profile in pairs(player.profiles)do count=count+1;if count>5 or not name(profile_name)or type(profile)~="table"or fields(profile,{revision=1,plan=1})~=2 or not integer(profile.revision)or profile.revision<1 or type(profile.plan)~="table"then return false end;local normalized=normalize({weapons=profile.plan.weapons});if not normalized or encode(normalized)~=encode(profile.plan)then return false end end
  if player.preferred~=nil and(not name(player.preferred)or not player.profiles[player.preferred]or player.select_revision<1)then return false end
 end
 for request_id,r in pairs(s.requests)do if not id(request_id)or type(r)~="table"or fields(r,{key=1,ok=1,code=1,data=1})~=4 or type(r.key)~="string"or r.key==""or type(r.ok)~="boolean"or type(r.code)~="string"or r.code==""or type(r.data)~="table"or not serial(r.data)then return false end end
 self.players=cp(s.players);self.requests=cp(s.requests);self.last_now=s.last_now;return true
end
function Profiles.new(o)o=o or{};local self=setmetatable({players={},requests={},last_now=0,stopped=false},Profiles);local s=o.state;if s~=nil and not restore(self,s)then return nil,"invalid_state"end;return self end
function Profiles:_call(rid,m,args)if not id(rid)then return false,"invalid_request_id",{}end;local k=sig(m,args);local old=self.requests[rid];if old then if old.key~=k then return false,"request_conflict",{}end;return old.ok,old.code,cp(old.data)end;return nil,k end
function Profiles:_done(rid,k,ok,code,data)self.requests[rid]={key=k,ok=ok,code=code,data=cp(data or{})};return ok,code,cp(data or{})end
function Profiles:put(rid,p,n,spec,rev)if self.stopped then return false,"shutdown",{}end;local old,k,d=self:_call(rid,"put",{p,n,rev,spec});if old~=nil then return old,k,d end;if not id(p)or not name(n)or not integer(rev)or rev<1 then return self:_done(rid,k,false,"invalid_profile",{})end;local plan,err=normalize(spec);if not plan then return self:_done(rid,k,false,err,{})end;local player=self.players[p]or{profiles={},preferred=nil,select_revision=0};self.players[p]=player;local current=player.profiles[n];if current and rev<=current.revision then return self:_done(rid,k,false,"stale_revision",{})end;local count=0;for _ in pairs(player.profiles)do count=count+1 end;if not current and count>=5 then return self:_done(rid,k,false,"profile_limit",{})end;player.profiles[n]={revision=rev,plan=plan};return self:_done(rid,k,true,"stored",{name=n,revision=rev})end
function Profiles:select(rid,p,n,rev)if self.stopped then return false,"shutdown",{}end;local old,k,d=self:_call(rid,"select",{p,n,rev});if old~=nil then return old,k,d end;if not id(p)or not name(n)or not integer(rev)or rev<1 then return self:_done(rid,k,false,"invalid_profile",{})end;local player=self.players[p];if not player or not player.profiles[n]then return self:_done(rid,k,false,"not_found",{})end;if rev<=player.select_revision then return self:_done(rid,k,false,"stale_revision",{})end;player.preferred=n;player.select_revision=rev;return self:_done(rid,k,true,"selected",{name=n,revision=rev})end
function Profiles:get(p,n)local x=self.players[p];local v=x and x.profiles[n];if not v then return nil,"not_found"end;return cp(v)end
function Profiles:preferred(p)local x=self.players[p];return x and x.preferred or nil end
function Profiles:plan(p)local x=self.players[p];local v=x and x.preferred and x.profiles[x.preferred];if not v then return nil,"not_found"end;return cp(v.plan)end
function Profiles:disconnect(p,now)if type(now)=="number"and now==now and now>=0 and now>self.last_now then self.last_now=now end;return true,"retained",{player_id=p}end
function Profiles:save(now)if type(now)=="number"and now==now and now>=0 and now>self.last_now then self.last_now=now end;return{schema_version=1,last_now=self.last_now,players=cp(self.players),requests=cp(self.requests)}end
function Profiles:shutdown()self.stopped=true;return true,"shutdown"end
return Profiles
