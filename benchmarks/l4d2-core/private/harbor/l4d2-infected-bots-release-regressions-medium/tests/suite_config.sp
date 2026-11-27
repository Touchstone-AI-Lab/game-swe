#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <sdktools>
#undef REQUIRE_PLUGIN
#include <l4dinfectedbots>
#include <gcb_harness>

public Plugin myinfo =
{
    name = "GCB infected-bots config suite",
    author = "GameCodeBench",
    description = "",
    version = "1"
};

int g_ConfigSurvivorCount;
int g_ReloadSurvivorCount;
int g_ConfigSurvivor;

public void OnPluginStart()
{
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
    // The headless server has no networked administrator. Permit this suite's
    // nonzero survivor bot to cross SourceMod's RegAdminCmd gate; the target
    // still runs its public command handler and all configuration logic.
    AddCommandOverride("sm_timer", Override_Command, 0);
    AddCommandOverride("sm_zlimit", Override_Command, 0);
    int survivor = GrantRootToSurvivor();
    g_ConfigSurvivor = survivor;
    if (survivor != 0)
    {
        for (int client = 1; client <= MaxClients; client++)
        {
            if (IsClientInGame(client) && GetClientTeam(client) == 2 && IsPlayerAlive(client))
            {
                g_ConfigSurvivorCount++;
            }
        }
    }
    ConVar data = FindConVar("l4d_infectedbots_read_data");
    if (data != null)
    {
        data.SetString("gcb_a");
    }
    CreateTimer(1.0, CheckFirstLoad, _, TIMER_FLAG_NO_MAPCHANGE);
}

int GrantRootToSurvivor()
{
    for (int client = 1; client <= MaxClients; client++)
    {
        if (IsClientInGame(client) && GetClientTeam(client) == 2 && IsPlayerAlive(client))
        {
            AdminId admin = CreateAdmin("gcb-config");
            SetAdminFlag(admin, Admin_Root, true);
            SetUserAdmin(client, admin, true);
            return client;
        }
    }
    int wake = CreateFakeClient("gcb-config-survivor");
    if (wake > 0)
    {
        ChangeClientTeam(wake, 2);
        DispatchSpawn(wake);
        AdminId admin = CreateAdmin("gcb-config");
        SetAdminFlag(admin, Admin_Root, true);
        SetUserAdmin(wake, admin, true);
        return wake;
    }
    return 0;
}

bool ConfigStringEquals(const char[] expected)
{
    char value[32];
    return L4DInfectedBots_GetConfigString("coop_versus_join_access", value, sizeof(value)) == 1
        && StrEqual(value, expected);
}

Action CheckFirstLoad(Handle timer)
{
    GCB_Case(
        "config_library_and_single_survivor_guard",
        LibraryExists("l4dinfectedbots") && g_ConfigSurvivorCount == 1,
        "library=%d alive_survivors=%d",
        LibraryExists("l4dinfectedbots"),
        g_ConfigSurvivorCount
    );
    int maxSpecials = L4DInfectedBots_GetConfigInt("max_specials");
    float spawnMin = L4DInfectedBots_GetConfigFloat("spawn_time_min");
    GCB_Case(
        "config_settings_count_profile_overlays_all_types",
        maxSpecials == 17 && FloatAbs(spawnMin - 3.25) < 0.01 && ConfigStringEquals("b"),
        "max=%d min=%.2f string_b=%d",
        maxSpecials,
        spawnMin,
        ConfigStringEquals("b")
    );
    float spawnMax = L4DInfectedBots_GetConfigFloat("spawn_time_max");
    GCB_Case(
        "config_settings_count_omitted_keys_inherit_default",
        FloatAbs(spawnMax - 12.0) < 0.01,
        "spawn_max=%.2f",
        spawnMax
    );

    int client = (
        g_ConfigSurvivor > 0
        && IsClientInGame(g_ConfigSurvivor)
        && GetClientTeam(g_ConfigSurvivor) == 2
        && IsPlayerAlive(g_ConfigSurvivor)
    ) ? g_ConfigSurvivor : 0;
    if (client == 0)
    {
        GCB_Case("config_admin_overrides_are_temporary", false, "no in-game survivor was available");
        GCB_Case("config_reload_replaces_overrides_and_applies_map_profiles", false, "reload was not attempted");
        GCB_Final(5);
        return Plugin_Stop;
    }
    FakeClientCommand(client, "sm_zlimit 5");
    FakeClientCommand(client, "sm_timer 77 88");
    CreateTimer(0.4, CheckOverride);
    return Plugin_Stop;
}

Action CheckOverride(Handle timer)
{
    float minimum = L4DInfectedBots_GetConfigFloat("spawn_time_min");
    float maximum = L4DInfectedBots_GetConfigFloat("spawn_time_max");
    int maxSpecials = L4DInfectedBots_GetConfigInt("max_specials");
    GCB_Case(
        "config_admin_overrides_are_temporary",
        maxSpecials == 5 && FloatAbs(minimum - 77.0) < 0.01 && FloatAbs(maximum - 88.0) < 0.01,
        "max=%d min=%.2f max_time=%.2f",
        maxSpecials,
        minimum,
        maximum
    );
    if (
        g_ConfigSurvivor > 0
        && IsClientInGame(g_ConfigSurvivor)
        && GetClientTeam(g_ConfigSurvivor) == 2
        && !IsPlayerAlive(g_ConfigSurvivor)
    )
    {
        DispatchSpawn(g_ConfigSurvivor);
    }
    for (int client = 1; client <= MaxClients; client++)
    {
        if (IsClientInGame(client) && GetClientTeam(client) == 2 && IsPlayerAlive(client))
        {
            g_ReloadSurvivorCount++;
        }
    }
    FindConVar("l4d_infectedbots_read_data").SetString("gcb_b");
    // LoadData resets the profile array immediately; the plugin's public
    // survivor-count timer then selects the matching active profile.
    CreateTimer(2.2, CheckReload, _, TIMER_FLAG_NO_MAPCHANGE);
    return Plugin_Stop;
}

Action CheckReload(Handle timer)
{
    int maxSpecials = L4DInfectedBots_GetConfigInt("max_specials");
    float minimum = L4DInfectedBots_GetConfigFloat("spawn_time_min");
    float maximum = L4DInfectedBots_GetConfigFloat("spawn_time_max");
    bool passed = g_ReloadSurvivorCount == 1
        && maxSpecials == 15
        && FloatAbs(minimum - 4.5) < 0.01
        && FloatAbs(maximum - 15.0) < 0.01
        && ConfigStringEquals("c");
    GCB_Case(
        "config_reload_replaces_overrides_and_applies_map_profiles",
        passed,
        "survivors=%d max=%d min=%.2f max_time=%.2f string_c=%d",
        g_ReloadSurvivorCount,
        maxSpecials,
        minimum,
        maximum,
        ConfigStringEquals("c")
    );
    GCB_Final(5);
    return Plugin_Stop;
}
