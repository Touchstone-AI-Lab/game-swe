#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>
#undef REQUIRE_PLUGIN
#include <spawn_infected_nolimit>
#include <gcb_harness>

public Plugin myinfo =
{
    name = "GCB infected-bots finale suite",
    author = "GameCodeBench",
    description = "",
    version = "1"
};

int g_PreparedSurvivor;
int g_SurvivorAnchor = -1;
int g_VictimUserId;
int g_VictimDeaths;
bool g_LifecycleReenabled;

public void OnPluginStart()
{
    HookEvent("player_death", Event_ObservedDeath, EventHookMode_Post);
    ConVar hibernate = FindConVar("sv_hibernate_when_empty");
    if (hibernate != null)
    {
        hibernate.SetBool(false);
    }
}

public void OnAllPluginsLoaded()
{
    ServerCommand("sm plugins load disabled/02_spawn_infected_nolimit.smx");
    ServerCommand("sm plugins load disabled/03_l4dinfectedbots.smx");
    ServerExecute();
}

public void OnConfigsExecuted()
{
    ConVar data = FindConVar("l4d_infectedbots_read_data");
    if (data != null)
    {
        data.SetString("gcb_finale");
    }
    CreateTimer(1.0, PrepareRound, _, TIMER_FLAG_NO_MAPCHANGE);
}

void Event_ObservedDeath(Event event, const char[] name, bool dontBroadcast)
{
    if (event.GetInt("userid") == g_VictimUserId)
    {
        g_VictimDeaths++;
    }
}

int AliveInfected()
{
    int count;
    for (int client = 1; client <= MaxClients; client++)
    {
        if (IsClientInGame(client) && GetClientTeam(client) == 3 && IsPlayerAlive(client))
        {
            count++;
        }
    }
    return count;
}

int AliveSurvivor()
{
    for (int client = 1; client <= MaxClients; client++)
    {
        if (IsClientInGame(client) && GetClientTeam(client) == 2 && IsPlayerAlive(client))
        {
            return client;
        }
    }
    int wake = CreateFakeClient("gcb-finale-survivor");
    if (wake > 0)
    {
        ChangeClientTeam(wake, 2);
        DispatchSpawn(wake);
        int anchor = FindEntityByClassname(-1, "info_survivor_position");
        if (anchor == -1)
        {
            anchor = FindEntityByClassname(-1, "info_player_start");
        }
        if (anchor != -1)
        {
            float position[3];
            GetEntPropVector(anchor, Prop_Data, "m_vecAbsOrigin", position);
            TeleportEntity(wake, position, NULL_VECTOR, NULL_VECTOR);
            g_SurvivorAnchor = anchor;
        }
        if (IsClientInGame(wake) && GetClientTeam(wake) == 2 && IsPlayerAlive(wake))
        {
            return wake;
        }
    }
    return 0;
}

Action PrepareRound(Handle timer)
{
    g_PreparedSurvivor = AliveSurvivor();
    ConVar allow = FindConVar("l4d_infectedbots_allow");
    if (allow != null)
    {
        allow.SetBool(false);
        allow.SetBool(true);
        g_LifecycleReenabled = allow.BoolValue;
    }
    CreateTimer(1.0, StartRoundAfterReenable, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

Action StartRoundAfterReenable(Handle timer)
{
    Event roundStart = CreateEvent("round_start", true);
    if (roundStart != null)
    {
        roundStart.Fire();
    }
    CreateTimer(3.0, EmitFinaleWin, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

Action EmitFinaleWin(Handle timer)
{
    GCB_Case(
        "finale_library_loaded",
        LibraryExists("l4dinfectedbots") && LibraryExists("spawn_infected_nolimit"),
        "libraries=%d/%d",
        LibraryExists("l4dinfectedbots"),
        LibraryExists("spawn_infected_nolimit")
    );
    int before = AliveInfected();
    int infected = -1;
    if (g_PreparedSurvivor != 0 && before == 0)
    {
        float position[3], angles[3];
        GetClientAbsOrigin(g_PreparedSurvivor, position);
        GetClientAbsAngles(g_PreparedSurvivor, angles);
        position[0] += 80.0;
        infected = NoLimit_CreateInfected("smoker", position, angles);
    }
    bool victimCreated = infected > 0 && IsClientInGame(infected) && IsPlayerAlive(infected);
    if (victimCreated)
    {
        g_VictimUserId = GetClientUserId(infected);
        ForcePlayerSuicide(infected);
    }
    Event event = CreateEvent("finale_win", true);
    bool created = event != null;
    if (created)
    {
        event.Fire();
    }
    GCB_Case(
        "finale_win_event_available",
        created && victimCreated && before == 0 && g_VictimDeaths == 1 && g_LifecycleReenabled,
        "event=%d lifecycle=%d survivor=%d victim=%d death=%d preexisting=%d anchor=%d",
        created,
        g_LifecycleReenabled,
        g_PreparedSurvivor,
        infected,
        g_VictimDeaths,
        before,
        g_SurvivorAnchor
    );
    CreateTimer(8.5, CheckNoSpawn);
    return Plugin_Stop;
}

Action CheckNoSpawn(Handle timer)
{
    int count = AliveInfected();
    GCB_Case(
        "finale_win_cancels_pending_replenishment",
        count == 0,
        "alive_infected=%d after finale_win",
        count
    );
    GCB_Final(3);
    return Plugin_Stop;
}
