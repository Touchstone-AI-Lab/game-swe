using System.Collections;
using System.Collections.Generic;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewValley;
using StardewValley.Objects;
using SObject = StardewValley.Object;

namespace GcbHarness.Suites
{
    /// <summary>Extending a running setup must take effect without reloading the save.
    /// The two discriminating placements touch the existing setup only through a chest:
    /// a furnace on the far side of the first setup's chest, and an ore chest beside the
    /// second setup's chest. The sentinels connect through a furnace or through a chest
    /// placed before its machine, which work on the broken tree too.
    ///
    /// Layout (farm tiles):
    ///   row 20: [furnace F2][chest A][furnace F1][furnace F1b]   x = 9..12
    ///   row 23: [chest D][chest C][furnace F3]                   x = 8..10
    /// The rows are three tiles apart so neither setup is adjacent to the other.</summary>
    public sealed class SetupExtensionSuite : IGcbSuite
    {
        public string GroupName => "automate.setup-extension";

        private const string CopperOre = "(O)378";
        private const string Coal = "(O)382";

        private static readonly Rectangle FarmArea = new(8, 20, 6, 4);

        private SObject? _furnaceF3;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("sentinel: a chest feeds a furnace placed next to it", this.SentinelFirstSetup, timeoutTicks: 2400),
            new GcbCase("sentinel: a furnace placed next to a running furnace starts", this.SentinelFurnaceBesideFurnace, timeoutTicks: 2400),
            new GcbCase("a furnace placed on the far side of the chest starts without a reload", this.FurnaceBesideChest, timeoutTicks: 2400),
            new GcbCase("setup: a second furnace idles next to an empty chest", this.SecondSetupIdles, timeoutTicks: 1200),
            new GcbCase("ore in a new chest placed beside the empty chest reaches the furnace", this.ChestBesideChest, timeoutTicks: 2400),
        ];

        private static GcbWait UntilSmelting(SObject furnace)
        {
            int deadline = 1800;
            return GcbWait.Until(() => furnace.heldObject.Value is not null || --deadline <= 0);
        }

        private IEnumerator SentinelFirstSetup()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, FarmArea);
            var chestA = (Chest)GcbWorld.Place(farm, new Vector2(10, 20), "(BC)130");
            chestA.addItem(GcbWorld.Stack(CopperOre, 60));
            chestA.addItem(GcbWorld.Stack(Coal, 20));
            SObject furnaceF1 = GcbWorld.Place(farm, new Vector2(11, 20), "(BC)13");

            yield return UntilSmelting(furnaceF1);
            GcbAssert.IsNotNull(furnaceF1.heldObject.Value, "the first furnace is smelting");
        }

        private IEnumerator SentinelFurnaceBesideFurnace()
        {
            SObject furnaceF1b = GcbWorld.Place(Game1.getFarm(), new Vector2(12, 20), "(BC)13");

            yield return UntilSmelting(furnaceF1b);
            GcbAssert.IsNotNull(furnaceF1b.heldObject.Value, "the furnace beside the first furnace is smelting");
        }

        private IEnumerator FurnaceBesideChest()
        {
            SObject furnaceF2 = GcbWorld.Place(Game1.getFarm(), new Vector2(9, 20), "(BC)13");

            yield return UntilSmelting(furnaceF2);
            GcbAssert.IsNotNull(furnaceF2.heldObject.Value, "the furnace on the far side of the chest is smelting");
        }

        private IEnumerator SecondSetupIdles()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.Place(farm, new Vector2(9, 23), "(BC)130");
            this._furnaceF3 = GcbWorld.Place(farm, new Vector2(10, 23), "(BC)13");

            yield return GcbWait.Ticks(300);
            GcbAssert.IsTrue(this._furnaceF3.heldObject.Value is null, "the furnace next to the empty chest has nothing to smelt");
        }

        private IEnumerator ChestBesideChest()
        {
            var chestD = (Chest)GcbWorld.Place(Game1.getFarm(), new Vector2(8, 23), "(BC)130");
            chestD.addItem(GcbWorld.Stack(CopperOre, 20));
            chestD.addItem(GcbWorld.Stack(Coal, 5));

            yield return UntilSmelting(this._furnaceF3!);
            GcbAssert.IsNotNull(this._furnaceF3!.heldObject.Value, "the second furnace smelts ore from the new chest");
        }
    }
}
