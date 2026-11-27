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
int g_ConfigCallbacks;
bool g_ConfigBasic;
bool g_ConfigTypeSpecial;
bool g_ConfigPluginSpecial;
int g_InitialConfigCallbacks;
bool g_InitialConfigBasic;
bool g_InitialConfigTypeSpecial;
bool g_InitialConfigPluginSpecial;
int g_HealthBot = -1;
int g_WarpBot = -1;
int g_SpawnAdmin = -1;
int g_SpawnStage;
int g_Destination = -1;
int g_Subject = -1;
int g_PinOwner = -1;
int g_PinStep;
int g_PinControlAttempt;
int g_SpawnPollAttempt;
int g_AdminAttempt;
int g_CleanAttempt;
int g_SurvivorAttempt;
int g_LifecycleTank = -1;
int g_LifecycleSurvivor = -1;
int g_BossStage;
int g_BossPollAttempt;
int g_HypnoTank = -1;
int g_HypnoSurvivor = -1;
int g_HypnoOldRef = INVALID_ENT_REFERENCE;
int g_HypnoHealthBefore;
int g_HypnoTankHealthBefore;
bool g_HypnoRoundClean;
float g_HypnoSpawnRequestedAt;
float g_HypnoPostSpawnAt = -1.0;
int g_MultiTank = -1;
int g_MultiCapture;
int g_MultiRefs[32];
int g_MultiRefCount;
int g_RainbowTank = -1;
int g_RainbowSource = -1;
int g_RainbowTarget = -1;
int g_RainbowWeapon = INVALID_ENT_REFERENCE;
int g_RainbowSourceA[4];
int g_RainbowSourceB[4];
int g_RainbowTargetA[4];
int g_RainbowTargetB[4];
bool g_RainbowRewardForward;
bool g_RainbowTankDied;
int g_RainbowTankPollAttempt;
int g_CooldownTank = -1;
int g_CooldownSurvivor = -1;
int g_CooldownWeapon = INVALID_ENT_REFERENCE;
int g_CooldownAcidCount;
bool g_CooldownCapture;
int g_CooldownTankPollAttempt;
bool g_HitIssued;
bool g_PinControlMoved;
float g_SubjectOrigin[3] = {128.0, 128.0, 64.0};
float g_DestinationOrigin[3] = {640.0, 128.0, 64.0};
float g_PinnedOrigin[3];

public Plugin myinfo =
{
	name = "GCB Mutant Tanks behavioral suite",
	author = "GameCodeBench",
	description = "Public-forward and engine-observable regression checks",
	version = "1.0"
};

public void OnEntityCreated(int entity, const char[] classname)
{
	if (StrEqual(SUITE_GROUP, "panic_fallback") && g_MultiCapture > 0
		&& StrEqual(classname, "infected")
		&& g_MultiRefCount < sizeof(g_MultiRefs))
	{
		g_MultiRefs[g_MultiRefCount++] = EntIndexToEntRef(entity);
	}
	if (StrEqual(SUITE_GROUP, "cooldown") && g_CooldownCapture
		&& StrEqual(classname, "spitter_projectile"))
	{
		SDKHook(entity, SDKHook_SpawnPost, OnCooldownProjectileSpawnPost);
	}
}

void OnCooldownProjectileSpawnPost(int entity)
{
	if (!g_CooldownCapture || entity <= MaxClients || !IsValidEntity(entity)) return;
	int owner = HasEntProp(entity, Prop_Data, "m_hOwnerEntity")
		? GetEntPropEnt(entity, Prop_Data, "m_hOwnerEntity") : -1;
	int thrower = HasEntProp(entity, Prop_Data, "m_hThrower")
		? GetEntPropEnt(entity, Prop_Data, "m_hThrower") : -1;
	PrintToServer("GCB cooldown projectile: entity=%d owner=%d thrower=%d tank=%d", entity, owner, thrower, g_CooldownTank);
	if (owner == g_CooldownTank || thrower == g_CooldownTank)
	{
		g_CooldownAcidCount++;
	}
}

public Action MT_OnRewardSurvivor(int survivor, int tank, int &type, int priority, float &duration, bool apply)
{
	if (StrEqual(SUITE_GROUP, "rainbow_transfer") && apply
		&& survivor == g_RainbowSource && tank == g_RainbowTank)
	{
		g_RainbowRewardForward = true;
	}
	return Plugin_Continue;
}

void Case(const char[] name, bool ok, const char[] detail)
{
	g_Total++;
	if (ok) g_Passed++;
	PrintToServer("@@GCB_SM@@%s:CASE:%s:%s:%s", NONCE, name, ok ? "PASS" : "FAIL", detail);
}

public void MT_OnConfigsLoaded(const char[] subsection, const char[] key, const char[] value,
	int type, int admin, int mode, bool special, const char[] specsection)
{
	g_ConfigCallbacks++;
	if (StrEqual(subsection, "General") && StrEqual(key, "Type Range")
		&& StrEqual(value, "1-3") && type == -1 && admin == -1 && mode == 1
		&& !special && specsection[0] == '\0')
	{
		g_ConfigBasic = true;
	}
	if (StrEqual(value, "1-3"))
	{
		PrintToServer("GCB config diagnostic: subsection=%s key=%s type=%d admin=%d mode=%d special=%d specsection=%s",
			subsection, key, type, admin, mode, special, specsection);
	}
	if (StrEqual(subsection, "Health") && StrEqual(key, "Smoker Base Health")
		&& StrEqual(value, "777") && type == 1 && admin == -1 && mode == 1
		&& special && StrEqual(specsection, "Special"))
	{
		g_ConfigTypeSpecial = true;
	}
	if (StrEqual(subsection, "Health") && StrEqual(key, "Smoker Base Health")
		&& StrEqual(value, "606") && type == -1 && admin == -1 && mode == 1
		&& special && StrEqual(specsection, "Special"))
	{
		g_ConfigPluginSpecial = true;
	}
}

bool PluginNamed(Handle plugin, const char[] expected)
{
	char name[96];
	return plugin != null && GetPluginInfo(plugin, PlInfo_Name, name, sizeof(name)) && StrEqual(name, expected);
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
		SetEntProp(client, Prop_Data, "m_iHealth", 250);
		SetEntProp(client, Prop_Data, "m_iMaxHealth", 250);
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
	PrintToServer("GCB client diagnostic: client=%d team=%d class=%d alive=%d health=%d",
		client, GetClientTeam(client), team == 3 ? GetEntProp(client, Prop_Send, "m_zombieClass") : 0,
		IsPlayerAlive(client), GetEntProp(client, Prop_Data, "m_iHealth"));
	return client;
}

void RemoveClient(int &client)
{
	if (client > 0 && IsClientConnected(client)) KickClient(client);
	client = -1;
}

void PlaceAtMapSpawn(int client)
{
	int entity = FindEntityByClassname(-1, "info_survivor_position");
	if (entity == -1) entity = FindEntityByClassname(-1, "info_player_start");
	float origin[3] = {0.0, 0.0, 128.0};
	if (entity > MaxClients) GetEntPropVector(entity, Prop_Send, "m_vecOrigin", origin);
	origin[2] += 16.0;
	TeleportEntity(client, origin, NULL_VECTOR, NULL_VECTOR);
	PrintToServer("GCB spawn origin diagnostic: entity=%d pos=%.1f %.1f %.1f", entity, origin[0], origin[1], origin[2]);
}

public void OnAllPluginsLoaded()
{
	CreateTimer(2.0, BeginSuite);
}

public void MT_OnPostTankSpawn(int tank)
{
	int type = MT_GetTankType(tank);
	PrintToServer("GCB spawn diagnostic: stage=%d client=%d type=%d team=%d class=%d health=%d max=%d custom=%d",
		g_SpawnStage, tank, type, GetClientTeam(tank), GetEntProp(tank, Prop_Send, "m_zombieClass"),
		GetEntProp(tank, Prop_Data, "m_iHealth"), GetEntProp(tank, Prop_Data, "m_iMaxHealth"), MT_IsCustomTankSupported(tank));
	if (g_SpawnStage == 1 && type == 1 && g_HealthBot <= 0)
	{
		g_HealthBot = tank;
		g_SpawnStage = 0;
	}
	else if (g_SpawnStage == 2 && type == 3 && g_HealthBot <= 0)
	{
		g_HealthBot = tank;
		g_SpawnStage = 0;
	}
	else if (g_SpawnStage == 3 && type == 2 && g_WarpBot <= 0)
	{
		g_WarpBot = tank;
		g_SpawnStage = 0;
	}
	else if (g_SpawnStage == 10 && type == 1 && g_LifecycleTank <= 0)
	{
		g_LifecycleTank = tank;
		if (g_LifecycleSurvivor > 0 && IsClientInGame(g_LifecycleSurvivor))
		{
			float origin[3];
			GetClientAbsOrigin(g_LifecycleSurvivor, origin);
			origin[0] += 96.0;
			TeleportEntity(tank, origin, NULL_VECTOR, NULL_VECTOR);
		}
		g_SpawnStage = 0;
	}
	else if (g_SpawnStage >= 20 && g_SpawnStage <= 22 && type == (g_SpawnStage - 19))
	{
		g_HypnoTank = tank;
		g_HypnoPostSpawnAt = GetGameTime();
		g_SpawnStage = 0;
	}
	else if (g_SpawnStage >= 30 && g_SpawnStage <= 33 && type == (g_SpawnStage - 29))
	{
		g_MultiTank = tank;
		g_SpawnStage = 0;
	}
	else if (g_SpawnStage == 40 && type == 1
		&& GetEntProp(tank, Prop_Send, "m_zombieClass") == 8)
	{
		g_RainbowTank = tank;
		g_SpawnStage = 0;
	}
	else if (g_SpawnStage >= 50 && g_SpawnStage <= 51 && type == (g_SpawnStage - 49)
		&& GetEntProp(tank, Prop_Send, "m_zombieClass") == 8)
	{
		g_CooldownTank = tank;
		g_SpawnStage = 0;
	}
}

