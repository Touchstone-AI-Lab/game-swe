#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <sdkhooks>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"
#define GASCAN_MODEL "models/props_junk/gascan001a.mdl"
#define CONTROL_MODEL "models/props_junk/propanecanister001a.mdl"

int g_Passed;
int g_Total;
int g_Attacker;
int g_GasCan;
int g_PreCount;
int g_PostCount;
int g_PreGasCan = -1;
int g_PreInflictor = -1;
int g_PreAttacker = -1;
int g_PostGasCan = -1;
int g_PostInflictor = -1;
int g_PostAttacker = -1;

public Plugin myinfo =
{
	name = "GCB Left4DHooks unpicked gas-can suite",
	author = "GameCodeBench",
	description = "Private real-engine physics-prop forward checks",
	version = "1.0"
};

void Case(const char[] name, bool ok, const char[] detail)
{
	g_Total++;
	if (ok) g_Passed++;
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

public Action L4D2_CGasCan_EventKilled(int gascan, int &inflictor, int &attacker)
{
	g_PreCount++;
	g_PreGasCan = gascan;
	g_PreInflictor = inflictor;
	g_PreAttacker = attacker;
	return Plugin_Continue;
}

public void L4D2_CGasCan_EventKilled_Post(int gascan, int inflictor, int attacker)
{
	g_PostCount++;
	g_PostGasCan = gascan;
	g_PostInflictor = inflictor;
	g_PostAttacker = attacker;
}

int CreatePhysicalGasCan()
{
	int gascan = CreateEntityByName("prop_physics");
	if (gascan > MaxClients)
	{
		DispatchKeyValue(gascan, "model", GASCAN_MODEL);
		DispatchSpawn(gascan);
		ActivateEntity(gascan);
		SetEntProp(gascan, Prop_Data, "m_takedamage", 2);
		SetEntProp(gascan, Prop_Data, "m_iHealth", 1);
	}
	return gascan;
}

public void OnMapStart()
{
	PrecacheModel(GASCAN_MODEL, true);
	PrecacheModel(CONTROL_MODEL, true);
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	g_Attacker = CreateFakeClient("gcb-gascan-attacker");
	if (g_Attacker > 0) ChangeClientTeam(g_Attacker, 2);

	// Map-placed cans that have never entered a player's inventory use the
	// generic physics-prop damage path while retaining the gas-can model.
	g_GasCan = CreatePhysicalGasCan();
	bool ready = LibraryExists("left4dhooks") && g_Attacker > 0 && g_GasCan > MaxClients;
	Case("runtime_unpicked_gascan_fixture_ready", ready, "the library, survivor attacker, and an unpicked physical gas can are available");

	if (ready) SDKHooks_TakeDamage(g_GasCan, g_Attacker, g_Attacker, 1000.0, DMG_BULLET);
	CreateTimer(0.25, CheckGasCan);
	return Plugin_Stop;
}

Action CheckGasCan(Handle timer)
{
	Case("unpicked_gascan_pre_forward_once", g_PreCount == 1, "damaging one never-picked-up gas can dispatches exactly one pre forward");
	Case("unpicked_gascan_pre_forward_arguments", g_PreGasCan == g_GasCan && g_PreInflictor == g_Attacker && g_PreAttacker == g_Attacker,
		"the pre forward identifies the damaged gas can and its real inflictor and attacker");
	Case("unpicked_gascan_post_forward_once", g_PostCount == 1, "the same damage dispatches exactly one post forward");
	Case("unpicked_gascan_post_forward_arguments", g_PostGasCan == g_GasCan && g_PostInflictor == g_Attacker && g_PostAttacker == g_Attacker,
		"the post forward preserves the matching gas can, inflictor, and attacker");

	g_PreCount = 0;
	g_PostCount = 0;
	int weaponGasCan = CreateEntityByName("weapon_gascan");
	if (weaponGasCan > MaxClients)
	{
		DispatchSpawn(weaponGasCan);
		ActivateEntity(weaponGasCan);
		SetEntProp(weaponGasCan, Prop_Data, "m_takedamage", 2);
		SetEntProp(weaponGasCan, Prop_Data, "m_iHealth", 1);
		SDKHooks_TakeDamage(weaponGasCan, g_Attacker, g_Attacker, 1000.0, DMG_BULLET);
	}
	CreateTimer(0.25, CheckWeaponGasCan);
	return Plugin_Stop;
}

Action CheckWeaponGasCan(Handle timer)
{
	Case("weapon_gascan_path_dispatches_once", g_PreCount == 1 && g_PostCount == 1,
		"the existing weapon-gas-can class path still dispatches one pre/post pair without duplication");
	Case("weapon_gascan_path_preserves_arguments", g_PreInflictor == g_Attacker && g_PreAttacker == g_Attacker
		&& g_PostInflictor == g_Attacker && g_PostAttacker == g_Attacker,
		"the existing class path preserves its real inflictor and attacker");

	int preBefore = g_PreCount;
	int postBefore = g_PostCount;
	int prop = CreateEntityByName("prop_physics");
	if (prop > MaxClients)
	{
		DispatchKeyValue(prop, "model", CONTROL_MODEL);
		DispatchSpawn(prop);
		ActivateEntity(prop);
		SetEntProp(prop, Prop_Data, "m_takedamage", 2);
		SetEntProp(prop, Prop_Data, "m_iHealth", 1);
		SDKHooks_TakeDamage(prop, g_Attacker, g_Attacker, 1000.0, DMG_BULLET);
	}
	CreateTimer(0.25, CheckControl, (preBefore << 16) | (postBefore & 0xFFFF));
	return Plugin_Stop;
}

Action CheckControl(Handle timer, any packed)
{
	int preBefore = packed >> 16;
	int postBefore = packed & 0xFFFF;
	Case("ordinary_physics_prop_never_dispatches_gascan_family", g_PreCount == preBefore && g_PostCount == postBefore,
		"damaging an ordinary physics prop does not dispatch gas-can forwards");

	if (g_Attacker > 0 && IsClientConnected(g_Attacker)) KickClient(g_Attacker);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
