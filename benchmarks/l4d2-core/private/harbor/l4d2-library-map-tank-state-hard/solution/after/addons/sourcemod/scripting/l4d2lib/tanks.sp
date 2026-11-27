#if defined _l4d2lib_tanks_included
	#endinput
#endif
#define _l4d2lib_tanks_included

/* Global Vars */
static Handle
	g_hFwdFirstTankSpawn = null,
	g_hFwdTankPassControl = null,
	g_hFwdTankDeath = null,
	g_hTankDeathTimer = null;

static bool
	g_bIsTankActive = false;

static int
	g_iTankClient = -1,
	g_iTankPassCount = 0;

void Tanks_AskPluginLoad2()
{
	g_hFwdFirstTankSpawn = CreateGlobalForward("L4D2_OnTankFirstSpawn", ET_Ignore, Param_Cell);  //never used
	g_hFwdTankPassControl = CreateGlobalForward("L4D2_OnTankPassControl", ET_Ignore, Param_Cell, Param_Cell, Param_Cell); //l4d2_tank_support & l4d2_fix_spawn_order
	g_hFwdTankDeath = CreateGlobalForward("L4D2_OnTankDeath", ET_Ignore, Param_Cell);  //never used
}

void Tanks_OnMapStart()
{
	ResetStatus();
}

void Tanks_RoundStart()
{
	ResetStatus();
}

static int g_TankSerial;

static bool TankValid(int client)
{
    return client > 0 && client <= MaxClients && IsClientInGame(client)
        && !IsClientInKickQueue(client) && IsPlayerAlive(client)
        && GetClientTeam(client) == 3 && GetEntProp(client, Prop_Send, "m_zombieClass") == 8;
}

void Tanks_TankSpawn(Event event)
{
    int client = GetClientOfUserId(event.GetInt("userid"));
    if (!TankValid(client)) return;
    if (g_bIsTankActive && GetClientFromSerial(g_TankSerial) == g_iTankClient) return;
    ResetStatus();
    g_bIsTankActive = true;
    g_iTankClient = client;
    g_TankSerial = GetClientSerial(client);
    Call_StartForward(g_hFwdFirstTankSpawn);
    Call_PushCell(client);
    Call_Finish();
}

void Tanks_ItemPickup(Event event)
{
    if (!g_bIsTankActive) return;
    if (GetClientFromSerial(g_TankSerial) != g_iTankClient) { ResetStatus(); return; }
    char item[64];event.GetString("item", item, sizeof(item));
    int client = GetClientOfUserId(event.GetInt("userid"));
    if (!StrEqual(item, "tank_claw") || !TankValid(client) || client == g_iTankClient) return;
    int previous = g_iTankClient, passes = g_iTankPassCount++;
    g_iTankClient = client;
    g_TankSerial = GetClientSerial(client);
    delete g_hTankDeathTimer;
    Call_StartForward(g_hFwdTankPassControl);
    Call_PushCell(previous);Call_PushCell(client);Call_PushCell(passes);
    Call_Finish();
}

void Tanks_PlayerDeath(Event event)
{
    int client = GetClientOfUserId(event.GetInt("userid"));
    if (!g_bIsTankActive || client != g_iTankClient || GetClientFromSerial(g_TankSerial) != client
        || g_hTankDeathTimer != null) return;
    g_hTankDeathTimer = CreateTimer(0.5, TankDeath_Timer, g_TankSerial, TIMER_FLAG_NO_MAPCHANGE);
}

Action TankDeath_Timer(Handle timer, int serial)
{
    if (timer != g_hTankDeathTimer) return Plugin_Stop;
    g_hTankDeathTimer = null;
    int client = GetClientFromSerial(serial);
    if (!g_bIsTankActive || serial != g_TankSerial || client != g_iTankClient || client <= 0) {
        ResetStatus();return Plugin_Stop;
    }
    ResetStatus();
    Call_StartForward(g_hFwdTankDeath);Call_PushCell(client);Call_Finish();
    return Plugin_Stop;
}

public void OnClientDisconnect(int client)
{
    if (g_bIsTankActive && client == g_iTankClient) ResetStatus();
}

static void ResetStatus()
{
    g_bIsTankActive = false;g_iTankClient = -1;g_iTankPassCount = 0;g_TankSerial = 0;
    delete g_hTankDeathTimer;
}
