using System.Collections;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.Objects;
using SObject = StardewValley.Object;

namespace GcbHarness.Suites
{
    /// <summary>The subset of Automate's public mod API this suite consumes.</summary>
    public interface IAutomateApi
    {
        IDictionary<Vector2, int> GetMachineStates(GameLocation location, Rectangle tileArea);
    }

    /// <summary>Composite regression suite: four independent defect groups in one tree,
    /// asserted through live game state. Case order is load-bearing — the initial-scan
    /// probe must run before anything is placed, because creating any automated group
    /// rebuilds the machine caches on both trees and would mask that defect.</summary>
    public sealed class CompositeSuite : IGcbSuite
    {
        public string GroupName => "automate.release-regressions";

        private static readonly Rectangle SentinelArea = new(8, 20, 4, 3);
        private static readonly Rectangle BrokenArea = new(30, 20, 4, 3);
        private static readonly Vector2 HutTile = new(16, 28);

        private IModHelper? _helper;
        private IAutomateApi? _api;
        private Chest? _sentinelChest;
        private SObject? _sentinelFurnace;
        private Chest? _fridge;
        private SObject? _fridgeFurnace;
        private Chest? _brokenChest;
        private SObject? _brokenFurnace;
        private Chest? _hutChest;
        private Chest? _hutSideChest;

        public void OnEntry(IModHelper helper)
        {
            this._helper = helper;
        }

        private static Rectangle WholeFarm(Farm farm)
        {
            var layer = farm.Map.Layers[0];
            return new Rectangle(0, 0, layer.LayerWidth, layer.LayerHeight);
        }

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("machine overlay data is available right after a save loads", this.ApiInitialScan, timeoutTicks: 1200),
            new GcbCase("sentinel: a chest feeds an adjacent furnace", this.SentinelSmelt, timeoutTicks: 1800),
            new GcbCase("sentinel: the finished bar is collected into the chest", this.SentinelCollect, timeoutTicks: 1800),
            new GcbCase("the API reports the automated machine group", this.ApiReportsGroup, timeoutTicks: 900),
            new GcbCase("mini-fridge feeds an adjacent furnace", this.FridgeFeedsFurnace, timeoutTicks: 1800),
            new GcbCase("furnace output is collected back into the mini-fridge", this.FridgeCollectsOutput, timeoutTicks: 1800),
            new GcbCase("a zero-size output is discarded and the machine empties", this.ZeroStackDiscarded, timeoutTicks: 2400),
            new GcbCase("the machine resumes processing input after the discard", this.MachineResumes, timeoutTicks: 1200),
            new GcbCase("setup: build a Junimo hut with a connected chest", this.HutSetup, timeoutTicks: 1200),
            new GcbCase("sentinel: fertilizer and gems are moved out of the hut per config", this.HutSentinelMoved, timeoutTicks: 3000),
            new GcbCase("seeds stay in the hut when the seed behavior is Ignore", this.HutSeedsStay, timeoutTicks: 600),
        ];

        // --- G3: API must publish machine data from the initial save-load scan -------
        private IEnumerator ApiInitialScan()
        {
            this._api = this._helper!.ModRegistry.GetApi<IAutomateApi>("Pathoschild.Automate");
            GcbAssert.IsNotNull(this._api, "Automate exposes its mod API");

            yield return GcbWait.Ticks(360); // several automation intervals; nothing placed yet

            Farm farm = Game1.getFarm();
            GcbAssert.IsTrue(this._api!.GetMachineStates(farm, WholeFarm(farm)).Any(),
                "API reports the farm's machines (e.g. the shipping bin) after the initial scan");
        }

