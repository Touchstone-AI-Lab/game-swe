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
    /// <summary>Verifies that Automate leaves a machine alone while it is still working
    /// on what it was given, without breaking collection from machines that have
    /// genuinely finished.
    ///
    /// The discriminators are the two incubators: on the base tree Automate reports them
    /// as done while the egg is still incubating and moves the egg into the connected
    /// chest, so it never hatches. The suite deliberately covers BOTH vanilla incubators,
    /// in the two different farm buildings they belong in — a fix that special-cases the
    /// machine by name or ID passes the coop case and fails the barn one, so only a
    /// data-driven fix passes. The furnace sentinels bracket that: one before the
    /// incubator cases and one after, so a fix that simply collects less is caught even
    /// though every incubator assertion would pass.
    ///
    /// Every piece of pre-state is built through the game's own entry points — buildings
    /// via buildStructure, machines via placementAction, eggs via the drop-in action a
    /// player's click runs — so no assertion here can pin an implementation choice.</summary>
    public sealed class IncubatorSuite : IGcbSuite
    {
        public string GroupName => "automate.incubator-egg-theft";

        private static readonly Rectangle FarmArea = new(8, 20, 6, 4);
        private static readonly Vector2 CoopTile = new(20, 26);
        private static readonly Vector2 BarnTile = new(32, 26);

        private Chest? _farmChest;
        private SObject? _furnace;

        private Chest? _coopChest;
        private SObject? _incubator;

        private Chest? _barnChest;
        private SObject? _ostrichIncubator;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("setup: a coop and a barn, each with an incubator wired to a chest", this.Setup, timeoutTicks: 3000),
            new GcbCase("sentinel: a finished furnace is collected", this.SentinelFurnaceCollected, timeoutTicks: 2400),
            new GcbCase("an incubating egg is left in the coop incubator", this.EggStaysInIncubator, timeoutTicks: 2400),
            new GcbCase("an incubating egg is left in the ostrich incubator", this.EggStaysInOstrichIncubator, timeoutTicks: 2400),
            new GcbCase("sentinel: a finished furnace is still collected afterwards", this.SentinelStillCollectsAfter, timeoutTicks: 2400),
        ];

        private IEnumerator Setup()
        {
            Farm farm = Game1.getFarm();

            // --- farm: chest + furnace ---------------------------------------------------
            GcbWorld.ClearArea(farm, FarmArea);
            this._farmChest = (Chest)GcbWorld.Place(farm, new Vector2(FarmArea.X, FarmArea.Y), "(BC)130");
            this._furnace = GcbWorld.Place(farm, new Vector2(FarmArea.X + 1, FarmArea.Y), "(BC)13");
            this._farmChest.addItem(GcbWorld.Stack("(O)378", 20)); // copper ore
            this._farmChest.addItem(GcbWorld.Stack("(O)382", 8));  // coal

            // --- coop: incubator + chest --------------------------------------------------
            GcbWorld.ClearArea(farm, new Rectangle((int)CoopTile.X - 2, (int)CoopTile.Y - 2, 10, 8));
            GcbAssert.IsTrue(
                farm.buildStructure("Coop", CoopTile, Game1.player, out Building coop, magicalConstruction: true, skipSafetyChecks: true),
                "coop was built on the farm");
            GameLocation? coopInside = coop.GetIndoors();
            GcbAssert.IsNotNull(coopInside, "coop has an interior");
            (Vector2 coopLeft, Vector2 coopRight) = GcbWorld.FindAdjacentPlaceablePair(coopInside!);
            this._incubator = GcbWorld.Place(coopInside!, coopLeft, "(BC)101");        // Incubator
            this._coopChest = (Chest)GcbWorld.Place(coopInside!, coopRight, "(BC)130");

            // --- barn: ostrich incubator + chest ------------------------------------------
            GcbWorld.ClearArea(farm, new Rectangle((int)BarnTile.X - 2, (int)BarnTile.Y - 2, 12, 8));
            GcbAssert.IsTrue(
                farm.buildStructure("Barn", BarnTile, Game1.player, out Building barn, magicalConstruction: true, skipSafetyChecks: true),
                "barn was built on the farm");
            GameLocation? barnInside = barn.GetIndoors();
            GcbAssert.IsNotNull(barnInside, "barn has an interior");
            (Vector2 barnLeft, Vector2 barnRight) = GcbWorld.FindAdjacentPlaceablePair(barnInside!);
            this._ostrichIncubator = GcbWorld.Place(barnInside!, barnLeft, "(BC)254"); // Ostrich Incubator
            this._barnChest = (Chest)GcbWorld.Place(barnInside!, barnRight, "(BC)130");

            // Start both incubations through the game's own drop-in action — the same call
            // a player's click makes — never by assigning heldObject directly.
            SObject egg = (SObject)GcbWorld.Stack("(O)176", 1);          // Egg
            GcbAssert.IsTrue(this._incubator.performObjectDropInAction(egg, false, Game1.player),
                "coop incubator accepted an egg");
            SObject ostrichEgg = (SObject)GcbWorld.Stack("(O)289", 1);   // Ostrich Egg
            GcbAssert.IsTrue(this._ostrichIncubator.performObjectDropInAction(ostrichEgg, false, Game1.player),
                "ostrich incubator accepted an egg");

            GcbAssert.IsNotNull(this._incubator.heldObject.Value, "coop incubator is holding the egg");
            GcbAssert.IsNotNull(this._ostrichIncubator.heldObject.Value, "ostrich incubator is holding the egg");

            yield return GcbWait.Ticks(180); // let Automate rescan every changed location
        }

        private IEnumerator SentinelFurnaceCollected()
        {
            GcbAssert.IsNotNull(this._furnace, "setup placed the furnace");

            int deadline = 1800;
            yield return GcbWait.Until(() => this._furnace!.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value, "furnace started smelting from the chest");

            GcbWorld.AdvanceClock(4);
            deadline = 1800;
            yield return GcbWait.Until(
                () => (this._farmChest?.Items.Any(i => i?.QualifiedItemId == "(O)334") ?? false) || --deadline <= 0);
            GcbAssert.IsTrue(this._farmChest!.Items.Any(i => i?.QualifiedItemId == "(O)334"),
                "copper bar was collected into the chest");
        }

        private IEnumerator EggStaysInIncubator()
        {
            GcbAssert.IsNotNull(this._incubator, "setup placed the coop incubator");

            // Several full automation cycles at the incubator (default interval: 60 ticks).
            yield return GcbWait.Ticks(900);

            GcbAssert.IsNotNull(this._incubator!.heldObject.Value, "the egg is still in the coop incubator");
            GcbAssert.IsTrue(!this._coopChest!.Items.Any(i => i?.QualifiedItemId == "(O)176"),
                "no egg was moved into the coop chest");
        }

        private IEnumerator EggStaysInOstrichIncubator()
        {
            GcbAssert.IsNotNull(this._ostrichIncubator, "setup placed the ostrich incubator");

            yield return GcbWait.Ticks(900);

            GcbAssert.IsNotNull(this._ostrichIncubator!.heldObject.Value, "the egg is still in the ostrich incubator");
            GcbAssert.IsTrue(!this._barnChest!.Items.Any(i => i?.QualifiedItemId == "(O)289"),
                "no egg was moved into the barn chest");
        }

        private IEnumerator SentinelStillCollectsAfter()
        {
            // The furnace has had ore and coal available throughout; after everything
            // above, Automate must still be feeding and emptying it. A fix that stops
            // collecting too broadly fails here even though every incubator case passed.
            int barsBefore = this._farmChest!.Items.Where(i => i?.QualifiedItemId == "(O)334").Sum(i => i!.Stack);

            int deadline = 1800;
            yield return GcbWait.Until(() => this._furnace!.heldObject.Value is not null || --deadline <= 0);
            GcbAssert.IsNotNull(this._furnace!.heldObject.Value, "furnace took another batch of ore");

            GcbWorld.AdvanceClock(4);
            deadline = 1800;
            yield return GcbWait.Until(
                () => this._farmChest.Items.Where(i => i?.QualifiedItemId == "(O)334").Sum(i => i!.Stack) > barsBefore || --deadline <= 0);
            GcbAssert.IsTrue(
                this._farmChest.Items.Where(i => i?.QualifiedItemId == "(O)334").Sum(i => i!.Stack) > barsBefore,
                "another copper bar was collected after the incubators were left alone");
        }
    }
}
