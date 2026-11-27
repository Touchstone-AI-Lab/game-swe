using System.Collections;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.Characters;
using StardewValley.Constants;
using StardewValley.Menus;
using StardewValley.Monsters;
using StardewValley.Tools;

namespace GcbHarness.Suites
{
    /// <summary>Verifies CJB Cheats Menu cheats that run on their own once enabled in
    /// config.json (tests/mod-config.json enables one-hit kill, always treasure, auto-feed
    /// animals, auto-pet animals and auto-pet pets). Pre-state is built through the game's
    /// own entry points: buildings are constructed instantly, animals are adopted into
    /// their building, monsters and pets are spawned into a location's character list,
    /// hay is stored and taken through the game's silo helpers, and the fishing minigame is
    /// opened as the game opens it when a fish bites. Outcomes are read from live entity
    /// state (monster health and form, trough contents, silo hay, pet/petted flags, and
    /// the minigame's treasure flags).</summary>
    public sealed class CjbCheatsRegressionsSuite : IGcbSuite
    {
        public string GroupName => "cjb-cheats-menu.release-regressions";

        private static readonly Vector2 CoopTile = new(44, 22);
        private static readonly Vector2 SiloTile = new(54, 22);
        private const int ChickenCount = 2;
        private const int CastCount = 120;

        private IModHelper? _helper;
        private AnimalHouse? _coop;
        private readonly List<FarmAnimal> _chickens = new();

        public void OnEntry(IModHelper helper)
        {
            this._helper = helper;
        }

        public IEnumerable<GcbCase> Cases =>
        [
            GcbCase.Sync("sentinel: the cheats mod is loaded and the world is ready", this.Sentinel),
            new GcbCase("one-hit kill: a monster drops to 1 health and keeps its maximum health", this.OneHitKillKeepsMaxHealth, timeoutTicks: 600),
            new GcbCase("one-hit kill: a grub stays a grub instead of turning into a fly", this.OneHitKillGrubStaysGrub, timeoutTicks: 1800),
            new GcbCase("auto-feed: troughs are filled with hay taken from the silo", this.AutoFeedUsesSiloHay, timeoutTicks: 1200),
            new GcbCase("auto-feed: troughs are filled even when no silo has hay left", this.AutoFeedWithoutSiloHay, timeoutTicks: 1200),
            new GcbCase("auto-pet animals: animals living in a farm building are petted", this.AutoPetFarmAnimals, timeoutTicks: 600),
            new GcbCase("auto-pet animals: an animal in town is left alone", this.AutoPetSkipsTownAnimal, timeoutTicks: 600),
            new GcbCase("auto-pet pets: the player's pet on the farm is petted", this.AutoPetFarmPet, timeoutTicks: 600),
            new GcbCase("auto-pet pets: a pet NPC in town is left alone", this.AutoPetSkipsTownPet, timeoutTicks: 600),
            new GcbCase("always treasure: every catch has a chest, never golden without fishing mastery", this.TreasureWithoutMastery, timeoutTicks: 3000),
            new GcbCase("always treasure: with fishing mastery some chests are golden", this.TreasureWithMastery, timeoutTicks: 3000),
        ];

        /*********
        ** Helpers
        *********/
        private static Vector2 FreeTileNear(GameLocation location, Vector2 origin, int minDistance)
        {
            var layer = location.Map.Layers[0];
            for (int radius = minDistance; radius < 30; radius++)
            {
                for (int dx = -radius; dx <= radius; dx++)
                {
                    foreach (int dy in new[] { -radius, radius })
                    {
                        var tile = new Vector2(origin.X + dx, origin.Y + dy);
                        if (tile.X < 1 || tile.Y < 1 || tile.X >= layer.LayerWidth - 1 || tile.Y >= layer.LayerHeight - 1)
                            continue;
                        if (location.CanItemBePlacedHere(tile))
                            return tile;
                    }
                }
            }
            throw new GcbAssertException($"no free tile found in {location.Name}");
        }

