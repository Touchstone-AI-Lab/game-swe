#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>
#undef REQUIRE_PLUGIN
#include <spawn_infected_nolimit>
#include <gcb_harness>

native bool L4D_HasPlayerControlledZombies();

public Plugin myinfo =
{
    name = "GCB infected-bots initial timer suite",
    author = "GameCodeBench",
    description = "",
    version = "1"
};

bool g_ObserveReplacement;
float g_DeathTime;
float g_InitialRequestLowerBound = -1.0;
float g_FirstReplacementTime = -1.0;
int g_VictimUserId;
int g_VictimDeaths;
bool g_PlayerControlledMode;
int g_SurvivorAnchor = -1;
int g_PreparedSurvivor;

public void OnPluginStart()
{
    HookEvent("player_death", Event_ObservedDeath, EventHookMode_Post);
    HookEvent("player_spawn", Event_ObservedSpawn, EventHookMode_Post);
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
        data.SetString("gcb_initial");
    }
    // The target receives its own OnConfigsExecuted after this startup-loaded
    // suite. Allow its enable timer to install hooks, then begin a fresh round.
    CreateTimer(1.0, PrepareRound, _, TIMER_FLAG_NO_MAPCHANGE);
}

void Event_ObservedDeath(Event event, const char[] name, bool dontBroadcast)
{
    if (event.GetInt("userid") == g_VictimUserId)
    {
        g_VictimDeaths++;
        if (g_VictimDeaths == 1)
        {
            g_DeathTime = GetGameTime();
            g_FirstReplacementTime = -1.0;
            g_ObserveReplacement = true;
        }
    }
}

// Record the first living replacement, including one that dies before a later
// timer sample. The frame observer also handles team assignment after spawn.
void ObserveReplacement()
{
    if (g_ObserveReplacement && g_FirstReplacementTime < 0.0 && AliveInfected() > 0)
    {
        g_FirstReplacementTime = GetGameTime();
    }
}

void Event_ObservedSpawn(Event event, const char[] name, bool dontBroadcast)
{
    ObserveReplacement();
}

public void OnGameFrame()
{
    ObserveReplacement();
}

Action PrepareRound(Handle timer)
{
    // Establish a live, navigable survivor before round_start so the target's
    // safe-zone timer can enter GameStart and arm its initial-spawn window.
    g_PreparedSurvivor = AliveSurvivor();
    g_InitialRequestLowerBound = GetGameTime();
    Event roundStart = CreateEvent("round_start", true);
    if (roundStart != null)
    {
        roundStart.Fire();
    }
    CreateTimer(3.0, CreateVictim, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
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
    int wake = CreateFakeClient("gcb-initial-survivor");
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

Action CreateVictim(Handle timer)
{
    g_PlayerControlledMode = L4D_HasPlayerControlledZombies();
    GCB_Case(
        "initial_timer_libraries_loaded",
        LibraryExists("l4dinfectedbots")
            && LibraryExists("spawn_infected_nolimit")
            && g_PlayerControlledMode,
        "libraries=%d/%d controlled=%d",
        LibraryExists("l4dinfectedbots"),
        LibraryExists("spawn_infected_nolimit"),
        g_PlayerControlledMode
    );
    int survivor = AliveSurvivor();
    int before = AliveInfected();
    int infected = -1;
    if (survivor != 0 && before == 0)
    {
        float position[3], angles[3];
        GetClientAbsOrigin(survivor, position);
        GetClientAbsAngles(survivor, angles);
        position[0] += 80.0;
        infected = NoLimit_CreateInfected("smoker", position, angles);
    }
    bool created = infected > 0 && IsClientInGame(infected) && IsPlayerAlive(infected);
    GCB_Case(
        "initial_timer_victim_created",
        created && before == 0,
        "survivor=%d prepared=%d infected=%d preexisting=%d anchor=%d",
        survivor,
        g_PreparedSurvivor,
        infected,
        before,
        g_SurvivorAnchor
    );
    if (created)
    {
        g_VictimUserId = GetClientUserId(infected);
        ForcePlayerSuicide(infected);
    }
    CreateTimer(9.2, CheckLate);
    return Plugin_Stop;
}

Action CheckLate(Handle timer)
{
    ObserveReplacement();
    g_ObserveReplacement = false;
    int count = AliveInfected();
    float elapsed = g_FirstReplacementTime - g_InitialRequestLowerBound;
    // round_start is a public lower bound: the safe-zone startup poll may arm
    // the initial wave later. Do not incorrectly restart its clock at death.
    // This conservatively rejects normal-delay and four-second death timers;
    // it does not certify the exact private timer's scheduling timestamp.
    float tolerance = 2.0 * GetTickInterval() + 0.001;
    bool noEarlyReplacement = g_FirstReplacementTime < 0.0 || elapsed >= 8.0 - tolerance;
    GCB_Case(
        "initial_timer_not_overwritten_by_normal_delay",
        g_VictimDeaths > 0 && g_InitialRequestLowerBound >= 0.0 && noEarlyReplacement,
        "first_spawn_after_round=%.4f required=8.0 tolerance=%.4f round_time=%.4f death_time=%.4f victim_deaths=%d",
        elapsed,
        tolerance,
        g_InitialRequestLowerBound,
        g_DeathTime,
        g_VictimDeaths
    );
    GCB_Case(
        "initial_timer_eventually_replenishes",
        count > 0,
        "alive_infected=%d after initial delay",
        count
    );
    // The target clears its initial window at initial_spawn_time + 5 seconds.
    // Wait past that boundary, then prove a fresh death uses the normal timer.
    CreateTimer(3.0, BeginNormalPhase, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

Action BeginNormalPhase(Handle timer)
{
    int victim;
    for (int client = 1; client <= MaxClients; client++)
    {
        if (IsClientInGame(client) && GetClientTeam(client) == 3 && IsPlayerAlive(client))
        {
            victim = client;
            break;
        }
    }
    if (victim == 0)
    {
        GCB_Case(
            "initial_timer_normal_delay_resumes_after_window",
            false,
            "no infected was available after the initial window"
        );
        GCB_Final(5);
        return Plugin_Stop;
    }
    ForcePlayerSuicide(victim);
    CreateTimer(2.2, CheckNormalPhase, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

Action CheckNormalPhase(Handle timer)
{
    int count = AliveInfected();
    GCB_Case(
        "initial_timer_normal_delay_resumes_after_window",
        count > 0,
        "alive_infected=%d after normal one-second delay",
        count
    );
    GCB_Final(5);
    return Plugin_Stop;
}