Action BeginSuite(Handle timer)
{
	if (StrEqual(SUITE_GROUP, "boss"))
	{
		StartLifecycle();
		return Plugin_Stop;
	}
	if (StrEqual(SUITE_GROUP, "hypno"))
	{
		StartHypno();
		return Plugin_Stop;
	}
	if (StrEqual(SUITE_GROUP, "panic_fallback"))
	{
		StartPanicFallback();
		return Plugin_Stop;
	}
	if (StrEqual(SUITE_GROUP, "rainbow_transfer"))
	{
		StartRainbowTransfer();
		return Plugin_Stop;
	}
	if (StrEqual(SUITE_GROUP, "cooldown"))
	{
		StartCooldown();
		return Plugin_Stop;
	}
	if (StrEqual(SUITE_GROUP, "health"))
	{
		StartHealthSpecific();
		return Plugin_Stop;
	}
	if (StrEqual(SUITE_GROUP, "warp"))
	{
		StartWarp();
		return Plugin_Stop;
	}
	Handle core = FindPluginByFile("00_mutant_tanks.smx");
	Handle abilities = FindPluginByFile("10_mt_abilities.smx");
	Handle abilities2 = FindPluginByFile("11_mt_abilities2.smx");
	Case("runtime_core_loaded", PluginNamed(core, "[L4D & L4D2] Mutant Tanks"), "the frozen core loads with its upstream metadata");
	Case("runtime_primary_ability_module_loaded", PluginNamed(abilities, "[MT] Abilities Set #1"), "the source-built Hypno ability aggregate loads");
	Case("runtime_warp_module_loaded", PluginNamed(abilities2, "[MT] Abilities Set #2"), "the source-built secondary ability aggregate loads");

	g_InitialConfigCallbacks = g_ConfigCallbacks;
	g_InitialConfigBasic = g_ConfigBasic;
	g_InitialConfigTypeSpecial = g_ConfigTypeSpecial;
	g_InitialConfigPluginSpecial = g_ConfigPluginSpecial;
	g_ConfigCallbacks = 0;
	g_ConfigBasic = false;
	g_ConfigTypeSpecial = false;
	g_ConfigPluginSpecial = false;
	ServerCommand("sm_mt_reload");
	ServerExecute();
	CreateTimer(2.0, CheckConfig);
	return Plugin_Stop;
}

Action CheckConfig(Handle timer)
{
	Case("config_reload_dispatches_callbacks", g_InitialConfigCallbacks >= 20 && g_ConfigCallbacks >= 20,
		"initial load and sm_mt_reload each dispatch at least twenty observable public callbacks");
	Case("config_forward_preserves_basic_arguments", g_InitialConfigBasic && g_ConfigBasic,
		"initial load and reload both preserve ordinary subsection, key, value, type, admin and mode context");
	Case("config_forward_preserves_special_context",
		g_InitialConfigTypeSpecial && g_InitialConfigPluginSpecial
		&& g_ConfigTypeSpecial && g_ConfigPluginSpecial,
		"initial load and reload preserve exact type-level and plugin-level nested context");
	Finish();
	return Plugin_Stop;
}

void StartHealthSpecific()
{
	g_SpawnStage = 0;
	g_HealthBot = -1;
	g_SpawnAdmin = MakeClient("gcb-health-specific-admin", 3, 1);
	if (g_SpawnAdmin > 0) PlaceAtMapSpawn(g_SpawnAdmin);
	CreateTimer(0.50, ApplyHealthSpecific);
	CreateTimer(3.50, CheckHealthSpecific);
}

Action ApplyHealthSpecific(Handle timer)
{
	g_SpawnStage = 1;
	g_HealthBot = -1;
	if (g_SpawnAdmin > 0) MT_SpawnTank(g_SpawnAdmin, 1, 1);
	return Plugin_Stop;
}

Action CheckHealthSpecific(Handle timer)
{
	bool custom = g_HealthBot > 0 && IsClientInGame(g_HealthBot) && MT_IsCustomTankSupported(g_HealthBot);
	int health = custom ? GetEntProp(g_HealthBot, Prop_Data, "m_iHealth") : -1;
	int maximum = custom ? GetEntProp(g_HealthBot, Prop_Data, "m_iMaxHealth") : -1;
	Case("health_smoker_mutation_completes", custom, "the public MT_SpawnTank native completes a mutant Smoker spawn");
	Case("health_type_explicit_si_override_remains", custom && health == 888 && maximum == 888,
		"an explicit type-level Smoker base 777 plus extra 111 remains authoritative");
	RemoveClient(g_HealthBot);
	RemoveClient(g_SpawnAdmin);
	g_SpawnStage = 0;
	g_HealthBot = -1;
	g_SpawnAdmin = MakeClient("gcb-health-fallback-admin", 3, 1);
	if (g_SpawnAdmin > 0) PlaceAtMapSpawn(g_SpawnAdmin);
	CreateTimer(0.50, ApplyHealthFallback);
	CreateTimer(3.50, CheckHealthFallback);
	return Plugin_Stop;
}

Action ApplyHealthFallback(Handle timer)
{
	g_SpawnStage = 2;
	g_HealthBot = -1;
	if (g_SpawnAdmin > 0) MT_SpawnTank(g_SpawnAdmin, 3, 1);
	return Plugin_Stop;
}

Action CheckHealthFallback(Handle timer)
{
	bool custom = g_HealthBot > 0 && IsClientInGame(g_HealthBot) && MT_IsCustomTankSupported(g_HealthBot);
	int health = custom ? GetEntProp(g_HealthBot, Prop_Data, "m_iHealth") : -1;
	int maximum = custom ? GetEntProp(g_HealthBot, Prop_Data, "m_iMaxHealth") : -1;
	Case("health_plugin_si_fallback_beats_generic_defaults", custom && health == 612 && maximum == 612,
		"an omitted type health block selects plugin Smoker 606 plus 6 for live and maximum health");
	RemoveClient(g_HealthBot);
	RemoveClient(g_SpawnAdmin);
	Finish();
	return Plugin_Stop;
}

void StartWarp()
{
	ServerCommand("director_stop");
	ServerExecute();
	for (int client = 1; client <= MaxClients; client++)
	{
		if (IsClientInGame(client) && IsFakeClient(client)
			&& (GetClientTeam(client) == 2 || GetClientTeam(client) == 3)) KickClient(client);
	}
	g_HealthBot = -1;
	g_WarpBot = -1;
	g_SpawnAdmin = -1;
	g_Destination = -1;
	g_Subject = -1;
	g_PinOwner = -1;
	g_CleanAttempt = 0;
	CreateTimer(1.50, CheckWarpClean);
}

void FailAllWarp(const char[] detail)
{
	Case("warp_unpinned_survivor_still_moves", false, detail);
	Case("warp_smoker_pin_is_preserved", false, detail);
	Case("warp_hunter_pin_is_preserved", false, detail);
	Case("warp_jockey_pin_is_preserved", false, detail);
	Case("warp_charger_pin_is_preserved", false, detail);
	Finish();
}

Action CheckWarpClean(Handle timer)
{
	int remaining;
	for (int client = 1; client <= MaxClients; client++)
	{
		if (IsClientInGame(client) && IsFakeClient(client)
			&& (GetClientTeam(client) == 2 || GetClientTeam(client) == 3)) remaining++;
	}
	PrintToServer("GCB warp clean diagnostic: attempt=%d remaining=%d", g_CleanAttempt, remaining);
	if (remaining > 0 && g_CleanAttempt < 10)
	{
		g_CleanAttempt++;
		CreateTimer(0.50, CheckWarpClean);
		return Plugin_Stop;
	}
	if (remaining > 0)
	{
		FailAllWarp("the asynchronous Warp fixture cleanup did not reach an empty player state");
		return Plugin_Stop;
	}
	CreateTimer(0.25, SetupWarpSurvivors);
	return Plugin_Stop;
}

Action SetupWarpSurvivors(Handle timer)
{
	g_Destination = MakeClient("gcb-warp-destination", 2);
	g_Subject = MakeClient("gcb-warp-subject", 2);
	if (g_Destination > 0)
	{
		TeleportEntity(g_Destination, g_DestinationOrigin);
		SetEntityMoveType(g_Destination, MOVETYPE_NONE);
	}
	if (g_Subject > 0)
	{
		TeleportEntity(g_Subject, g_SubjectOrigin);
		SetEntityMoveType(g_Subject, MOVETYPE_WALK);
	}
	g_PinStep = 0;
	g_SurvivorAttempt = 0;
	CreateTimer(0.75, CheckWarpSurvivors);
	return Plugin_Stop;
}

