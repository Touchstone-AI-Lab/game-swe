using System;
using Microsoft.Xna.Framework;
using StardewValley;
using SObject = StardewValley.Object;

namespace GcbHarness.Framework
{
    /// <summary>World-state helpers for suites. Pre-state is built through the game's
    /// own public surface wherever it has one (item registry, placement actions, clock
    /// updates); the only direct mutation is clearing debris from the fixture farm,
    /// which stands in for the player clearing it by hand.</summary>
    public static class GcbWorld
    {
        /// <summary>Remove objects, terrain features, and resource clumps from a tile
        /// rectangle so placements are deterministic regardless of world-gen debris.</summary>
        public static void ClearArea(GameLocation location, Rectangle tileArea)
        {
            for (int x = tileArea.Left; x < tileArea.Right; x++)
            {
                for (int y = tileArea.Top; y < tileArea.Bottom; y++)
                {
                    var tile = new Vector2(x, y);
                    location.objects.Remove(tile);
                    location.terrainFeatures.Remove(tile);
                }
            }

            var pixelArea = new Rectangle(tileArea.X * 64, tileArea.Y * 64, tileArea.Width * 64, tileArea.Height * 64);
            location.resourceClumps.RemoveWhere(clump => clump.getBoundingBox().Intersects(pixelArea));
            location.furniture.RemoveWhere(f => f.boundingBox.Value.Intersects(pixelArea));
        }

        /// <summary>Place a big craftable or object into the world through the game's own
        /// placement action (the same code path as a player placing the item), and return
        /// the placed instance.</summary>
        public static SObject Place(GameLocation location, Vector2 tile, string qualifiedItemId)
        {
            if (ItemRegistry.Create(qualifiedItemId) is not SObject item)
                throw new GcbAssertException($"item {qualifiedItemId} did not resolve to an Object");

            bool placed = item.placementAction(location, (int)tile.X * 64, (int)tile.Y * 64, Game1.player);
            if (!placed || !location.objects.TryGetValue(tile, out SObject? placedObj))
                throw new GcbAssertException($"placement of {qualifiedItemId} at {tile} in {location.Name} failed");
            return placedObj;
        }

        /// <summary>Create an item stack.</summary>
        public static Item Stack(string qualifiedItemId, int count)
        {
            return ItemRegistry.Create(qualifiedItemId, count);
        }

        /// <summary>Advance the in-game clock through the game's ten-minute update, which
        /// is what drives machine processing time.</summary>
        public static void AdvanceClock(int tenMinuteSteps)
        {
            for (int i = 0; i < tenMinuteSteps; i++)
                Game1.performTenMinuteClockUpdate();
        }

        /// <summary>Find a horizontally adjacent pair of tiles the game itself considers
        /// clear and placeable, so suites don't hard-code coordinates against map
        /// layouts.</summary>
        public static (Vector2 left, Vector2 right) FindAdjacentPlaceablePair(GameLocation location)
        {
            var layer = location.Map.Layers[0];
            for (int y = 1; y < layer.LayerHeight - 1; y++)
            {
                for (int x = 1; x < layer.LayerWidth - 2; x++)
                {
                    var a = new Vector2(x, y);
                    var b = new Vector2(x + 1, y);
                    if (location.CanItemBePlacedHere(a) && location.CanItemBePlacedHere(b))
                        return (a, b);
                }
            }
            throw new GcbAssertException($"no adjacent placeable tile pair found in {location.Name}");
        }
    }
}
