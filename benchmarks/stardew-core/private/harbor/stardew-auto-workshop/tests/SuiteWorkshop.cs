using System.Collections;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.Objects;
using SObject = StardewValley.Object;

namespace GcbHarness.Suites
{
    /// <summary>Behavioural test for a generated automation mod. Nothing here names a
    /// technique or calls into the agent's mod; every case drives the world through
    /// game entry points and reads live state.
    ///
    /// Case order is load-bearing: the farm furnace threads through feed -> collect ->
    /// zero-stack glitch -> full-chest, each stage using the machine state the previous
    /// one left behind.</summary>
    public sealed class WorkshopSuite : IGcbSuite
    {
        public string GroupName => "generation.auto-workshop";

        private static readonly Rectangle FarmArea = new(8, 20, 8, 5);

        private Chest? _chest;
        private SObject? _furnace;
        private SObject? _loneFurnace;
        private SObject? _coopAFurnace;
        private SObject? _coopBFurnace;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("setup: a chest against a furnace, a far chest, and a lone furnace", this.Setup, timeoutTicks: 1200),
            new GcbCase("the furnace is fed from the adjacent chest", this.Fed, timeoutTicks: 3000),
            new GcbCase("the finished bar is collected into the chest", this.Collected, timeoutTicks: 3000),
            new GcbCase("a zero-quantity product is cleared away", this.ZeroCleared, timeoutTicks: 3000),
            new GcbCase("the machine carries on with the next batch", this.Resumes, timeoutTicks: 3000),
            new GcbCase("a full chest never costs the product", this.FullChestHolds, timeoutTicks: 3600),
            new GcbCase("the product is delivered once space opens", this.DeliveredAfterSpace, timeoutTicks: 3000),
            new GcbCase("the far chest and the lone furnace stay untouched", this.NoOverreach, timeoutTicks: 1200),
            new GcbCase("setup: two coops of the same type, chest and furnace inside each", this.TwinCoopSetup, timeoutTicks: 3000),
            new GcbCase("machines in the first coop run", this.CoopAWorks, timeoutTicks: 2400),
            new GcbCase("machines in the second coop run too", this.CoopBWorks, timeoutTicks: 2400),
        ];

        private IEnumerator Setup()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, FarmArea);

            this._chest = (Chest)GcbWorld.Place(farm, new Vector2(FarmArea.X, FarmArea.Y), "(BC)130");
            this._furnace = GcbWorld.Place(farm, new Vector2(FarmArea.X + 1, FarmArea.Y), "(BC)13");

            // A second furnace whose nearest chest is two tiles away: neither may act.
            this._loneFurnace = GcbWorld.Place(farm, new Vector2(FarmArea.X + 4, FarmArea.Y), "(BC)13");
            Chest farChest = (Chest)GcbWorld.Place(farm, new Vector2(FarmArea.X + 6, FarmArea.Y), "(BC)130");
            farChest.addItem(GcbWorld.Stack("(O)378", 20));
            farChest.addItem(GcbWorld.Stack("(O)382", 8));

            this._chest.addItem(GcbWorld.Stack("(O)378", 25)); // copper ore
            this._chest.addItem(GcbWorld.Stack("(O)382", 10)); // coal
            yield return GcbWait.Ticks(60);
        }

        private IEnumerator Fed()
        {
            int deadline = 2400;
            yield return GcbWait.Until(() => this._furnace!.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value, "the furnace started smelting from the chest");
        }

        private IEnumerator Collected()
        {
            GcbWorld.AdvanceClock(4);
            int deadline = 2400;
            yield return GcbWait.Until(
                () => (this._chest?.Items.Any(i => i?.QualifiedItemId == "(O)334") ?? false) || --deadline <= 0);
            GcbAssert.IsTrue(this._chest!.Items.Any(i => i?.QualifiedItemId == "(O)334"),
                "the copper bar was moved into the chest");
        }

        private IEnumerator ZeroCleared()
        {
            int deadline = 2400;
            yield return GcbWait.Until(() => this._furnace!.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value, "another batch is running");

            GcbWorld.AdvanceClock(4);
            yield return GcbWait.Until(() => this._furnace.readyForHarvest.Value);
            this._furnace.heldObject.Value!.Stack = 0; // the glitch under test

            int deadline2 = 2400;
            yield return GcbWait.Until(() => !this._furnace.readyForHarvest.Value || --deadline2 <= 0);
            GcbAssert.IsTrue(!this._furnace.readyForHarvest.Value, "the zero-quantity product was cleared");
        }

        private IEnumerator Resumes()
        {
            int deadline = 2400;
            yield return GcbWait.Until(
                () => (this._furnace!.heldObject.Value is not null && !this._furnace.readyForHarvest.Value) || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value, "the furnace took the next batch");
            GcbAssert.IsTrue(!this._furnace.readyForHarvest.Value, "the furnace is processing, not jammed");
        }

        private IEnumerator FullChestHolds()
        {
            // Fill every remaining chest slot with full stacks the bar cannot merge into.
            int capacity = this._chest!.GetActualCapacity();
            int guard = 80;
            while (this._chest.Items.Count(i => i is not null) < capacity && --guard > 0)
                this._chest.addItem(GcbWorld.Stack("(O)390", 999)); // stone
            GcbAssert.IsTrue(this._chest.Items.Count(i => i is not null) >= capacity, "the chest is completely full");

            GcbWorld.AdvanceClock(4);
            int deadline = 1200;
            yield return GcbWait.Until(() => this._furnace!.readyForHarvest.Value || --deadline <= 0);
            GcbAssert.IsTrue(this._furnace!.readyForHarvest.Value, "the batch finished while the chest was full");

            // Give the mod several cycles to make the mistake, then check nothing was lost.
            yield return GcbWait.Ticks(360);
            GcbAssert.IsNotNull(this._furnace.heldObject.Value, "the product is still safe in the machine");
            GcbAssert.IsTrue(this._furnace.heldObject.Value!.Stack > 0, "the held product kept its quantity");
        }

        private IEnumerator DeliveredAfterSpace()
        {
            int before = this._chest!.Items.Where(i => i?.QualifiedItemId == "(O)334").Sum(i => i!.Stack);

            // Free exactly one slot, the ordinary way a player would: take a stack out.
            Item? junk = this._chest.Items.FirstOrDefault(i => i?.QualifiedItemId == "(O)390");
            GcbAssert.IsNotNull(junk, "a junk stack exists to remove");
            this._chest.Items.Remove(junk!);
            this._chest.clearNulls();

            int deadline = 2400;
            yield return GcbWait.Until(
                () => this._chest.Items.Where(i => i?.QualifiedItemId == "(O)334").Sum(i => i!.Stack) > before
                      || --deadline <= 0);
            GcbAssert.IsTrue(
                this._chest.Items.Where(i => i?.QualifiedItemId == "(O)334").Sum(i => i!.Stack) > before,
                "the held bar arrived in the chest after space opened");
        }

        private IEnumerator NoOverreach()
        {
            yield return GcbWait.Ticks(300);
            GcbAssert.IsTrue(this._loneFurnace!.heldObject.Value is null,
                "the furnace with no adjacent chest was never fed");
        }

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
            yield return GcbWait.Ticks(120);
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