Action CheckWarpSurvivors(Handle timer)
{
	bool ready = g_Destination > 0 && IsClientInGame(g_Destination) && IsPlayerAlive(g_Destination)
		&& g_Subject > 0 && IsClientInGame(g_Subject) && IsPlayerAlive(g_Subject);
	if (ready)
	{
		StartWarpPair();
		return Plugin_Stop;
	}
	if (g_SurvivorAttempt < 10)
	{
		g_SurvivorAttempt++;
		CreateTimer(0.50, CheckWarpSurvivors);
		return Plugin_Stop;
	}
	FailAllWarp("the asynchronous Warp fixture could not establish two living survivors");
	return Plugin_Stop;
}

void StartWarpPair()
{
	g_WarpBot = -1;
	g_AdminAttempt = 0;
	CreateWarpAdmin();
}

void CreateWarpAdmin()
{
	g_SpawnAdmin = MakeClient("gcb-warp-spawn-admin", 3, 1);
	if (g_SpawnAdmin > 0) PlaceAtMapSpawn(g_SpawnAdmin);
	g_SpawnStage = 0;
	CreateTimer(0.75, QualifyWarpAdmin);
}

Action QualifyWarpAdmin(Handle timer)
{
	bool valid = g_SpawnAdmin > 0 && IsClientInGame(g_SpawnAdmin) && IsPlayerAlive(g_SpawnAdmin);
	int type = valid ? MT_GetTankType(g_SpawnAdmin) : -1;
	PrintToServer("GCB warp-admin diagnostic: attempt=%d client=%d valid=%d type=%d",
		g_AdminAttempt, g_SpawnAdmin, valid, type);
	if (valid && type == 2 && MT_IsCustomTankSupported(g_SpawnAdmin))
	{
		g_WarpBot = g_SpawnAdmin;
		g_SpawnAdmin = -1;
		CreateTimer(0.50, BeginWarpControl);
		return Plugin_Stop;
	}
	if (valid)
	{
		CreateTimer(0.25, ApplyWarpType);
		return Plugin_Stop;
	}
	RemoveClient(g_SpawnAdmin);
	if (g_AdminAttempt < 6)
	{
		g_AdminAttempt++;
		CreateTimer(1.00, RetryWarpAdmin);
		return Plugin_Stop;
	}
	CreateTimer(0.10, PollWarpSpawn);
	return Plugin_Stop;
}

Action RetryWarpAdmin(Handle timer)
{
	CreateWarpAdmin();
	return Plugin_Stop;
}

Action ApplyWarpType(Handle timer)
{
	g_SpawnStage = 3;
	g_WarpBot = -1;
	if (g_SpawnAdmin > 0 && IsClientInGame(g_SpawnAdmin)) MT_SpawnTank(g_SpawnAdmin, 2, 1);
	g_SpawnPollAttempt = 0;
	CreateTimer(0.50, PollWarpSpawn);
	return Plugin_Stop;
}

Action PollWarpSpawn(Handle timer)
{
	bool ready = g_WarpBot > 0 && IsClientInGame(g_WarpBot)
		&& MT_IsCustomTankSupported(g_WarpBot) && MT_GetTankType(g_WarpBot) == 2;
	if (ready)
	{
		CreateTimer(0.50, BeginWarpControl);
		return Plugin_Stop;
	}
	if (g_SpawnPollAttempt < 24)
	{
		g_SpawnPollAttempt++;
		CreateTimer(0.50, PollWarpSpawn);
		return Plugin_Stop;
	}
	if (g_PinStep == 0)
	{
		Case("warp_unpinned_survivor_still_moves", false,
			"the initialized Warp attacker did not relocate the unpinned control");
	}
	static const char names[][] = {
		"warp_smoker_pin_is_preserved", "warp_hunter_pin_is_preserved",
		"warp_jockey_pin_is_preserved", "warp_charger_pin_is_preserved"
	};
	Case(names[g_PinStep], false, "the paired unpinned control never triggered Warp");
	AdvanceWarpPair();
	return Plugin_Stop;
}

void ResetSubject()
{
	if (g_Subject <= 0 || !IsClientInGame(g_Subject)) return;
	SetEntityHealth(g_Subject, 1000);
	TeleportEntity(g_Subject, g_SubjectOrigin, NULL_VECTOR, NULL_VECTOR);
	SetEntityMoveType(g_Subject, MOVETYPE_WALK);
	SetEntPropEnt(g_Subject, Prop_Send, "m_tongueOwner", -1);
	SetEntPropEnt(g_Subject, Prop_Send, "m_pounceAttacker", -1);
	SetEntPropEnt(g_Subject, Prop_Send, "m_jockeyAttacker", -1);
	SetEntPropEnt(g_Subject, Prop_Send, "m_pummelAttacker", -1);
}

bool HitSubject()
{
	if (g_Subject <= 0 || !IsClientInGame(g_Subject)
		|| g_WarpBot <= 0 || !IsClientInGame(g_WarpBot)) return false;
	SDKHooks_TakeDamage(g_Subject, g_WarpBot, g_WarpBot, 1.0, DMG_CLUB, -1, NULL_VECTOR, NULL_VECTOR, false);
	return true;
}

bool SubjectStayed()
{
	float after[3];
	GetClientAbsOrigin(g_Subject, after);
	return GetVectorDistance(after, g_PinnedOrigin) < 24.0;
}

bool WarpMovedToDestination()
{
	float after[3];
	if (g_Subject <= 0 || !IsClientInGame(g_Subject)) return false;
	GetClientAbsOrigin(g_Subject, after);
	return GetVectorDistance(after, g_SubjectOrigin) > 100.0
		&& GetVectorDistance(after, g_DestinationOrigin) < 100.0;
}

Action BeginWarpControl(Handle timer)
{
	if (g_Destination > 0 && IsClientInGame(g_Destination))
	{
		TeleportEntity(g_Destination, g_DestinationOrigin, NULL_VECTOR, NULL_VECTOR);
		SetEntityMoveType(g_Destination, MOVETYPE_NONE);
	}
	g_PinControlAttempt = 0;
	RunWarpControl();
	return Plugin_Stop;
}

void RunWarpControl()
{
	float attackerOrigin[3] = {160.0, 128.0, 64.0};
	if (g_WarpBot > 0) TeleportEntity(g_WarpBot, attackerOrigin, NULL_VECTOR, NULL_VECTOR);
	ResetSubject();
	g_HitIssued = HitSubject();
	CreateTimer(0.25, CheckWarpControl);
}

Action RetryWarpControl(Handle timer)
{
	RunWarpControl();
	return Plugin_Stop;
}

Action CheckWarpControl(Handle timer)
{
	g_PinControlMoved = g_HitIssued && WarpMovedToDestination();
	PrintToServer("GCB warp control diagnostic: pin=%d attempt=%d moved=%d bot=%d type=%d",
		g_PinStep, g_PinControlAttempt, g_PinControlMoved, g_WarpBot,
		g_WarpBot > 0 && IsClientInGame(g_WarpBot) ? MT_GetTankType(g_WarpBot) : -1);
	if (!g_PinControlMoved && g_PinControlAttempt < 8)
	{
		g_PinControlAttempt++;
		CreateTimer(1.10, RetryWarpControl);
		return Plugin_Stop;
	}
	if (g_PinStep == 0)
	{
		Case("warp_unpinned_survivor_still_moves", g_PinControlMoved,
			"the initialized Warp mutant relocates an eligible unpinned survivor through SDKHooks damage");
	}
	if (!g_PinControlMoved)
	{
		static const char names[][] = {
			"warp_smoker_pin_is_preserved", "warp_hunter_pin_is_preserved",
			"warp_jockey_pin_is_preserved", "warp_charger_pin_is_preserved"
		};
		Case(names[g_PinStep], false, "the paired unpinned control never triggered Warp");
		AdvanceWarpPair();
		return Plugin_Stop;
	}
	CreateTimer(1.10, RunPinnedStep);
	return Plugin_Stop;
}

Action RunPinnedStep(Handle timer)
{
	ResetSubject();
	char prop[32];
	int zombieClass;
	switch (g_PinStep)
	{
		case 0: { strcopy(prop, sizeof(prop), "m_tongueOwner"); zombieClass = 1; }
		case 1: { strcopy(prop, sizeof(prop), "m_pounceAttacker"); zombieClass = 3; }
		case 2: { strcopy(prop, sizeof(prop), "m_jockeyAttacker"); zombieClass = 5; }
		case 3: { strcopy(prop, sizeof(prop), "m_pummelAttacker"); zombieClass = 6; }
	}
	RemoveClient(g_PinOwner);
	g_PinOwner = MakeClient("gcb-pin-owner", 3, zombieClass, false);
	if (g_PinOwner > 0)
	{
		TeleportEntity(g_PinOwner, g_SubjectOrigin, NULL_VECTOR, NULL_VECTOR);
		SetEntityMoveType(g_PinOwner, MOVETYPE_NONE);
	}
	if (g_Subject > 0 && g_PinOwner > 0) SetEntPropEnt(g_Subject, Prop_Send, prop, g_PinOwner);
	if (g_Subject > 0) GetClientAbsOrigin(g_Subject, g_PinnedOrigin);
	g_HitIssued = HitSubject();
	CreateTimer(0.10, CheckPinnedStep);
	return Plugin_Stop;
}

