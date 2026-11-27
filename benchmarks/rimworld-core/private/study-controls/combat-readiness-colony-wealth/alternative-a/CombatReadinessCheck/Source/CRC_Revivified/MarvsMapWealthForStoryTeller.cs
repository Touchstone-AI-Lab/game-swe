using Verse;

namespace CRC_Reintegrated;

public static class MarvsMapWealthForStoryTeller
{
    public static bool Prefix(Map __instance, ref float __result)
    {
        // Only a player home in normal wealth mode is re-counted; everything else keeps the
        // game's own getter. The getter reports wealth, so no points curve is applied here.
        bool ownGetter = !__instance.IsPlayerHome || Find.Storyteller.difficulty.fixedWealthMode;
        if (ownGetter)
            return true;

        ArmouryUtility.GetStorytellerArmouryPoints(__instance, out float armouryWealth);
        float buildingShare = (float)(__instance.wealthWatcher.WealthBuildings *
            (double)CRC_Loader.Settings.PercentOfValueForBuildings / 100.0);
        __result = armouryWealth + buildingShare;
        return false;
    }
}
