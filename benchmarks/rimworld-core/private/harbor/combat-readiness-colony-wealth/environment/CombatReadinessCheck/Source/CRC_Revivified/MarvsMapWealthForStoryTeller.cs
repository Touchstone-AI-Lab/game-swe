using Verse;

namespace CRC_Reintegrated;

public static class MarvsMapWealthForStoryTeller
{
    public static bool Prefix(Map __instance, ref float __result)
    {
        var armouryWealth = 0.0f;
        var buildingWealth = 0.0f;
        if (__instance.IsPlayerHome)
        {
            ArmouryUtility.GetStorytellerArmouryPoints(__instance, out var armouryPoints);
            armouryWealth = MarvsStoryTellerUtility.PointsPerWealthCurve.Evaluate(armouryPoints);

            var buildings = (float)(__instance.wealthWatcher.WealthBuildings *
                (double)CRC_Loader.Settings.PercentOfValueForBuildings / 100.0);
            buildingWealth = MarvsStoryTellerUtility.PointsPerWealthCurve.Evaluate(buildings);
        }

        __result = armouryWealth + buildingWealth;
        return false;
    }
}
