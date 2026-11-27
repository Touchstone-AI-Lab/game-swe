local C={};C.__index=C;local function cp(v)if type(v)~="table"then return v end;local o={};for k,x in pairs(v)do o[cp(k)]=cp(x)end;return o end;local function id(v)return type(v)=="string"and#v>0 and#v<=128 and v:match("^[%w][%w_.:%-]*$")end;local function find(rows,p)for _,r in ipairs(rows)do if r.player_id==p then return r end end end;local function clock(s,n)if type(n)~="number"or n~=n or n<0 or n>=math.huge then return nil end;if n>s.last_now then s.last_now=n end;return s.last_now end
local function live(s,skip,uninfected)local a={};for _,p in ipairs(s.player_rows)do if p.player_id~=skip and p.alive and p.connected and(not uninfected or not p.infected)then a[#a+1]=p.player_id end end;table.sort(a);return a end;local function key(k,a)local p={k};for _,v in ipairs(a)do p[#p+1]=type(v)=="table"and table.concat(v,",")or tostring(v)end;return table.concat(p,"|")end
local function int(v,min)return type(v)=="number"and v%1==0 and v>=min and v<math.huge end;local function finite(v)return type(v)=="number"and v==v and v>=0 and v<math.huge end
local function array(v)if type(v)~="table"then return false end;local n=0;for k in pairs(v)do if not int(k,1)then return false end;n=n+1 end;return n==#v end;local function fields(v,a)local n=0;for k in pairs(v)do if not a[k]then return false end;n=n+1 end;return n end
local function serial(v,seen)local t=type(v);if t=="nil"or t=="string"or t=="boolean"then return true end;if t=="number"then return v==v and v<math.huge and v>-math.huge end;if t~="table"then return false end;seen=seen or{};if seen[v]then return false end;seen[v]=true;for k,x in pairs(v)do if(type(k)~="string"and type(k)~="number")or not serial(k,seen)or not serial(x,seen)then return false end end;seen[v]=nil;return true end
local function restore(s,st)
 local allowed={schema_version=1,status=1,round_id=1,variant=1,holder=1,deadline=1,object_id=1,object_revision=1,last_sequence=1,last_now=1,settlements=1,result=1,audit=1,player_rows=1,event_rows=1}
 if type(st)~="table"or st.schema_version~=1 or not fields(st,allowed)
  or(st.status~="waiting"and st.status~="active"and st.status~="finished"and st.status~="cleanup")
  or st.object_id~=s.object_id or st.object_revision~=s.object_revision
  or not int(st.last_sequence,0)or not finite(st.last_now)or not int(st.settlements,0)
  or st.settlements>1 or not array(st.player_rows)or not array(st.event_rows)
  or not array(st.audit)or not serial(st.audit)then return false end
 local players,events={},{}
 for _,p in ipairs(st.player_rows)do
  if type(p)~="table"or fields(p,{player_id=1,revision=1,alive=1,connected=1,infected=1})~=5
   or not id(p.player_id)or players[p.player_id]or not int(p.revision,1)
   or type(p.alive)~="boolean"or type(p.connected)~="boolean"or type(p.infected)~="boolean"then return false end
  players[p.player_id]=p
 end
 for _,e in ipairs(st.event_rows)do
  if type(e)~="table"or fields(e,{id=1,key=1,ok=1,code=1,data=1})~=5
   or not id(e.id)or events[e.id]or type(e.key)~="string"or e.key==""
   or type(e.ok)~="boolean"or type(e.code)~="string"or e.code==""
   or type(e.data)~="table"or not serial(e.data)then return false end
  events[e.id]=true
 end
 if st.status=="waiting"then
  if #st.player_rows~=0 or st.round_id~=nil or st.variant~=nil or st.holder~=nil
   or st.deadline~=nil or st.result~=nil or st.settlements~=0 then return false end
 else
  if #st.player_rows~=3 or not id(st.round_id)
   or(st.variant~="exploding"and st.variant~="infectious")or not finite(st.deadline)then return false end
  if st.status=="active"then
   if not players[st.holder]or st.result~=nil or st.settlements~=0
    or st.last_now>=st.deadline then return false end
  else
   if(st.holder~=nil and not players[st.holder])or type(st.result)~="table"
    or st.settlements~=1 or st.result.variant~=st.variant or st.result.holder~=st.holder
    or not array(st.result.eliminated)or not array(st.result.winners)
    or not finite(st.result.settled_at)then return false end
   local winners={}
   for _,pid in ipairs(st.result.winners)do
    local p=players[pid]
    if not p or winners[pid]or not p.alive or not p.connected or pid==st.holder
     or(st.variant=="infectious"and p.infected)then return false end
    winners[pid]=true
   end
  end
 end
 for _,a in ipairs(st.audit)do
  if type(a)~="table"or type(a.type)~="string"or not finite(a.at)or a.at>st.last_now then return false end
 end
 for k,v in pairs(st)do if k~="schema_version"then s[k]=cp(v)end end
 return true
end
function C.new(o)o=o or{};local oid=o.object_id or"hot:1";local orev=o.object_revision or 1;if not id(oid)or type(orev)~="number"or orev<1 or orev%1~=0 then return nil,"invalid_options"end;local s=setmetatable({status="waiting",object_id=oid,object_revision=orev,player_rows={},event_rows={},audit={},last_sequence=0,last_now=0,settlements=0,stopped=false},C);local st=o.state;if st and not restore(s,st)then return nil,"invalid_state"end;return s end
function C:_old(e,k,a)if not id(e)then return false,"invalid_event",{}end;local sig=key(k,a);for _,r in ipairs(self.event_rows)do if r.id==e then if r.key~=sig then return false,"event_conflict",{}end;return r.ok,r.code,cp(r.data)end end;return nil,sig end;function C:_put(e,k,ok,c,d)self.event_rows[#self.event_rows+1]={id=e,key=k,ok=ok,code=c,data=cp(d or{})};return ok,c,cp(d or{})end
function C:start(e,r,v,players,h,d)local old,k,x=self:_old(e,"start",{r,v,players,h,d});if old~=nil then return old,k,x end;if self.stopped then return false,"shutdown",{}end;if self.status~="waiting"or not id(r)or(v~="exploding"and v~="infectious")or not array(players)or#players~=3 or not id(h)or not finite(d)or d<=self.last_now then return self:_put(e,k,false,"invalid_round",{})end;local seen={};for _,p in ipairs(players)do if not id(p)or seen[p]then return self:_put(e,k,false,"invalid_players",{})end;seen[p]=1;self.player_rows[#self.player_rows+1]={player_id=p,revision=1,alive=true,connected=true,infected=false}end;if not find(self.player_rows,h)then return self:_put(e,k,false,"invalid_holder",{})end;self.round_id=r;self.variant=v;self.holder=h;self.deadline=d;self.status="active";self.audit[#self.audit+1]={type="active",at=self.last_now};return self:_put(e,k,true,"started",{holder=h})end
function C:touch(e,oid,orev,pid,prev,seq,t)local a={oid,orev,pid,prev,seq,t};local old,k,x=self:_old(e,"touch",a);if old~=nil then return old,k,x end;if self.stopped then return false,"shutdown",{}end;local n=clock(self,t);if not n then return false,"invalid_time",{}end;if self.status~="active"or n>=self.deadline then self:tick(n);return self:_put(e,k,false,"round_closed",{})end;local p=find(self.player_rows,pid);if oid~=self.object_id or orev~=self.object_revision then return self:_put(e,k,false,"wrong_object",{})end;if not p or p.revision~=prev or not p.alive or not p.connected then return self:_put(e,k,false,"invalid_player",{})end;if type(seq)~="number"or seq%1~=0 or seq<=self.last_sequence then return self:_put(e,k,false,"stale_sequence",{})end;self.last_sequence=seq;local from=self.holder;self.holder=pid;if self.variant=="infectious"then p.infected=true end;self.audit[#self.audit+1]={type="touch",at=n,sequence=seq,from=from,to=pid};return self:_put(e,k,true,"transferred",{from=from,to=pid,sequence=seq})end
function C:_settle(reason,t)if self.status~="active"then return end;self.status="resolving";local h=self.holder;if h and self.variant=="infectious"then local row=find(self.player_rows,h);if row then row.infected=true end end;local win=live(self,h,self.variant=="infectious");self.result={reason=reason,holder=h,eliminated=h and{h}or{},winners=win,variant=self.variant,settled_at=t};self.settlements=self.settlements+1;self.audit[#self.audit+1]={type="resolving",at=t};self.status="finished";self.audit[#self.audit+1]={type="finished",at=t}end
function C:_life(e,kind,pid,rev,t)local old,k,x=self:_old(e,kind,{pid,rev,t});if old~=nil then return old,k,x end;local n=clock(self,t);local p=find(self.player_rows,pid);if not n or not p or p.revision~=rev then return self:_put(e,k,false,"invalid_player",{})end;if kind=="death"then p.alive=false else p.connected=false end;if self.holder==pid then local a=live(self,pid);self.holder=a[1];if not self.holder then self:_settle(kind,n)end end;self.audit[#self.audit+1]={type=kind,at=n,player_id=pid};return self:_put(e,k,true,kind,{holder=self.holder})end
function C:death(e,p,r,t)return self:_life(e,"death",p,r,t)end;function C:disconnect(e,p,r,t)return self:_life(e,"disconnect",p,r,t)end
function C:respawn(e,p,oldrev,newrev,t)local old,k,x=self:_old(e,"respawn",{p,oldrev,newrev,t});if old~=nil then return old,k,x end;local n=clock(self,t);local row=find(self.player_rows,p);if not n or not row or row.revision~=oldrev or not int(newrev,1)or newrev<=oldrev then return self:_put(e,k,false,"invalid_player",{})end;row.revision=newrev;row.alive=true;row.connected=true;self.audit[#self.audit+1]={type="respawn",at=n,player_id=p,revision=newrev};return self:_put(e,k,true,"respawned",{revision=newrev})end
function C:tick(t)if self.stopped then return false,"shutdown",{}end;local n=clock(self,t);if not n then return false,"invalid_time",{}end;if self.status=="active"and n>=self.deadline then self:_settle("deadline",n)elseif self.status=="finished"and n>=self.deadline+1 then self.status="cleanup";self.audit[#self.audit+1]={type="cleanup",at=n}end;return true,"ticked",{status=self.status,settlements=self.settlements}end
function C:snapshot(t)if t~=nil then self:tick(t)end;return{schema_version=1,status=self.status,round_id=self.round_id,variant=self.variant,holder=self.holder,deadline=self.deadline,object_id=self.object_id,object_revision=self.object_revision,last_sequence=self.last_sequence,last_now=self.last_now,settlements=self.settlements,result=cp(self.result),audit=cp(self.audit),player_rows=cp(self.player_rows)}end
function C:save(t)local s=self:snapshot(t);s.event_rows=cp(self.event_rows);return s end;function C:shutdown()self.stopped=true;return true,"shutdown"end;return C
