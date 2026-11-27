#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <nextmap>

#define NONCE "__GCB_NONCE__"

bool g_Issued;

public Plugin myinfo =
{
	name = "GCB Competitive Rework active-transition suite",
	author = "GameCodeBench",
	description = "Private Director-state transition check",
	version = "1.0"
};

void Finish(bool ok, const char[] detail)
{
	PrintToServer("@@GCB_SM@@%s:CASE:changelevel_partial_is_honored_while_transitioning:%s:%s", NONCE, ok ? "PASS" : "FAIL", detail);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:1", NONCE, ok ? 1 : 0);
	ServerCommand("quit");
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, IssueTransitioningPartial, _, TIMER_FLAG_NO_MAPCHANGE);
}

public void OnMapStart()
{
	if (!g_Issued) return;
	char map[64];
	GetCurrentMap(map, sizeof(map));
	Finish(strcmp(map, "c1m2_streets") == 0, "the resolved full map reaches the engine even after Director transition state is set");
}

Action IssueTransitioningPartial(Handle timer)
{
	GameData data = new GameData("l4d2_fix_changelevel");
	Address transitioning = data == null ? Address_Null : data.GetAddress("CDirector::m_isTransitioning");
	delete data;
	if (transitioning == Address_Null)
	{
		Finish(false, "the pinned Director transition address is unavailable");
		return Plugin_Stop;
	}
	StoreToAddress(transitioning, 1, NumberType_Int8);
	g_Issued = true;
	ForceChangeLevel("c1m2", "GameCodeBench transitioning-partial check");
	CreateTimer(7.0, TransitionTimeout, transitioning, TIMER_FLAG_NO_MAPCHANGE);
	return Plugin_Stop;
}

Action TransitionTimeout(Handle timer, any rawAddress)
{
	StoreToAddress(view_as<Address>(rawAddress), 0, NumberType_Int8);
	Finish(false, "the transitioning branch did not honor the unique partial name");
	return Plugin_Stop;
}
