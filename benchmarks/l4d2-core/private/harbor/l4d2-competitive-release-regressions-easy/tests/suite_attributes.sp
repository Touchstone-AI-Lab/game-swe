#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <sdkhooks>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;
Handle g_UnloadForward;
Handle g_ReloadModifierCall;
int g_Attacker = -1;
int g_Tank = -1;
int g_Rifle = -1;
int g_Shotgun = -1;

public Plugin myinfo =
{
	name = "GCB Competitive Rework attribute suite",
	author = "GameCodeBench",
	description = "Private engine attribute and named-forward checks",
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
	char name[64], author[64], version[32];
	return plugin != null
		&& GetPluginInfo(plugin, PlInfo_Name, name, sizeof(name))
		&& GetPluginInfo(plugin, PlInfo_Author, author, sizeof(author))
		&& GetPluginInfo(plugin, PlInfo_Version, version, sizeof(version))
		&& StrEqual(name, "L4D2 Weapon Attributes")
		&& StrEqual(author, "Jahze, A1m`, Forgetest")
		&& StrEqual(version, "3.1.0");
}

void SetWeaponInt(const char[] weapon, const char[] attribute, int value)
{
	ServerCommand("sm_weapon %s %s %d", weapon, attribute, value);
	ServerExecute();
}

void SetWeaponFloat(const char[] weapon, const char[] attribute, float value)
{
	ServerCommand("sm_weapon %s %s %.3f", weapon, attribute, value);
	ServerExecute();
}

bool EmitUnload()
{
	if (g_UnloadForward == null) return false;
	Action result;
	Call_StartForward(g_UnloadForward);
	return Call_Finish(result) == SP_ERROR_NONE;
}

bool InvokeConfigsExecuted(Handle plugin)
{
	Function callback = GetFunctionByName(plugin, "OnConfigsExecuted");
	if (callback == INVALID_FUNCTION) return false;
	Call_StartFunction(plugin, callback);
	return Call_Finish() == SP_ERROR_NONE;
}

float ReloadModifier()
{
	if (g_ReloadModifierCall == null || g_Shotgun <= MaxClients || !IsValidEntity(g_Shotgun)) return -999.0;
	return SDKCall(g_ReloadModifierCall, g_Shotgun);
}

int TankDamage(float damage = 20.0)
{
	if (g_Tank <= 0 || !IsClientInGame(g_Tank) || g_Attacker <= 0 || !IsClientInGame(g_Attacker)) return -999;
	SetEntityHealth(g_Tank, 1000);
	SDKHooks_TakeDamage(g_Tank, g_Rifle, g_Attacker, damage, DMG_BULLET, g_Rifle, .bypassHooks = false);
	return 1000 - GetClientHealth(g_Tank);
}

