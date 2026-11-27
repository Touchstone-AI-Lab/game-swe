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
    /// <summary>Verifies that one broken third-party integration cannot stop Automate
    /// from running the rest of a location.
    ///
    /// The image ships a second mod, Smart Machines, as a compiled assembly only — its
    /// source is not in this repository. It patches a game method and throws for one
    /// machine type. On the base tree that exception escapes Automate's location scan,
    /// so nothing in the location is automated, including machines the other mod never
    /// touches.
    ///
    /// The discriminator is deliberately about the *bystander*: a chest and furnace that
    /// have nothing to do with the broken machine must keep working. The suite never
    /// asserts anything about the broken machine itself, so any isolation strategy
    /// passes — skipping the tile, skipping the entity, or catching further out — and no
    /// assertion here pins how the fix is written.</summary>
    public sealed class ConflictSuite : IGcbSuite
    {
        public string GroupName => "automate.thirdparty-conflict";

        private static readonly Rectangle FarmArea = new(8, 20, 8, 4);

        private Chest? _chest;
        private SObject? _furnace;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("setup: a chest, a furnace, and the machine the other mod breaks", this.Setup, timeoutTicks: 1200),
            new GcbCase("the furnace is still automated despite the broken machine", this.FurnaceStillAutomated, timeoutTicks: 3000),
            new GcbCase("its output is still collected", this.OutputStillCollected, timeoutTicks: 3000),
        ];

        private IEnumerator Setup()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, FarmArea);

            this._chest = (Chest)GcbWorld.Place(farm, new Vector2(FarmArea.X, FarmArea.Y), "(BC)130");
            this._furnace = GcbWorld.Place(farm, new Vector2(FarmArea.X + 1, FarmArea.Y), "(BC)13");

            // The keg is what Smart Machines breaks. It sits in the same location — and
            // in the same machine group — as the furnace.
            GcbWorld.Place(farm, new Vector2(FarmArea.X + 2, FarmArea.Y), "(BC)12");

            this._chest.addItem(GcbWorld.Stack("(O)378", 20)); // copper ore
            this._chest.addItem(GcbWorld.Stack("(O)382", 8));  // coal

            // The other mod's profile store only fails once it is consulted after
            // startup, so the keg is placed while everything still looks healthy —
            // which is also the player's situation: the machines were already there
            // when the mod was installed.
            yield return GcbWait.Ticks(600);
        }

        private IEnumerator FurnaceStillAutomated()
        {
            // Placing a chest beside the group is an ordinary player action, and it is
            // what makes Automate re-scan this location. That re-scan is where the other
            // mod now throws — the same trigger as the reporter's "once per scan" errors.
            Farm farm = Game1.getFarm();
            GcbWorld.Place(farm, new Vector2(FarmArea.X + 3, FarmArea.Y), "(BC)130");
            this._chest!.addItem(GcbWorld.Stack("(O)378", 10));

            int deadline = 2400;
            yield return GcbWait.Until(() => this._furnace!.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value,
                "the furnace started smelting even though another mod breaks the keg beside it");
        }

        private IEnumerator OutputStillCollected()
        {
            GcbWorld.AdvanceClock(4);
            int deadline = 2400;
            yield return GcbWait.Until(
                () => (this._chest?.Items.Any(i => i?.QualifiedItemId == "(O)334") ?? false) || --deadline <= 0);
            GcbAssert.IsTrue(this._chest!.Items.Any(i => i?.QualifiedItemId == "(O)334"),
                "the copper bar was collected into the chest");
        }
    }
}
