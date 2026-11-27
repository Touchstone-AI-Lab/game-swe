#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <sdkhooks>
#include <mutant_tanks>

#define NONCE "__GCB_NONCE__"
#define SUITE_GROUP "__GCB_GROUP__"

int g_Passed;
int g_Total;
int g_Source = -1;
int g_Target = -1;
int g_Admin = -1;
int g_Tank = -1;
int g_Victim = -1;
int g_SourceWeapon = INVALID_ENT_REFERENCE;
int g_TargetWeapon = INVALID_ENT_REFERENCE;
int g_SpawnStage;
int g_ExpectedTankType;
int g_DeathNumber;
int g_SpawnAttempts;
int g_ApplyCount;
int g_ApplyTypes;
int g_ExpiryCount;
int g_ProbeClient = -1;
int g_ProbeExpected;
int g_ProbeAttempts;
int g_FirstType;
int g_SecondType;
int g_ExpectedRegen;
int g_ExpectedDamage;
int g_ExpiryDamage = -1;
bool g_ReplacementDone;
bool g_ExpiryAmmoReady;

public Plugin myinfo =
{
	name = "GCB Mutant Tanks reward-stack prototype",
	author = "GameCodeBench",
	description = "Real-server reward stacking, replacement, and expiry checks",
	version = "1.0"
};

