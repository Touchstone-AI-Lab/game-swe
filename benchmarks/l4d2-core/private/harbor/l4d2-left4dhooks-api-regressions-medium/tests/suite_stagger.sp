#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Target;
int g_Source;
int g_Passed;
int g_Total;

public Plugin myinfo =
{
	name = "GCB Left4DHooks stagger lifecycle suite",
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
	if (g_Target > 0 && IsClientConnected(g_Target)) KickClient(g_Target);
	if (g_Source > 0 && IsClientConnected(g_Source)) KickClient(g_Source);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
}

void StaggerNow()
{
	L4D_StaggerPlayer(g_Target, g_Source, NULL_VECTOR);
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, StartSuite);
}

Action StartSuite(Handle timer)
{
	g_Source = CreateFakeClient("gcb-stagger-source");
	g_Target = CreateFakeClient("gcb-stagger-target");
	if (g_Source > 0)
	{
		ChangeClientTeam(g_Source, 2);
		L4D_RespawnPlayer(g_Source);
	}
	if (g_Target > 0)
	{
		ChangeClientTeam(g_Target, 3);
		SetEntProp(g_Target, Prop_Send, "m_zombieClass", 3);
		L4D_RespawnPlayer(g_Target);
	}

	bool ready = LibraryExists("left4dhooks")
		&& g_Source > 0 && IsClientInGame(g_Source) && IsPlayerAlive(g_Source)
		&& g_Target > 0 && IsClientInGame(g_Target) && IsPlayerAlive(g_Target)
		&& GetClientTeam(g_Target) == 3;
	Case("runtime_stagger_library_and_clients_ready", ready, "a live survivor and live special infected exercise the public natives");
	if (!ready)
	{
		Case("initial_stagger_becomes_active", false, "fixture did not become ready");
		Case("same_frame_restagger_survives_cancel_window", false, "fixture did not become ready");
		Case("next_frame_restagger_survives_cancel_window", false, "fixture did not become ready");
		Case("completed_cancel_still_allows_later_stagger", false, "fixture did not become ready");
		Finish();
		return Plugin_Stop;
	}

	StaggerNow();
	CreateTimer(0.02, CheckInitial);
	return Plugin_Stop;
}

Action CheckInitial(Handle timer)
{
	Case("initial_stagger_becomes_active", L4D_IsPlayerStaggering(g_Target), "the first real stagger is observable");
	L4D_CancelStagger(g_Target);
	StaggerNow();
	RequestFrame(ObserveSameFrameOne);
	return Plugin_Stop;
}

void ObserveSameFrameOne()
{
	RequestFrame(CheckSameFrame);
}

void CheckSameFrame()
{
	float cycle = GetEntPropFloat(g_Target, Prop_Send, "m_flCycle");
	Case("same_frame_restagger_survives_cancel_window", L4D_IsPlayerStaggering(g_Target) && cycle < 0.99, "an immediate new stagger keeps its animation active through the cancellation window");
	L4D_CancelStagger(g_Target);
	RequestFrame(RestaggerNextFrame);
}

void RestaggerNextFrame()
{
	StaggerNow();
	RequestFrame(ObserveNextFrameOne);
}

void ObserveNextFrameOne()
{
	RequestFrame(CheckNextFrame);
}

void CheckNextFrame()
{
	float cycle = GetEntPropFloat(g_Target, Prop_Send, "m_flCycle");
	Case("next_frame_restagger_survives_cancel_window", L4D_IsPlayerStaggering(g_Target) && cycle < 0.99, "a next-frame stagger keeps its animation active through the cancellation window");
	L4D_CancelStagger(g_Target);
	CreateTimer(0.20, StartLateGuard);
}

Action StartLateGuard(Handle timer)
{
	StaggerNow();
	CreateTimer(0.02, CheckLateGuard);
	return Plugin_Stop;
}

Action CheckLateGuard(Handle timer)
{
	Case("completed_cancel_still_allows_later_stagger", L4D_IsPlayerStaggering(g_Target), "a completed cancellation does not disable future stagger behavior");
	Finish();
	return Plugin_Stop;
}
