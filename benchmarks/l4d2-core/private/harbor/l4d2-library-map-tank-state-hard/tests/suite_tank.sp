int g_T[3],g_S,g_First,g_Deaths,g_Passes,g_Old[16],g_New[16],g_Count[16],g_Dead;
bool g_Nested,g_Respawn;
int g_BeforeDeath,g_BeforeFirst,g_Replacement,g_OldSlot;
void Tank(int client)
{
    ChangeClientTeam(client,3);SetEntProp(client,Prop_Send,"m_zombieClass",8);
    SetEntProp(client,Prop_Send,"m_lifeState",0);SetEntProp(client,Prop_Send,"m_iHealth",6000);
}
void EventFor(const char[] name,int client,const char[] item="")
{
    Event e=CreateEvent(name,true);e.SetInt("userid",client>0?GetClientUserId(client):0);
    if(StrEqual(name,"item_pickup"))e.SetString("item",item);e.Fire();
}
void Round(){Event e=CreateEvent("round_start",true);e.Fire();}
public void OnMapStart()
{
    Wake();CreateTimer(1.0,Begin);
}
public void L4D2_OnTankFirstSpawn(int client){g_First++;PrintToServer("GCB first=%d client=%d serial=%d",g_First,client,GetClientSerial(client));}
public void L4D2_OnTankPassControl(int old,int next,int passes)
{
    if(g_Passes<16){g_Old[g_Passes]=old;g_New[g_Passes]=next;g_Count[g_Passes]=passes;}g_Passes++;
    if(g_Nested){g_Nested=false;EventFor("item_pickup",g_T[2],"tank_claw");}
}
public void L4D2_OnTankDeath(int client)
{
    g_Deaths++;g_Dead=client;
    if(g_Respawn){g_Respawn=false;Tank(g_T[1]);EventFor("tank_spawn",g_T[1]);}
}
public Action Begin(Handle timer)
{
    g_S=CreateFakeClient("gcb-tank-wake");ChangeClientTeam(g_S,2);
    for(int i=0;i<3;i++){g_T[i]=CreateFakeClient("gcb-tank-state");Tank(g_T[i]);}
    Round();for(int i=0;i<3;i++)Tank(g_T[i]);
    EventFor("tank_spawn",0);EventFor("tank_spawn",g_S);
    SetEntProp(g_T[2],Prop_Send,"m_zombieClass",3);EventFor("tank_spawn",g_T[2]);
    Case("spawn-rejects-nontanks",g_First==0,"invalid userid, survivor and hunter rejected");Tank(g_T[2]);
    EventFor("tank_spawn",g_T[0]);EventFor("tank_spawn",g_T[0]);
    Case("spawn-exactly-once",g_First==1,"one first-spawn transition");
    EventFor("item_pickup",g_T[0],"tank_claw");
    Case("same-owner-pickup-ignored",g_Passes==0,"duplicate is not a handoff");
    EventFor("item_pickup",g_S,"tank_claw");EventFor("item_pickup",g_T[1],"pistol");
    Case("pickup-rejects-unrelated",g_Passes==0,"survivor and unrelated item");
    EventFor("item_pickup",g_T[1],"tank_claw");
    Case("handoff-first-count",g_Passes==1&&g_Count[0]==0&&g_Old[0]==g_T[0]&&g_New[0]==g_T[1],"published zero-based count and owners");
    EventFor("item_pickup",g_T[1],"tank_claw");
    Case("duplicate-handoff-no-count",g_Passes==1,"duplicate owner does not advance count");
    EventFor("player_death",g_T[0]);CreateTimer(0.65,NonOwner);return Plugin_Stop;
}
public Action NonOwner(Handle timer)
{
    Case("nonowner-death-ignored",g_Deaths==0,"non-owner cannot close encounter");
    EventFor("player_death",g_T[1]);CreateTimer(0.30,DuplicateDeath);
    EventFor("item_pickup",g_T[1],"tank_claw");
    CreateTimer(0.65,Dead);return Plugin_Stop;
}
public Action DuplicateDeath(Handle timer)
{
    EventFor("player_death",g_T[1]);return Plugin_Stop;
}
public Action Dead(Handle timer)
{
    Case("duplicate-death-once",g_Deaths==1&&g_Dead==g_T[1],"duplicate death only one notification; same-owner pickup does not cancel");
    Tank(g_T[0]);Tank(g_T[1]);EventFor("tank_spawn",g_T[0]);
    Case("new-encounter-after-death",g_First==2,"completed death retires ownership");
    EventFor("player_death",g_T[0]);EventFor("item_pickup",g_T[1],"tank_claw");
    Case("new-encounter-count-reset",g_Passes==2&&g_Count[1]==0,"first pass in next encounter");
    CreateTimer(0.65,Passed);return Plugin_Stop;
}
public Action Passed(Handle timer)
{
    EventFor("item_pickup",g_T[0],"tank_claw");
    Case("handoff-cancels-death",g_Deaths==1&&g_Passes==3&&g_Old[2]==g_T[1]&&g_Count[2]==1,"owner and pass count survive old grace timer");
    EventFor("player_death",g_T[0]);Round();Tank(g_T[2]);EventFor("tank_spawn",g_T[2]);
    g_BeforeFirst=g_First;CreateTimer(0.65,Reset);return Plugin_Stop;
}
public Action Reset(Handle timer)
{
    Case("round-cancels-old-death",g_Deaths==1&&g_First==g_BeforeFirst,"old timer does not touch fresh encounter");
    Round();for(int i=0;i<3;i++)Tank(g_T[i]);EventFor("tank_spawn",g_T[0]);
    g_Passes=0;g_Nested=true;EventFor("item_pickup",g_T[1],"tank_claw");
    Case("nested-handoff-count-committed",g_Passes==2&&g_Count[0]==0&&g_Count[1]==1,"observer sees next committed count");
    Case("nested-handoff-owner-committed",g_Old[1]==g_T[1]&&g_New[1]==g_T[2],"nested transfer starts at committed owner");
    EventFor("item_pickup",g_T[0],"tank_claw");
    Case("nested-state-survives-return",g_Passes==3&&g_Count[2]==2&&g_Old[2]==g_T[2],"outer callback cannot roll back nested owner/count");
    g_Respawn=true;g_BeforeFirst=g_First;EventFor("player_death",g_T[0]);
    CreateTimer(0.65,ReentrantDeath);return Plugin_Stop;
}
public Action ReentrantDeath(Handle timer)
{
    Case("death-forward-can-start-next",g_First==g_BeforeFirst+1&&g_Deaths==2,"state retired before observer spawns next Tank");
    g_Passes=0;Tank(g_T[2]);EventFor("item_pickup",g_T[2],"tank_claw");
    Case("death-reentrant-state-survives",g_Passes==1&&g_Count[0]==0&&g_Old[0]==g_T[1],"new encounter survives old callback return");
    g_BeforeDeath=g_Deaths;g_OldSlot=g_T[2];EventFor("player_death",g_T[2]);SetEntProp(g_T[2],Prop_Send,"m_lifeState",1);SetEntProp(g_T[2],Prop_Send,"m_iHealth",0);KickClientEx(g_T[2],"fixture connection retirement");
    CreateTimer(0.15,Reconnect);return Plugin_Stop;
}
public Action Reconnect(Handle timer)
{
    g_Replacement=CreateFakeClient("gcb-new-connection");Tank(g_Replacement);
    Case("connection-slot-reused-fixture",g_Replacement==g_OldSlot,"exercise actual index reuse");
    PrintToServer("GCB replacement client=%d serial=%d team=%d class=%d alive=%d kick=%d",g_Replacement,GetClientSerial(g_Replacement),GetClientTeam(g_Replacement),GetEntProp(g_Replacement,Prop_Send,"m_zombieClass"),IsPlayerAlive(g_Replacement),IsClientInKickQueue(g_Replacement));
    g_BeforeFirst=g_First;EventFor("tank_spawn",g_Replacement);
    Case("reused-slot-starts-new-encounter",g_First==g_BeforeFirst+1,"new connection gets first spawn");
    KickClientEx(g_T[0],"unrelated connection retirement");CreateTimer(0.65,Disconnected);return Plugin_Stop;
}
public Action Disconnected(Handle timer)
{
    PrintToServer("GCB connection results deaths=%d before=%d first=%d",g_Deaths,g_BeforeDeath,g_First);
    Case("disconnect-cancels-pending-death",g_Deaths==g_BeforeDeath,"old connection cannot emit death for replacement");
    g_BeforeFirst=g_First;EventFor("tank_spawn",g_Replacement);
    Case("unrelated-disconnect-preserves-owner",g_First==g_BeforeFirst,"duplicate new owner spawn still ignored");
    Finish();return Plugin_Stop;
}
public void OnClientDisconnect(int client){PrintToServer("GCB disconnected client=%d",client);}
