#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;

public Plugin myinfo =
{
	name = "GCB Left4DHooks entity-address suite",
	author = "GameCodeBench",
	description = "Private real-engine address round-trip checks",
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
	bool loaded = LibraryExists("left4dhooks");
	Case("runtime_entity_address_library_loaded", loaded,
		"the published entity-address native is available after a normal load");

	int checked;
	int roundTrips;
	int nonEdicts;
	int nonEdictRoundTrips;
	bool stable = true;

	for (int entity = 0; entity <= 4096; entity++)
	{
		if (!IsValidEdict(entity) && !IsValidEntity(entity))
			continue;

		Address address = GetEntityAddress(entity);
		if (address == Address_Null)
			continue;

		checked++;
		int first = L4D_GetEntityFromAddress(address);
		int second = L4D_GetEntityFromAddress(address);
		if (first == entity)
			roundTrips++;
		if (first != second)
			stable = false;

		if (!IsValidEdict(entity) && IsValidEntity(entity))
		{
			nonEdicts++;
			if (first == entity)
				nonEdictRoundTrips++;
		}
	}

	char detail[192];
	FormatEx(detail, sizeof(detail), "checked=%d non-edict=%d", checked, nonEdicts);
	Case("entity_address_fixture_covers_engine_entities", checked > 0 && nonEdicts > 0, detail);

	FormatEx(detail, sizeof(detail), "round-tripped=%d/%d", roundTrips, checked);
	Case("entity_addresses_roundtrip_for_all_live_entities", checked > 0 && roundTrips == checked, detail);

	FormatEx(detail, sizeof(detail), "non-edict round-tripped=%d/%d", nonEdictRoundTrips, nonEdicts);
	Case("non_edict_entity_addresses_roundtrip", nonEdicts > 0 && nonEdictRoundTrips == nonEdicts, detail);

	Case("entity_address_lookup_is_stable", stable,
		"two reads of every live entity address return the same engine index");
	Case("null_entity_address_returns_negative_one", L4D_GetEntityFromAddress(Address_Null) == -1,
		"the null address remains the documented invalid lookup");

	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
