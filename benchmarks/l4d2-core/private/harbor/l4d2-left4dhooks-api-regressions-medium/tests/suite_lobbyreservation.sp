#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;

public Plugin myinfo =
{
	name = "GCB Left4DHooks lobby reservation suite",
	author = "GameCodeBench",
	description = "Private native parsing and server-memory round-trip checks",
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
	Case("runtime_lobby_reservation_library_loaded", loaded,
		"the published lobby reservation natives are available");

	char original[20];
	char actual[20];
	L4D_GetLobbyReservation(original, sizeof(original));

	L4D_SetLobbyReservation("1");
	L4D_GetLobbyReservation(actual, sizeof(actual));
	Case("short_lobby_cookie_call_survives", true,
		"a one-digit hexadecimal cookie returns normally without a native error");
	Case("short_lobby_cookie_preserves_word_placement", StrEqual(actual, "100000000", false),
		"the one-digit cookie retains the established high-word representation");

	L4D_SetLobbyReservation("123456789ABCDEF0");
	L4D_GetLobbyReservation(actual, sizeof(actual));
	Case("full_lobby_cookie_roundtrips", StrEqual(actual, "123456789ABCDEF0", false),
		"a full 64-bit hexadecimal cookie round-trips exactly");

	L4D_SetLobbyReservation(original);
	L4D_GetLobbyReservation(actual, sizeof(actual));
	Case("lobby_cookie_can_be_restored", StrEqual(actual, original, false),
		"the original reservation cookie is restored after the checks");

	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
