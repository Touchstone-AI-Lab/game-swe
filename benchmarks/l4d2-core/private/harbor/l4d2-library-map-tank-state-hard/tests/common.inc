#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>
#undef REQUIRE_PLUGIN
#include <l4d2lib>
#define NONCE "__GCB_NONCE__"
int g_Passed,g_Total;
public Plugin myinfo={name="GCB library contracts",author="GameCodeBench",version="1"};
void Case(const char[] name,bool ok,const char[] detail)
{
    g_Total++;if(ok)g_Passed++;
    PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s",NONCE,name,ok?"PASS":"FAIL",detail);
}
void Finish()
{
    PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d",NONCE,g_Passed,g_Total);
    for(int i=0;i<128;i++)PrintToServer("GCB flush %d ......................................",i);
    ServerCommand("quit");
}
void Wake()
{
    FindConVar("sv_hibernate_when_empty").BoolValue=false;
    FindConVar("sb_all_bot_game").BoolValue=true;
    FindConVar("allow_all_bot_survivor_team").BoolValue=true;
    FindConVar("director_no_specials").BoolValue=true;
    FindConVar("director_no_mobs").BoolValue=true;
}
