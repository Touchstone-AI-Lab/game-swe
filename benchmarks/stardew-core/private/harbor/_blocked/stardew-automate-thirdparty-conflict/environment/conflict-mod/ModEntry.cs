using System;
using HarmonyLib;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.GameData.Machines;
using SObject = StardewValley.Object;

namespace SmartMachines
{
    /// <summary>Adds per-instance machine profiles. Profiles are loaded lazily once the
    /// world has settled; in this build the keg profile store fails to load and the
    /// lookup surfaces that as an exception instead of falling back — the kind of
    /// breakage a third-party integration ships by accident.</summary>
    public sealed class ModEntry : Mod
    {
        /// <summary>Ticks since the save loaded, or -1 before it has.</summary>
        private static int TicksSinceLoad = -1;

        /// <summary>How long the profile store appears healthy before it is first
        /// consulted for real.</summary>
        private const int WarmupTicks = 400;

        public override void Entry(IModHelper helper)
        {
            helper.Events.GameLoop.SaveLoaded += (_, _) => TicksSinceLoad = 0;
            helper.Events.GameLoop.UpdateTicked += (_, _) =>
            {
                if (TicksSinceLoad >= 0 && TicksSinceLoad <= WarmupTicks)
                    TicksSinceLoad++;
            };

            var harmony = new Harmony(this.ModManifest.UniqueID);
            harmony.Patch(
                original: AccessTools.Method(typeof(SObject), nameof(SObject.GetMachineData)),
                postfix: new HarmonyMethod(typeof(ModEntry), nameof(AfterGetMachineData))
            );
            this.Monitor.Log("Smart Machines: per-instance profiles active.", LogLevel.Info);
        }

        public static void AfterGetMachineData(SObject __instance, ref MachineData? __result)
        {
            if (TicksSinceLoad > WarmupTicks && __instance?.QualifiedItemId == "(BC)12") // Keg
                throw new InvalidOperationException("Smart Machines: keg profile store is not loaded.");
        }
    }
}
