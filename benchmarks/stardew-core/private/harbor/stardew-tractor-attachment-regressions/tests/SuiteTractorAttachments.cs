using System.Collections;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.Characters;
using StardewValley.Objects;
using StardewValley.TerrainFeatures;
using StardewValley.Tools;
using SObject = StardewValley.Object;

namespace GcbHarness.Suites
{
    /// <summary>Verifies Tractor Mod tool attachments by driving a real tractor on the
    /// fixture farm. tests/mod-config.json sets the tool distance and the options under
    /// test (fruit-tree sapling clearing on, grown fruit trees off; placed-object breaking
    /// on, mine-stone breaking off; Parsnip and Torch as custom attachments).
    ///
    /// Pre-state goes through the game's own entry points: the garage is built instantly,
    /// its stable spawns the tractor as it does overnight, the player walks up and mounts
    /// it with the normal interaction, and targets are placed with placement actions or
    /// added as terrain features and litter the way world generation adds them. Each group
    /// moves the tractor to a freshly cleared patch, holds one tool or item, and reads the
    /// result from live world state.</summary>
    public sealed class TractorAttachmentsSuite : IGcbSuite
    {
        public string GroupName => "tractor-mod.attachment-regressions";

        /// <summary>The <see cref="Character.modData"/> key Tractor Mod documents for identifying tractors.</summary>
        private const string TractorDataKey = "Pathoschild.TractorMod";
        private const string GarageId = "Pathoschild.TractorMod_Stable";
        private static readonly Vector2 GarageTile = new(40, 30);
        private const int WorkTicks = 360;

        private Horse? _tractor;
        private int _emptySlot = -1;

        private FruitTree? _grownFruitTree;
        private float _grownFruitTreeHealth;
        private Vector2 _grownTile;
        private Vector2 _saplingTile;
        private IndoorPot? _emptyPot;
        private IndoorPot? _bushPot;
        private Vector2 _customCenter;
        private Vector2 _stoneTile;
        private Vector2 _torchTile;

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("setup: the player builds a garage and rides the tractor", this.RideTractor, timeoutTicks: 3000),
            new GcbCase("axe: a sapling is cleared when sapling clearing is on", this.AxeClearsSapling, timeoutTicks: 1200),
            GcbCase.Sync("axe: a full-grown fruit tree is left alone when grown-tree chopping is off", this.AxeKeepsGrownFruitTree),
            new GcbCase("seeds: an empty garden pot is sown", this.SeedsSowEmptyPot, timeoutTicks: 1200),
            GcbCase.Sync("seeds: a garden pot holding a bush is not sown", this.SeedsSkipBushPot),
            new GcbCase("custom attachments: a placeable item is placed around the tractor", this.CustomPlacesTorches, timeoutTicks: 1200),
            new GcbCase("custom attachments: an item that can't be placed is never put on the ground", this.CustomSkipsParsnips, timeoutTicks: 1200),
            new GcbCase("pickaxe: placed objects are broken when that option is on", this.PickaxeBreaksPlacedObject, timeoutTicks: 1200),
            GcbCase.Sync("pickaxe: stones stay when stone breaking is off", this.PickaxeKeepsStone),
        ];

        /*********
        ** Helpers
        *********/
        private static bool PlayerFree()
        {
            return Context.IsPlayerFree && !Game1.fadeToBlack && Game1.player.freezePause <= 0;
        }

        private static Horse? FindTractor(GameLocation location)
        {
            return location.characters.OfType<Horse>().FirstOrDefault(h => h.modData.ContainsKey(TractorDataKey));
        }

        private int EmptySlot()
        {
            if (this._emptySlot >= 0 && Game1.player.Items[this._emptySlot] is null)
                return this._emptySlot;
            for (int i = 0; i < 12; i++)
            {
                if (Game1.player.Items.Count <= i || Game1.player.Items[i] is null)
                {
                    this._emptySlot = i;
                    return i;
                }
            }
            throw new GcbAssertException("no empty toolbar slot for holding nothing");
        }

        private void HoldNothing()
        {
            Game1.player.CurrentToolIndex = this.EmptySlot();
        }

        /// <summary>Put an item on the toolbar (reusing an existing stack of the same item) and hold it.</summary>
        private static Item Hold(string qualifiedId, int stack)
        {
            Farmer player = Game1.player;
            Item? item = player.Items.Take(12).FirstOrDefault(i => i?.QualifiedItemId == qualifiedId);
            if (item is null)
            {
                item = ItemRegistry.Create(qualifiedId, stack);
                GcbAssert.IsTrue(player.addItemToInventoryBool(item), $"{qualifiedId} added to the inventory");
            }
            int index = player.Items.IndexOf(item);
            GcbAssert.IsTrue(index >= 0 && index < 12, $"{qualifiedId} is on the toolbar (slot {index})");
            player.CurrentToolIndex = index;
            return item;
        }

