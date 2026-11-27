#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>

public void OnPluginStart() { PrintToServer("GCB bootstrap loaded"); }

public void OnMapStart()
{
    PrintToServer("GCB bootstrap map start");
    FindConVar("sb_all_bot_game").IntValue=1;
    FindConVar("allow_all_bot_survivor_team").IntValue=1;
    ConVar hibernate = FindConVar("sv_hibernate_when_empty");
    if (hibernate != null) hibernate.IntValue = 0;
    int client = CreateFakeClient("gcb-director-fixture");
    if (client > 0) ChangeClientTeam(client, 2);
    PrintToServer("GCB bootstrap client=%d",client);
    CreateTimer(1.0, StartFixture, _, TIMER_FLAG_NO_MAPCHANGE);
}

public Action StartFixture(Handle timer)
{
    int flags = GetCommandFlags("script");
    SetCommandFlags("script", flags & ~FCVAR_CHEAT);
    ServerCommand("script \"GCB_L4D2.Run(null)\"");
    ServerExecute();
    SetCommandFlags("script", flags);
    CreateTimer(0.15, PulseFixture, _, TIMER_REPEAT | TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

public Action PulseFixture(Handle timer)
{
    int flags = GetCommandFlags("script");
    SetCommandFlags("script", flags & ~FCVAR_CHEAT);
    ServerCommand("script \"GCB_L4D2.Tick()\"");
    ServerExecute();
    SetCommandFlags("script", flags);
    return Plugin_Continue;
}