        private static void Spawn(GameLocation location, NPC npc)
        {
            npc.currentLocation = location;
            location.characters.Add(npc);
        }

        private AnimalHouse Coop()
        {
            if (this._coop is not null)
                return this._coop;

            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, new Rectangle((int)CoopTile.X - 2, (int)CoopTile.Y - 2, 10, 8));
            GcbAssert.IsTrue(
                farm.buildStructure("Coop", CoopTile, Game1.player, out Building coop, magicalConstruction: true, skipSafetyChecks: true),
                "coop was built");
            GcbAssert.IsTrue(coop.GetIndoors() is AnimalHouse, "coop has an animal house interior");
            var inside = (AnimalHouse)coop.GetIndoors();
            for (int i = 0; i < ChickenCount; i++)
            {
                var chicken = new FarmAnimal("White Chicken", Game1.Multiplayer.getNewID(), Game1.player.UniqueMultiplayerID);
                inside.adoptAnimal(chicken);
                this._chickens.Add(chicken);
            }
            this._coop = inside;
            return inside;
        }

        private static int HayInTroughs(AnimalHouse house)
        {
            return house.objects.Values.Count(obj => obj.QualifiedItemId == "(O)178");
        }

        private static void ClearTroughs(AnimalHouse house)
        {
            // Stands in for the animals eating their hay overnight.
            foreach (Vector2 tile in house.objects.Pairs.Where(p => p.Value.QualifiedItemId == "(O)178").Select(p => p.Key).ToArray())
                house.objects.Remove(tile);
        }

        private static bool PettedToday(Pet pet)
        {
            return pet.lastPetDay.TryGetValue(Game1.player.UniqueMultiplayerID, out int day) && day == Game1.Date.TotalDays;
        }

        private static int SelectFishingRod()
        {
            Farmer player = Game1.player;
            Item? rod = player.Items.FirstOrDefault(item => item is FishingRod);
            if (rod is null)
            {
                rod = ItemRegistry.Create("(T)BambooPole");
                GcbAssert.IsTrue(player.addItemToInventoryBool(rod), "fishing rod added to the inventory");
            }
            int index = player.Items.IndexOf(rod);
            GcbAssert.IsTrue(index >= 0 && index < 12, $"fishing rod is on the toolbar (slot {index})");
            player.CurrentToolIndex = index;
            return index;
        }

        /// <summary>Hold the fishing rod and wait until the game reports it as the current tool.</summary>
        private static IEnumerator HoldFishingRod()
        {
            SelectFishingRod();
            int deadline = 120;
            yield return GcbWait.Until(() => Game1.player.CurrentTool is FishingRod || --deadline <= 0);
            GcbAssert.IsTrue(Game1.player.CurrentTool is FishingRod, "fishing rod is the current tool");
        }

        /// <summary>Open the fishing minigame the way a fish bite does, give the cheats a few
        /// ticks, and record whether the catch shows a treasure chest and whether it's golden.</summary>
        private IEnumerator Casts(int count, List<(bool treasure, bool golden)> outcomes)
        {
            for (int i = 0; i < count; i++)
            {
                var bar = new BobberBar("145", 0.5f, treasure: false, new List<string>(), setFlagOnCatch: null!, isBossFish: false);
                Game1.activeClickableMenu = bar;
                yield return GcbWait.Ticks(3);
                outcomes.Add((bar.treasure, bar.goldenTreasure));
                if (object.ReferenceEquals(Game1.activeClickableMenu, bar))
                    Game1.activeClickableMenu = null;
                yield return GcbWait.Ticks(1);
            }
        }

        /*********
        ** Cases
        *********/
        private void Sentinel()
        {
            GcbAssert.IsTrue(this._helper!.ModRegistry.IsLoaded("CJBok.CheatsMenu"), "CJB Cheats Menu is loaded");
            GcbAssert.IsTrue(Context.IsWorldReady, "world is ready");
            GcbAssert.IsNotNull(Game1.currentLocation, "player has a current location");
        }

