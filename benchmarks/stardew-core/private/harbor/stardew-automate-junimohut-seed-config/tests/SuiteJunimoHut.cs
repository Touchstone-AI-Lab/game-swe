using System.Collections;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.Objects;

namespace GcbHarness.Suites
{
    /// <summary>Verifies the per-item-type Junimo hut behavior config. The verifier
    /// installs a config with JunimoHutBehaviorForSeeds=Ignore and
    /// JunimoHutBehaviorForFertilizer=MoveIntoChests, so in one boot: fertilizer and
    /// gems must be moved out of the hut (sentinels proving the pipeline runs), while
    /// seeds must stay in the hut (fails while the seed setting reads the wrong config
    /// field).</summary>
    public sealed class JunimoHutSuite : IGcbSuite
    {
        public string GroupName => "automate.junimohut-seed-config";

        private static readonly Vector2 HutTile = new(30, 20);
        private Chest? _hutChest;
        private Chest? _sideChest;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("setup: build a Junimo hut with a connected chest", this.Setup, timeoutTicks: 1200),
            new GcbCase("sentinel: fertilizer is moved out of the hut per config", this.FertilizerMoved, timeoutTicks: 3000),
            new GcbCase("seeds stay in the hut when the seed behavior is Ignore", this.SeedsStay, timeoutTicks: 600),
        ];

        private IEnumerator Setup()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, new Rectangle((int)HutTile.X - 2, (int)HutTile.Y - 2, 8, 6));

            GcbAssert.IsTrue(
                farm.buildStructure("Junimo Hut", HutTile, Game1.player, out Building hut, magicalConstruction: true, skipSafetyChecks: true),
                "Junimo hut was built on the farm");
            JunimoHut junimoHut = (JunimoHut)hut;

            this._hutChest = junimoHut.GetOutputChest();
            GcbAssert.IsNotNull(this._hutChest, "hut has an output chest");

            // A chest orthogonally adjacent to the hut's footprint receives moved items.
            this._sideChest = (Chest)GcbWorld.Place(farm, new Vector2(HutTile.X - 1, HutTile.Y), "(BC)130");

            this._hutChest!.addItem(GcbWorld.Stack("(O)472", 7)); // parsnip seeds
            this._hutChest.addItem(GcbWorld.Stack("(O)368", 4));  // basic fertilizer
            this._hutChest.addItem(GcbWorld.Stack("(O)72", 2));   // diamond (gem sentinel)
            yield break;
        }

        private IEnumerator FertilizerMoved()
        {
            // The hut outputs one item stack per automation cycle, so wait until both
            // expected stacks have crossed over before asserting.
            int deadline = 2400;
            yield return GcbWait.Until(
                () => (this._sideChest is not null
                       && this._sideChest.Items.Any(i => i?.QualifiedItemId == "(O)368")
                       && this._sideChest.Items.Any(i => i?.QualifiedItemId == "(O)72"))
                      || --deadline <= 0);

            GcbAssert.IsTrue(this._sideChest!.Items.Any(i => i?.QualifiedItemId == "(O)368"),
                "fertilizer was moved from the hut into the adjacent chest");
            GcbAssert.IsTrue(this._sideChest.Items.Any(i => i?.QualifiedItemId == "(O)72"),
                "gems were moved from the hut into the adjacent chest");
        }

        private IEnumerator SeedsStay()
        {
            // The pipeline demonstrably ran (previous case); give it a little more time,
            // then require the seeds to still be in the hut.
            yield return GcbWait.Ticks(240);

            GcbAssert.IsTrue(this._hutChest!.Items.Any(i => i?.QualifiedItemId == "(O)472"),
                "seeds are still in the hut (seed behavior is Ignore)");
            GcbAssert.IsTrue(!this._sideChest!.Items.Any(i => i?.QualifiedItemId == "(O)472"),
                "no seeds were moved into the adjacent chest");
        }
    }
}
