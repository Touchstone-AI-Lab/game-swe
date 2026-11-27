#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <nextmap>

#define NONCE "__GCB_NONCE__"

public Plugin myinfo =
{
	name = "GCB Competitive Rework invalid-map guard",
	author = "GameCodeBench",
	description = "Private isolated real-server guard check",
	version = "1.0"
};

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, IssueInvalid, _, TIMER_FLAG_NO_MAPCHANGE);
}

Action IssueInvalid(Handle timer)
{
	ForceChangeLevel("__gcb_no_such_map__", "GameCodeBench invalid-map guard");
	CreateTimer(2.0, CheckInvalid, _, TIMER_FLAG_NO_MAPCHANGE);
	return Plugin_Stop;
}

Action CheckInvalid(Handle timer)
{
	char map[64];
	GetCurrentMap(map, sizeof(map));
	bool ok = StrEqual(map, "c1m1_hotel");
	PrintToServer("@@GCB_SM@@%s:CASE:changelevel_invalid_name_is_not_rewritten:%s:invalid input does not move the server to an unrelated map", NONCE, ok ? "PASS" : "FAIL");
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:1", NONCE, ok ? 1 : 0);
	ServerCommand("quit");
	return Plugin_Stop;
}
