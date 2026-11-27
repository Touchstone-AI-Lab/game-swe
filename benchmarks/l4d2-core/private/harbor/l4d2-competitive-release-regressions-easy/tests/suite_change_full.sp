#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <nextmap>
#include <dhooks>

#define NONCE "__GCB_NONCE__"

bool g_Issued;
bool g_DirectorObserved;
DynamicDetour g_Observer;

public Plugin myinfo =
{
	name = "GCB Competitive Rework full-map guard",
	author = "GameCodeBench",
	description = "Private complete-map and Director preservation guards",
	version = "1.0"
};

void Case(const char[] name, bool ok, const char[] detail)
{
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

void Finish(bool mapOk, bool directorOk, const char[] detail)
{
	Case("changelevel_complete_name_still_works", mapOk, detail);
	Case("changelevel_director_work_is_preserved_for_complete_name", directorOk,
		"the existing Director begin-changelevel work still receives the complete name");
	int passed = (mapOk ? 1 : 0) + (directorOk ? 1 : 0);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:2", NONCE, passed);
	ServerCommand("quit");
}

public void OnPluginStart()
{
	GameData data = new GameData("gcb_change_observer");
	if (data != null)
	{
		g_Observer = DynamicDetour.FromConf(data, "CTerrorGameRules::OnBeginChangeLevel");
		if (g_Observer != null) g_Observer.Enable(Hook_Pre, ObserveDirectorChange);
	}
	delete data;
}

MRESReturn ObserveDirectorChange(DHookParam params)
{
	char map[64];
	params.GetString(1, map, sizeof(map));
	if (g_Issued && StrEqual(map, "c1m3_mall")) g_DirectorObserved = true;
	return MRES_Ignored;
}

public void OnMapStart()
{
	if (!g_Issued)
	{
		CreateTimer(1.0, IssueFull, _, TIMER_FLAG_NO_MAPCHANGE);
		return;
	}
	char map[64];
	GetCurrentMap(map, sizeof(map));
	Finish(StrEqual(map, "c1m3_mall"), g_DirectorObserved,
		"an already complete installed map name reaches the engine unchanged");
}

Action IssueFull(Handle timer)
{
	g_Issued = true;
	ForceChangeLevel("c1m3_mall", "GameCodeBench complete-name guard");
	CreateTimer(9.0, FullTimeout, _, TIMER_FLAG_NO_MAPCHANGE);
	return Plugin_Stop;
}

Action FullTimeout(Handle timer)
{
	Finish(false, g_DirectorObserved, "the full installed map did not complete its transition");
	return Plugin_Stop;
}
