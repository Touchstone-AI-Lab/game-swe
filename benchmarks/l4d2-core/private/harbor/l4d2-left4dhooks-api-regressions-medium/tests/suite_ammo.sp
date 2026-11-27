#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;

public Plugin myinfo =
{
	name = "GCB Left4DHooks Ammo suite",
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
	Case("runtime_ammo_library_loaded", LibraryExists("left4dhooks"), "left4dhooks library is available");

	int top = AmmoDef.GetAmmoIndex();
	Case("ammo_index_range_is_engine_valid", top > 2 && top < 128, "AmmoDef exposes a bounded index range");

	bool nonempty = true;
	bool roundtrip = true;
	bool stable = true;
	bool unique = true;
	bool fieldsStable = true;
	StringMap names = new StringMap();
	for (int index = 1; index < top; index++)
	{
		Ammo_t ammo = AmmoDef.GetAmmoOfIndex(index);
		char first[64];
		char second[64];
		int damageType = ammo.nDamageType;
		ammo.GetName(first, sizeof(first));
		ammo.GetName(second, sizeof(second));
		if (first[0] == '\0') nonempty = false;
		if (strcmp(first, second) != 0) stable = false;
		if (first[0] == '\0' || AmmoDef.Index(first) != index) roundtrip = false;
		if (ammo.nDamageType != damageType) fieldsStable = false;
		int previous;
		if (first[0] == '\0' || names.GetValue(first, previous)) unique = false;
		else names.SetValue(first, index);
	}
	delete names;

	Case("ammo_names_are_nonempty", nonempty, "every valid Ammo_t has a name");
	Case("ammo_name_roundtrips_to_index", roundtrip, "AmmoDef.Index(GetName()) recovers the source index");
	Case("ammo_names_are_stable_and_unique", stable && unique, "repeated reads agree and valid entries are distinct");
	Case("ammo_getname_preserves_other_fields", fieldsStable, "GetName does not mutate nDamageType");
	Finish();
	return Plugin_Stop;
}