        private IEnumerator OneHitKillKeepsMaxHealth()
        {
            GameLocation location = Game1.currentLocation;
            Vector2 tile = FreeTileNear(location, Game1.player.Tile, 3);
            var slime = new GreenSlime(tile * 64f, 0);
            int maxHealth = slime.MaxHealth;
            GcbAssert.IsTrue(maxHealth > 1, $"a fresh slime has more than 1 max health ({maxHealth})");
            Spawn(location, slime);
            try
            {
                yield return GcbWait.Ticks(30);
                GcbAssert.AreEqual(1, slime.Health, "slime health with one-hit kill on");
                GcbAssert.AreEqual(maxHealth, slime.MaxHealth, "slime max health with one-hit kill on");
            }
            finally
            {
                location.characters.Remove(slime);
            }
        }

        private IEnumerator OneHitKillGrubStaysGrub()
        {
            GameLocation location = Game1.currentLocation;
            Vector2 tile = FreeTileNear(location, Game1.player.Tile, 4);
            var grub = new Grub(tile * 64f, hard: false);
            GcbAssert.IsTrue(grub.MaxHealth > 1, $"a fresh grub has more than 1 max health ({grub.MaxHealth})");
            Spawn(location, grub);
            try
            {
                // A grub below half health starts turning into a fly after about two seconds
                // and finishes about five seconds later; give it well over that.
                yield return GcbWait.Ticks(900);
                GcbAssert.AreEqual(1, grub.Health, "grub health with one-hit kill on");
                GcbAssert.IsTrue(location.characters.Contains(grub), "the grub is still in the location");
                GcbAssert.IsTrue(!grub.pupating.Value, "the grub has not started turning into a fly");
                GcbAssert.IsTrue(!location.characters.OfType<Fly>().Any(), "no fly appeared in the location");
            }
            finally
            {
                location.characters.Remove(grub);
                location.characters.RemoveWhere(npc => npc is Fly);
            }
        }

        private IEnumerator AutoFeedUsesSiloHay()
        {
            Farm farm = Game1.getFarm();
            AnimalHouse coop = this.Coop();
            GcbWorld.ClearArea(farm, new Rectangle((int)SiloTile.X - 1, (int)SiloTile.Y - 1, 5, 5));
            GcbAssert.IsTrue(
                farm.buildStructure("Silo", SiloTile, Game1.player, out Building _, magicalConstruction: true, skipSafetyChecks: true),
                "silo was built");
            ClearTroughs(coop);
            int leftover = GameLocation.StoreHayInAnySilo(5, farm);
            GcbAssert.AreEqual(0, leftover, "hay that didn't fit in the silo");
            GcbAssert.AreEqual(5, farm.piecesOfHay.Value, "hay in the silo before feeding");

            int deadline = 600;
            yield return GcbWait.Until(() => HayInTroughs(coop) >= ChickenCount || --deadline <= 0);
            yield return GcbWait.Ticks(120);
            GcbAssert.AreEqual(ChickenCount, HayInTroughs(coop), "hay in the coop's troughs");
            GcbAssert.AreEqual(5 - ChickenCount, farm.piecesOfHay.Value, "hay left in the silo");
        }

        private IEnumerator AutoFeedWithoutSiloHay()
        {
            Farm farm = Game1.getFarm();
            AnimalHouse coop = this.Coop();
            ClearTroughs(coop);
            while (GameLocation.GetHayFromAnySilo(farm) is not null)
            {
                // take the remaining hay out of the silo, as a player would from the hopper
            }
            GcbAssert.AreEqual(0, farm.piecesOfHay.Value, "hay in the silo before feeding");

            int deadline = 600;
            yield return GcbWait.Until(() => HayInTroughs(coop) >= ChickenCount || --deadline <= 0);
            GcbAssert.AreEqual(ChickenCount, HayInTroughs(coop), "hay in the coop's troughs with an empty silo");
        }

