using System.Collections;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.Characters;
using SObject = StardewValley.Object;

namespace GcbHarness.Suites
{
    /// <summary>Behavioural test for a generated mod. The agent writes the mod from a
    /// requirement; nothing here names a technique, a patch target, or a class, so any
    /// implementation that produces the behaviour passes.
    ///
    /// Everything is driven through the game's own entry points: the horse flute is used
    /// via <c>performUseAction</c> — the same call the game makes when the player uses
    /// the item — and the result is read from the world (is the player's horse now in
    /// the room?). The suite never calls into the agent's mod.
    ///
    /// The outdoor case is the sentinel: vanilla already allows it, so it must pass on
    /// an empty mod and on a correct one. A submission that summons the horse indoors by
    /// breaking the ordinary rules fails it.</summary>
    public sealed class SummonSuite : IGcbSuite
    {
        public string GroupName => "generation.summon-horse-anywhere";

        private static readonly Vector2 StableTile = new(18, 14);

        /// <summary>The horse flute's qualified item id.</summary>
        private const string HorseFlute = "(O)911";

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("setup: the player owns a horse and carries a horse flute", this.Setup, timeoutTicks: 2400),
            new GcbCase("sentinel: the flute still summons the horse outdoors", this.SummonOutdoors, timeoutTicks: 6000),
            new GcbCase("the flute summons the horse indoors", this.SummonIndoors, timeoutTicks: 6000),
        ];

        private static Horse? FindPlayerHorse(GameLocation location)
        {
            return location.characters.OfType<Horse>().FirstOrDefault(h => h.getOwner() == Game1.player);
        }

        /// <summary>Whether the game will accept an item-use action right now. The
        /// game rejects <c>performUseAction</c> outright while the player cannot move
        /// or the screen is still fading, which happens for a while after a warp.</summary>
        private static bool CanUseItems()
        {
            return Game1.player is not null
                && Game1.player.canMove
                && !Game1.fadeToBlack
                && !Game1.eventUp
                && Game1.player.freezePause <= 0;
        }

        /// <summary>Move the player to a tile where the game's own live summon check
        /// reports no room problem. Probing the real predicate from the player's actual
        /// position is the only drift-proof way to pick a spot: a pre-warp scan of the
        /// same rectangles was measured to disagree with the live check. The Indoors
        /// flag is deliberately ignored here — it is the behaviour under test, not a
        /// placement concern.</summary>
        private static bool PlaceWhereRoomCheckPasses()
        {
            GameLocation loc = Game1.currentLocation!;
            var layer = loc.Map.Layers[0];
            for (int y = 2; y < layer.LayerHeight - 2; y++)
            for (int x = 2; x < layer.LayerWidth - 3; x++)
            {
                Game1.player.Position = new Vector2(x * 64, y * 64);
                var r = Utility.GetHorseWarpRestrictionsForFarmer(Game1.player);
                if ((r & Utility.HorseWarpRestrictions.NoRoom) == 0)
                    return true;
            }
            return false;
        }

        private static SObject Flute()
        {
            return (SObject)GcbWorld.Stack(HorseFlute, 1);
        }

        private IEnumerator Setup()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, new Rectangle((int)StableTile.X - 2, (int)StableTile.Y - 2, 10, 8));

            GcbAssert.IsTrue(
                farm.buildStructure("Stable", StableTile, Game1.player, out Building stable, magicalConstruction: true, skipSafetyChecks: true),
                "a stable was built on the farm");

            // The stable spawns and registers the horse, exactly as it does in play.
            ((Stable)stable).grabHorse();
            yield return GcbWait.Ticks(120);

            Horse? horse = FindPlayerHorse(farm);
            GcbAssert.IsNotNull(horse, "the player owns a horse on the farm");

            // Name the horse as the game's first-ride naming flow does. The game's
            // summon restrictions treat an unnamed horse as "no owned horse".
            horse!.Name = "Copper";
            Game1.player.horseName.Value = "Copper";

            Game1.player.addItemToInventory(Flute());
            yield return GcbWait.Ticks(30);
        }

        private IEnumerator SummonOutdoors()
        {
            Farm farm = Game1.getFarm();
            // The summon requires standing room (a 2-tile-wide clear rectangle at the
            // player's feet); clear the landing area first.
            GcbWorld.ClearArea(farm, new Rectangle(38, 28, 6, 5));
            Game1.warpFarmer("Farm", 40, 30, false);
            int warp = 600;
            yield return GcbWait.Until(() => Game1.currentLocation?.Name == "Farm" || --warp <= 0);
            GcbAssert.AreEqual("Farm", Game1.currentLocation?.Name, "player is outdoors on the farm");
            int ready = 900;
            yield return GcbWait.Until(() => CanUseItems() || --ready <= 0);
            GcbAssert.IsTrue(CanUseItems(), "the game accepts item use outdoors");
            GcbAssert.IsTrue(PlaceWhereRoomCheckPasses(), "a summon-capable spot exists outdoors");

            // Move the horse well away so a summon is actually needed.
            Horse? horse = FindPlayerHorse(farm);
            GcbAssert.IsNotNull(horse, "the horse is on the farm");
            horse!.setTilePosition(5, 5);

            Flute().performUseAction(Game1.currentLocation);

            // The game plays a ~1.5s animation before it warps the horse.
            int deadline = 3600;
            yield return GcbWait.Until(
                () =>
                {
                    Horse? h = FindPlayerHorse(Game1.currentLocation);
                    return (h is not null && System.Math.Abs(h.TilePoint.X - Game1.player.TilePoint.X) <= 3
                                          && System.Math.Abs(h.TilePoint.Y - Game1.player.TilePoint.Y) <= 3)
                           || --deadline <= 0;
                });

            Horse? summoned = FindPlayerHorse(Game1.currentLocation);
            GcbAssert.IsNotNull(summoned, "the horse is in the player's location outdoors");
            GcbAssert.IsTrue(System.Math.Abs(summoned!.TilePoint.X - Game1.player.TilePoint.X) <= 3
                          && System.Math.Abs(summoned.TilePoint.Y - Game1.player.TilePoint.Y) <= 3,
                "the horse arrived next to the player outdoors");
        }

        private IEnumerator SummonIndoors()
        {
            Game1.warpFarmer("FarmHouse", 6, 6, false);
            int warp = 600;
            yield return GcbWait.Until(() => Game1.currentLocation?.Name == "FarmHouse" || --warp <= 0);
            GcbAssert.AreEqual("FarmHouse", Game1.currentLocation?.Name, "player is inside the farmhouse");
            int ready = 900;
            yield return GcbWait.Until(() => CanUseItems() || --ready <= 0);
            GcbAssert.IsTrue(CanUseItems(), "the game accepts item use indoors");
            GcbAssert.IsTrue(PlaceWhereRoomCheckPasses(), "a summon-capable spot exists in the farmhouse");
            GcbAssert.IsTrue(FindPlayerHorse(Game1.currentLocation!) is null,
                "the horse is not already indoors before the flute is used");

            Flute().performUseAction(Game1.currentLocation);

            int deadline = 3600;
            yield return GcbWait.Until(
                () => FindPlayerHorse(Game1.currentLocation!) is not null || --deadline <= 0);

            Horse? summoned = FindPlayerHorse(Game1.currentLocation!);
            GcbAssert.IsNotNull(summoned, "the horse was summoned into the farmhouse");
        }
    }
}
