#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;
int g_Client;
int g_Pistol;
bool g_Ready;
float g_EmptyTimestamp;

public Plugin myinfo =
{
	name = "GCB Competitive Rework incap suite",
	author = "GameCodeBench",
	description = "Private engine-dispatched player-command checks",
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
	char name[64], author[64], version[32], url[128];
	return plugin != null
		&& GetPluginInfo(plugin, PlInfo_Name, name, sizeof(name))
		&& GetPluginInfo(plugin, PlInfo_Author, author, sizeof(author))
		&& GetPluginInfo(plugin, PlInfo_Version, version, sizeof(version))
		&& GetPluginInfo(plugin, PlInfo_URL, url, sizeof(url))
		&& StrEqual(name, "[L4D/2] Incap Fire Fix")
		&& StrEqual(author, "Sir") && StrEqual(version, "1.0.1")
		&& StrEqual(url, "https://github.com/SirPlease/L4D2-Competitive-Rework");
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, BeginSuite);
}

Action BeginSuite(Handle timer)
{
	Handle task = FindPluginByFile("l4d2_incap_fire_fix.smx");
	Case("incap_runtime_plugin_loaded", MetadataMatches(task),
		"the submitted plugin loads with its established metadata");

	g_Client = CreateFakeClient("gcb-incap-survivor");
	if (g_Client > 0) ChangeClientTeam(g_Client, 2);
	g_Pistol = CreateEntityByName("weapon_pistol");
	if (g_Pistol > MaxClients)
	{
		DispatchSpawn(g_Pistol);
		SetEntPropEnt(g_Client, Prop_Send, "m_hActiveWeapon", g_Pistol);
	}
	g_Ready = task != null && g_Client > 0 && IsClientInGame(g_Client)
		&& g_Pistol > MaxClients && IsValidEntity(g_Pistol);
	if (g_Ready)
	{
		SetEntProp(g_Client, Prop_Send, "m_isIncapacitated", 1, 1);
		SetEntProp(g_Pistol, Prop_Send, "m_iClip1", 0);
		g_EmptyTimestamp = GetGameTime() - 0.25;
		SetEntPropFloat(g_Pistol, Prop_Send, "m_flNextSecondaryAttack", g_EmptyTimestamp);
	}
	CreateTimer(0.20, CheckEmpty);
	return Plugin_Stop;
}

Action CheckEmpty(Handle timer)
{
	float now = GetGameTime();
	float after = g_Ready ? GetEntPropFloat(g_Pistol, Prop_Send, "m_flNextSecondaryAttack") : 9999.0;
	Case("incap_empty_clip_leaves_reload_unblocked", g_Ready && FloatAbs(after - g_EmptyTimestamp) < 0.0001,
		"an empty clip preserves the seeded timestamp during real player commands");
	if (g_Ready)
	{
		SetEntProp(g_Pistol, Prop_Send, "m_iClip1", 5);
		SetEntPropFloat(g_Pistol, Prop_Send, "m_flNextSecondaryAttack", now - 0.25);
	}
	CreateTimer(0.20, CheckLoaded);
	return Plugin_Stop;
}

Action CheckLoaded(Handle timer)
{
	float now = GetGameTime();
	float after = g_Ready ? GetEntPropFloat(g_Pistol, Prop_Send, "m_flNextSecondaryAttack") : -1.0;
	Case("incap_loaded_clip_delays_secondary_attack", g_Ready && after >= now + 0.30,
		"the established loaded-clip shove suppression remains active");
	if (g_Ready) SetEntProp(g_Client, Prop_Send, "m_isIncapacitated", 0, 1);
	CreateTimer(0.20, CheckRelease);
	return Plugin_Stop;
}

Action CheckRelease(Handle timer)
{
	float now = GetGameTime();
	float after = g_Ready ? GetEntPropFloat(g_Pistol, Prop_Send, "m_flNextSecondaryAttack") : 9999.0;
	Case("incap_exit_releases_applied_delay", g_Ready && after <= now + 0.10,
		"leaving incap clears a delay owned by the plugin");
	if (g_Ready)
	{
		ChangeClientTeam(g_Client, 3);
		SetEntProp(g_Client, Prop_Send, "m_isIncapacitated", 1, 1);
		SetEntPropFloat(g_Pistol, Prop_Send, "m_flNextSecondaryAttack", now + 4.0);
	}
	CreateTimer(0.20, CheckNonSurvivor);
	return Plugin_Stop;
}

Action CheckNonSurvivor(Handle timer)
{
	float now = GetGameTime();
	float after = g_Ready ? GetEntPropFloat(g_Pistol, Prop_Send, "m_flNextSecondaryAttack") : -1.0;
	Case("incap_non_survivor_is_unchanged", g_Ready && after >= now + 3.60,
		"the plugin leaves clients outside the Survivor path untouched");
	if (g_Ready)
	{
		ChangeClientTeam(g_Client, 2);
		SetEntProp(g_Client, Prop_Send, "m_isIncapacitated", 1, 1);
		SetEntPropEnt(g_Client, Prop_Send, "m_hActiveWeapon", -1);
	}
	CreateTimer(0.20, FinishSuite);
	return Plugin_Stop;
}

Action FinishSuite(Handle timer)
{
	bool safe = g_Ready && IsClientInGame(g_Client)
		&& FindPluginByFile("l4d2_incap_fire_fix.smx") != null;
	Case("incap_missing_active_weapon_is_safe", safe,
		"real player-command dispatch tolerates a missing active weapon");
	if (g_Pistol > MaxClients && IsValidEntity(g_Pistol)) RemoveEntity(g_Pistol);
	if (g_Client > 0 && IsClientConnected(g_Client)) KickClient(g_Client);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
