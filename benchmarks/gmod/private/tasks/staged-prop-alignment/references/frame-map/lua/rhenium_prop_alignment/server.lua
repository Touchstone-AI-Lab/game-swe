if _G.RheniumPropAlignmentServer then return _G.RheniumPropAlignmentServer end
local Alignment=include("rhenium_prop_alignment/alignment.lua")
local Server={HookPrefix="RheniumPropAlignment",TimerName="RheniumPropAlignment.Cleanup"}
local core,installed=nil,false;local players,entities,progress={}, {}, {};local request_serial=0
local function valid_player(p)return IsValid(p)and p:IsPlayer()end
local function binding(e)return entities[e]end
function Server.Install(options)
 if installed then return Server end;options=options or{};core=assert(Alignment.new({max_operations=2,state=options.state}));request_serial=0;for _ in pairs((options.state and options.state.requests)or{})do request_serial=request_serial+1 end;installed=true
 hook.Add("CanTool",Server.HookPrefix..".CanTool",function(p,trace,tool)if tool=="rhenium_align"then local b=binding(trace and trace.Entity);if not(valid_player(p)and players[p]~=nil and(b~=nil or(progress[p]or 0)>=3))then return false end end end)
 hook.Add("PlayerDisconnected",Server.HookPrefix..".Disconnect",function(p)progress[p]=nil end)
 hook.Add("EntityRemoved",Server.HookPrefix..".Removed",function(e)entities[e]=nil end)
 timer.Create(Server.TimerName,1,0,function()end);return Server
end
function Server.BindPlayer(p,id)if not installed or not valid_player(p)or type(id)~="string"then return false end;players[p]=id;return true end
function Server.BindEntity(e,id,revision)if not installed or not IsValid(e)or type(id)~="string"or type(revision)~="number"then return false end;entities[e]={id=id,revision=revision};return true end
function Server.HandleTrace(p,trace)
 if not installed or not valid_player(p)or players[p]==nil or type(trace)~="table"or not trace.Hit or trace.HitPos==nil then return false,"invalid_trace",{}end
 local n=progress[p]or 0;local selected=p.RheniumAlignmentEntity
 if n==0 then selected=trace.Entity;if not binding(selected)then return false,"unbound_entity",{}end;p.RheniumAlignmentEntity=selected end
 local b=binding(selected);if not b then return false,"unbound_entity",{}end
 local allowed=hook.Run("CanTool",p,trace,"rhenium_align");if allowed==false then return false,"permission_denied",{}end
 local frames={"source","source","source","target","target","target"};local slots={"origin","x","y","origin","x","y"};local v=trace.HitPos
 request_serial=request_serial+1
 local ok,code,data=core:stage("adapter-stage:"..request_serial,players[p],b.id,b.revision,frames[n+1],slots[n+1],{x=v.x,y=v.y,z=v.z})
 if ok then progress[p]=n+1 end;return ok,code,data
end
function Server.Execute(p,e,request_id,mode)
 if mode~="copy"and mode~="move"then return false,"invalid_mode",{}end
 if not installed or players[p]==nil or not IsValid(e)or not binding(e)then return false,"invalid_context",{}end
 local b=binding(e);local pos=e:GetPos();local ok,code,data=core:solve(request_id,players[p],b.id,b.revision,{x=pos.x,y=pos.y,z=pos.z});if not ok then return ok,code,data end
 local target_pos=Vector(data.position.x,data.position.y,data.position.z);local target_ang=Vector(data.basis.x.x,data.basis.x.y,data.basis.x.z):AngleEx(Vector(data.basis.z.x,data.basis.z.y,data.basis.z.z))
 if mode=="move"then
  local old_pos,old_ang=e:GetPos(),e:GetAngles();e:SetPos(target_pos);e:SetAngles(target_ang)
  undo.Create("Rhenium Prop Alignment Move");undo.AddFunction(function(_,entity,restore_pos,restore_ang)if IsValid(entity)then entity:SetPos(restore_pos);entity:SetAngles(restore_ang)end end,e,old_pos,old_ang);undo.SetPlayer(p)
  if undo.Finish()~=true then e:SetPos(old_pos);e:SetAngles(old_ang);return false,"undo_failed",{}end
  progress[p]=nil;p.RheniumAlignmentEntity=nil;data.moved=e;data.created={};return true,"executed",data
 end
 local made={};local clone=ents.Create(e:GetClass());if not IsValid(clone)then return false,"create_failed",{}end;made[#made+1]=clone
 clone:SetModel(e:GetModel());clone:SetPos(target_pos);clone:SetAngles(target_ang);clone:Spawn();clone:Activate();local physics=clone:GetPhysicsObject();if IsValid(physics)then physics:EnableMotion(false)end
 local weld=constraint.Weld(e,clone,0,0,0,false,false);if not IsValid(weld)then clone:Remove();return false,"constraint_failed",{}end;made[#made+1]=weld
 undo.Create("Rhenium Prop Alignment");for _,x in ipairs(made)do undo.AddEntity(x)end;undo.SetPlayer(p);if undo.Finish()~=true then for _,x in ipairs(made)do if IsValid(x)then x:Remove()end end;return false,"undo_failed",{}end
 progress[p]=nil;p.RheniumAlignmentEntity=nil;data.created=made;return true,"executed",data
end
function Server.Save()return core and core:save()end
function Server.Shutdown()if installed then hook.Remove("CanTool",Server.HookPrefix..".CanTool");hook.Remove("PlayerDisconnected",Server.HookPrefix..".Disconnect");hook.Remove("EntityRemoved",Server.HookPrefix..".Removed");timer.Remove(Server.TimerName);installed=false end;if core then core:shutdown()end;players={};entities={};progress={};request_serial=0;return true,"shutdown"end
_G.RheniumPropAlignmentServer=Server
return Server
