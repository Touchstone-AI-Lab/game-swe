#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <l4dinfectedbots>

public Plugin myinfo =
{
    name = "GCB infected-bots public API compile consumer",
    author = "GameCodeBench",
    description = "Compile-only type and declaration check",
    version = "1"
};

public void OnPluginStart()
{
    int maxSpecials = L4DInfectedBots_GetConfigInt("max_specials");
    float spawnMinimum = L4DInfectedBots_GetConfigFloat("spawn_time_min");
    char access[32];
    int stringStatus = L4DInfectedBots_GetConfigString(
        "coop_versus_join_access",
        access,
        sizeof(access)
    );
    PrintToServer(
        "public API compile consumer: %d %.2f %d %s",
        maxSpecials,
        spawnMinimum,
        stringStatus,
        access
    );
}
