#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#undef REQUIRE_PLUGIN
#include <l4dinfectedbots>
#include <gcb_harness>

public Plugin myinfo =
{
    name = "GCB infected-bots capacity suite",
    author = "GameCodeBench",
    description = "",
    version = "1"
};

int g_AdminClient;
int g_Expected;
int g_ZLimitCommands;

public void OnPluginStart()
{
    AddCommandListener(Command_ZLimitObserved, "sm_zlimit");
    ConVar hibernate = FindConVar("sv_hibernate_when_empty");
    if (hibernate != null)
    {
        hibernate.SetBool(false);
    }
}

Action Command_ZLimitObserved(int client, const char[] command, int argc)
{
    g_ZLimitCommands++;
    return Plugin_Continue;
}

public void OnAllPluginsLoaded()
{
    LoadRuntime(null);
}

public void OnMapStart()
{
}

public void OnAutoConfigsBuffered()
{
}

public void OnConfigsExecuted()
{
    ConfigureRuntime(null);
}

Action LoadRuntime(Handle timer)
{
    ServerCommand("sm plugins load disabled/02_spawn_infected_nolimit.smx");
    ServerCommand("sm plugins load disabled/03_l4dinfectedbots.smx");
    ServerExecute();
    return Plugin_Stop;
}

Action ConfigureRuntime(Handle timer)
{
    // Headless dedicated servers have no networked administrator. SourceMod
    // intentionally excludes bot clients from normal admin authentication, so
    // grant this verifier-owned nonzero client command access through the
    // documented command-override API. The target still performs its normal
    // client, allow-cvar, argument, and capacity logic.
    AddCommandOverride("sm_zlimit", Override_Command, 0);
    ConVar data = FindConVar("l4d_infectedbots_read_data");
    if (data != null)
    {
        data.SetString("gcb_capacity");
    }
    ConVar allow = FindConVar("l4d_infectedbots_allow");
    if (allow != null)
    {
        allow.SetBool(false);
        allow.SetBool(true);
    }
    CreateTimer(1.0, BeginTest, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

int SurvivorCount()
{
    int count;
    for (int client = 1; client <= MaxClients; client++)
    {
        if (IsClientInGame(client) && GetClientTeam(client) == 2)
        {
            count++;
        }
    }
    return count;
}

int SurvivorAdmin()
{
    for (int client = 1; client <= MaxClients; client++)
    {
        if (IsClientInGame(client) && GetClientTeam(client) == 2)
        {
            AdminId admin = CreateAdmin("gcb-capacity");
            SetAdminFlag(admin, Admin_Root, true);
            SetUserAdmin(client, admin, true);
            return client;
        }
    }
    return 0;
}

Action BeginTest(Handle timer)
{
    GCB_Case("capacity_library_loaded", LibraryExists("l4dinfectedbots"), "public library is available");
    int survivors = SurvivorCount();
    if (survivors == 0)
    {
        int wake = CreateFakeClient("gcb-capacity-survivor");
        if (wake > 0)
        {
            ChangeClientTeam(wake, 2);
            survivors = SurvivorCount();
        }
    }
    int client = SurvivorAdmin();
    if (client == 0 || survivors == 0)
    {
        GCB_Case("capacity_exact_runtime_slots", false, "no in-game survivor was available");
        GCB_Case("capacity_unclamped_request_is_preserved", false, "admin command could not run");
        GCB_Final(3);
        return Plugin_Stop;
    }

    FakeClientCommand(client, "sm_zlimit 2");
    g_AdminClient = client;
    g_Expected = MaxClients - survivors;
    CreateTimer(0.3, CheckBelowCapacity, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

Action CheckBelowCapacity(Handle timer)
{
    int belowCapacity = L4DInfectedBots_GetConfigInt("max_specials");
    GCB_Case(
        "capacity_unclamped_request_is_preserved",
        belowCapacity == 2,
        "expected=2 observed=%d flags=%d fake=%d ingame=%d allow=%d zlimit_seen=%d",
        belowCapacity,
        GetUserFlagBits(g_AdminClient),
        IsFakeClient(g_AdminClient),
        IsClientInGame(g_AdminClient),
        FindConVar("l4d_infectedbots_allow").BoolValue,
        g_ZLimitCommands
    );
    FakeClientCommand(g_AdminClient, "sm_zlimit 30");
    CreateTimer(0.3, CheckClamped, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

Action CheckClamped(Handle timer)
{
    int observed = L4DInfectedBots_GetConfigInt("max_specials");
    GCB_Case(
        "capacity_exact_runtime_slots",
        observed == g_Expected,
        "expected=%d observed=%d",
        g_Expected,
        observed
    );
    GCB_Final(3);
    return Plugin_Stop;
}
