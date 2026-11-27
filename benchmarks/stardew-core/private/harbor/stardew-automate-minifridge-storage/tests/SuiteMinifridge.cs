using System.Collections;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewValley;
using StardewValley.Objects;
using SObject = StardewValley.Object;

namespace GcbHarness.Suites
{
    /// <summary>Verifies that mini-fridges participate in automation as storage
    /// containers. Sentinel: a standard chest must feed an adjacent furnace on both the
    /// base and fixed trees; the mini-fridge cases only pass once the regression is
    /// fixed. All setup goes through the game's own item registry and placement
    /// actions; assertions read live machine/chest state.</summary>
    public sealed class MinifridgeSuite : IGcbSuite
    {
        public string GroupName => "automate.minifridge-storage";

        // The chest sentinel lives on the farm; the mini-fridge cases live inside the
        // farmhouse (mini-fridges are indoor-only). Separate locations also guarantee
        // separate Automate machine groups.
        private static readonly Rectangle ChestArea = new(8, 20, 4, 3);

        private Chest? _fridge;
        private SObject? _fridgeFurnace;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("sentinel: standard chest feeds an adjacent furnace", this.SentinelChestFeedsFurnace, timeoutTicks: 1200),
            new GcbCase("mini-fridge feeds an adjacent furnace", this.FridgeFeedsFurnace, timeoutTicks: 1200),
            new GcbCase("furnace output is collected back into the mini-fridge", this.FridgeCollectsOutput, timeoutTicks: 1800),
        ];

        private IEnumerator SentinelChestFeedsFurnace()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, ChestArea);

            var chest = (Chest)GcbWorld.Place(farm, new Vector2(ChestArea.X, ChestArea.Y), "(BC)130");
            SObject furnace = GcbWorld.Place(farm, new Vector2(ChestArea.X + 1, ChestArea.Y), "(BC)13");
            chest.addItem(GcbWorld.Stack("(O)378", 5)); // copper ore
            chest.addItem(GcbWorld.Stack("(O)382", 1)); // coal

            // Let Automate rescan (object list changed) and run automation cycles
            // (default interval: 60 ticks).
            yield return GcbWait.Until(() => furnace.heldObject.Value is not null);

            GcbAssert.IsNotNull(furnace.heldObject.Value, "furnace started smelting from a standard chest");
            GcbAssert.IsTrue(!chest.Items.Any(i => i?.QualifiedItemId == "(O)378"),
                "copper ore was consumed from the standard chest");
        }

        private IEnumerator FridgeFeedsFurnace()
        {
            // Mini-fridges are indoor-only and need the level-1 (kitchen) farmhouse,
            // which the fixture save provides. Let the game pick a legal spot rather
            // than hard-coding tiles against the interior layout.
            GameLocation house = Game1.getLocationFromName("FarmHouse");
            GcbAssert.IsNotNull(house, "farmhouse location exists");
            (Vector2 left, Vector2 right) = GcbWorld.FindAdjacentPlaceablePair(house);

            this._fridge = (Chest)GcbWorld.Place(house, left, "(BC)216");
            this._fridgeFurnace = GcbWorld.Place(house, right, "(BC)13");
            this._fridge.addItem(GcbWorld.Stack("(O)378", 5));
            this._fridge.addItem(GcbWorld.Stack("(O)382", 1));

            // Same wait budget as the sentinel: if the mini-fridge is not recognized as
            // a container, the furnace never starts and this times out into a failure.
            int deadline = 900;
            yield return GcbWait.Until(() => this._fridgeFurnace.heldObject.Value is not null || --deadline <= 0);

            GcbAssert.IsNotNull(this._fridgeFurnace.heldObject.Value, "furnace started smelting from a mini-fridge");
            GcbAssert.IsTrue(!this._fridge.Items.Any(i => i?.QualifiedItemId == "(O)378"),
                "copper ore was consumed from the mini-fridge");
        }

        private IEnumerator FridgeCollectsOutput()
        {
            GcbAssert.IsNotNull(this._fridgeFurnace?.heldObject.Value, "previous case left the furnace smelting");

            // A furnace takes 30 in-game minutes; advance the clock past that and let
            // Automate's collection cycle run.
            GcbWorld.AdvanceClock(4);
            int deadline = 900;
            yield return GcbWait.Until(
                () => (this._fridge?.Items.Any(i => i?.QualifiedItemId == "(O)334") ?? false) || --deadline <= 0);

            GcbAssert.IsTrue(this._fridge!.Items.Any(i => i?.QualifiedItemId == "(O)334"),
                "copper bar was collected into the mini-fridge");
        }
    }
}
