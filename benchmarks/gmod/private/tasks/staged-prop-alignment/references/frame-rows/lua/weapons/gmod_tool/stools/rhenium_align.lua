TOOL.Category="Rhenium";TOOL.Name="Staged Prop Alignment";TOOL.Command=nil;TOOL.ConfigName="";TOOL.AddToMenu=false
local function server()return include("rhenium_prop_alignment/server.lua")end
function TOOL:LeftClick(trace)if CLIENT then return true end;local ok=server().HandleTrace(self:GetOwner(),trace);return ok and true or false end
function TOOL:RightClick(trace)if CLIENT then return true end;local p=self:GetOwner();local ok=server().Execute(p,p.RheniumAlignmentEntity or trace.Entity,"execute:"..tostring(CurTime()),"copy");return ok and true or false end
