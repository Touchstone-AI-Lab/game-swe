#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_MolotovPre;
int g_MolotovPost;
int g_LastProjectile = -1;
int g_VomitPre;
int g_VomitPost;

public Plugin myinfo =
{
	name = "GCB Left4DHooks Molotov guard suite",
	author = "GameCodeBench",
	description = "Private real-engine behavioral guard",
	version = "1.0"
};

public Action L4D_MolotovProjectile_Pre(int client, float pos[3], float ang[3], float vel[3], float rot[3])
{
	g_MolotovPre++;
	return Plugin_Continue;
}

public void L4D_MolotovProjectile_Post(int client, int projectile, const float pos[3], const float ang[3], const float vel[3], const float rot[3])
{
	g_MolotovPost++;
	g_LastProjectile = projectile;
}

public Action L4D2_VomitJarProjectile_Pre(int client, float pos[3], float ang[3], float vel[3], float rot[3])
{
	g_VomitPre++;
	return Plugin_Continue;
}

public void L4D2_VomitJarProjectile_Post(int client, int projectile, const float pos[3], const float ang[3], const float vel[3], const float rot[3])
{
	g_VomitPost++;
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	float pos[3] = { 128.0, 128.0, 256.0 };
	float ang[3] = { 0.0, 0.0, 0.0 };
	float vel[3] = { 0.0, 0.0, 0.0 };
	float rot[3] = { 0.0, 0.0, 0.0 };
	int projectile = L4D_MolotovPrj(0, pos, ang, vel, rot);
	bool valid = projectile > MaxClients && IsValidEntity(projectile);
	bool ok = valid && g_MolotovPre == 1 && g_MolotovPost == 1 && g_LastProjectile == projectile;
	PrintToServer("@@GCB_SM@@%s:CASE:molotov_forward_family_remains_functional:%s:normal Molotov creation retains its pre/post forward contract", NONCE, ok ? "PASS" : "FAIL");
	int molotovPreBefore = g_MolotovPre;
	int molotovPostBefore = g_MolotovPost;
	int bile = L4D2_VomitJarPrj(0, pos, ang, vel, rot);
	bool bileValid = bile > MaxClients && IsValidEntity(bile);
	bool isolated = bileValid && g_VomitPre == 1 && g_VomitPost == 1
		&& g_MolotovPre == molotovPreBefore && g_MolotovPost == molotovPostBefore;
	PrintToServer("@@GCB_SM@@%s:CASE:vomit_creation_never_dispatches_molotov_family:%s:bile creation dispatches only the VomitJar family", NONCE, isolated ? "PASS" : "FAIL");
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:2", NONCE, (ok ? 1 : 0) + (isolated ? 1 : 0));
	if (valid) RemoveEntity(projectile);
	if (bileValid) RemoveEntity(bile);
	ServerCommand("quit");
	return Plugin_Stop;
}
