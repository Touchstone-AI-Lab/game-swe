#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <nextmap>
#include <dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;
int g_Phase;
int g_DirectorCalls;
int g_FirstDirectorCalls;
int g_SecondDirectorCalls;
bool g_DirectorNamesFull = true;
DynamicDetour g_Observer;

public Plugin myinfo =
{
	name = "GCB Competitive Rework changelevel suite",
	author = "GameCodeBench",
	description = "Private real-map and Director argument checks",
	version = "1.0"
};

void Case(const char[] name, bool ok, const char[] detail)
{
	g_Total++;
	if (ok) g_Passed++;
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

bool MetadataMatches(Handle plugin)
{
	char name[64], author[96], version[32], url[128];
	return plugin != null
		&& GetPluginInfo(plugin, PlInfo_Name, name, sizeof(name))
		&& GetPluginInfo(plugin, PlInfo_Author, author, sizeof(author))
		&& GetPluginInfo(plugin, PlInfo_Version, version, sizeof(version))
		&& GetPluginInfo(plugin, PlInfo_URL, url, sizeof(url))
		&& StrEqual(name, "[L4D2] Fix Changelevel")
		&& StrEqual(author, "Lux (for \"l4d2_changelevel\"), Forgetest")
		&& StrEqual(version, "1.3")
		&& StrEqual(url, "https://github.com/Target5150/MoYu_Server_Stupid_Plugins");
}

void Finish()
{
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
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
	g_DirectorCalls++;
	if (g_Phase == 1)
	{
		g_FirstDirectorCalls++;
		if (!StrEqual(map, "c1m2_streets")) g_DirectorNamesFull = false;
	}
	if (g_Phase == 2)
	{
		g_SecondDirectorCalls++;
		if (!StrEqual(map, "c2m3_coaster")) g_DirectorNamesFull = false;
	}
	return MRES_Ignored;
}

public void OnAllPluginsLoaded()
{
	Case("changelevel_runtime_plugin_loaded",
		MetadataMatches(FindPluginByFile("l4d2_fix_changelevel.smx")) && g_Observer != null,
		"the submitted plugin metadata and verifier-owned Director observer load");
}

public void OnMapStart()
{
	if (g_Phase == 0)
	{
		g_Phase = 1;
		CreateTimer(1.0, IssueFirst, _, TIMER_FLAG_NO_MAPCHANGE);
	}
	else if (g_Phase == 1)
	{
		char map[64];
		GetCurrentMap(map, sizeof(map));
		Case("changelevel_unique_partial_reaches_full_map", StrEqual(map, "c1m2_streets"),
			"c1m2 reaches c1m2_streets");
		g_Phase = 2;
		CreateTimer(1.0, IssueSecond, _, TIMER_FLAG_NO_MAPCHANGE);
	}
	else if (g_Phase == 2)
	{
		char map[64];
		GetCurrentMap(map, sizeof(map));
		Case("changelevel_second_unique_partial_reaches_full_map", StrEqual(map, "c2m3_coaster"),
			"a second unique prefix is resolved generically");
		Case("changelevel_director_receives_same_full_map",
			g_DirectorNamesFull && g_DirectorCalls >= 2
				&& g_FirstDirectorCalls >= 1 && g_SecondDirectorCalls >= 1,
			"Director transition work receives each same resolved full map name");
		Finish();
	}
}

Action IssueFirst(Handle timer)
{
	ForceChangeLevel("c1m2", "GameCodeBench first unique-partial check");
	CreateTimer(9.0, FirstTimeout, _, TIMER_FLAG_NO_MAPCHANGE);
	return Plugin_Stop;
}

Action IssueSecond(Handle timer)
{
	ForceChangeLevel("c2m3", "GameCodeBench second unique-partial check");
	CreateTimer(9.0, SecondTimeout, _, TIMER_FLAG_NO_MAPCHANGE);
	return Plugin_Stop;
}

Action FirstTimeout(Handle timer)
{
	Case("changelevel_unique_partial_reaches_full_map", false,
		"the first unique partial did not reach its installed full map");
	Case("changelevel_second_unique_partial_reaches_full_map", false,
		"the first transition failed before the second prefix could be tested");
	Case("changelevel_director_receives_same_full_map", false,
		"the complete Director transition sequence did not run");
	Finish();
	return Plugin_Stop;
}

Action SecondTimeout(Handle timer)
{
	Case("changelevel_second_unique_partial_reaches_full_map", false,
		"the second unique partial did not reach its installed full map");
	Case("changelevel_director_receives_same_full_map", false,
		"the complete Director transition sequence did not receive full names");
	Finish();
	return Plugin_Stop;
}