void Case(const char[] suffix, bool ok, const char[] detail)
{
	char name[128];
	FormatEx(name, sizeof name, "%s_%s", SUITE_GROUP, suffix);
	g_Total++;
	if (ok) g_Passed++;
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

int MakeClient(const char[] name, int team, int zombieClass = 0, bool notifyCore = true)
{
	int client = CreateFakeClient(name);
	if (client <= 0) return -1;
	ChangeClientTeam(client, team);
	if (team == 3 && zombieClass > 0)
	{
		SetEntProp(client, Prop_Send, "m_zombieClass", zombieClass);
		DispatchSpawn(client);
		SetEntProp(client, Prop_Send, "m_zombieClass", zombieClass);
		SetEntProp(client, Prop_Send, "m_isGhost", 0, 1);
		SetEntProp(client, Prop_Send, "m_lifeState", 0);
		SetEntProp(client, Prop_Data, "m_iHealth", 1000);
		SetEntProp(client, Prop_Data, "m_iMaxHealth", 1000);
		if (notifyCore)
		{
			Event spawned = CreateEvent("player_spawn");
			spawned.SetInt("userid", GetClientUserId(client));
			spawned.Fire();
		}
	}
	else if (team == 2)
	{
		DispatchSpawn(client);
		SetEntityHealth(client, 1000);
	}
	return client;
}

int MakeDamageVictim()
{
	int entity = CreateEntityByName("infected");
	if (entity <= MaxClients || !IsValidEntity(entity)) return -1;
	DispatchSpawn(entity);
	ActivateEntity(entity);
	PlaceAtMapSpawn(entity);
	SetEntityMoveType(entity, MOVETYPE_NONE);
	if (HasEntProp(entity, Prop_Data, "m_takedamage"))
	{
		SetEntProp(entity, Prop_Data, "m_takedamage", 2, 1);
	}
	SetEntProp(entity, Prop_Data, "m_iHealth", 1000);
	SetEntProp(entity, Prop_Data, "m_iMaxHealth", 1000);
	return entity;
}

void RemoveClient(int &client)
{
	if (client > 0 && IsClientConnected(client)) KickClient(client);
	client = -1;
}

void RemoveScenarioBots()
{
	for (int client = 1; client <= MaxClients; client++)
	{
		if (IsClientInGame(client) && IsFakeClient(client)
			&& (GetClientTeam(client) == 2 || GetClientTeam(client) == 3))
		{
			KickClient(client);
		}
	}
}

void PlaceAtMapSpawn(int client)
{
	int entity = FindEntityByClassname(-1, "info_survivor_position");
	if (entity == -1) entity = FindEntityByClassname(-1, "info_player_start");
	float origin[3] = {0.0, 0.0, 128.0};
	if (entity > MaxClients) GetEntPropVector(entity, Prop_Send, "m_vecOrigin", origin);
	origin[2] += 16.0;
	TeleportEntity(client, origin, NULL_VECTOR, NULL_VECTOR);
}

int GivePrimary(int client)
{
	int weapon = GivePlayerItem(client, "weapon_smg");
	if (weapon > MaxClients)
	{
		EquipPlayerWeapon(client, weapon);
		SetEntProp(weapon, Prop_Send, "m_iClip1", 50);
		int ammoType = GetEntProp(weapon, Prop_Send, "m_iPrimaryAmmoType");
		if (ammoType > 0) SetEntProp(client, Prop_Send, "m_iAmmo", 100, .element = ammoType);
		return EntIndexToEntRef(weapon);
	}
	return INVALID_ENT_REFERENCE;
}

int WeaponForClient(int client)
{
	int reference = (client == g_Source) ? g_SourceWeapon : g_TargetWeapon;
	int weapon = EntRefToEntIndex(reference);
	if (weapon <= MaxClients || !IsValidEntity(weapon)
		|| GetEntPropEnt(weapon, Prop_Data, "m_hOwnerEntity") != client)
	{
		weapon = GetPlayerWeaponSlot(client, 0);
	}
	return weapon;
}

bool ResetAmmo(int client)
{
	int weapon = WeaponForClient(client);
	if (weapon <= MaxClients || !IsValidEntity(weapon)) return false;
	SetEntProp(weapon, Prop_Send, "m_iClip1", 0);
	int ammoType = GetEntProp(weapon, Prop_Send, "m_iPrimaryAmmoType");
	if (ammoType <= 0) return false;
	SetEntProp(client, Prop_Send, "m_iAmmo", 0, .element = ammoType);
	return true;
}

void ReadAmmo(int client, int &clip, int &reserve)
{
	clip = reserve = -1;
	int weapon = WeaponForClient(client);
	if (weapon <= MaxClients || !IsValidEntity(weapon)) return;
	clip = GetEntProp(weapon, Prop_Send, "m_iClip1");
	int ammoType = GetEntProp(weapon, Prop_Send, "m_iPrimaryAmmoType");
	if (ammoType > 0) reserve = GetEntProp(client, Prop_Send, "m_iAmmo", .element = ammoType);
}

int FindLiveTank(int type)
{
	for (int client = 1; client <= MaxClients; client++)
	{
		if (client != g_Admin && IsClientInGame(client) && IsPlayerAlive(client)
			&& GetClientTeam(client) == 3
			&& GetEntProp(client, Prop_Send, "m_zombieClass") == 8
			&& MT_GetTankType(client) == type)
		{
			return client;
		}
	}
	return -1;
}

public void MT_OnPostTankSpawn(int tank)
{
	if (g_SpawnStage == 70 && MT_GetTankType(tank) == g_ExpectedTankType
		&& GetEntProp(tank, Prop_Send, "m_zombieClass") == 8)
	{
		g_Tank = tank;
		g_SpawnStage = 0;
	}
}

public Action MT_OnRewardSurvivor(int survivor, int tank, int &type, int priority,
	float &duration, bool apply)
{
	if (apply && survivor == g_Source && (type & (MT_REWARD_DAMAGEBOOST|MT_REWARD_AMMO))
		== (MT_REWARD_DAMAGEBOOST|MT_REWARD_AMMO))
	{
		g_ApplyCount++;
		g_ApplyTypes |= type;
		PrintToServer("GCB reward apply: survivor=%d tank=%d type=%d priority=%d duration=%.2f count=%d",
			survivor, tank, type, priority, duration, g_ApplyCount);
	}
	else if (!apply && g_ReplacementDone && survivor == g_Target
		&& (type & (MT_REWARD_DAMAGEBOOST|MT_REWARD_AMMO))
		== (MT_REWARD_DAMAGEBOOST|MT_REWARD_AMMO))
	{
		g_ExpiryCount++;
		PrintToServer("GCB reward expiry: survivor=%d type=%d count=%d", survivor, type, g_ExpiryCount);
	}
	return Plugin_Continue;
}

public void OnAllPluginsLoaded()
{
	CreateTimer(2.0, BeginSuite);
}

Action BeginSuite(Handle timer)
{
	if (!StrEqual(SUITE_GROUP, "reward_ab") && !StrEqual(SUITE_GROUP, "reward_ba"))
	{
		Case("valid_group", false, "unknown reward prototype group");
		Finish();
		return Plugin_Stop;
	}

	bool ab = StrEqual(SUITE_GROUP, "reward_ab");
	g_FirstType = ab ? 1 : 2;
	g_SecondType = ab ? 2 : 1;
	g_ExpectedRegen = ab ? 10 : 30;
	g_ExpectedDamage = ab ? 15 : 35;

	ServerCommand("sv_cheats 1");
	ServerCommand("director_stop");
	ServerExecute();
	RemoveScenarioBots();
	CreateTimer(1.0, CreateFixture);
	return Plugin_Stop;
}

Action CreateFixture(Handle timer)
{
	g_Source = MakeClient("gcb-reward-source", 2);
	g_Target = MakeClient("gcb-reward-target", 2);
	if (g_Source > 0)
	{
		PlaceAtMapSpawn(g_Source);
		SetEntityMoveType(g_Source, MOVETYPE_NONE);
		g_SourceWeapon = GivePrimary(g_Source);
	}
	if (g_Target > 0)
	{
		PlaceAtMapSpawn(g_Target);
		SetEntityMoveType(g_Target, MOVETYPE_NONE);
		g_TargetWeapon = GivePrimary(g_Target);
	}
	g_Admin = MakeClient("gcb-reward-admin", 3, 1);
	if (g_Admin > 0) PlaceAtMapSpawn(g_Admin);

	bool ready = g_Source > 0 && g_Target > 0 && g_Admin > 0
		&& WeaponForClient(g_Source) > MaxClients && WeaponForClient(g_Target) > MaxClients;
	if (!ready)
	{
		FailAll("the two survivors, SMGs, or Tank spawn administrator were unavailable");
		return Plugin_Stop;
	}
	g_Victim = MakeDamageVictim();
	int baseline = MeasureDamage(g_Source);
	PrintToServer("GCB damage baseline: delta=%d expected=10", baseline);
	if (baseline != 10)
	{
		FailAll("the real common-infected damage fixture did not establish a ten-damage baseline");
		return Plugin_Stop;
	}
	CreateTimer(0.5, SpawnNextTank);
	return Plugin_Stop;
}

Action SpawnNextTank(Handle timer)
{
	g_ExpectedTankType = (g_DeathNumber == 0) ? g_FirstType : g_SecondType;
	g_Tank = -1;
	g_SpawnAttempts = 0;
	g_SpawnStage = 70;
	MT_SpawnTank(g_Admin, g_ExpectedTankType, 8);
	CreateTimer(0.4, KillCurrentTank);
	return Plugin_Stop;
}

Action KillCurrentTank(Handle timer)
{
	if (g_Tank <= 0 || !IsClientInGame(g_Tank) || !IsPlayerAlive(g_Tank)
		|| GetEntProp(g_Tank, Prop_Send, "m_zombieClass") != 8)
	{
		g_Tank = FindLiveTank(g_ExpectedTankType);
	}
	if (g_Tank <= 0 || !IsClientInGame(g_Tank) || !IsPlayerAlive(g_Tank))
	{
		if (g_SpawnAttempts++ < 35)
		{
			CreateTimer(0.2, KillCurrentTank);
			return Plugin_Stop;
		}
		FailAll("a real configured Tank did not become ready for the reward death path");
		return Plugin_Stop;
	}

	int weapon = WeaponForClient(g_Source);
	if (weapon <= MaxClients)
	{
		FailAll("the source survivor lost its real SMG before the Tank death");
		return Plugin_Stop;
	}
	SetEntProp(g_Tank, Prop_Data, "m_iMaxHealth", 50);
	SetEntityHealth(g_Tank, 1);
	SDKHooks_TakeDamage(g_Tank, g_Source, g_Source, 5000.0, DMG_BULLET,
		weapon, NULL_VECTOR, NULL_VECTOR, false);
	CreateTimer(0.35, InspectTankDeath);
	return Plugin_Stop;
}

Action InspectTankDeath(Handle timer)
{
	bool dead = g_Tank > 0 && IsClientInGame(g_Tank) && !IsPlayerAlive(g_Tank);
	int expectedApplies = g_DeathNumber + 1;
	PrintToServer("GCB death: order=%s number=%d type=%d dead=%d applies=%d",
		SUITE_GROUP, g_DeathNumber + 1, g_ExpectedTankType, dead, g_ApplyCount);
	if (!dead || g_ApplyCount < expectedApplies)
	{
		FailAll("a real Tank death did not synchronously reach the public reward apply forward");
		return Plugin_Stop;
	}
	RemoveClient(g_Tank);
	g_DeathNumber++;
	if (g_DeathNumber < 2)
	{
		CreateTimer(0.45, SpawnNextTank);
		return Plugin_Stop;
	}

	Case("two_real_tank_rewards_observed",
		g_ApplyCount == 2 && (g_ApplyTypes & (MT_REWARD_DAMAGEBOOST|MT_REWARD_AMMO))
			== (MT_REWARD_DAMAGEBOOST|MT_REWARD_AMMO),
		"both configured Tank deaths credit the same survivor through the public apply forward");
	int delta = MeasureDamage(g_Source);
	Case("stacked_damage_before_replacement", delta == g_ExpectedDamage,
		"a real bullet hit exposes the exact order-dependent stacked damage multiplier");
	if (!StartActiveAmmoProbe(g_Source))
	{
		Case("stacked_ammo_before_replacement", false,
			"the source SMG could not begin an ammo-regeneration probe");
		FailRemaining("the source SMG could not begin an ammo-regeneration probe");
	}
	return Plugin_Stop;
}

int MeasureDamage(int attacker)
{
	if (g_Victim <= MaxClients || !IsValidEntity(g_Victim)
		|| attacker <= 0 || !IsClientInGame(attacker)) return -1;
	int weapon = WeaponForClient(attacker);
	if (weapon <= MaxClients) return -1;
	SetEntProp(g_Victim, Prop_Data, "m_iHealth", 1000);
	int before = GetEntProp(g_Victim, Prop_Data, "m_iHealth");
	SDKHooks_TakeDamage(g_Victim, attacker, attacker, 10.0, DMG_BULLET,
		weapon, NULL_VECTOR, NULL_VECTOR, false);
	int after = GetEntProp(g_Victim, Prop_Data, "m_iHealth");
	PrintToServer("GCB damage: attacker=%d before=%d after=%d delta=%d expected=%d",
		attacker, before, after, before - after, g_ExpectedDamage);
	return before - after;
}

bool StartActiveAmmoProbe(int client)
{
	if (!ResetAmmo(client)) return false;
	g_ProbeClient = client;
	g_ProbeExpected = g_ExpectedRegen;
	g_ProbeAttempts = 0;
	CreateTimer(0.05, PollPreReplacementAmmo);
	return true;
}

Action PollPreReplacementAmmo(Handle timer)
{
	int clip, reserve;
	ReadAmmo(g_ProbeClient, clip, reserve);
	if (clip <= 0 && reserve <= 0 && g_ProbeAttempts++ < 40)
	{
		CreateTimer(0.05, PollPreReplacementAmmo);
		return Plugin_Stop;
	}
	PrintToServer("GCB pre-replacement ammo: clip=%d reserve=%d expected=%d attempts=%d",
		clip, reserve, g_ProbeExpected, g_ProbeAttempts);
	Case("stacked_ammo_before_replacement", clip == g_ProbeExpected && reserve == g_ProbeExpected,
		"the first real SMG regeneration tick exposes the exact order-dependent stack value");
	CreateTimer(0.1, ApplyReplacement);
	return Plugin_Stop;
}

Action ApplyReplacement(Handle timer)
{
	Event takeover = CreateEvent("bot_player_replace");
	if (takeover == null)
	{
		FailRemaining("the public bot_player_replace event could not be created");
		return Plugin_Stop;
	}
	takeover.SetInt("bot", GetClientUserId(g_Source));
	takeover.SetInt("player", GetClientUserId(g_Target));
	takeover.Fire();
	g_ReplacementDone = true;
	CreateTimer(0.35, CheckReplacementDamage);
	return Plugin_Stop;
}

Action CheckReplacementDamage(Handle timer)
{
	int targetDelta = MeasureDamage(g_Target);
	Case("replacement_target_keeps_damage", targetDelta == g_ExpectedDamage,
		"the incoming survivor keeps the live stacked damage reward after public takeover");
	int oldDelta = MeasureDamage(g_Source);
	Case("replacement_old_owner_loses_damage", oldDelta == 10,
		"the replaced survivor returns to baseline damage instead of retaining a duplicate reward");
	if (!ResetAmmo(g_Target) || !ResetAmmo(g_Source))
	{
		FailAfterReplacementDamage("the two survivor SMGs could not begin replacement ammo probes");
		return Plugin_Stop;
	}
	g_ProbeClient = g_Target;
	g_ProbeExpected = g_ExpectedRegen;
	g_ProbeAttempts = 0;
	CreateTimer(0.05, PollReplacementAmmo);
	return Plugin_Stop;
}

Action PollReplacementAmmo(Handle timer)
{
	int targetClip, targetReserve, oldClip, oldReserve;
	ReadAmmo(g_Target, targetClip, targetReserve);
	ReadAmmo(g_Source, oldClip, oldReserve);
	if (targetClip <= 0 && targetReserve <= 0 && g_ProbeAttempts++ < 40)
	{
		CreateTimer(0.05, PollReplacementAmmo);
		return Plugin_Stop;
	}
	PrintToServer("GCB replacement ammo: target=%d/%d old=%d/%d expected=%d attempts=%d",
		targetClip, targetReserve, oldClip, oldReserve, g_ProbeExpected, g_ProbeAttempts);
	Case("replacement_target_keeps_ammo", targetClip == g_ProbeExpected && targetReserve == g_ProbeExpected,
		"the incoming survivor's real SMG receives the migrated stack's first regeneration tick");
	Case("replacement_old_owner_loses_ammo", oldClip == 0 && oldReserve == 0,
		"the replaced survivor's real SMG receives no regeneration from stale copied state");
	CreateTimer(0.1, WaitForExpiry);
	return Plugin_Stop;
}

Action WaitForExpiry(Handle timer)
{
	static int attempts;
	if (g_ExpiryCount <= 0 && attempts++ < 240)
	{
		CreateTimer(0.1, WaitForExpiry);
		return Plugin_Stop;
	}
	// Delay all three expiry verdicts through a full observation window.  This
	// catches duplicate apply=false forwards that arrive after the first one.
	g_ExpiryDamage = MeasureDamage(g_Target);
	g_ExpiryAmmoReady = ResetAmmo(g_Target);
	CreateTimer(1.25, CheckExpiryAmmo);
	return Plugin_Stop;
}

Action CheckExpiryAmmo(Handle timer)
{
	int clip, reserve;
	if (g_ExpiryAmmoReady) ReadAmmo(g_Target, clip, reserve);
	else clip = reserve = -1;
	PrintToServer("GCB expiry ammo: clip=%d reserve=%d expiry_count=%d", clip, reserve, g_ExpiryCount);
	Case("public_expiry_forward_observed", g_ExpiryCount == 1,
		"the migrated reward ends exactly once through the public apply=false reward forward");
	Case("expiry_restores_baseline_damage", g_ExpiryDamage == 10,
		"after expiry, a real bullet hit returns to its unmodified ten damage");
	Case("expiry_stops_ammo_regeneration", g_ExpiryAmmoReady && clip == 0 && reserve == 0,
		"after expiry, a real SMG remains empty across a full regeneration interval");
	Finish();
	return Plugin_Stop;
}

void FailAll(const char[] detail)
{
	Case("two_real_tank_rewards_observed", false, detail);
	Case("stacked_damage_before_replacement", false, detail);
	Case("stacked_ammo_before_replacement", false, detail);
	FailRemaining(detail);
}

void FailRemaining(const char[] detail)
{
	Case("replacement_target_keeps_damage", false, detail);
	Case("replacement_old_owner_loses_damage", false, detail);
	FailAfterReplacementDamage(detail);
}

void FailAfterReplacementDamage(const char[] detail)
{
	Case("replacement_target_keeps_ammo", false, detail);
	Case("replacement_old_owner_loses_ammo", false, detail);
	Case("public_expiry_forward_observed", false, detail);
	Case("expiry_restores_baseline_damage", false, detail);
	Case("expiry_stops_ammo_regeneration", false, detail);
	Finish();
}

void Finish()
{
	RemoveClient(g_Tank);
	RemoveClient(g_Admin);
	if (g_Victim > MaxClients && IsValidEntity(g_Victim)) RemoveEntity(g_Victim);
	g_Victim = -1;
	RemoveClient(g_Source);
	RemoveClient(g_Target);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
}