Action CheckPinnedStep(Handle timer)
{
	static const char names[][] = {
		"warp_smoker_pin_is_preserved", "warp_hunter_pin_is_preserved",
		"warp_jockey_pin_is_preserved", "warp_charger_pin_is_preserved"
	};
	Case(names[g_PinStep], g_PinControlMoved && g_HitIssued && SubjectStayed(),
		"the same initialized attacker warps its paired control but preserves the class-matched pinned survivor");
	AdvanceWarpPair();
	return Plugin_Stop;
}

void AdvanceWarpPair()
{
	RemoveClient(g_PinOwner);
	g_PinStep++;
	if (g_PinStep < 4) CreateTimer(1.10, BeginWarpControl);
	else Finish();
	return;
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

void StartLifecycle()
{
	ServerCommand("sv_cheats 1");
	ServerCommand("director_stop");
	ServerExecute();
	RemoveScenarioBots();
	g_LifecycleTank = -1;
	g_BossStage = 0;
	g_BossPollAttempt = 0;
	CreateTimer(1.0, BeginBossLifecycle);
}

Action BeginBossLifecycle(Handle timer)
{
	g_LifecycleSurvivor = MakeClient("gcb-lifecycle-survivor", 2);
	if (g_LifecycleSurvivor > 0) PlaceAtMapSpawn(g_LifecycleSurvivor);
	g_SpawnAdmin = MakeClient("gcb-boss-admin", 3, 1);
	if (g_SpawnAdmin > 0) PlaceAtMapSpawn(g_SpawnAdmin);
	CreateTimer(0.5, SpawnBossLifecycle);
	return Plugin_Stop;
}

Action SpawnBossLifecycle(Handle timer)
{
	g_SpawnStage = 10;
	g_LifecycleTank = -1;
	if (g_SpawnAdmin > 0) MT_SpawnTank(g_SpawnAdmin, 1, 1);
	CreateTimer(1.5, BeginBossEvolution);
	return Plugin_Stop;
}

void FailBossLifecycle(const char[] detail)
{
	Case("boss_four_stage_evolution_completes", false, detail);
	Case("boss_final_stage_timer_remains_healthy", false, detail);
	RemoveClient(g_LifecycleTank);
	RemoveClient(g_SpawnAdmin);
	RemoveClient(g_LifecycleSurvivor);
	Finish();
}

Action BeginBossEvolution(Handle timer)
{
	bool ready = g_LifecycleTank > 0 && IsClientInGame(g_LifecycleTank)
		&& MT_IsCustomTankSupported(g_LifecycleTank) && MT_GetTankType(g_LifecycleTank) == 1;
	if (!ready)
	{
		FailBossLifecycle("the public spawn did not produce the configured four-stage Boss");
		return Plugin_Stop;
	}
	g_BossStage = 1;
	g_BossPollAttempt = 0;
	SetEntityHealth(g_LifecycleTank, 750);
	CreateTimer(0.2, PollBossEvolution);
	return Plugin_Stop;
}

Action PollBossEvolution(Handle timer)
{
	if (g_LifecycleTank <= 0 || !IsClientInGame(g_LifecycleTank))
	{
		FailBossLifecycle("the Boss disappeared before all configured forms completed");
		return Plugin_Stop;
	}
	int expected = g_BossStage + 1;
	if (MT_GetTankType(g_LifecycleTank) == expected)
	{
		if (g_BossStage == 4)
		{
			Case("boss_four_stage_evolution_completes", true,
				"engine health thresholds advance the live Boss through all four configured public types");
			CreateTimer(0.5, CheckBossFinalTimer);
			return Plugin_Stop;
		}
		g_BossStage++;
		g_BossPollAttempt = 0;
		static const int thresholds[] = {550, 350, 150};
		SetEntityHealth(g_LifecycleTank, thresholds[g_BossStage - 2]);
		CreateTimer(0.2, PollBossEvolution);
		return Plugin_Stop;
	}
	if (g_BossPollAttempt++ < 30)
	{
		CreateTimer(0.2, PollBossEvolution);
		return Plugin_Stop;
	}
	FailBossLifecycle("a configured Boss health threshold did not reach its next public type");
	return Plugin_Stop;
}

Action CheckBossFinalTimer(Handle timer)
{
	bool healthy = g_LifecycleTank > 0 && IsClientInGame(g_LifecycleTank)
		&& IsPlayerAlive(g_LifecycleTank) && MT_GetTankType(g_LifecycleTank) == 5;
	Case("boss_final_stage_timer_remains_healthy", healthy,
		"the final Boss form remains valid beyond multiple repeating-timer ticks");
	RemoveClient(g_LifecycleTank);
	RemoveClient(g_SpawnAdmin);
	RemoveClient(g_LifecycleSurvivor);
	Finish();
	return Plugin_Stop;
}

bool IsHypnoShield(int entity, int owner = -1)
{
	if (entity <= MaxClients || !IsValidEntity(entity)) return false;
	char classname[32], model[PLATFORM_MAX_PATH];
	GetEntityClassname(entity, classname, sizeof(classname));
	if (!StrEqual(classname, "prop_dynamic")) return false;
	GetEntPropString(entity, Prop_Data, "m_ModelName", model, sizeof(model));
	if (!StrEqual(model, "models/props_unique/airport/atlas_break_ball.mdl")) return false;
	return owner <= 0 || GetEntPropEnt(entity, Prop_Data, "m_hMoveParent") == owner;
}

int CountHypnoShields(int owner = -1)
{
	int count;
	int entity = -1;
	while ((entity = FindEntityByClassname(entity, "prop_dynamic")) != INVALID_ENT_REFERENCE)
	{
		if (IsHypnoShield(entity, owner)) count++;
	}
	return count;
}

int FindHypnoShieldRef(int owner)
{
	int entity = -1;
	while ((entity = FindEntityByClassname(entity, "prop_dynamic")) != INVALID_ENT_REFERENCE)
	{
		if (IsHypnoShield(entity, owner)) return EntIndexToEntRef(entity);
	}
	return INVALID_ENT_REFERENCE;
}

void StartHypno()
{
	ServerCommand("director_stop");
	ServerExecute();
	RemoveScenarioBots();
	g_HypnoTank = -1;
	g_HypnoSurvivor = -1;
	g_HypnoOldRef = INVALID_ENT_REFERENCE;
	CreateTimer(1.0, BeginHypnoVisibleDisabled);
}

void SpawnHypnoType(int type, const char[] name)
{
	g_HypnoTank = -1;
	g_HypnoSpawnRequestedAt = GetGameTime();
	g_HypnoPostSpawnAt = -1.0;
	g_SpawnAdmin = MakeClient(name, 3, 1);
	if (g_SpawnAdmin > 0) PlaceAtMapSpawn(g_SpawnAdmin);
	g_SpawnStage = 19 + type;
	if (g_SpawnAdmin > 0) MT_SpawnTank(g_SpawnAdmin, type, 1);
}

// Start the same observation window at the actual public spawn forward in
// every scenario. Allow the documented one-second deferred creation plus
// server scheduling tolerance; never unload the aggregate before that window.
bool WaitForHypnoSpawnWindow(Timer callback)
{
	float now = GetGameTime();
	bool waiting = g_HypnoPostSpawnAt < 0.0
		? now - g_HypnoSpawnRequestedAt < 5.0
		: now - g_HypnoPostSpawnAt < 1.4;
	if (waiting) CreateTimer(0.05, callback);
	return waiting;
}

Action BeginHypnoVisibleDisabled(Handle timer)
{
	SpawnHypnoType(1, "gcb-hypno-visible-disabled");
	CreateTimer(1.4, CheckHypnoVisibleDisabled);
	return Plugin_Stop;
}

Action CheckHypnoVisibleDisabled(Handle timer)
{
	if (WaitForHypnoSpawnWindow(CheckHypnoVisibleDisabled)) return Plugin_Stop;
	int currentRef = FindHypnoShieldRef(g_HypnoTank);
	bool exactlyOne = g_HypnoTank > 0 && CountHypnoShields(g_HypnoTank) == 1
		&& currentRef != INVALID_ENT_REFERENCE;
	Case("hypno_view1_disabled_spawns_one_shield", exactlyOne,
		"View 1 creates exactly one owner-parented shield at post-spawn even when gameplay activation is disabled");
	g_HypnoOldRef = currentRef;
	RemoveClient(g_HypnoTank);
	RemoveClient(g_SpawnAdmin);
	CreateTimer(0.3, CheckHypnoTankRemoval);
	return Plugin_Stop;
}

Action CheckHypnoTankRemoval(Handle timer)
{
	bool removed = CountHypnoShields() == 0
		&& (g_HypnoOldRef == INVALID_ENT_REFERENCE || EntRefToEntIndex(g_HypnoOldRef) == INVALID_ENT_REFERENCE);
	Case("hypno_tank_removal_cleans_shield", removed,
		"removing the owning Tank removes its shield entity and invalidates the old entref");
	CreateTimer(0.3, BeginHypnoRespawn);
	return Plugin_Stop;
}

Action BeginHypnoRespawn(Handle timer)
{
	SpawnHypnoType(1, "gcb-hypno-respawn");
	CreateTimer(0.3, CheckHypnoRespawn);
	return Plugin_Stop;
}

Action CheckHypnoRespawn(Handle timer)
{
	if (WaitForHypnoSpawnWindow(CheckHypnoRespawn)) return Plugin_Stop;
	int currentRef = FindHypnoShieldRef(g_HypnoTank);
	PrintToServer("GCB hypno respawn diagnostic: count=%d oldref=%d oldidx=%d newref=%d owner=%d",
		CountHypnoShields(g_HypnoTank), g_HypnoOldRef,
		EntRefToEntIndex(g_HypnoOldRef), currentRef, g_HypnoTank);
	bool renewed = CountHypnoShields(g_HypnoTank) == 1
		&& currentRef != INVALID_ENT_REFERENCE && currentRef != g_HypnoOldRef
		&& (g_HypnoOldRef == INVALID_ENT_REFERENCE || EntRefToEntIndex(g_HypnoOldRef) == INVALID_ENT_REFERENCE);
	Case("hypno_respawn_uses_new_shield_entref", renewed,
		"a later Tank lifecycle owns one new shield and never reuses the removed entity reference");
	RemoveClient(g_HypnoTank);
	RemoveClient(g_SpawnAdmin);
	CreateTimer(0.3, BeginHypnoViewZero);
	return Plugin_Stop;
}

Action BeginHypnoViewZero(Handle timer)
{
	g_HypnoSurvivor = MakeClient("gcb-hypno-survivor", 2);
	if (g_HypnoSurvivor > 0) PlaceAtMapSpawn(g_HypnoSurvivor);
	SpawnHypnoType(2, "gcb-hypno-view-zero");
	CreateTimer(1.4, CheckHypnoViewZero);
	return Plugin_Stop;
}

Action CheckHypnoViewZero(Handle timer)
{
	if (WaitForHypnoSpawnWindow(CheckHypnoViewZero)) return Plugin_Stop;
	bool none = CountHypnoShields(g_HypnoTank) == 0;
	Case("hypno_view0_never_spawns_shield", none,
		"View 0 produces no shield at spawn or after normal ability-activation ticks");
	if (g_HypnoTank <= 0 || !IsClientInGame(g_HypnoTank)
		|| g_HypnoSurvivor <= 0 || !IsClientInGame(g_HypnoSurvivor))
	{
		Case("hypno_view0_gameplay_hit_still_applies", false,
			"the live Tank/survivor pair was unavailable for the observable damage effect");
		RemoveClient(g_HypnoTank);
		RemoveClient(g_SpawnAdmin);
		RemoveClient(g_HypnoSurvivor);
		CreateTimer(0.3, BeginHypnoVisibleEnabled);
		return Plugin_Stop;
	}
	SetEntityHealth(g_HypnoTank, 1000);
	SetEntityHealth(g_HypnoSurvivor, 1000);
	SDKHooks_TakeDamage(g_HypnoSurvivor, g_HypnoTank, g_HypnoTank, 1.0, DMG_CLUB, -1, NULL_VECTOR, NULL_VECTOR, false);
	CreateTimer(0.1, ApplyHypnoReturnDamage);
	return Plugin_Stop;
}

Action ApplyHypnoReturnDamage(Handle timer)
{
	g_HypnoHealthBefore = GetEntProp(g_HypnoSurvivor, Prop_Data, "m_iHealth");
	g_HypnoTankHealthBefore = GetEntProp(g_HypnoTank, Prop_Data, "m_iHealth");
	SDKHooks_TakeDamage(g_HypnoTank, g_HypnoSurvivor, g_HypnoSurvivor, 100.0, DMG_BULLET, -1, NULL_VECTOR, NULL_VECTOR, false);
	CreateTimer(0.1, CheckHypnoReturnDamage);
	return Plugin_Stop;
}

Action CheckHypnoReturnDamage(Handle timer)
{
	int after = GetEntProp(g_HypnoSurvivor, Prop_Data, "m_iHealth");
	int tankAfter = GetEntProp(g_HypnoTank, Prop_Data, "m_iHealth");
	int reflected = g_HypnoHealthBefore - after;
	PrintToServer("GCB hypno damage diagnostic: survivor_before=%d survivor_after=%d reflected=%d tank_before=%d tank_after=%d",
		g_HypnoHealthBefore, after, reflected, g_HypnoTankHealthBefore, tankAfter);
	Case("hypno_view0_gameplay_hit_still_applies",
		reflected >= 9 && reflected <= 11 && tankAfter == g_HypnoTankHealthBefore,
		"a guaranteed View 0 hit remains gameplay-active and reflects the divided bullet damage to the affected survivor");
	RemoveClient(g_HypnoTank);
	RemoveClient(g_SpawnAdmin);
	RemoveClient(g_HypnoSurvivor);
	CreateTimer(0.3, BeginHypnoVisibleEnabled);
	return Plugin_Stop;
}

Action BeginHypnoVisibleEnabled(Handle timer)
{
	g_HypnoSurvivor = MakeClient("gcb-hypno-visible-survivor", 2);
	if (g_HypnoSurvivor > 0) PlaceAtMapSpawn(g_HypnoSurvivor);
	SpawnHypnoType(3, "gcb-hypno-visible-enabled");
	CreateTimer(1.4, CheckHypnoVisibleEnabled);
	return Plugin_Stop;
}

Action CheckHypnoVisibleEnabled(Handle timer)
{
	if (WaitForHypnoSpawnWindow(CheckHypnoVisibleEnabled)) return Plugin_Stop;
	int currentRef = FindHypnoShieldRef(g_HypnoTank);
	bool single = CountHypnoShields(g_HypnoTank) == 1
		&& currentRef != INVALID_ENT_REFERENCE;
	Case("hypno_view1_enabled_activation_does_not_duplicate", single,
		"View 1 has the same single owner-parented shield before and after normal ability activation");
	Event roundEnd = CreateEvent("round_end");
	if (roundEnd != null) roundEnd.Fire();
	CreateTimer(0.3, CheckHypnoRoundCleanup);
	return Plugin_Stop;
}

Action CheckHypnoRoundCleanup(Handle timer)
{
	g_HypnoRoundClean = CountHypnoShields() == 0;
	PrintToServer("GCB hypno round cleanup diagnostic: clean=%d count=%d", g_HypnoRoundClean, CountHypnoShields());
	RemoveClient(g_HypnoTank);
	RemoveClient(g_SpawnAdmin);
	RemoveClient(g_HypnoSurvivor);
	Event roundStart = CreateEvent("round_start");
	if (roundStart != null) roundStart.Fire();
	CreateTimer(0.5, SpawnHypnoForPluginCleanup);
	return Plugin_Stop;
}

Action SpawnHypnoForPluginCleanup(Handle timer)
{
	SpawnHypnoType(3, "gcb-hypno-plugin-cleanup");
	CreateTimer(0.3, UnloadHypnoAggregate);
	return Plugin_Stop;
}

Action UnloadHypnoAggregate(Handle timer)
{
	if (WaitForHypnoSpawnWindow(UnloadHypnoAggregate)) return Plugin_Stop;
	bool shieldReady = CountHypnoShields(g_HypnoTank) == 1;
	PrintToServer("GCB hypno pre-unload diagnostic: ready=%d count=%d owner=%d", shieldReady,
		CountHypnoShields(g_HypnoTank), g_HypnoTank);
	ServerCommand("sm plugins unload 10_mt_abilities.smx");
	ServerExecute();
	g_HypnoRoundClean = g_HypnoRoundClean && shieldReady;
	CreateTimer(0.4, CheckHypnoPluginCleanup);
	return Plugin_Stop;
}

Action CheckHypnoPluginCleanup(Handle timer)
{
	bool clean = g_HypnoRoundClean && CountHypnoShields() == 0
		&& FindPluginByFile("10_mt_abilities.smx") == null;
	PrintToServer("GCB hypno post-unload diagnostic: prior=%d count=%d loaded=%d", g_HypnoRoundClean,
		CountHypnoShields(), FindPluginByFile("10_mt_abilities.smx") != null);
	Case("hypno_round_and_plugin_cleanup_leave_no_orphans", clean,
		"round reset and aggregate unload each remove all shield entities without leaving an orphan");
	RemoveClient(g_HypnoTank);
	RemoveClient(g_SpawnAdmin);
	Finish();
	return Plugin_Stop;
}

void ResetMultiCapture(int mode)
{
	for (int i = 0; i < g_MultiRefCount; i++)
	{
		int entity = EntRefToEntIndex(g_MultiRefs[i]);
		if (entity > MaxClients && IsValidEntity(entity)) RemoveEntity(entity);
		g_MultiRefs[i] = INVALID_ENT_REFERENCE;
	}
	g_MultiRefCount = 0;
	g_MultiCapture = mode;
}

bool IsAllowedUncommonModel(const char[] model)
{
	return StrEqual(model, "models/infected/common_male_ceda.mdl")
		|| StrEqual(model, "models/infected/common_male_jimmy.mdl")
		|| StrEqual(model, "models/infected/common_male_fallen_survivor.mdl")
		|| StrEqual(model, "models/infected/common_male_clown.mdl")
		|| StrEqual(model, "models/infected/common_male_mud.mdl")
		|| StrEqual(model, "models/infected/common_male_roadcrew.mdl")
		|| StrEqual(model, "models/infected/common_male_riot.mdl");
}

int CountCapturedUncommon(int &first)
{
	int count;
	first = INVALID_ENT_REFERENCE;
	for (int i = 0; i < g_MultiRefCount; i++)
	{
		int entity = EntRefToEntIndex(g_MultiRefs[i]);
		if (entity <= MaxClients || !IsValidEntity(entity)) continue;
		char classname[32], model[PLATFORM_MAX_PATH];
		GetEntityClassname(entity, classname, sizeof(classname));
		GetEntPropString(entity, Prop_Data, "m_ModelName", model, sizeof(model));
		if (StrEqual(classname, "infected") && IsAllowedUncommonModel(model))
		{
			if (first == INVALID_ENT_REFERENCE) first = entity;
			count++;
		}
	}
	return count;
}

void RemoveMultiTank()
{
	RemoveClient(g_MultiTank);
	RemoveClient(g_SpawnAdmin);
}

void SpawnMultiTank(int type, int stage, const char[] name)
{
	RemoveMultiTank();
	g_MultiTank = -1;
	g_SpawnAdmin = MakeClient(name, 3, 1);
	if (g_SpawnAdmin > 0) PlaceAtMapSpawn(g_SpawnAdmin);
	g_SpawnStage = stage;
	if (g_SpawnAdmin > 0) MT_SpawnTank(g_SpawnAdmin, type, 1);
}

void StartPanicFallback()
{
	ServerCommand("director_stop");
	ServerCommand("z_common_limit 0");
	ServerExecute();
	RemoveScenarioBots();
	g_MultiTank = -1;
	g_MultiCapture = 0;
	g_MultiRefCount = 0;
	CreateTimer(1.0, BeginPanicGuard);
}

Action BeginPanicGuard(Handle timer)
{
	ResetMultiCapture(3);
	SpawnMultiTank(1, 30, "gcb-panic-explicit");
	CreateTimer(0.5, CheckPanicGuard);
	return Plugin_Stop;
}

Action CheckPanicGuard(Handle timer)
{
	int uncommon;
	int count = CountCapturedUncommon(uncommon);
	char model[PLATFORM_MAX_PATH];
	if (uncommon > MaxClients && IsValidEntity(uncommon))
		GetEntPropString(uncommon, Prop_Data, "m_ModelName", model, sizeof(model));
	PrintToServer("GCB Panic fallback guard diagnostic: count=%d model=%s raw=%d", count, model, g_MultiRefCount);
	Case("panic_explicit_uncommon_type_guard_works",
		g_MultiRefCount == 1 && count == 1 && StrEqual(model, "models/infected/common_male_clown.mdl"),
		"the explicit Panic Type=8 control creates exactly one real clown uncommon infected");
	ResetMultiCapture(0);
	RemoveMultiTank();
	CreateTimer(0.3, BeginPanicFallback);
	return Plugin_Stop;
}

Action BeginPanicFallback(Handle timer)
{
	ResetMultiCapture(4);
	SpawnMultiTank(2, 31, "gcb-panic-empty");
	CreateTimer(0.5, CheckPanicFallback);
	return Plugin_Stop;
}

Action CheckPanicFallback(Handle timer)
{
	int uncommon;
	int count = CountCapturedUncommon(uncommon);
	char model[PLATFORM_MAX_PATH];
	if (uncommon > MaxClients && IsValidEntity(uncommon))
		GetEntPropString(uncommon, Prop_Data, "m_ModelName", model, sizeof(model));
	PrintToServer("GCB Panic fallback target diagnostic: count=%d model=%s raw=%d", count, model, g_MultiRefCount);
	Case("panic_empty_type_spawns_one_uncommon", g_MultiRefCount == 1 && count == 1,
		"an empty Panic Type mask still creates exactly the configured one real uncommon infected");
	Case("panic_fallback_uncommon_uses_allowed_model", g_MultiRefCount == 1 && count == 1 && IsAllowedUncommonModel(model),
		"the fallback uncommon uses one of the seven documented uncommon-infected models");
	ResetMultiCapture(0);
	RemoveMultiTank();
	Finish();
	return Plugin_Stop;
}

void ReadRenderColor(int client, int color[4])
{
	color[0] = color[1] = color[2] = color[3] = -1;
	if (client > 0 && IsClientInGame(client))
	{
		GetEntityRenderColor(client, color[0], color[1], color[2], color[3]);
	}
}

bool RGBChanged(int first[4], int second[4])
{
	return first[0] != second[0] || first[1] != second[1] || first[2] != second[2];
}

bool RGBWhite(int color[4])
{
	return color[0] == 255 && color[1] == 255 && color[2] == 255;
}

void PrintRainbowColors(const char[] phase)
{
	PrintToServer("GCB rainbow %s: sourceA=%d,%d,%d sourceB=%d,%d,%d targetA=%d,%d,%d targetB=%d,%d,%d reward=%d",
		phase,
		g_RainbowSourceA[0], g_RainbowSourceA[1], g_RainbowSourceA[2],
		g_RainbowSourceB[0], g_RainbowSourceB[1], g_RainbowSourceB[2],
		g_RainbowTargetA[0], g_RainbowTargetA[1], g_RainbowTargetA[2],
		g_RainbowTargetB[0], g_RainbowTargetB[1], g_RainbowTargetB[2],
		g_RainbowRewardForward);
}

void FailRainbow(const char[] detail)
{
	Case("rainbow_reward_animates_before_takeover", false, detail);
	Case("rainbow_bot_to_player_migrates_animation", false, detail);
	Case("rainbow_old_bot_stops_after_takeover", false, detail);
	Case("rainbow_player_to_bot_migrates_animation", false, detail);
	Case("rainbow_old_player_stops_after_idle", false, detail);
	Finish();
}

void StartRainbowTransfer()
{
	ServerCommand("sv_cheats 1");
	ServerCommand("director_stop");
	ServerExecute();
	RemoveScenarioBots();
	g_RainbowTank = -1;
	g_RainbowSource = -1;
	g_RainbowTarget = -1;
	g_RainbowRewardForward = false;
	g_RainbowTankDied = false;
	g_RainbowTankPollAttempt = 0;
	g_RainbowWeapon = INVALID_ENT_REFERENCE;
	CreateTimer(1.0, BeginRainbowTransfer);
}

Action BeginRainbowTransfer(Handle timer)
{
	g_RainbowSource = MakeClient("gcb-rainbow-bot", 2);
	g_RainbowTarget = MakeClient("gcb-rainbow-player", 2);
	if (g_RainbowSource > 0)
	{
		PlaceAtMapSpawn(g_RainbowSource);
		SetEntityMoveType(g_RainbowSource, MOVETYPE_NONE);
		int weapon = GivePlayerItem(g_RainbowSource, "weapon_smg");
		if (weapon > MaxClients)
		{
			EquipPlayerWeapon(g_RainbowSource, weapon);
			g_RainbowWeapon = EntIndexToEntRef(weapon);
		}
	}
	if (g_RainbowTarget > 0)
	{
		PlaceAtMapSpawn(g_RainbowTarget);
		SetEntityMoveType(g_RainbowTarget, MOVETYPE_NONE);
	}
	g_SpawnAdmin = MakeClient("gcb-rainbow-tank-admin", 3, 1);
	if (g_SpawnAdmin > 0) PlaceAtMapSpawn(g_SpawnAdmin);
	g_SpawnStage = 40;
	if (g_SpawnAdmin > 0) MT_SpawnTank(g_SpawnAdmin, 1, 8);
	CreateTimer(1.2, KillRainbowTank);
	return Plugin_Stop;
}

Action KillRainbowTank(Handle timer)
{
	if (g_RainbowTank <= 0 || !IsClientInGame(g_RainbowTank)
		|| GetEntProp(g_RainbowTank, Prop_Send, "m_zombieClass") != 8)
	{
		g_RainbowTank = FindLiveMutantTank(1, g_SpawnAdmin);
	}
	bool ready = g_RainbowTank > 0 && IsClientInGame(g_RainbowTank) && IsPlayerAlive(g_RainbowTank)
		&& GetEntProp(g_RainbowTank, Prop_Send, "m_zombieClass") == 8
		&& g_RainbowSource > 0 && IsClientInGame(g_RainbowSource) && IsPlayerAlive(g_RainbowSource)
		&& g_RainbowTarget > 0 && IsClientInGame(g_RainbowTarget) && IsPlayerAlive(g_RainbowTarget);
	if (!ready)
	{
		if (g_RainbowTankPollAttempt++ < 30)
		{
			CreateTimer(0.2, KillRainbowTank);
			return Plugin_Stop;
		}
		FailRainbow("the dedicated-server fixture could not establish the Tank and two living survivors");
		return Plugin_Stop;
	}
	SetEntProp(g_RainbowTank, Prop_Data, "m_iMaxHealth", 50);
	SetEntityHealth(g_RainbowTank, 1);
	int weapon = EntRefToEntIndex(g_RainbowWeapon);
	if (weapon <= MaxClients || !IsValidEntity(weapon))
	{
		FailRainbow("the survivor's real SMG inflictor was unavailable for the Tank death");
		return Plugin_Stop;
	}
	SDKHooks_TakeDamage(g_RainbowTank, g_RainbowSource, g_RainbowSource, 5000.0,
		DMG_BULLET, weapon, NULL_VECTOR, NULL_VECTOR, false);
	CreateTimer(0.2, InspectRainbowDeath);
	return Plugin_Stop;
}

Action InspectRainbowDeath(Handle timer)
{
	g_RainbowTankDied = g_RainbowTank > 0 && IsClientInGame(g_RainbowTank)
		&& !IsPlayerAlive(g_RainbowTank);
	PrintToServer("GCB rainbow death diagnostic: tank=%d connected=%d alive=%d health=%d source=%d reward=%d",
		g_RainbowTank,
		g_RainbowTank > 0 && IsClientConnected(g_RainbowTank),
		g_RainbowTank > 0 && IsClientInGame(g_RainbowTank) && IsPlayerAlive(g_RainbowTank),
		g_RainbowTank > 0 && IsClientInGame(g_RainbowTank) ? GetEntProp(g_RainbowTank, Prop_Data, "m_iHealth") : -1,
		g_RainbowSource, g_RainbowRewardForward);
	CreateTimer(0.5, SampleRainbowRewardA);
	return Plugin_Stop;
}

Action SampleRainbowRewardA(Handle timer)
{
	ReadRenderColor(g_RainbowSource, g_RainbowSourceA);
	CreateTimer(0.4, SampleRainbowRewardB);
	return Plugin_Stop;
}

Action SampleRainbowRewardB(Handle timer)
{
	ReadRenderColor(g_RainbowSource, g_RainbowSourceB);
	PrintRainbowColors("reward");
	bool animated = g_RainbowTankDied && g_RainbowRewardForward && RGBChanged(g_RainbowSourceA, g_RainbowSourceB)
		&& !RGBWhite(g_RainbowSourceA) && !RGBWhite(g_RainbowSourceB);
	Case("rainbow_reward_animates_before_takeover", animated,
		"a real Tank death emits the public reward forward and starts a changing rainbow body color");
	if (g_RainbowSource <= 0 || g_RainbowTarget <= 0
		|| !IsClientInGame(g_RainbowSource) || !IsClientInGame(g_RainbowTarget))
	{
		Case("rainbow_bot_to_player_migrates_animation", false, "the replacement pair disconnected before bot_player_replace");
		Case("rainbow_old_bot_stops_after_takeover", false, "the replacement pair disconnected before bot_player_replace");
		Case("rainbow_player_to_bot_migrates_animation", false, "the replacement pair disconnected before player_bot_replace");
		Case("rainbow_old_player_stops_after_idle", false, "the replacement pair disconnected before player_bot_replace");
		Finish();
		return Plugin_Stop;
	}
	Event takeover = CreateEvent("bot_player_replace");
	if (takeover != null)
	{
		takeover.SetInt("bot", GetClientUserId(g_RainbowSource));
		takeover.SetInt("player", GetClientUserId(g_RainbowTarget));
		takeover.Fire();
	}
	CreateTimer(0.15, SampleTakeoverA);
	return Plugin_Stop;
}

Action SampleTakeoverA(Handle timer)
{
	ReadRenderColor(g_RainbowSource, g_RainbowSourceA);
	ReadRenderColor(g_RainbowTarget, g_RainbowTargetA);
	CreateTimer(0.4, SampleTakeoverB);
	return Plugin_Stop;
}

Action SampleTakeoverB(Handle timer)
{
	ReadRenderColor(g_RainbowSource, g_RainbowSourceB);
	ReadRenderColor(g_RainbowTarget, g_RainbowTargetB);
	PrintRainbowColors("bot_player_replace");
	Case("rainbow_bot_to_player_migrates_animation",
		RGBChanged(g_RainbowTargetA, g_RainbowTargetB)
			&& !RGBWhite(g_RainbowTargetA) && !RGBWhite(g_RainbowTargetB),
		"bot_player_replace migrates the live reward animation to the replacement survivor");
	Case("rainbow_old_bot_stops_after_takeover",
		RGBWhite(g_RainbowSourceA) && RGBWhite(g_RainbowSourceB),
		"the replaced bot is reset to a stable neutral render color after takeover");
	Event idle = CreateEvent("player_bot_replace");
	if (idle != null)
	{
		idle.SetInt("player", GetClientUserId(g_RainbowTarget));
		idle.SetInt("bot", GetClientUserId(g_RainbowSource));
		idle.Fire();
	}
	CreateTimer(0.15, SampleIdleA);
	return Plugin_Stop;
}

Action SampleIdleA(Handle timer)
{
	ReadRenderColor(g_RainbowSource, g_RainbowSourceA);
	ReadRenderColor(g_RainbowTarget, g_RainbowTargetA);
	CreateTimer(0.4, SampleIdleB);
	return Plugin_Stop;
}

Action SampleIdleB(Handle timer)
{
	ReadRenderColor(g_RainbowSource, g_RainbowSourceB);
	ReadRenderColor(g_RainbowTarget, g_RainbowTargetB);
	PrintRainbowColors("player_bot_replace");
	Case("rainbow_player_to_bot_migrates_animation",
		RGBChanged(g_RainbowSourceA, g_RainbowSourceB)
			&& !RGBWhite(g_RainbowSourceA) && !RGBWhite(g_RainbowSourceB),
		"player_bot_replace migrates the live reward animation back to the idle bot");
	Case("rainbow_old_player_stops_after_idle",
		RGBWhite(g_RainbowTargetA) && RGBWhite(g_RainbowTargetB),
		"the idled survivor is reset to a stable neutral render color after replacement");
	Finish();
	return Plugin_Stop;
}

void FailCooldown(const char[] detail)
{
	Case("acid_melee_cooldown_blocks_window_repeat", false, detail);
	Case("ammo_melee_cooldown_blocks_window_repeat", false, detail);
	Case("acid_melee_cooldown_recovers_after_expiry", false, detail);
	Case("ammo_melee_cooldown_recovers_after_expiry", false, detail);
	Case("acid_zero_cooldown_allows_cross_second_repeat", false, detail);
	Case("ammo_zero_cooldown_allows_cross_second_repeat", false, detail);
	Finish();
}

void StartCooldown()
{
	ServerCommand("sv_cheats 1");
	ServerCommand("director_stop");
	ServerExecute();
	RemoveScenarioBots();
	g_CooldownTank = -1;
	g_CooldownSurvivor = -1;
	g_CooldownWeapon = INVALID_ENT_REFERENCE;
	g_CooldownCapture = false;
	g_CooldownAcidCount = 0;
	CreateTimer(1.0, BeginCooldown);
}

Action BeginCooldown(Handle timer)
{
	g_CooldownSurvivor = MakeClient("gcb-cooldown-survivor", 2);
	if (g_CooldownSurvivor <= 0)
	{
		FailCooldown("the dedicated server could not create the survivor fixture");
		return Plugin_Stop;
	}
	PlaceAtMapSpawn(g_CooldownSurvivor);
	SetEntityMoveType(g_CooldownSurvivor, MOVETYPE_NONE);
	int oldWeapon = GetPlayerWeaponSlot(g_CooldownSurvivor, 0);
	if (oldWeapon > MaxClients && IsValidEntity(oldWeapon))
	{
		RemovePlayerItem(g_CooldownSurvivor, oldWeapon);
		RemoveEntity(oldWeapon);
	}
	int weapon = GivePlayerItem(g_CooldownSurvivor, "weapon_smg");
	if (weapon > MaxClients)
	{
		EquipPlayerWeapon(g_CooldownSurvivor, weapon);
		g_CooldownWeapon = EntIndexToEntRef(weapon);
	}
	SpawnCooldownTank(1);
	CreateTimer(1.0, BeginCooldownTwoSecond);
	return Plugin_Stop;
}

void SpawnCooldownTank(int type)
{
	RemoveClient(g_CooldownTank);
	RemoveClient(g_SpawnAdmin);
	g_CooldownTank = -1;
	g_CooldownTankPollAttempt = 0;
	g_SpawnAdmin = MakeClient(type == 1 ? "gcb-cooldown-two" : "gcb-cooldown-zero", 3, 1);
	if (g_SpawnAdmin > 0) PlaceAtMapSpawn(g_SpawnAdmin);
	g_SpawnStage = 49 + type;
	if (g_SpawnAdmin > 0) MT_SpawnTank(g_SpawnAdmin, type, 8);
}

int FindLiveMutantTank(int type, int excluded)
{
	for (int client = 1; client <= MaxClients; client++)
	{
		if (client != excluded && IsClientInGame(client) && IsPlayerAlive(client) && GetClientTeam(client) == 3
			&& GetEntProp(client, Prop_Send, "m_zombieClass") == 8
			&& MT_GetTankType(client) == type)
		{
			return client;
		}
	}
	return -1;
}

int CooldownWeaponIndex()
{
	int weapon = EntRefToEntIndex(g_CooldownWeapon);
	return weapon > MaxClients && IsValidEntity(weapon) ? weapon : -1;
}

int TankClawIndex()
{
	if (g_CooldownTank <= 0 || !IsClientInGame(g_CooldownTank)) return -1;
	int weapon = GetEntPropEnt(g_CooldownTank, Prop_Send, "m_hActiveWeapon");
	char classname[32];
	if (weapon > MaxClients && IsValidEntity(weapon))
	{
		GetEntityClassname(weapon, classname, sizeof(classname));
		if (StrEqual(classname, "weapon_tank_claw")) return weapon;
	}
	weapon = -1;
	while ((weapon = FindEntityByClassname(weapon, "weapon_tank_claw")) != INVALID_ENT_REFERENCE)
	{
		if (GetEntPropEnt(weapon, Prop_Data, "m_hOwnerEntity") == g_CooldownTank) return weapon;
	}
	return -1;
}

bool ResetCooldownAmmo()
{
	int weapon = (g_CooldownSurvivor > 0 && IsClientInGame(g_CooldownSurvivor))
		? GetPlayerWeaponSlot(g_CooldownSurvivor, 0) : -1;
	if (weapon > MaxClients && IsValidEntity(weapon))
	{
		g_CooldownWeapon = EntIndexToEntRef(weapon);
	}
	if (weapon <= MaxClients || g_CooldownSurvivor <= 0 || !IsClientInGame(g_CooldownSurvivor)) return false;
	char classname[32];
	GetEntityClassname(weapon, classname, sizeof(classname));
	if (StrContains(classname, "weapon_smg") != 0) return false;
	int ammoType = GetEntProp(weapon, Prop_Send, "m_iPrimaryAmmoType");
	if (ammoType < 0) return false;
	SetEntProp(weapon, Prop_Send, "m_iClip1", 100);
	SetEntProp(g_CooldownSurvivor, Prop_Send, "m_iAmmo", 100, .element = ammoType);
	SetEntityHealth(g_CooldownSurvivor, 1000);
	return true;
}

void ReadCooldownAmmo(int &clip, int &reserve)
{
	clip = reserve = -1;
	int weapon = CooldownWeaponIndex();
	if (weapon <= MaxClients || g_CooldownSurvivor <= 0 || !IsClientInGame(g_CooldownSurvivor)) return;
	int ammoType = GetEntProp(weapon, Prop_Send, "m_iPrimaryAmmoType");
	if (ammoType < 0) return;
	clip = GetEntProp(weapon, Prop_Send, "m_iClip1");
	reserve = GetEntProp(g_CooldownSurvivor, Prop_Send, "m_iAmmo", .element = ammoType);
}

bool IssueCooldownClawHit()
{
	int claw = TankClawIndex();
	if (claw <= MaxClients || g_CooldownTank <= 0 || !IsClientInGame(g_CooldownTank)
		|| g_CooldownSurvivor <= 0 || !IsClientInGame(g_CooldownSurvivor)) return false;
	float origin[3];
	GetClientAbsOrigin(g_CooldownSurvivor, origin);
	origin[0] += 32.0;
	TeleportEntity(g_CooldownTank, origin, NULL_VECTOR, NULL_VECTOR);
	SetEntityMoveType(g_CooldownTank, MOVETYPE_NONE);
	SetEntityHealth(g_CooldownSurvivor, 1000);
	SDKHooks_TakeDamage(g_CooldownSurvivor, claw, g_CooldownTank, 1.0,
		DMG_CLUB, claw, NULL_VECTOR, NULL_VECTOR, false);
	return true;
}

Action BeginCooldownTwoSecond(Handle timer)
{
	if (g_CooldownTank <= 0 || !IsClientInGame(g_CooldownTank)
		|| GetEntProp(g_CooldownTank, Prop_Send, "m_zombieClass") != 8)
	{
		g_CooldownTank = FindLiveMutantTank(1, g_SpawnAdmin);
	}
	bool ready = g_CooldownTank > 0 && IsClientInGame(g_CooldownTank) && IsPlayerAlive(g_CooldownTank)
		&& GetEntProp(g_CooldownTank, Prop_Send, "m_zombieClass") == 8
		&& MT_GetTankType(g_CooldownTank) == 1 && ResetCooldownAmmo() && TankClawIndex() > MaxClients;
	if (!ready)
	{
		if (g_CooldownTankPollAttempt++ < 30)
		{
			CreateTimer(0.2, BeginCooldownTwoSecond);
			return Plugin_Stop;
		}
		FailCooldown("the Cooldown=2 Tank, weapon, or survivor fixture was unavailable");
		return Plugin_Stop;
	}
	g_CooldownAcidCount = 0;
	g_CooldownCapture = true;
	IssueCooldownClawHit();
	CreateTimer(1.2, CooldownWindowSecondHit);
	return Plugin_Stop;
}

Action CooldownWindowSecondHit(Handle timer)
{
	IssueCooldownClawHit();
	CreateTimer(0.25, CheckCooldownWindow);
	return Plugin_Stop;
}

Action CheckCooldownWindow(Handle timer)
{
	int clip, reserve;
	ReadCooldownAmmo(clip, reserve);
	PrintToServer("GCB cooldown window: acid=%d clip=%d reserve=%d time=%d", g_CooldownAcidCount, clip, reserve, GetTime());
	Case("acid_melee_cooldown_blocks_window_repeat", g_CooldownAcidCount == 1,
		"two successful claw hits inside Cooldown=2 create only one real spitter projectile");
	Case("ammo_melee_cooldown_blocks_window_repeat", clip == 90 && reserve == 90,
		"two successful claw hits inside Cooldown=2 drain magazine and reserve exactly once");
	CreateTimer(1.85, CooldownExpiredThirdHit);
	return Plugin_Stop;
}

Action CooldownExpiredThirdHit(Handle timer)
{
	IssueCooldownClawHit();
	CreateTimer(0.25, CheckCooldownExpired);
	return Plugin_Stop;
}

Action CheckCooldownExpired(Handle timer)
{
	int clip, reserve;
	ReadCooldownAmmo(clip, reserve);
	PrintToServer("GCB cooldown expiry: acid=%d clip=%d reserve=%d time=%d", g_CooldownAcidCount, clip, reserve, GetTime());
	Case("acid_melee_cooldown_recovers_after_expiry", g_CooldownAcidCount == 2,
		"a later claw hit after Cooldown=2 expires creates the second real spitter projectile");
	Case("ammo_melee_cooldown_recovers_after_expiry", clip == 80 && reserve == 80,
		"a later claw hit after Cooldown=2 expires performs the second magazine and reserve drain");
	g_CooldownCapture = false;
	SpawnCooldownTank(2);
	CreateTimer(1.0, BeginCooldownZero);
	return Plugin_Stop;
}

Action BeginCooldownZero(Handle timer)
{
	if (g_CooldownTank <= 0 || !IsClientInGame(g_CooldownTank)
		|| GetEntProp(g_CooldownTank, Prop_Send, "m_zombieClass") != 8)
	{
		g_CooldownTank = FindLiveMutantTank(2, g_SpawnAdmin);
	}
	bool ready = g_CooldownTank > 0 && IsClientInGame(g_CooldownTank) && IsPlayerAlive(g_CooldownTank)
		&& GetEntProp(g_CooldownTank, Prop_Send, "m_zombieClass") == 8
		&& MT_GetTankType(g_CooldownTank) == 2 && ResetCooldownAmmo() && TankClawIndex() > MaxClients;
	if (!ready)
	{
		if (g_CooldownTankPollAttempt++ < 30)
		{
			CreateTimer(0.2, BeginCooldownZero);
			return Plugin_Stop;
		}
		Case("acid_zero_cooldown_allows_cross_second_repeat", false,
			"the Cooldown=0 Tank, weapon, or survivor fixture was unavailable");
		Case("ammo_zero_cooldown_allows_cross_second_repeat", false,
			"the Cooldown=0 Tank, weapon, or survivor fixture was unavailable");
		Finish();
		return Plugin_Stop;
	}
	g_CooldownAcidCount = 0;
	g_CooldownCapture = true;
	IssueCooldownClawHit();
	CreateTimer(1.2, CooldownZeroSecondHit);
	return Plugin_Stop;
}

Action CooldownZeroSecondHit(Handle timer)
{
	IssueCooldownClawHit();
	CreateTimer(0.25, CheckCooldownZero);
	return Plugin_Stop;
}

Action CheckCooldownZero(Handle timer)
{
	int clip, reserve;
	ReadCooldownAmmo(clip, reserve);
	PrintToServer("GCB cooldown zero: acid=%d clip=%d reserve=%d time=%d", g_CooldownAcidCount, clip, reserve, GetTime());
	Case("acid_zero_cooldown_allows_cross_second_repeat", g_CooldownAcidCount == 2,
		"Cooldown=0 allows both cross-second claw hits to create real spitter projectiles");
	Case("ammo_zero_cooldown_allows_cross_second_repeat", clip == 80 && reserve == 80,
		"Cooldown=0 allows both cross-second claw hits to drain magazine and reserve");
	g_CooldownCapture = false;
	Finish();
	return Plugin_Stop;
}

void Finish()
{
	RemoveClient(g_HealthBot);
	RemoveClient(g_WarpBot);
	RemoveClient(g_SpawnAdmin);
	RemoveClient(g_Destination);
	RemoveClient(g_Subject);
	RemoveClient(g_PinOwner);
	RemoveClient(g_LifecycleTank);
	RemoveClient(g_LifecycleSurvivor);
	RemoveClient(g_HypnoTank);
	RemoveClient(g_HypnoSurvivor);
	ResetMultiCapture(0);
	RemoveClient(g_MultiTank);
	RemoveClient(g_RainbowTank);
	RemoveClient(g_RainbowSource);
	RemoveClient(g_RainbowTarget);
	RemoveClient(g_CooldownTank);
	RemoveClient(g_CooldownSurvivor);
	PrintToServer("@@GCB_SM@@%s:FINAL:%d:%d", NONCE, g_Passed, g_Total);
	ServerCommand("quit");
}
