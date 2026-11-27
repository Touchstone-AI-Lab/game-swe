#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>

public void OnMapStart()
{
    ConVar hibernate = FindConVar("sv_hibernate_when_empty");
    if (hibernate != null) hibernate.IntValue = 0;
    int client = CreateFakeClient("gcb-director-fixture");
    if (client > 0) ChangeClientTeam(client, 2);
    CreateTimer(1.0, StartFixture, _, TIMER_FLAG_NO_MAPCHANGE);
}

public Action StartFixture(Handle timer)
{
    int flags = GetCommandFlags("script");
    SetCommandFlags("script", flags & ~FCVAR_CHEAT);
    ServerCommand("script printl(\"GCB fixture clock \" + Time()); ::GCB_L4D2.Run(null)");
    ServerExecute();
    SetCommandFlags("script", flags);
    return Plugin_Stop;
}
