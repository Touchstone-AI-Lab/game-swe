#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;

public Plugin myinfo =
{
	name = "GCB Left4DHooks melee-info suite",
	author = "GameCodeBench",
	description = "Private real-engine melee database checks",
	version = "1.0"
};

void Case(const char[] name, bool ok, const char[] detail)
{
	g_Total++;
	if (ok) g_Passed++;
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	int id = L4D2_GetMeleeWeaponIndex("fireaxe");
	Case("runtime_melee_info_library_loaded", LibraryExists("left4dhooks") && id >= 0,
		"left4dhooks and the map's fireaxe melee definition are available");

	float damage = L4D2_GetFloatMeleeAttribute(id, L4D2FMWA_Damage);
	int flags = L4D2_GetIntMeleeAttribute(id, L4D2IMWA_DamageFlags);
	bool decapitates = L4D2_GetBoolMeleeAttribute(id, L4D2BMWA_Decapitates);
	Case("melee_float_attribute_is_readable", damage > 0.0 && damage < 1000.0,
		"the real fireaxe damage attribute is a bounded positive float");
	Case("melee_int_attribute_is_readable", flags >= 0, "the real fireaxe damage flags are readable");
	Case("melee_bool_attribute_is_stable", L4D2_GetBoolMeleeAttribute(id, L4D2BMWA_Decapitates) == decapitates,
		"repeated reads of the real decapitation flag agree");

	float changed = damage + 7.25;
	L4D2_SetFloatMeleeAttribute(id, L4D2FMWA_Damage, changed);
	bool roundtrip = FloatAbs(L4D2_GetFloatMeleeAttribute(id, L4D2FMWA_Damage) - changed) < 0.01;
	L4D2_SetFloatMeleeAttribute(id, L4D2FMWA_Damage, damage);
	roundtrip = roundtrip && FloatAbs(L4D2_GetFloatMeleeAttribute(id, L4D2FMWA_Damage) - damage) < 0.01;
	Case("melee_float_attribute_roundtrips_and_restores", roundtrip,
		"a temporary fireaxe damage update round-trips and restores the original value");

	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
