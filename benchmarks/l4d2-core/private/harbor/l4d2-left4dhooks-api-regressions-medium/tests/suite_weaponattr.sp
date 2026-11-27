#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"
#define TEST_WEAPON "weapon_rifle"

int g_Passed;
int g_Total;

public Plugin myinfo =
{
	name = "GCB Left4DHooks weapon-attribute suite",
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

bool Near(float actual, float expected)
{
	return FloatAbs(actual - expected) < 0.001;
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	bool loaded = LibraryExists("left4dhooks") && L4D2_IsValidWeapon(TEST_WEAPON);
	Case("runtime_weaponattr_library_loaded", loaded, "left4dhooks and the engine rifle definition are available");
	if (!loaded)
	{
		Case("ordinary_float_weapon_attribute_roundtrips", false, "weapon definition unavailable");
		Case("penetration_layers_store_integral_count", false, "weapon definition unavailable");
		Case("penetration_layers_preserve_adjacent_power", false, "weapon definition unavailable");
		Case("missing_float_weapon_attribute_returns_negative_one", false, "weapon definition unavailable");
		PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
		ServerCommand("quit");
		return Plugin_Stop;
	}

	float originalLayers = L4D2_GetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationNumLayers);
	float originalPower = L4D2_GetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationPower);

	L4D2_SetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationPower, 2.75);
	float power = L4D2_GetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationPower);
	Case("ordinary_float_weapon_attribute_roundtrips", Near(power, 2.75), "ordinary decimal float attributes round-trip unchanged");

	L4D2_SetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationNumLayers, 3.75);
	float layers = L4D2_GetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationNumLayers);
	Case("penetration_layers_store_integral_count", Near(layers, 3.0), "3.75 stores and reads as the integral layer count 3.0");

	float powerAfterLayers = L4D2_GetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationPower);
	Case("penetration_layers_preserve_adjacent_power", Near(powerAfterLayers, 2.75), "setting layer count leaves adjacent penetration power unchanged");

	float missing = L4D2_GetFloatWeaponAttribute("weapon_gcb_missing", L4D2FWA_PenetrationPower);
	Case("missing_float_weapon_attribute_returns_negative_one", Near(missing, -1.0), "missing weapon returns numeric -1.0");

	L4D2_SetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationNumLayers, originalLayers);
	L4D2_SetFloatWeaponAttribute(TEST_WEAPON, L4D2FWA_PenetrationPower, originalPower);

	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
