using System;
using HarmonyLib;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.Characters;
using SObject = StardewValley.Object;

namespace SummonAnywhere
{
    /// <summary>Study control (E0 "alternative"): an independent implementation of the public
    /// requirement. It never changes what the game's restriction check reports. Instead it
    /// steps in front of the horse flute's use action, and only when the game would refuse
    /// for the single reason "the player is indoors" does it perform the summon itself.
    /// Outdoors, and whenever any other rule blocks the summon, the game's own code runs (or
    /// its own refusal message is shown), so every other condition keeps applying.</summary>
    public sealed class ModEntry : Mod
    {
        private const string HorseFluteId = "(O)911";
        private const int FluteDelayMilliseconds = 1500;

        private static IMonitor? Log;

        public override void Entry(IModHelper helper)
        {
            Log = this.Monitor;

            var harmony = new Harmony(this.ModManifest.UniqueID);
            harmony.Patch(
                original: AccessTools.Method(typeof(SObject), nameof(SObject.performUseAction), new[] { typeof(GameLocation) }),
                prefix: new HarmonyMethod(typeof(ModEntry), nameof(BeforeItemUsed))
            );
        }

        /// <summary>Runs before the game handles an item's use action.</summary>
        /// <returns>True to let the game handle the use, false when this mod handled it.</returns>
        public static bool BeforeItemUsed(SObject __instance, ref bool __result)
        {
            try
            {
                if (__instance.QualifiedItemId != HorseFluteId || !Context.IsWorldReady || !Game1.IsMasterGame)
                    return true;

                Farmer who = Game1.player;
                if (!CanUseItemsNow(who))
                    return true; // the game rejects the use itself

                Utility.HorseWarpRestrictions restrictions = Utility.GetHorseWarpRestrictionsForFarmer(who);
                if ((restrictions & Utility.HorseWarpRestrictions.Indoors) == 0)
                    return true; // outdoors: untouched base-game behaviour (including its refusals)

                // indoors: every rule other than "indoors" still decides whether the horse may come
                Utility.HorseWarpRestrictions others = restrictions & ~Utility.HorseWarpRestrictions.Indoors;
                if (others != Utility.HorseWarpRestrictions.None)
                {
                    string? refusal = Utility.GetHorseWarpErrorMessage(others);
                    if (refusal is not null)
                        Game1.showRedMessage(refusal);
                    __result = false;
                    return false;
                }

                who.currentLocation.playSound("horse_flute");
                who.faceDirection(Game1.down);
                DelayedAction.functionAfterDelay(() => BringHorseTo(who), FluteDelayMilliseconds);
                __result = false; // the flute is not consumed
                return false;
            }
            catch (Exception ex)
            {
                Log?.Log($"Indoor horse summon failed, falling back to the base game:\n{ex}", LogLevel.Error);
                return true;
            }
        }

        private static bool CanUseItemsNow(Farmer who)
        {
            return !Game1.eventUp
                && !Game1.isFestival()
                && !Game1.fadeToBlack
                && !who.swimming.Value
                && !who.bathingClothes.Value
                && !who.onBridge.Value;
        }

        /// <summary>Move the player's horse next to the player, after re-checking the rules the way the game does when the flute finishes playing.</summary>
        private static void BringHorseTo(Farmer who)
        {
            if (!Context.IsWorldReady || who.currentLocation is null)
                return;

            Utility.HorseWarpRestrictions others = Utility.GetHorseWarpRestrictionsForFarmer(who) & ~Utility.HorseWarpRestrictions.Indoors;
            if (others != Utility.HorseWarpRestrictions.None)
                return;

            Horse? horse = FindOwnedHorse(who);
            if (horse is null || horse.rider is not null)
                return;

            horse.mutex.RequestLock(() =>
            {
                horse.mutex.ReleaseLock();

                GameLocation destination = who.currentLocation;
                Vector2 tile = who.Tile;
                horse.currentLocation?.playSound("wand", horse.Tile);
                Game1.warpCharacter(horse, destination, tile);
                destination.playSound("wand", tile);
            });
        }

        private static Horse? FindOwnedHorse(Farmer who)
        {
            Horse? found = null;
            Utility.ForEachBuilding(building =>
            {
                if (building is Stable stable && stable.getStableHorse() is Horse horse && horse.getOwner() == who)
                {
                    found = horse;
                    return false;
                }
                return true;
            });
            return found;
        }
    }
}
