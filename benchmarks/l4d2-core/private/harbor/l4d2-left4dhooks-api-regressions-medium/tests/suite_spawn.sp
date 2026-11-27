#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;

public Plugin myinfo =
{
	name = "GCB Left4DHooks spawn-time suite",
	author = "GameCodeBench",
	description = "Private real-engine behavioral checks",
	version = "1.0"
};

void Case(const char[] name, bool ok, const char[] detail)
{
	g_Total++;
	if (ok) g_Passed++;
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

void Finish()
{
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	Case("runtime_spawn_library_loaded", LibraryExists("left4dhooks"), "left4dhooks library is available");
	Case("spawn_timer_invalid_zero", FloatAbs(L4D2Direct_GetSpawnTimer(0) - (-1.0)) < 0.001, "client zero returns -1.0");
	Case("spawn_timer_invalid_above_max", FloatAbs(L4D2Direct_GetSpawnTimer(MaxClients + 1) - (-1.0)) < 0.001, "client above MaxClients returns -1.0");

	int client = CreateFakeClient("gcb-infected");
	if (client > 0) ChangeClientTeam(client, 3);
	bool available = client > 0 && IsClientInGame(client);
	float before = GetGameTime();
	int teamBefore = available ? GetClientTeam(client) : -1;
	L4D_SetPlayerSpawnTime(client, 25.0, false);
	float absolute = L4D2Direct_GetSpawnTimer(client);
	float relative = L4D_GetPlayerSpawnTime(client);
	Case("spawn_timer_returns_absolute_field", available && FloatAbs(absolute - (before + 25.0)) < 0.75, "direct API exposes m_flBecomeGhostAt");

	L4D_SetPlayerSpawnTime(client, 7.25, false);
	float updated = L4D2Direct_GetSpawnTimer(client);
	float remaining = L4D_GetPlayerSpawnTime(client);
	Case("spawn_timer_updates_and_relative_api_remains_distinct", FloatAbs(updated - (GetGameTime() + 7.25)) < 0.75 && relative > 23.5 && relative <= 25.1 && remaining > 6.5 && remaining <= 7.3, "direct and relative APIs retain separate contracts");
	Case("spawn_timer_read_preserves_adjacent_state", available && IsClientInGame(client) && GetClientTeam(client) == teamBefore, "direct reads do not alter client state");
	if (available) KickClient(client);
	Finish();
	return Plugin_Stop;
}
