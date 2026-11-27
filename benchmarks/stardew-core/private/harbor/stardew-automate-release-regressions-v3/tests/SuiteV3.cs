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

    /// <summary>Every defect group in this task sits at "missing edge-case branch"
    /// difficulty or above — none is an identifier-level typo. On the v1 composite
    /// the identifier-level groups did not discriminate between submissions, while
    /// edge-case groups such as the zero-size output wedge did. Raising the per-group
    /// floor is the difficulty lever this task relies on, so every group here is at
    /// least a missing edge-case branch.
    ///
    /// A fourth reverted defect (the missing null-Location guard on a removed bush,
    /// upstream 001e64aa) is present in the tree and reported in the instruction but
    /// carries NO assertion: its observable could not be produced reliably in the
    /// harness, and a test that cannot be made to work should not ship. It stays as
    /// haystack, exactly as darkrp-release-regressions-v3 kept its food-sound revert.
    ///
    /// Case order is load-bearing: the API probe must run before anything is placed,
    /// because creating any automated group rebuilds the caches on both trees and would
    /// mask that defect.</summary>
    public sealed class V3Suite : IGcbSuite
    {
        public string GroupName => "automate.release-regressions-v3";

        private static readonly Rectangle FarmArea = new(8, 20, 6, 4);

        private IModHelper? _helper;
        private IAutomateApi? _api;

        private Chest? _farmChest;
        private SObject? _furnace;


        private SObject? _coopAFurnace;
        private SObject? _coopBFurnace;

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
            new GcbCase("sentinel: a chest feeds an adjacent furnace", this.SentinelSmelt, timeoutTicks: 2400),
            new GcbCase("sentinel: the finished bar is collected", this.SentinelCollect, timeoutTicks: 2400),
            new GcbCase("a zero-size output is discarded and the machine empties", this.ZeroStackDiscarded, timeoutTicks: 3000),
            new GcbCase("the machine resumes processing input after the discard", this.MachineResumes, timeoutTicks: 2400),
            new GcbCase("setup: two coops of the same type, each with its own chest and furnace", this.TwinCoopSetup, timeoutTicks: 3000),
            new GcbCase("machines in the first coop run", this.CoopAWorks, timeoutTicks: 2400),
            new GcbCase("machines in the second coop run too", this.CoopBWorks, timeoutTicks: 2400),
        ];

        // --- G2: the API must publish what the initial save-load scan found -----------
        private IEnumerator ApiInitialScan()
        {
            this._api = this._helper!.ModRegistry.GetApi<IAutomateApi>("Pathoschild.Automate");
            GcbAssert.IsNotNull(this._api, "Automate exposes its mod API");

            yield return GcbWait.Ticks(360); // several automation intervals; nothing placed yet

            Farm farm = Game1.getFarm();
            GcbAssert.IsTrue(this._api!.GetMachineStates(farm, WholeFarm(farm)).Any(),
                "API reports the farm's machines (e.g. the shipping bin) after the initial scan");
        }

        private IEnumerator SentinelSmelt()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, FarmArea);
            this._farmChest = (Chest)GcbWorld.Place(farm, new Vector2(FarmArea.X, FarmArea.Y), "(BC)130");
            this._furnace = GcbWorld.Place(farm, new Vector2(FarmArea.X + 1, FarmArea.Y), "(BC)13");
            this._farmChest.addItem(GcbWorld.Stack("(O)378", 20));
            this._farmChest.addItem(GcbWorld.Stack("(O)382", 8));

            int deadline = 1800;
            yield return GcbWait.Until(() => this._furnace.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace.heldObject.Value, "furnace started smelting");
        }

        private IEnumerator SentinelCollect()
        {
            GcbWorld.AdvanceClock(4);
            int deadline = 1800;
            yield return GcbWait.Until(
                () => (this._farmChest?.Items.Any(i => i?.QualifiedItemId == "(O)334") ?? false) || --deadline <= 0);
            GcbAssert.IsTrue(this._farmChest!.Items.Any(i => i?.QualifiedItemId == "(O)334"),
                "copper bar was collected into the chest");
        }

        // --- G1: a zero-size output must be discarded, not retried forever ------------
        private IEnumerator ZeroStackDiscarded()
        {
            int deadline = 1800;
            yield return GcbWait.Until(() => this._furnace!.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value, "furnace has another batch running");

            GcbWorld.AdvanceClock(4);
            yield return GcbWait.Until(() => this._furnace.readyForHarvest.Value);
            this._furnace.heldObject.Value!.Stack = 0; // the external corruption under test

            int deadline2 = 1800;
            yield return GcbWait.Until(() => !this._furnace.readyForHarvest.Value || --deadline2 <= 0);
            GcbAssert.IsTrue(!this._furnace.readyForHarvest.Value,
                "the zero-size output was cleared from the machine");
        }

        private IEnumerator MachineResumes()
        {
            int deadline = 1800;
            yield return GcbWait.Until(
                () => (this._furnace!.heldObject.Value is not null && !this._furnace.readyForHarvest.Value) || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value, "furnace took the next batch of ore");
            GcbAssert.IsTrue(!this._furnace.readyForHarvest.Value, "furnace is processing, not wedged");
        }

        // --- G4: duplicate building interiors must stay independent -------------------
        private IEnumerator TwinCoopSetup()
        {
            Farm farm = Game1.getFarm();
            SObject? furnaceA = null, furnaceB = null;

            foreach (Vector2 site in new[] { new Vector2(44, 22), new Vector2(54, 22) })
            {
                GcbWorld.ClearArea(farm, new Rectangle((int)site.X - 2, (int)site.Y - 2, 10, 8));
                GcbAssert.IsTrue(
                    farm.buildStructure("Coop", site, Game1.player, out Building coop, magicalConstruction: true, skipSafetyChecks: true),
                    $"coop was built at {site}");
                GameLocation? inside = coop.GetIndoors();
                GcbAssert.IsNotNull(inside, "coop has an interior");

                (Vector2 left, Vector2 right) = GcbWorld.FindAdjacentPlaceablePair(inside!);
                var chest = (Chest)GcbWorld.Place(inside!, left, "(BC)130");
                SObject furnace = GcbWorld.Place(inside!, right, "(BC)13");
                chest.addItem(GcbWorld.Stack("(O)378", 5));
                chest.addItem(GcbWorld.Stack("(O)382", 1));

                if (furnaceA is null) furnaceA = furnace;
                else furnaceB = furnace;
            }

            this._coopAFurnace = furnaceA;
            this._coopBFurnace = furnaceB;
            yield return GcbWait.Ticks(180);
        }

        private IEnumerator CoopAWorks()
        {
            int deadline = 1800;
            yield return GcbWait.Until(() => this._coopAFurnace!.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._coopAFurnace!.heldObject.Value, "the first coop's furnace is smelting");
        }

        private IEnumerator CoopBWorks()
        {
            int deadline = 1800;
            yield return GcbWait.Until(() => this._coopBFurnace!.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._coopBFurnace!.heldObject.Value, "the second coop's furnace is smelting");
        }
    }
}
