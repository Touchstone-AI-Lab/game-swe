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
    /// <summary>Verifies handling of machines holding a zero-size output stack — the
    /// state left behind when another mod's broken machine logic produces an empty
    /// item stack. The furnace reaches its ready state through the normal smelting
    /// path; the only direct mutation is zeroing the held stack, which IS the external
    /// corruption under test. Base tree: the push fails forever and the machine wedges.
    /// Fixed tree: the output is discarded and the machine keeps working.</summary>
    public sealed class ZeroStackOutputSuite : IGcbSuite
    {
        public string GroupName => "automate.zero-stack-output";

        private static readonly Rectangle SentinelArea = new(8, 20, 4, 3);
        private static readonly Rectangle BrokenArea = new(30, 20, 4, 3);

        private Chest? _brokenChest;
        private SObject? _brokenFurnace;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("sentinel: a normal furnace cycle lands its bar in the chest", this.SentinelNormalCycle, timeoutTicks: 2400),
            new GcbCase("a zero-size output is discarded and the machine empties", this.ZeroStackDiscarded, timeoutTicks: 2400),
            new GcbCase("the machine resumes processing input after the discard", this.MachineResumes, timeoutTicks: 1200),
        ];

        private IEnumerator SentinelNormalCycle()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, SentinelArea);
            var chest = (Chest)GcbWorld.Place(farm, new Vector2(SentinelArea.X, SentinelArea.Y), "(BC)130");
            SObject furnace = GcbWorld.Place(farm, new Vector2(SentinelArea.X + 1, SentinelArea.Y), "(BC)13");
            chest.addItem(GcbWorld.Stack("(O)378", 5)); // copper ore
            chest.addItem(GcbWorld.Stack("(O)382", 1)); // coal

            int deadline = 900;
            yield return GcbWait.Until(() => furnace.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(furnace.heldObject.Value, "furnace started smelting");

            GcbWorld.AdvanceClock(4); // furnace takes 30 in-game minutes
            deadline = 900;
            yield return GcbWait.Until(
                () => chest.Items.Any(i => i?.QualifiedItemId == "(O)334") || --deadline <= 0);
            GcbAssert.IsTrue(chest.Items.Any(i => i?.QualifiedItemId == "(O)334"),
                "copper bar was collected into the chest");
        }

        private IEnumerator ZeroStackDiscarded()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, BrokenArea);
            this._brokenChest = (Chest)GcbWorld.Place(farm, new Vector2(BrokenArea.X, BrokenArea.Y), "(BC)130");
            this._brokenFurnace = GcbWorld.Place(farm, new Vector2(BrokenArea.X + 1, BrokenArea.Y), "(BC)13");
            this._brokenChest.addItem(GcbWorld.Stack("(O)378", 10)); // enough ore for two batches
            this._brokenChest.addItem(GcbWorld.Stack("(O)382", 2));

            int deadline = 900;
            yield return GcbWait.Until(() => this._brokenFurnace.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._brokenFurnace.heldObject.Value, "furnace started smelting");

            // Let the batch finish, then corrupt the ready output the way a broken
            // third-party mod would: an item stack of size zero.
            GcbWorld.AdvanceClock(4);
            yield return GcbWait.Until(() => this._brokenFurnace.readyForHarvest.Value);
            this._brokenFurnace.heldObject.Value!.Stack = 0;

            // Fixed behavior: Automate discards the broken output (matching what
            // happens when the player empties the machine by hand) so the machine
            // leaves its ready state. Base behavior: the push fails every cycle and
            // the machine stays wedged in ready state forever.
            int deadline2 = 1500;
            yield return GcbWait.Until(() => !this._brokenFurnace.readyForHarvest.Value || --deadline2 <= 0);
            GcbAssert.IsTrue(!this._brokenFurnace.readyForHarvest.Value,
                "the zero-size output was cleared from the machine");
            GcbAssert.IsTrue(!this._brokenChest.Items.Any(i => i?.QualifiedItemId == "(O)334" && i.Stack <= 0),
                "no zero-size item stack was pushed into the chest");
        }

        private IEnumerator MachineResumes()
        {
            // With the broken output discarded, the remaining ore in the chest must
            // start a fresh batch: actively processing, not sitting in ready state.
            int deadline = 900;
            yield return GcbWait.Until(
                () => this._brokenFurnace!.heldObject.Value is not null && !this._brokenFurnace.readyForHarvest.Value || --deadline <= 0);

            GcbAssert.IsNotNull(this._brokenFurnace!.heldObject.Value, "furnace took the next batch of ore");
            GcbAssert.IsTrue(!this._brokenFurnace.readyForHarvest.Value, "furnace is actively processing, not wedged");
        }
    }
}
