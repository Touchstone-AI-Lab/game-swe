#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;
int g_PreCount;
int g_PostCount;
int g_PreA;
int g_PreB;
int g_PostA;
int g_PostB;

public Plugin myinfo =
{
	name = "GCB Left4DHooks campaign-score forward suite",
	author = "GameCodeBench",
	description = "Private real-engine forward parameter checks",
	version = "1.0"
};

void Case(const char[] name, bool ok, const char[] detail)
{
	g_Total++;
	if (ok) g_Passed++;
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

public Action L4D_OnSetCampaignScores(int &scoreA, int &scoreB)
{
	g_PreCount++;
	g_PreA = scoreA;
	g_PreB = scoreB;
	scoreA += 11;
	scoreB += 22;
	return Plugin_Changed;
}

public void L4D_OnSetCampaignScores_Post(int scoreA, int scoreB)
{
	g_PostCount++;
	g_PostA = scoreA;
	g_PostB = scoreB;
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	Case("runtime_campaign_scores_library_loaded", LibraryExists("left4dhooks"), "left4dhooks library is available");
	L4D_SetCampaignScores(120, 340);
	Case("campaign_scores_pre_forward_once", g_PreCount == 1, "one engine score update dispatches one pre forward");
	Case("campaign_scores_pre_receives_original_values", g_PreA == 120 && g_PreB == 340,
		"the pre forward receives both original score values");
	Case("campaign_scores_post_forward_once", g_PostCount == 1, "one engine score update dispatches one post forward");
	Case("campaign_scores_changed_values_reach_post", g_PostA == 131 && g_PostB == 362,
		"Plugin_Changed score values reach the post forward as ordinary values");
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
