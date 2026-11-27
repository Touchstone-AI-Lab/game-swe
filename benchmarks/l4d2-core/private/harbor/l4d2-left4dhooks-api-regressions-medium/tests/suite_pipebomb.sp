#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <sdkhooks>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;
int g_CreatePre;
int g_CreatePost;
int g_DetonatePre;
int g_DetonatePost;
int g_LastCreated = -1;
int g_LastDetonated = -1;

public Plugin myinfo =
{
	name = "GCB Left4DHooks pipe-bomb isolation suite",
	author = "GameCodeBench",
	description = "Private real-engine detour-lifecycle checks",
	version = "1.0"
};

void Case(const char[] name, bool ok, const char[] detail)
{
	g_Total++;
	if (ok) g_Passed++;
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

public Action L4D_PipeBombProjectile_Pre(int client, float pos[3], float ang[3], float vel[3], float rot[3])
{
	g_CreatePre++;
	return Plugin_Continue;
}

public void L4D_PipeBombProjectile_Post(int client, int projectile, const float pos[3], const float ang[3], const float vel[3], const float rot[3])
{
	g_CreatePost++;
	g_LastCreated = projectile;
}

public Action L4D_PipeBomb_Detonate(int entity, int client)
{
	g_DetonatePre++;
	return Plugin_Continue;
}

public void L4D_PipeBomb_Detonate_Post(int entity, int client)
{
	g_DetonatePost++;
	g_LastDetonated = entity;
}

public void OnMapStart()
{
	PrecacheModel("models/props_junk/propanecanister001a.mdl", true);
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	Case("runtime_pipebomb_library_loaded", LibraryExists("left4dhooks"), "left4dhooks library is available");

	float pos[3] = { 192.0, 192.0, 256.0 };
	float ang[3] = { 0.0, 0.0, 0.0 };
	float vel[3] = { 0.0, 0.0, 0.0 };
	float rot[3] = { 0.0, 0.0, 0.0 };
	int projectile = L4D_PipeBombPrj(0, pos, ang, false, vel, rot);
	char classname[64];
	bool validProjectile = projectile > MaxClients && IsValidEntity(projectile);
	if (validProjectile) GetEntityClassname(projectile, classname, sizeof(classname));
	bool createOk = validProjectile && strcmp(classname, "pipe_bomb_projectile") == 0
		&& g_CreatePre == 1 && g_CreatePost == 1 && g_LastCreated == projectile;
	Case("real_pipebomb_creation_forwards_once", createOk, "one real pipe-bomb creation dispatches exactly one matching pre/post pair");

	if (validProjectile) L4D_DetonateProjectile(projectile);
	bool detonateOk = g_DetonatePre == 1 && g_DetonatePost == 1 && g_LastDetonated == projectile;
	Case("real_pipebomb_detonation_forwards_once", detonateOk, "one real pipe-bomb detonation dispatches exactly one matching pre/post pair");

	int createPreBefore = g_CreatePre;
	int createPostBefore = g_CreatePost;
	int detonatePreBefore = g_DetonatePre;
	int detonatePostBefore = g_DetonatePost;

	int prop = CreateEntityByName("prop_physics");
	int breaker = CreateFakeClient("gcb-pipe-breaker");
	if (breaker > 0) ChangeClientTeam(breaker, 2);
	bool propReady = prop > MaxClients;
	if (propReady)
	{
		DispatchKeyValue(prop, "model", "models/props_junk/propanecanister001a.mdl");
		DispatchKeyValue(prop, "health", "1");
		DispatchSpawn(prop);
		ActivateEntity(prop);
		TeleportEntity(prop, pos, NULL_VECTOR, NULL_VECTOR);
		SetEntProp(prop, Prop_Data, "m_takedamage", 2);
		SetEntProp(prop, Prop_Data, "m_iHealth", 1);
		SDKHooks_TakeDamage(prop, breaker, breaker, 1000.0, DMG_CLUB);
		if (IsValidEntity(prop)) AcceptEntityInput(prop, "Break", breaker, breaker);
	}
	CreateTimer(0.35, CheckBreakable, propReady ? EntIndexToEntRef(prop) : INVALID_ENT_REFERENCE);
	return Plugin_Stop;
}

Action CheckBreakable(Handle timer, any reference)
{
	bool destroyed = reference == INVALID_ENT_REFERENCE || EntRefToEntIndex(reference) == INVALID_ENT_REFERENCE;
	Case("breakable_prop_real_break_path_completes", destroyed, "a real breakable physics prop reaches its engine break lifecycle");
	Case("breakable_prop_never_dispatches_pipebomb_creation", g_CreatePre == 1 && g_CreatePost == 1,
		"breaking a non-pipe-bomb prop does not dispatch pipe-bomb creation forwards");
	Case("breakable_prop_never_dispatches_pipebomb_detonation", g_DetonatePre == 1 && g_DetonatePost == 1,
		"breaking a non-pipe-bomb prop does not dispatch pipe-bomb detonation forwards");

	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
