#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <left4dhooks>

#define NONCE "__GCB_NONCE__"

int g_Passed;
int g_Total;
int g_VomitPre;
int g_VomitPost;
int g_VomitHandled;
int g_PreClient = -1;
int g_PostClient = -1;
int g_PostProjectile = -1;
int g_HandledClient = -1;
int g_HandledProjectile = -1;
bool g_BlockNext;
bool g_ChangeNext;
float g_PrePos[3];
float g_PreAng[3];
float g_PreVel[3];
float g_PreRot[3];
float g_PostPos[3];
float g_PostAng[3];
float g_PostVel[3];
float g_PostRot[3];
float g_HandledPos[3];
float g_HandledAng[3];
float g_HandledVel[3];
float g_HandledRot[3];

public Plugin myinfo =
{
	name = "GCB Left4DHooks vomit-jar suite",
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

bool VectorNear(const float left[3], const float right[3])
{
	for (int i = 0; i < 3; i++)
	{
		if (FloatAbs(left[i] - right[i]) >= 0.02) return false;
	}
	return true;
}

public Action L4D2_VomitJarProjectile_Pre(int client, float pos[3], float ang[3], float vel[3], float rot[3])
{
	g_VomitPre++;
	g_PreClient = client;
	g_PrePos = pos;
	g_PreAng = ang;
	g_PreVel = vel;
	g_PreRot = rot;
	if (g_BlockNext)
	{
		g_BlockNext = false;
		return Plugin_Handled;
	}
	if (g_ChangeNext)
	{
		g_ChangeNext = false;
		pos = { 640.0, 768.0, 896.0 };
		ang = { 11.0, 22.0, 33.0 };
		vel = { 44.0, 55.0, 66.0 };
		rot = { 77.0, 88.0, 99.0 };
		return Plugin_Changed;
	}
	return Plugin_Continue;
}

public void L4D2_VomitJarProjectile_Post(int client, int projectile, const float pos[3], const float ang[3], const float vel[3], const float rot[3])
{
	g_VomitPost++;
	g_PostClient = client;
	g_PostProjectile = projectile;
	g_PostPos = pos;
	g_PostAng = ang;
	g_PostVel = vel;
	g_PostRot = rot;
}

public void L4D2_VomitJarProjectile_PostHandled(int client, int projectile, const float pos[3], const float ang[3], const float vel[3], const float rot[3])
{
	g_VomitHandled++;
	g_HandledClient = client;
	g_HandledProjectile = projectile;
	g_HandledPos = pos;
	g_HandledAng = ang;
	g_HandledVel = vel;
	g_HandledRot = rot;
}

public void OnAllPluginsLoaded()
{
	CreateTimer(1.0, RunSuite);
}

Action RunSuite(Handle timer)
{
	Case("runtime_vomit_library_loaded", LibraryExists("left4dhooks"), "left4dhooks library is available");

	int owner = CreateFakeClient("gcb-vomit-owner");
	if (owner > 0) ChangeClientTeam(owner, 2);
	float pos[3] = { 256.0, 384.0, 512.0 };
	float ang[3] = { 10.0, 20.0, 30.0 };
	float vel[3] = { 40.0, 50.0, 60.0 };
	float rot[3] = { 70.0, 80.0, 90.0 };
	int projectile = L4D2_VomitJarPrj(owner, pos, ang, vel, rot);
	char classname[64];
	bool valid = projectile > MaxClients && IsValidEntity(projectile);
	if (valid) GetEntityClassname(projectile, classname, sizeof(classname));
	float actualPos[3];
	if (valid) GetEntPropVector(projectile, Prop_Send, "m_vecOrigin", actualPos);
	int thrower = valid && HasEntProp(projectile, Prop_Send, "m_hThrower")
		? GetEntPropEnt(projectile, Prop_Send, "m_hThrower") : -1;

	Case("vomit_pre_forward_once", g_VomitPre == 1, "one bile-jar creation dispatches one pre forward");
	Case("vomit_post_forward_once", g_VomitPost == 1, "one unblocked creation dispatches one post forward");
	bool firstArgs = valid && strcmp(classname, "vomitjar_projectile") == 0
		&& g_PreClient == owner && g_PostClient == owner && g_PostProjectile == projectile && thrower == owner
		&& VectorNear(g_PrePos, pos) && VectorNear(g_PreAng, ang) && VectorNear(g_PreVel, vel) && VectorNear(g_PreRot, rot)
		&& VectorNear(g_PostPos, pos) && VectorNear(g_PostAng, ang) && VectorNear(g_PostVel, vel) && VectorNear(g_PostRot, rot)
		&& VectorNear(actualPos, pos);
	Case("vomit_projectile_result_and_arguments", firstArgs, "non-zero owner and all vector parameters match the created entity and post forward");

	g_ChangeNext = true;
	int changedProjectile = L4D2_VomitJarPrj(owner, pos, ang, vel, rot);
	float changedPos[3] = { 640.0, 768.0, 896.0 };
	float changedAng[3] = { 11.0, 22.0, 33.0 };
	float changedVel[3] = { 44.0, 55.0, 66.0 };
	float changedRot[3] = { 77.0, 88.0, 99.0 };
	bool changedValid = changedProjectile > MaxClients && IsValidEntity(changedProjectile);
	float changedActualPos[3];
	if (changedValid) GetEntPropVector(changedProjectile, Prop_Send, "m_vecOrigin", changedActualPos);
	bool changedOk = changedValid && g_VomitPre == 2 && g_VomitPost == 2
		&& g_PostClient == owner && g_PostProjectile == changedProjectile
		&& VectorNear(g_PostPos, changedPos) && VectorNear(g_PostAng, changedAng)
		&& VectorNear(g_PostVel, changedVel) && VectorNear(g_PostRot, changedRot)
		&& VectorNear(changedActualPos, changedPos);
	Case("vomit_changed_vectors_reach_creation_and_post", changedOk, "Plugin_Changed copyback reaches the engine entity and the post forward");

	g_BlockNext = true;
	int blocked = L4D2_VomitJarPrj(owner, pos, ang, vel, rot);
	bool handledOk = g_VomitPre == 3 && g_VomitPost == 2 && g_VomitHandled == 1 && blocked <= 0
		&& g_HandledClient == owner && g_HandledProjectile <= 0
		&& VectorNear(g_HandledPos, pos) && VectorNear(g_HandledAng, ang)
		&& VectorNear(g_HandledVel, vel) && VectorNear(g_HandledRot, rot);
	Case("vomit_handled_path_is_preserved", handledOk, "Plugin_Handled blocks creation and PostHandled keeps owner/vector semantics");

	if (valid) RemoveEntity(projectile);
	if (changedValid) RemoveEntity(changedProjectile);
	if (owner > 0 && IsClientConnected(owner)) KickClient(owner);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
	return Plugin_Stop;
}