        /// <summary>Clear a patch of farm around a center tile and drive the tractor onto it.</summary>
        private static Vector2 PreparePatch(Vector2 center)
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, new Rectangle((int)center.X - 3, (int)center.Y - 3, 7, 7));
            for (int x = -2; x <= 2; x++)
            {
                for (int y = -2; y <= 2; y++)
                {
                    var tile = new Vector2(center.X + x, center.Y + y);
                    if (tile != center)
                        GcbAssert.IsTrue(farm.CanItemBePlacedHere(tile), $"tile {tile} near {center} is open ground");
                }
            }
            return center;
        }

        /// <summary>Drive the tractor onto a tile. The rider's tile comes from the mount's
        /// bounding box, so the mount moves first and the rider follows.</summary>
        private static void DriveTo(Vector2 center)
        {
            Vector2 pixel = center * 64f;
            if (Game1.player.mount is Horse mount)
                mount.Position = pixel;
            Game1.player.Position = pixel;
        }

        private static void AssertAt(Vector2 center)
        {
            GcbAssert.AreEqual(center, Game1.player.Tile, "the tractor's tile");
        }

        private IEnumerator Work(string qualifiedId, int stack)
        {
            Hold(qualifiedId, stack);
            yield return GcbWait.Ticks(WorkTicks);
            this.HoldNothing();
            yield return GcbWait.Ticks(15);
        }

        /*********
        ** Cases
        *********/
        private IEnumerator RideTractor()
        {
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, new Rectangle((int)GarageTile.X - 2, (int)GarageTile.Y - 2, 10, 8));
            GcbAssert.IsTrue(
                farm.buildStructure(GarageId, GarageTile, Game1.player, out Building garage, magicalConstruction: true, skipSafetyChecks: true),
                "the tractor garage was built");
            GcbAssert.IsTrue(garage is Stable, "the garage is a stable-type building");

            // The garage's stable spawns its vehicle, as it does at the start of each day.
            ((Stable)garage).grabHorse();
            int spawn = 300;
            yield return GcbWait.Until(() => FindTractor(farm) is not null || --spawn <= 0);
            Horse? tractor = FindTractor(farm);
            GcbAssert.IsNotNull(tractor, "a tractor is parked at the garage");
            this._tractor = tractor;

            // walk out to the tractor
            this.HoldNothing();
            Point stand = tractor!.TilePoint;
            Game1.warpFarmer("Farm", stand.X + 1, stand.Y, false);
            int warp = 900;
            yield return GcbWait.Until(() => (Game1.currentLocation is Farm && PlayerFree()) || --warp <= 0);
            GcbAssert.IsTrue(Game1.currentLocation is Farm, "the player is on the farm");
            GcbAssert.IsTrue(PlayerFree(), "the player can act on the farm");

            // get on
            GcbAssert.IsTrue(tractor.checkAction(Game1.player, farm), "the tractor accepts the player");
            int mount = 900;
            yield return GcbWait.Until(() => (Game1.player.mount == tractor && PlayerFree()) || --mount <= 0);
            GcbAssert.IsTrue(Game1.player.mount == tractor, "the player is riding the tractor");
            GcbAssert.IsTrue(PlayerFree(), "the player can drive the tractor");
        }

        private IEnumerator AxeClearsSapling()
        {
            GcbAssert.IsTrue(Game1.player.mount == this._tractor, "the player is riding the tractor");
            Farm farm = Game1.getFarm();
            Vector2 center = PreparePatch(new Vector2(30, 40));
            this._saplingTile = center + new Vector2(-1, 0);
            Vector2 grownTile = center + new Vector2(1, 0);

            var sapling = new FruitTree("628", 2);
            farm.terrainFeatures.Add(this._saplingTile, sapling);
            var grown = new FruitTree("628", FruitTree.treeStage);
            farm.terrainFeatures.Add(grownTile, grown);
            this._grownFruitTree = grown;
            this._grownTile = grownTile;
            this._grownFruitTreeHealth = grown.health.Value;

            this.HoldNothing();
            DriveTo(center);
            yield return GcbWait.Ticks(15);
            AssertAt(center);
            IEnumerator work = this.Work("(T)Axe", 1);
            while (work.MoveNext())
                yield return work.Current;

            GcbAssert.IsTrue(!farm.terrainFeatures.ContainsKey(this._saplingTile), "the cherry sapling was cleared");
        }

        private void AxeKeepsGrownFruitTree()
        {
            Farm farm = Game1.getFarm();
            FruitTree? tree = this._grownFruitTree;
            GcbAssert.IsNotNull(tree, "the grown fruit tree was planted");
            Vector2 tile = this._grownTile;
            GcbAssert.IsTrue(farm.terrainFeatures.TryGetValue(tile, out TerrainFeature? feature) && object.ReferenceEquals(feature, tree), "the grown fruit tree is still planted");
            GcbAssert.IsTrue(!tree!.stump.Value && !tree.falling.Value, "the grown fruit tree was not felled");
            GcbAssert.AreEqual(this._grownFruitTreeHealth, tree.health.Value, "the grown fruit tree's health");
        }

        private IEnumerator SeedsSowEmptyPot()
        {
            GcbAssert.IsTrue(Game1.player.mount == this._tractor, "the player is riding the tractor");
            Farm farm = Game1.getFarm();
            Vector2 center = PreparePatch(new Vector2(40, 40));
            this._emptyPot = (IndoorPot)GcbWorld.Place(farm, center + new Vector2(-1, 0), "(BC)62");
            this._bushPot = (IndoorPot)GcbWorld.Place(farm, center + new Vector2(1, 0), "(BC)62");
            GcbAssert.IsTrue(
                this._bushPot.performObjectDropInAction(ItemRegistry.Create("(O)251"), false, Game1.player),
                "a tea sapling was planted in the second pot");
            GcbAssert.IsNotNull(this._bushPot.bush.Value, "the second pot holds a tea bush");

            this.HoldNothing();
            DriveTo(center);
            yield return GcbWait.Ticks(15);
            AssertAt(center);
            IEnumerator work = this.Work("(O)472", 10);
            while (work.MoveNext())
                yield return work.Current;

            GcbAssert.IsNotNull(this._emptyPot.hoeDirt.Value.crop, "a crop was sown in the empty pot");
        }

        private void SeedsSkipBushPot()
        {
            IndoorPot? pot = this._bushPot;
            GcbAssert.IsNotNull(pot, "the pot with a bush was placed");
            GcbAssert.IsNotNull(pot!.bush.Value, "the pot still holds its tea bush");
            GcbAssert.IsTrue(pot.hoeDirt.Value.crop is null, "no crop was sown in the pot that holds a bush");
        }

        private IEnumerator CustomPlacesTorches()
        {
            GcbAssert.IsTrue(Game1.player.mount == this._tractor, "the player is riding the tractor");
            Farm farm = Game1.getFarm();
            Vector2 center = PreparePatch(new Vector2(50, 40));
            this._customCenter = center;

            this.HoldNothing();
            DriveTo(center);
            yield return GcbWait.Ticks(15);
            AssertAt(center);
            IEnumerator work = this.Work("(O)93", 30);
            while (work.MoveNext())
                yield return work.Current;

            int torches = farm.objects.Pairs.Count(p => p.Value.QualifiedItemId == "(O)93"
                && System.Math.Abs(p.Key.X - center.X) <= 2 && System.Math.Abs(p.Key.Y - center.Y) <= 2);
            GcbAssert.IsTrue(torches > 0, $"torches were placed around the tractor (found {torches})");
        }

        private IEnumerator CustomSkipsParsnips()
        {
            GcbAssert.IsTrue(Game1.player.mount == this._tractor, "the player is riding the tractor");
            Farm farm = Game1.getFarm();
            Vector2 center = PreparePatch(new Vector2(50, 48));

            this.HoldNothing();
            DriveTo(center);
            yield return GcbWait.Ticks(15);
            AssertAt(center);
            Item parsnips = Hold("(O)24", 20);
            int before = parsnips.Stack;
            yield return GcbWait.Ticks(WorkTicks);
            this.HoldNothing();
            yield return GcbWait.Ticks(15);

            int placed = farm.objects.Pairs.Count(p => p.Value.QualifiedItemId == "(O)24");
            GcbAssert.AreEqual(0, placed, "parsnips lying on the farm as placed objects");
            GcbAssert.AreEqual(before, parsnips.Stack, "parsnips left in the held stack");
        }

        private IEnumerator PickaxeBreaksPlacedObject()
        {
            GcbAssert.IsTrue(Game1.player.mount == this._tractor, "the player is riding the tractor");
            Farm farm = Game1.getFarm();
            Vector2 center = PreparePatch(new Vector2(30, 48));
            this._torchTile = center + new Vector2(-1, 0);
            this._stoneTile = center + new Vector2(1, 0);
            GcbWorld.Place(farm, this._torchTile, "(O)93");
            // A field stone, as world generation and debris spawns add them.
            farm.objects.Add(this._stoneTile, ItemRegistry.Create<SObject>("(O)450"));
            GcbAssert.IsTrue(farm.objects[this._stoneTile].IsBreakableStone(), "the stone is ordinary breakable stone");

            this.HoldNothing();
            DriveTo(center);
            yield return GcbWait.Ticks(15);
            AssertAt(center);
            IEnumerator work = this.Work("(T)Pickaxe", 1);
            while (work.MoveNext())
                yield return work.Current;

            GcbAssert.IsTrue(!farm.objects.ContainsKey(this._torchTile), "the placed torch was broken");
        }

        private void PickaxeKeepsStone()
        {
            Farm farm = Game1.getFarm();
            GcbAssert.IsTrue(farm.objects.TryGetValue(this._stoneTile, out SObject? stone) && stone.QualifiedItemId == "(O)450", "the stone is still there");
        }
    }
}