        private IEnumerator AutoPetFarmAnimals()
        {
            this.Coop();
            int deadline = 300;
            yield return GcbWait.Until(() => this._chickens.All(c => c.wasPet.Value) || --deadline <= 0);
            GcbAssert.IsTrue(this._chickens.All(c => c.wasPet.Value), "every chicken in the coop was petted");
        }

        private IEnumerator AutoPetSkipsTownAnimal()
        {
            GameLocation town = Game1.getLocationFromName("Town");
            GcbAssert.IsNotNull(town, "town exists");
            var goat = new FarmAnimal("Goat", Game1.Multiplayer.getNewID(), 0);
            goat.currentLocation = town;
            goat.Position = new Vector2(30, 60) * 64f;
            town.animals.Add(goat.myID.Value, goat);
            try
            {
                yield return GcbWait.Ticks(240);
                GcbAssert.IsTrue(!goat.wasPet.Value, "the goat in town was not petted");
            }
            finally
            {
                town.animals.Remove(goat.myID.Value);
            }
        }

        private IEnumerator AutoPetFarmPet()
        {
            Farm farm = Game1.getFarm();
            Vector2 tile = FreeTileNear(farm, new Vector2(64, 15), 2);
            var cat = new Pet((int)tile.X, (int)tile.Y, "0", "Cat");
            Spawn(farm, cat);
            int deadline = 300;
            yield return GcbWait.Until(() => PettedToday(cat) || --deadline <= 0);
            GcbAssert.IsTrue(PettedToday(cat), "the cat on the farm was petted today");
        }

        private IEnumerator AutoPetSkipsTownPet()
        {
            GameLocation town = Game1.getLocationFromName("Town");
            GcbAssert.IsNotNull(town, "town exists");
            var dog = new Pet(32, 60, "0", "Dog");
            Spawn(town, dog);
            try
            {
                yield return GcbWait.Ticks(240);
                GcbAssert.IsTrue(!PettedToday(dog), "the dog in town was not petted");
            }
            finally
            {
                town.characters.Remove(dog);
            }
        }

        private IEnumerator TreasureWithoutMastery()
        {
            IEnumerator hold = HoldFishingRod();
            while (hold.MoveNext())
                yield return hold.Current;
            Game1.player.stats.Set(StatKeys.Mastery(Farmer.fishingSkill), 0);
            var outcomes = new List<(bool treasure, bool golden)>();
            IEnumerator casts = this.Casts(CastCount / 2, outcomes);
            while (casts.MoveNext())
                yield return casts.Current;

            GcbAssert.AreEqual(CastCount / 2, outcomes.Count(o => o.treasure), "casts with a treasure chest");
            GcbAssert.AreEqual(0, outcomes.Count(o => o.golden), "golden chests without fishing mastery");
        }

        private IEnumerator TreasureWithMastery()
        {
            IEnumerator hold = HoldFishingRod();
            while (hold.MoveNext())
                yield return hold.Current;
            Game1.player.stats.Set(StatKeys.Mastery(Farmer.fishingSkill), 1);
            var outcomes = new List<(bool treasure, bool golden)>();
            IEnumerator casts = this.Casts(CastCount, outcomes);
            while (casts.MoveNext())
                yield return casts.Current;

            int golden = outcomes.Count(o => o.golden);
            GcbAssert.AreEqual(CastCount, outcomes.Count(o => o.treasure), "casts with a treasure chest");
            GcbAssert.IsTrue(golden > 0, $"some of {CastCount} chests are golden with fishing mastery (got {golden})");
            GcbAssert.IsTrue(golden < CastCount, $"not every chest is golden (got {golden} of {CastCount})");
        }
    }
}
