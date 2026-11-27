#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_ClientA;
int g_ClientB;
int g_CallsA;
int g_CallsB;
int g_Passed;
int g_Total;
bool g_CheckDuplicates;
bool g_PreArmed;
bool g_DuplicateSeen;

public Plugin myinfo =
{
	name = "GCB Left4DHooks animation lifecycle suite",
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

Action OnAnimPre(int client, int &activity)
{
	if (client == g_ClientA)
	{
		g_CallsA++;
		if (g_CheckDuplicates)
		{
			if (g_PreArmed)
			{
				g_DuplicateSeen = true;
			}
			else
			{
				g_PreArmed = true;
			}
		}
	}
	else if (client == g_ClientB)
	{
		g_CallsB++;
	}
	return Plugin_Continue;
}

Action OnAnimPost(int client, int &sequence)
{
	if (client == g_ClientA)
	{
		g_PreArmed = false;
	}
	return Plugin_Continue;
}

void Stimulate(int client)
{
	if (client > 0 && IsClientInGame(client))
	{
		L4D_RespawnPlayer(client);
		FakeClientCommand(client, "+jump");
		FakeClientCommand(client, "-jump");
	}
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, StartSuite);
}

Action StartSuite(Handle timer)
{
	g_ClientA = CreateFakeClient("gcb-anim-a");
	g_ClientB = CreateFakeClient("gcb-anim-b");
	if (g_ClientA > 0) ChangeClientTeam(g_ClientA, 2);
	if (g_ClientB > 0) ChangeClientTeam(g_ClientB, 2);

	bool ready = LibraryExists("left4dhooks") && g_ClientA > 0 && g_ClientB > 0;
	bool hookA = ready && AnimHookEnable(g_ClientA, OnAnimPre, OnAnimPost);
	bool hookB = ready && AnimHookEnable(g_ClientB, OnAnimPre, OnAnimPost);
	Case("runtime_animhook_library_loaded", ready && hookA && hookB, "left4dhooks accepts hooks for two real client slots");
	Stimulate(g_ClientA);
	Stimulate(g_ClientB);
	CreateTimer(1.0, CheckInitial);
	return Plugin_Stop;
}

Action CheckInitial(Handle timer)
{
	bool active = g_CallsA > 0 && g_CallsB > 0;
	Case("two_client_animation_hooks_fire", active, "both client hooks receive real animation selection callbacks");

	AnimHookDisable(g_ClientA, OnAnimPre, OnAnimPost);
	AnimHookEnable(g_ClientA, OnAnimPre, OnAnimPost);
	g_CallsA = 0;
	g_CallsB = 0;
	g_PreArmed = false;
	g_DuplicateSeen = false;
	g_CheckDuplicates = true;
	Stimulate(g_ClientA);
	Stimulate(g_ClientB);
	CreateTimer(1.0, CheckReenabled);
	return Plugin_Stop;
}

Action CheckReenabled(Handle timer)
{
	g_CheckDuplicates = false;
	Case("reenabled_animation_hook_not_duplicated", g_CallsA > 0 && !g_DuplicateSeen, "disable/re-enable leaves one callback registration");
	Case("peer_animation_hook_survives_other_client_cycle", g_CallsB > 0, "the peer client remains independently hooked");

	AnimHookDisable(g_ClientA, OnAnimPre, OnAnimPost);
	int callsBefore = g_CallsA;
	Stimulate(g_ClientA);
	Stimulate(g_ClientB);
	DataPack pack = new DataPack();
	pack.WriteCell(callsBefore);
	pack.WriteCell(g_CallsB);
	CreateTimer(1.0, CheckFinalDisable, pack);
	return Plugin_Stop;
}

Action CheckFinalDisable(Handle timer, DataPack pack)
{
	pack.Reset();
	int callsBefore = pack.ReadCell();
	int peerBefore = pack.ReadCell();
	delete pack;
	Case("final_disable_removes_selected_client_callback", g_CallsA == callsBefore && g_CallsB > peerBefore, "final disable stops only the selected client callback");
	AnimHookDisable(g_ClientB, OnAnimPre, OnAnimPost);
	if (g_ClientA > 0 && IsClientInGame(g_ClientA)) KickClient(g_ClientA);
	if (g_ClientB > 0 && IsClientInGame(g_ClientB)) KickClient(g_ClientB);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