        // --- sentinels: plain chest automation works end to end ----------------------
        private IEnumerator SentinelSmelt()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, SentinelArea);
            this._sentinelChest = (Chest)GcbWorld.Place(farm, new Vector2(SentinelArea.X, SentinelArea.Y), "(BC)130");
            this._sentinelFurnace = GcbWorld.Place(farm, new Vector2(SentinelArea.X + 1, SentinelArea.Y), "(BC)13");
            this._sentinelChest.addItem(GcbWorld.Stack("(O)378", 5));
            this._sentinelChest.addItem(GcbWorld.Stack("(O)382", 1));

            int deadline = 1500;
            yield return GcbWait.Until(() => this._sentinelFurnace.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._sentinelFurnace.heldObject.Value, "furnace started smelting from a standard chest");
        }

        private IEnumerator SentinelCollect()
        {
            GcbWorld.AdvanceClock(4);
            int deadline = 1500;
            yield return GcbWait.Until(
                () => (this._sentinelChest?.Items.Any(i => i?.QualifiedItemId == "(O)334") ?? false) || --deadline <= 0);
            GcbAssert.IsTrue(this._sentinelChest!.Items.Any(i => i?.QualifiedItemId == "(O)334"),
                "copper bar was collected into the standard chest");
        }

        private IEnumerator ApiReportsGroup()
        {
            int deadline = 600;
            yield return GcbWait.Until(
                () => this._api!.GetMachineStates(Game1.getFarm(), SentinelArea).Any() || --deadline <= 0);
            GcbAssert.IsTrue(this._api!.GetMachineStates(Game1.getFarm(), SentinelArea).Any(),
                "API reports machine states for the automated group");
        }

        // --- G1: mini-fridges as storage containers ----------------------------------
        private IEnumerator FridgeFeedsFurnace()
        {
            GameLocation house = Game1.getLocationFromName("FarmHouse");
            GcbAssert.IsNotNull(house, "farmhouse location exists");
            (Vector2 left, Vector2 right) = GcbWorld.FindAdjacentPlaceablePair(house);

            this._fridge = (Chest)GcbWorld.Place(house, left, "(BC)216");
            this._fridgeFurnace = GcbWorld.Place(house, right, "(BC)13");
            this._fridge.addItem(GcbWorld.Stack("(O)378", 5));
            this._fridge.addItem(GcbWorld.Stack("(O)382", 1));

            int deadline = 1500;
            yield return GcbWait.Until(() => this._fridgeFurnace.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._fridgeFurnace.heldObject.Value, "furnace started smelting from a mini-fridge");
        }

        private IEnumerator FridgeCollectsOutput()
        {
            GcbAssert.IsNotNull(this._fridgeFurnace?.heldObject.Value, "previous case left the furnace smelting");
            GcbWorld.AdvanceClock(4);
            int deadline = 1500;
            yield return GcbWait.Until(
                () => (this._fridge?.Items.Any(i => i?.QualifiedItemId == "(O)334") ?? false) || --deadline <= 0);
            GcbAssert.IsTrue(this._fridge!.Items.Any(i => i?.QualifiedItemId == "(O)334"),
                "copper bar was collected into the mini-fridge");
        }

        // --- G4: zero-size outputs must be discarded, not retried forever ------------
        private IEnumerator ZeroStackDiscarded()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, BrokenArea);
            this._brokenChest = (Chest)GcbWorld.Place(farm, new Vector2(BrokenArea.X, BrokenArea.Y), "(BC)130");
            this._brokenFurnace = GcbWorld.Place(farm, new Vector2(BrokenArea.X + 1, BrokenArea.Y), "(BC)13");
            this._brokenChest.addItem(GcbWorld.Stack("(O)378", 10));
            this._brokenChest.addItem(GcbWorld.Stack("(O)382", 2));

            int deadline = 1500;
            yield return GcbWait.Until(() => this._brokenFurnace.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._brokenFurnace.heldObject.Value, "furnace started smelting");

            GcbWorld.AdvanceClock(4);
            yield return GcbWait.Until(() => this._brokenFurnace.readyForHarvest.Value);
            this._brokenFurnace.heldObject.Value!.Stack = 0; // the external corruption under test

            int deadline2 = 1500;
            yield return GcbWait.Until(() => !this._brokenFurnace.readyForHarvest.Value || --deadline2 <= 0);
            GcbAssert.IsTrue(!this._brokenFurnace.readyForHarvest.Value,
                "the zero-size output was cleared from the machine");
        }

        private IEnumerator MachineResumes()
        {
            int deadline = 900;
            yield return GcbWait.Until(
                () => (this._brokenFurnace!.heldObject.Value is not null && !this._brokenFurnace.readyForHarvest.Value) || --deadline <= 0);
            GcbAssert.IsNotNull(this._brokenFurnace!.heldObject.Value, "furnace took the next batch of ore");
            GcbAssert.IsTrue(!this._brokenFurnace.readyForHarvest.Value, "furnace is actively processing, not wedged");
        }

        // --- G2: Junimo hut per-item-type behavior config ----------------------------
        private IEnumerator HutSetup()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, new Rectangle((int)HutTile.X - 2, (int)HutTile.Y - 2, 8, 6));

            GcbAssert.IsTrue(
                farm.buildStructure("Junimo Hut", HutTile, Game1.player, out Building hut, magicalConstruction: true, skipSafetyChecks: true),
                "Junimo hut was built on the farm");
            this._hutChest = ((JunimoHut)hut).GetOutputChest();
            GcbAssert.IsNotNull(this._hutChest, "hut has an output chest");

            this._hutSideChest = (Chest)GcbWorld.Place(farm, new Vector2(HutTile.X - 1, HutTile.Y), "(BC)130");
            this._hutChest!.addItem(GcbWorld.Stack("(O)472", 7)); // parsnip seeds
            this._hutChest.addItem(GcbWorld.Stack("(O)368", 4));  // basic fertilizer
            this._hutChest.addItem(GcbWorld.Stack("(O)72", 2));   // diamond
            yield break;
        }

        private IEnumerator HutSentinelMoved()
        {
            int deadline = 2400;
            yield return GcbWait.Until(
                () => (this._hutSideChest is not null
                       && this._hutSideChest.Items.Any(i => i?.QualifiedItemId == "(O)368")
                       && this._hutSideChest.Items.Any(i => i?.QualifiedItemId == "(O)72"))
                      || --deadline <= 0);
            GcbAssert.IsTrue(this._hutSideChest!.Items.Any(i => i?.QualifiedItemId == "(O)368"),
                "fertilizer was moved from the hut into the adjacent chest");
            GcbAssert.IsTrue(this._hutSideChest.Items.Any(i => i?.QualifiedItemId == "(O)72"),
                "gems were moved from the hut into the adjacent chest");
        }

        private IEnumerator HutSeedsStay()
        {
            yield return GcbWait.Ticks(240);
            GcbAssert.IsTrue(this._hutChest!.Items.Any(i => i?.QualifiedItemId == "(O)472"),
                "seeds are still in the hut (seed behavior is Ignore)");
            GcbAssert.IsTrue(!this._hutSideChest!.Items.Any(i => i?.QualifiedItemId == "(O)472"),
                "no seeds were moved into the adjacent chest");
        }
    }
}
