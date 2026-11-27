using HarmonyLib;
using StardewModdingAPI;
using StardewValley;

namespace SummonAnywhere
{
    /// <summary>Reference solution, following Pathoschild's Horse Flute Anywhere
    /// (MIT): the game refuses to warp a horse to an indoor location because
    /// Utility.GetHorseWarpRestrictionsForFarmer reports an Indoors restriction, so
    /// clear that one flag and leave every other restriction alone.</summary>
    public sealed class ModEntry : Mod
    {
        public override void Entry(IModHelper helper)
        {
            var harmony = new Harmony(this.ModManifest.UniqueID);
            harmony.Patch(
                original: AccessTools.Method(typeof(Utility), nameof(Utility.GetHorseWarpRestrictionsForFarmer)),
                postfix: new HarmonyMethod(typeof(ModEntry), nameof(AfterGetHorseWarpRestrictions))
            );
        }

        public static void AfterGetHorseWarpRestrictions(ref Utility.HorseWarpRestrictions __result)
        {
            __result &= ~Utility.HorseWarpRestrictions.Indoors;
        }
    }
}
