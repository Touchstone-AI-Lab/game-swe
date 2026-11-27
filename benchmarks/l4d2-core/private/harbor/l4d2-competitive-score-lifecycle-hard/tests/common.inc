#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>
#include <sdkhooks>
#include <left4dhooks>

native int SMPlus_GetHealthBonus();
native int SMPlus_GetMaxHealthBonus();
native int SMPlus_GetDamageBonus();
native int SMPlus_GetMaxDamageBonus();
native int SMPlus_GetPillsBonus();
native int SMPlus_GetMaxPillsBonus();

#define NONCE "__GCB_NONCE__"
int g_Passed, g_Total, g_Client[4];
Handle g_ADM, g_End;
public Plugin myinfo = {name="GCB score lifecycle", author="GameCodeBench", version="1.0"};

public APLRes AskPluginLoad2(Handle myself, bool late, char[] error, int len)
{
    MarkNativeAsOptional("SMPlus_GetHealthBonus");
    MarkNativeAsOptional("SMPlus_GetMaxHealthBonus");
    MarkNativeAsOptional("SMPlus_GetDamageBonus");
    MarkNativeAsOptional("SMPlus_GetMaxDamageBonus");
    MarkNativeAsOptional("SMPlus_GetPillsBonus");
    MarkNativeAsOptional("SMPlus_GetMaxPillsBonus");
    return APLRes_Success;
}
public void OnPluginStart()
{
    g_ADM = CreateGlobalForward("L4D2_ADM_OnTemporaryHealthSubtracted", ET_Ignore, Param_Cell, Param_Cell, Param_Cell);
    g_End = CreateGlobalForward("L4D2_OnEndVersusModeRound", ET_Hook, Param_Cell);
}
public void OnMapStart()
{
    ConVar hibernate = FindConVar("sv_hibernate_when_empty");
    if (hibernate != null) hibernate.BoolValue = false;
    FindConVar("sb_all_bot_game").BoolValue = true;
    FindConVar("allow_all_bot_survivor_team").BoolValue = true;
    FindConVar("director_no_mobs").BoolValue = true;
    FindConVar("director_no_specials").BoolValue = true;
    FindConVar("sb_stop").BoolValue = true;
    FindConVar("pain_pills_decay_rate").FloatValue = 0.0;
    for (int i=0; i<4; i++)
    {
        g_Client[i] = CreateFakeClient("gcb-score-fixture");
        if (!g_Client[i]) SetFailState("cannot create survivor fixture");
        ChangeClientTeam(g_Client[i], 2);
    }
    CreateTimer(1.0, Begin);
}
void Case(const char[] name, bool ok, const char[] why)
{
    g_Total++;
    if (ok) g_Passed++;
    PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok?"PASS":"FAIL", why);
}
void Finish()
{
    PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE,g_Passed,g_Total);
    for (int i=0;i<128;i++) PrintToServer("GCB output flush %d ..........................................................",i);
    ServerCommand("quit");
}
void Cv(const char[] name, float value)
{
    ConVar cv=FindConVar(name);
    cv.SetBounds(ConVarBound_Lower, false);
    cv.SetBounds(ConVarBound_Upper, false);
    cv.FloatValue=value;
}
void Player(int client, int health=100, int state=0)
{
    if (GetClientTeam(client)!=2) ChangeClientTeam(client,2);
    SetEntProp(client, Prop_Send, "m_lifeState", state==1?2:0);
    SetEntProp(client, Prop_Send, "m_iHealth", health);
    SetEntProp(client, Prop_Send, "m_isIncapacitated",state==2?1:0);
    SetEntProp(client, Prop_Send, "m_isHangingFromLedge",state==3?1:0);
    SetEntProp(client, Prop_Send, "m_isFallingFromLedge",state==4?1:0);
    SetEntProp(client, Prop_Send, "m_currentReviveCount",0);
    Temp(client,31.0);
}
void Temp(int client, float value)
{
    SetEntPropFloat(client,Prop_Send,"m_healthBuffer",value);
    SetEntPropFloat(client,Prop_Send,"m_healthBufferTime",GetGameTime());
}
void Round(int half=0)
{
    GameRules_SetProp("m_bInSecondHalfOfRound",half);
    Event e=CreateEvent("round_start",true); e.Fire();
}
void Reset()
{
    for(int i=1;i<=MaxClients;i++)
    {
        if (!IsClientInGame(i)) continue;
        bool ours=false;
        for(int n=0;n<4;n++) if(g_Client[n]==i) ours=true;
        if(!ours && GetClientTeam(i)==2) ChangeClientTeam(i,1);
    }
    Cv("survivor_limit",4.0);
    Cv("sm2_bonus_per_survivor_multiplier",0.5);
    Cv("sm2_permament_health_proportion",0.75);
    Cv("sm2_pills_hp_factor",6.0);
    Cv("sm2_pills_max_bonus",30.0);
    for(int i=0;i<4;i++) Player(g_Client[i]);
    Round();
}
void Adm(int client,int before,int after)
{
    Call_StartForward(g_ADM); Call_PushCell(client); Call_PushCell(before); Call_PushCell(after); Call_Finish();
}
void End()
{
    Action result;
    Call_StartForward(g_End); Call_PushCell(true); Call_Finish(result);
}
void Grab(int client,int debit)
{
    SetEntProp(client,Prop_Send,"m_isHangingFromLedge",1);
    L4D2Direct_SetPreIncapHealthBuffer(client,debit);
    Event e=CreateEvent("player_ledge_grab",true); e.SetInt("userid",GetClientUserId(client)); e.Fire();
}
void Revive(int client,bool ledge=true)
{
    SetEntProp(client,Prop_Send,"m_isHangingFromLedge",0);
    SetEntProp(client,Prop_Send,"m_isIncapacitated",0);
    Event e=CreateEvent("revive_success",true);
    e.SetInt("userid",GetClientUserId(g_Client[1])); e.SetInt("subject",GetClientUserId(client));
    e.SetBool("ledge_hang",ledge); e.Fire();
}
int DamageAfterLoss(int loss, int upright=4, int team=4)
{
    // Public formula; normal p=.75 gives capacity=team*100/3.
    float capacity=float(team)*100.0/3.0;
    float result=(capacity-float(loss))*float(SMPlus_GetMaxDamageBonus())/capacity/float(team)*float(upright);
    return result>0.0?RoundToFloor(result):0;
}
