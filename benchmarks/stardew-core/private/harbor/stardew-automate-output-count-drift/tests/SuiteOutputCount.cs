using System;
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
    /// <summary>Item conservation when Automate stores a finished output in a chest that
    /// already holds that item. Every discriminating case measures the one quantity the
    /// instruction promises: a finished bar ends up either in the chest or still in the
    /// furnace, exactly once. The three chest states (free slots, no free slot with room
    /// on the stack, no free slot with a maxed stack) are the three reports.</summary>
    public sealed class OutputCountSuite : IGcbSuite
    {
        public string GroupName => "automate.output-count-drift";

        private const string CopperOre = "(O)378";
        private const string Coal = "(O)382";
        private const string CopperBar = "(O)334";

        private static readonly Rectangle FarmArea = new(8, 20, 6, 4);

        private Chest? _chest;
        private SObject? _furnace;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("sentinel: a chest feeds an adjacent furnace", this.SentinelSmelt, timeoutTicks: 2400),
            new GcbCase("sentinel: the first finished bar is stored in the empty chest", this.SentinelFirstBar, timeoutTicks: 2400),
            new GcbCase("a finished bar joining an existing stack adds exactly one bar", this.TopUpAddsOne, timeoutTicks: 3000),
            GcbCase.Sync("setup: the chest has no free slot left", this.FillChest),
            new GcbCase("with no free slot, a bar that fits the stack is stored and the furnace empties", this.FullChestAccepts, timeoutTicks: 3000),
            new GcbCase("with no free slot and a maxed stack, the finished bar stays in the furnace", this.MaxedStackHolds, timeoutTicks: 3000),
        ];

        private int Bars() => this._chest!.Items.Where(i => i?.QualifiedItemId == CopperBar).Sum(i => i!.Stack);

        private int _deadline;

        /// <summary>The harness pump only understands <see cref="GcbWait"/> yields, so the
        /// shared wait is a factory paired with <see cref="AssertRunningBatch"/>.</summary>
        private GcbWait UntilRunningBatch()
        {
            this._deadline = 1800;
            return GcbWait.Until(
                () => (this._furnace!.heldObject.Value is not null && !this._furnace.readyForHarvest.Value) || --this._deadline <= 0);
        }

        private void AssertRunningBatch()
        {
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value, "furnace is smelting a batch");
            GcbAssert.IsTrue(!this._furnace.readyForHarvest.Value, "the batch is still in progress");
        }

        private IEnumerator SentinelSmelt()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, FarmArea);
            this._chest = (Chest)GcbWorld.Place(farm, new Vector2(FarmArea.X, FarmArea.Y), "(BC)130");
            this._furnace = GcbWorld.Place(farm, new Vector2(FarmArea.X + 1, FarmArea.Y), "(BC)13");
            this._chest.addItem(GcbWorld.Stack(CopperOre, 300));
            this._chest.addItem(GcbWorld.Stack(Coal, 100));

            yield return this.UntilRunningBatch();
            this.AssertRunningBatch();
        }

        private IEnumerator SentinelFirstBar()
        {
            GcbWorld.AdvanceClock(4);
            int deadline = 1800;
            yield return GcbWait.Until(() => this.Bars() > 0 || --deadline <= 0);
            GcbAssert.AreEqual(1, this.Bars(), "copper bars in the chest after the first batch");
        }

        private IEnumerator TopUpAddsOne()
        {
            yield return this.UntilRunningBatch();
            this.AssertRunningBatch();

            int before = this.Bars();
            GcbWorld.AdvanceClock(4);
            int deadline = 1800;
            yield return GcbWait.Until(() => this.Bars() != before || --deadline <= 0);
            GcbAssert.AreEqual(before + 1, this.Bars(), "copper bars in the chest after one more batch");
        }

        private void FillChest()
        {
            Chest chest = this._chest!;
            int capacity = chest.GetActualCapacity();
            IEnumerable<string> fillers = Game1.objectData
                .Where(p => p.Value.Category == SObject.SeedsCategory)
                .Select(p => "(O)" + p.Key)
                .OrderBy(id => id, StringComparer.Ordinal);
            foreach (string id in fillers)
            {
                if (chest.Items.Count(i => i is not null) >= capacity)
                    break;
                if (chest.Items.Any(i => i?.QualifiedItemId == id))
                    continue;
                chest.addItem(GcbWorld.Stack(id, 1));
            }

            GcbAssert.AreEqual(capacity, chest.Items.Count(i => i is not null), "occupied chest slots");
            GcbAssert.IsTrue(this.Bars() < 999, "the copper bar stack still has room");
        }

        private IEnumerator FullChestAccepts()
        {
            yield return this.UntilRunningBatch();
            this.AssertRunningBatch();

            int before = this.Bars();
            GcbWorld.AdvanceClock(4);
            int deadline = 1800;
            yield return GcbWait.Until(
                () => (this.Bars() != before && !this._furnace!.readyForHarvest.Value) || --deadline <= 0);
            GcbAssert.IsTrue(!this._furnace!.readyForHarvest.Value, "the furnace handed over its finished bar");
            GcbAssert.AreEqual(before + 1, this.Bars(), "copper bars in the chest after the batch");
        }

        private IEnumerator MaxedStackHolds()
        {
            yield return this.UntilRunningBatch();
            this.AssertRunningBatch();

            this._chest!.addItem(GcbWorld.Stack(CopperBar, 999 - this.Bars()));
            GcbAssert.AreEqual(999, this.Bars(), "the copper bar stack is maxed");

            GcbWorld.AdvanceClock(4);
            // note (luojiaxuan): several automation cycles, past the 5-second retry pause after a failed store.
            yield return GcbWait.Ticks(420);

            SObject furnace = this._furnace!;
            GcbAssert.IsTrue(furnace.readyForHarvest.Value, "the furnace still holds its finished batch");
            GcbAssert.AreEqual(CopperBar, furnace.heldObject.Value?.QualifiedItemId, "item waiting in the furnace");
            GcbAssert.AreEqual(999, this.Bars(), "copper bars in the chest");
        }
    }
}
