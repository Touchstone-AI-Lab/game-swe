#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>
#define NONCE "__GCB_NONCE__"
int g_Passed,g_Total;
public Plugin myinfo={name="GCB Confogl transactions",author="GameCodeBench",version="1"};
void Case(const char[] name,bool ok,const char[] detail)
{
    g_Total++;if(ok)g_Passed++;
    PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s",NONCE,name,ok?"PASS":"FAIL",detail);
    for(int i=0;i<64;i++)PrintToServer("GCB progress flush .................................................................");
}
void Finish()
{
    PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d",NONCE,g_Passed,g_Total);
    for(int i=0;i<128;i++)PrintToServer("GCB flush %d ......................................",i);
    ServerCommand("quit");
}
void Cmd(const char[] command)
{
    ServerCommand("%s",command);ServerExecute();
    FindConVar("sb_all_bot_game").BoolValue=true;
    FindConVar("allow_all_bot_survivor_team").BoolValue=true;
}
bool Value(const char[] name,const char[] expected)
{
    char s[256];ConVar c=FindConVar(name);if(c==null)return false;
    c.GetString(s,sizeof(s));return StrEqual(s,expected);
}
void Cvar(const char[] name,const char[] value){CreateConVar(name,value).SetString(value);}
void ConfigCallback()
{
    Handle f=CreateGlobalForward("OnConfigsExecuted",ET_Ignore);
    Call_StartForward(f);Call_Finish();delete f;
}
void Load()
{
    Cvar("confogl_match_restart","0");
    Cvar("confogl_match_execcfg_on","");Cvar("confogl_match_execcfg_off","");
    Cvar("confogl_match_reloaded","1");
    Cmd("sm plugins load disabled/02_confogl.smx");
}