public void OnPluginStart()
{
	g_UnloadForward = CreateGlobalForward("LGO_OnMatchModeUnloaded", ET_Ignore);
	GameData data = new GameData("gcb_weapon_observer");
	if (data != null)
	{
		StartPrepSDKCall(SDKCall_Entity);
		if (PrepSDKCall_SetFromConf(data, SDKConf_Signature, "CBaseShotgun::GetReloadDurationModifier"))
		{
			PrepSDKCall_SetReturnInfo(SDKType_Float, SDKPass_Plain);
			g_ReloadModifierCall = EndPrepSDKCall();
		}
	}
	delete data;
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	Handle task = FindPluginByFile("l4d2_weapon_attributes.smx");
	bool runtime = MetadataMatches(task) && LibraryExists("left4dhooks")
		&& g_UnloadForward != null && g_ReloadModifierCall != null;
	Case("attributes_runtime_dependencies_loaded", runtime,
		"the submitted plugin metadata, Left4DHooks and verifier observers load together");

	g_Attacker = CreateFakeClient("gcb-attribute-survivor");
	if (g_Attacker > 0) ChangeClientTeam(g_Attacker, 2);
	g_Rifle = CreateEntityByName("weapon_rifle");
	g_Shotgun = CreateEntityByName("weapon_autoshotgun");
	if (g_Rifle > MaxClients) DispatchSpawn(g_Rifle);
	if (g_Shotgun > MaxClients) DispatchSpawn(g_Shotgun);
	if (g_Attacker > 0 && g_Rifle > MaxClients)
	{
		EquipPlayerWeapon(g_Attacker, g_Rifle);
		SetEntPropEnt(g_Attacker, Prop_Send, "m_hActiveWeapon", g_Rifle);
	}
	float position[3] = { 128.0, 128.0, 32.0 };
	float angles[3];
	g_Tank = L4D2_SpawnTank(position, angles);
	char activeWeapon[64];
	if (g_Attacker > 0) GetClientWeapon(g_Attacker, activeWeapon, sizeof(activeWeapon));
	PrintToServer("GCB entity diagnostics: attacker=%d weapon=%s tank=%d team=%d class=%d alive=%d",
		g_Attacker, activeWeapon, g_Tank,
		g_Tank > 0 ? GetClientTeam(g_Tank) : -1,
		g_Tank > 0 ? GetEntProp(g_Tank, Prop_Send, "m_zombieClass") : -1,
		g_Tank > 0 && IsPlayerAlive(g_Tank) ? 1 : 0);

	int rifleStock = L4D2_GetIntWeaponAttribute("rifle", L4D2IWA_Damage);
	int melee = L4D2_GetMeleeWeaponIndex("fireaxe");
	float meleeStock = melee >= 0 ? L4D2_GetFloatMeleeAttribute(melee, L4D2FMWA_Damage) : -1.0;
	int rifleBaseline = rifleStock + 3;
	float meleeBaseline = meleeStock + 4.0;
	L4D2_SetIntWeaponAttribute("rifle", L4D2IWA_Damage, rifleBaseline);
	if (melee >= 0) L4D2_SetFloatMeleeAttribute(melee, L4D2FMWA_Damage, meleeBaseline);
	float reloadBaseline = ReloadModifier();
	int tankBaseline = TankDamage();

	SetWeaponInt("rifle", "damage", rifleBaseline + 9);
	SetWeaponFloat("fireaxe", "damage", meleeBaseline + 11.0);
	SetWeaponFloat("rifle", "tankdamagemult", 2.0);
	SetWeaponFloat("autoshotgun", "reloaddurationmult", 1.75);
	int tankChanged = TankDamage();
	float reloadChanged = ReloadModifier();
	PrintToServer("GCB attribute diagnostics: tank base=%d changed=%d reload base=%.3f changed=%.3f", tankBaseline, tankChanged, reloadBaseline, reloadChanged);
	bool changed = L4D2_GetIntWeaponAttribute("rifle", L4D2IWA_Damage) == rifleBaseline + 9
		&& melee >= 0 && FloatAbs(L4D2_GetFloatMeleeAttribute(melee, L4D2FMWA_Damage) - (meleeBaseline + 11.0)) < 0.01
		&& tankBaseline > 0 && tankChanged >= tankBaseline * 2 - 1
		&& FloatAbs(reloadChanged - 1.75) < 0.01;
	Case("attributes_outgoing_mode_changes_take_effect", changed,
		"ordinary and plugin-managed outgoing mode attributes affect engine behavior");

	bool unloaded = runtime && EmitUnload();
	int tankRestored = TankDamage();
	float reloadRestored = ReloadModifier();
	bool restored = unloaded
		&& L4D2_GetIntWeaponAttribute("rifle", L4D2IWA_Damage) == rifleBaseline
		&& melee >= 0 && FloatAbs(L4D2_GetFloatMeleeAttribute(melee, L4D2FMWA_Damage) - meleeBaseline) < 0.01
		&& tankRestored == tankBaseline
		&& FloatAbs(reloadRestored - reloadBaseline) < 0.01;
	Case("attributes_unload_restores_engine_values", restored,
		"the named Confogl unload forward restores non-stock baselines and clears both multipliers");

	SetWeaponInt("rifle", "damage", rifleBaseline + 17);
	SetWeaponFloat("rifle", "tankdamagemult", 1.5);
	SetWeaponFloat("autoshotgun", "reloaddurationmult", 1.25);
	int tankSecond = TankDamage();
	float reloadSecond = ReloadModifier();
	PrintToServer("GCB second-mode diagnostics: tank base=%d changed=%d reload=%.3f", tankBaseline, tankSecond, reloadSecond);
	bool secondChanged = tankSecond > tankBaseline && FloatAbs(reloadSecond - 1.25) < 0.01;
	bool second = secondChanged && EmitUnload()
		&& L4D2_GetIntWeaponAttribute("rifle", L4D2IWA_Damage) == rifleBaseline
		&& TankDamage() == tankBaseline
		&& FloatAbs(ReloadModifier() - reloadBaseline) < 0.01;
	Case("attributes_second_mode_sees_true_baseline", second,
		"a second mode begins and ends at the same non-stock baseline without inherited multipliers");

	SetWeaponInt("rifle", "damage", rifleBaseline + 23);
	SetWeaponFloat("rifle", "tankdamagemult", 2.0);
	SetWeaponFloat("autoshotgun", "reloaddurationmult", 1.8);
	ServerCommand("sm_weapon_attributes_reset");
	ServerExecute();
	bool manual = L4D2_GetIntWeaponAttribute("rifle", L4D2IWA_Damage) == rifleBaseline
		&& TankDamage() == tankBaseline
		&& FloatAbs(ReloadModifier() - reloadBaseline) < 0.01;
	Case("attributes_manual_reset_command_remains_functional", manual,
		"the documented manual reset restores ordinary and plugin-managed values");

	SetWeaponInt("rifle", "damage", rifleBaseline + 29);
	SetWeaponFloat("autoshotgun", "reloaddurationmult", 1.2);
	L4D2_SetIntWeaponAttribute("rifle", L4D2IWA_Damage, rifleBaseline);
	bool configReset = InvokeConfigsExecuted(task)
		&& L4D2_GetIntWeaponAttribute("rifle", L4D2IWA_Damage) == rifleBaseline + 29
		&& FloatAbs(ReloadModifier() - 1.2) < 0.01;
	Case("attributes_config_reload_behavior_is_preserved", configReset,
		"normal config execution reapplies ordinary values without discarding plugin-managed state");

	ServerCommand("sm_weapon_attributes_reset");
	ServerExecute();
	if (g_Rifle > MaxClients && IsValidEntity(g_Rifle)) RemoveEntity(g_Rifle);
	if (g_Shotgun > MaxClients && IsValidEntity(g_Shotgun)) RemoveEntity(g_Shotgun);
	if (g_Attacker > 0 && IsClientConnected(g_Attacker)) KickClient(g_Attacker);
	if (g_Tank > 0 && IsClientConnected(g_Tank)) KickClient(g_Tank);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
