using FargowiltasSouls.Content.Items.Accessories.Enchantments;
using FargowiltasSouls.Content.Items.Accessories.Masomode;
using FargowiltasSouls.Content.Items.Accessories.Souls;
using FargowiltasSouls.Content.Items.Armor;
using FargowiltasSouls.Content.Items.Consumables;
using FargowiltasSouls.Core.AccessoryEffectSystem;
using Microsoft.Xna.Framework;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Terraria;
using Terraria.IO;
using Terraria.Localization;
using Terraria.ModLoader;

namespace FargowiltasSouls.Core.Toggler
{
    public class ToggleBackend
    {
        public readonly static string ConfigPath = Path.Combine(Main.SavePath, "ModConfigs", "FargowiltasSouls_Toggles.json");
        public Preferences Config;

        public Dictionary<AccessoryEffect, Toggle> Toggles = [];
        //public Point TogglerPosition;
        public bool CanPlayMaso = true;

        public const int CustomPresetCount = 3;
        public List<AccessoryEffect>[] CustomPresets = new List<AccessoryEffect>[CustomPresetCount];

        public bool Initialized;
        private ulong loadedGeneration;

        //not doing it in player.initialize because multiplayer clones players which makes new togglers which tries config load which has high overhead (lag)
        public void TryLoad()
        {
            if (Initialized)
            {
                ReconcileRegistry();
                return;
            }

            Preferences loadedConfig = new Preferences(ConfigPath);
            Dictionary<AccessoryEffect, Toggle> loadedToggles = [];
            ulong generation = ToggleLoader.Generation;
            List<KeyValuePair<AccessoryEffect, Toggle>> definitions =
                ToggleLoader.LoadedToggles?.ToList() ?? [];
            foreach (KeyValuePair<AccessoryEffect, Toggle> entry in definitions
                .OrderBy(entry => entry.Value.Identity, StringComparer.Ordinal))
                loadedToggles.Add(entry.Key, entry.Value.Materialize(entry.Key));
            if (generation != ToggleLoader.Generation)
                return;
            List<AccessoryEffect>[] loadedPresets = new List<AccessoryEffect>[CustomPresetCount];
            //TogglerPosition = new Point(0, 0);

            bool configExists = true;
            if (!Main.dedServ)
            {
                configExists = loadedConfig.Load();
            }

            //Dictionary<string, int> togglerPositionUnpack = Config.Get("TogglerPosition", new Dictionary<string, int>() { { "X", Main.screenWidth / 2 - 300 }, { "Y", Main.screenHeight / 2 - 200 } });
            //TogglerPosition = new Point(togglerPositionUnpack["X"], togglerPositionUnpack["Y"]);

            //if (!Main.dedServ)
            //    FargoUIManager.SoulToggler.SetPositionToPoint(TogglerPosition);

            CanPlayMaso = true; // Config.Get("CanPlayMaso", true);

            //TODO: figure out how to extract a plain list from json, only using Dict rn because i know it can be loaded from json
            if (!Main.dedServ)
            {
                for (int i = 0; i < loadedPresets.Length; i++)
                {
                    try
                    {
                        var toggleUnpack = loadedConfig.Get<Dictionary<string, bool>>($"CustomPresetsOff{i + 1}", null);
                        if (toggleUnpack != null)
                        {
                            loadedPresets[i] = loadedToggles
                                .Where(entry => toggleUnpack.ContainsKey(entry.Value.Identity))
                                .OrderBy(entry => entry.Value.Identity, StringComparer.Ordinal)
                                .Select(entry => entry.Key)
                                .ToList();
                        }
                    }
                    catch
                    {
                        loadedPresets[i] = null;
                    }
                }
            }

            Config = loadedConfig;
            Toggles = loadedToggles;
            CustomPresets = loadedPresets;
            CanPlayMaso = true;
            Initialized = true;
            loadedGeneration = generation;

            if (!Main.dedServ && !configExists)
                Save();
        }

        private void ReconcileRegistry()
        {
            if (!Initialized || loadedGeneration == ToggleLoader.Generation)
                return;

            ulong generation = ToggleLoader.Generation;
            List<KeyValuePair<AccessoryEffect, Toggle>> definitions =
                ToggleLoader.LoadedToggles?.ToList() ?? [];

            try
            {
                Dictionary<string, bool> oldValues = Toggles.Values
                    .Where(toggle => toggle != null && !string.IsNullOrEmpty(toggle.Identity))
                    .GroupBy(toggle => toggle.Identity, StringComparer.Ordinal)
                    .ToDictionary(group => group.Key, group => group.First().ToggleBool, StringComparer.Ordinal);

                Dictionary<AccessoryEffect, Toggle> replacement = [];
                Dictionary<string, AccessoryEffect> effectsByIdentity = new(StringComparer.Ordinal);
                foreach (KeyValuePair<AccessoryEffect, Toggle> entry in definitions
                    .OrderBy(entry => entry.Value.Identity, StringComparer.Ordinal))
                {
                    if (entry.Key == null || entry.Value == null || entry.Value.Header == null ||
                        string.IsNullOrEmpty(entry.Value.Identity) || effectsByIdentity.ContainsKey(entry.Value.Identity))
                        return;

                    Toggle materialized = entry.Value.Materialize(entry.Key);
                    if (oldValues.TryGetValue(materialized.Identity, out bool oldValue))
                        materialized.ToggleBool = oldValue;
                    replacement.Add(entry.Key, materialized);
                    effectsByIdentity.Add(materialized.Identity, entry.Key);
                }

                List<AccessoryEffect>[] reboundPresets = new List<AccessoryEffect>[CustomPresetCount];
                for (int i = 0; i < reboundPresets.Length; i++)
                {
                    if (CustomPresets[i] == null)
                        continue;

                    var identities = new SortedSet<string>(StringComparer.Ordinal);
                    foreach (AccessoryEffect effect in CustomPresets[i])
                    {
                        string identity = ResolveKnownIdentity(effect);
                        if (identity != null && effectsByIdentity.ContainsKey(identity))
                            identities.Add(identity);
                    }
                    reboundPresets[i] = identities.Select(identity => effectsByIdentity[identity]).ToList();
                }

                if (generation != ToggleLoader.Generation)
                    return;

                Toggles = replacement;
                CustomPresets = reboundPresets;
                loadedGeneration = generation;
            }
            catch
            {
                // A malformed replacement generation cannot partially replace
                // the last coherent player-local snapshot.
            }
        }

        internal void RefreshRegistry()
        {
            if (Initialized)
                ReconcileRegistry();
        }

        private string ResolveKnownIdentity(AccessoryEffect effect)
        {
            if (effect == null)
                return null;
            foreach (KeyValuePair<AccessoryEffect, Toggle> entry in Toggles)
                if (ReferenceEquals(entry.Key, effect) || ReferenceEquals(entry.Value.Effect, effect))
                    return entry.Value.Identity;
            try
            {
                return effect.FullName;
            }
            catch
            {
                return null;
            }
        }

        public void Save()
        {
            RefreshRegistry();
            if (!Initialized)
                return;

            if (!Main.dedServ)
            {
                //Config.Put("CanPlayMaso", CanPlayMaso);

                //Config.Put(TogglesByPlayer, ParsePackedToggles());

                //TogglerPosition = FargoUIManager.SoulToggler.GetPositionAsPoint();
                //Config.Put("TogglerPosition", UnpackPosition());

                for (int i = 0; i < CustomPresetCount; i++)
                {
                    Dictionary<string, bool> togglesOff = new();
                    if (CustomPresets[i] != null)
                    {
                        var identities = new SortedSet<string>(StringComparer.Ordinal);
                        foreach (AccessoryEffect effect in CustomPresets[i])
                        {
                            string identity = ResolveKnownIdentity(effect);
                            if (identity != null)
                                identities.Add(identity);
                        }
                        foreach (string identity in identities)
                            togglesOff[identity] = false;
                    }
                    Config.Put($"CustomPresetsOff{i + 1}", togglesOff);
                }

                Config.Save();
            }
        }

        public void LoadPlayerToggles(FargoSoulsPlayer modPlayer)
        {
            RefreshRegistry();
            if (!Initialized || modPlayer == null)
                return;

            foreach (Toggle toggle in Toggles.Values)
                toggle.ToggleBool = toggle.DefaultValue;

            foreach (AccessoryEffect entry in modPlayer.disabledToggles)
            {
                string identity = ResolveKnownIdentity(entry);
                Toggle toggle = identity == null ? null : Toggles.Values.FirstOrDefault(candidate =>
                    string.Equals(candidate.Identity, identity, StringComparison.Ordinal));
                if (toggle != null)
                    toggle.ToggleBool = false;
            }

            modPlayer.TogglesToSync.Clear();
            foreach (KeyValuePair<AccessoryEffect, Toggle> entry in Toggles)
                modPlayer.TogglesToSync[entry.Key] = entry.Value.ToggleBool;
        }

        /*public Dictionary<string, int> UnpackPosition() => new Dictionary<string, int>() {
            { "X", TogglerPosition.X },
            { "Y", TogglerPosition.Y }
        };*/

        public void SetAll(bool value)
        {
            RefreshRegistry();
            if (!Initialized)
                return;
            foreach (Toggle toggle in Toggles.Values)
                toggle.ToggleBool = value;
        }

        private void SetRegistered<T>(bool value) where T : AccessoryEffect
        {
            SetRegistered(ModContent.GetInstance<T>(), value);
        }

        private void SetRegistered(AccessoryEffect effect, bool value)
        {
            if (effect == null || Toggles == null)
                return;
            string identity = ResolveKnownIdentity(effect);
            if (identity == null)
                return;
            foreach (KeyValuePair<AccessoryEffect, Toggle> entry in Toggles)
                if (string.Equals(entry.Value.Identity, identity, StringComparison.Ordinal))
                {
                    entry.Value.ToggleBool = value;
                    return;
                }
        }

        public void SomeEffects()
        {
            RefreshRegistry();
            if (!Initialized)
                return;
            SetAll(true);

            SetRegistered<BorealEffect>(false);
            SetRegistered<ShadewoodEffect>(false);

            SetRegistered<CobaltEffect>(false);
            SetRegistered<AncientCobaltEffect>(false);
            SetRegistered<ObsidianProcEffect>(false);
            SetRegistered<CopperEffect>(false);
            SetRegistered<AshWoodFireballs>(false);

            SetRegistered<GladiatorSpears>(false);
            SetRegistered<RedRidingEffect>(false);

            SetRegistered<BeeEffect>(false);
            SetRegistered<CactusEffect>(false);
            SetRegistered<PumpkinEffect>(false);
            SetRegistered<ChloroMinion>(false);
            SetRegistered<RainUmbrellaEffect>(false);
            SetRegistered<RainInnerTubeEffect>(false);
            SetRegistered<JungleJump>(false);
            SetRegistered<MoltenEffect>(false);
            SetRegistered<ShroomiteShroomEffect>(false);
            SetRegistered<DarkArtistMinion>(false);
            SetRegistered<NecroEffect>(false);
            SetRegistered<ShadowBalls>(false);
            SetRegistered<SpookyEffect>(false);
            SetRegistered<FossilBones>(false);
            SetRegistered<FossilBones>(false);
            SetRegistered<AncientHallowMinion>(false);
            SetRegistered<SpectreEffect>(false);
            SetRegistered<MeteorEffect>(false);
            SetRegistered<ZephyrJump>(false);
            SetRegistered<DevianttHearts>(false);
            SetRegistered<MasoAeolusFlower>(false);
            SetRegistered<SlimyShieldEffect>(false);
            SetRegistered<AgitatingLensEffect>(false);
            SetRegistered<SkeleMinionEffect>(false);
            SetRegistered<MasoCarrotEffect>(false);
            SetRegistered<RainbowSlimeMinion>(false);
            SetRegistered<NymphPerfumeEffect>(false);
            SetRegistered<WretchedPouchEffect>(false);
            SetRegistered<ProbeMinionEffect>(false);
            SetRegistered<GelicWingSpikes>(false);
            //SetRegistered<PungentEyeballCursor>(false);
            SetRegistered<PungentMinion>(false);
            SetRegistered<DeerclawpsEffect>(false);
            //SetRegistered<CultistMinionEffect>(false);
            SetRegistered<LihzahrdBoulders>(false);
            SetRegistered<PlantMinionEffect>(false);
            SetRegistered<CelestialRuneAttacks>(false);

            SetRegistered<UfoMinionEffect>(false);

            SetRegistered<MasoAbom>(false);

            SetRegistered<MasoRing>(false);

            SetRegistered<BuilderEffect>(false);

            SetRegistered<DefenseStarEffect>(false);
            SetRegistered<DefenseBeeEffect>(false);

            SetRegistered<SupersonicClimbing>(false);

            SetRegistered<TrawlerSporeSac>(false);


            foreach (Toggle toggle in Toggles.Values.Where(toggle => toggle.Effect.Name.Contains("Pet")))
            {
                toggle.ToggleBool = false;
            }
        }

        public void MinimalEffects()
        {
            RefreshRegistry();
            if (!Initialized)
                return;
            SetAll(false);

            SetRegistered<MythrilEffect>(true);
            SetRegistered<PalladiumEffect>(true);
            SetRegistered<IronEffect>(true);
            SetRegistered<CthulhuShield>(true);
            //SetRegistered<Tin>(true);
            SetRegistered<BeetleEffect>(true);
            SetRegistered<SpiderEffect>(true);
            SetRegistered<GoldToPiggy>(true);
            SetRegistered<JungleDashEffect>(true);
            SetRegistered<SupersonicTabi>(true);
            SetRegistered<ValhallaDash>(true);
            SetRegistered<SquireMountJump>(true);
            SetRegistered<SquireMountSpeed>(true);
            SetRegistered<NebulaEffect>(true);
            //SetRegistered<SolarEffect>(true);
            SetRegistered<HuntressEffect>(true);
            SetRegistered<CrystalAssassinDash>(true);
            SetRegistered<GladiatorBanner>(true);
            SetRegistered<ChalicePotionEffect>(true);

            SetRegistered<EternityTin>(true);

            SetRegistered<DeerSinewEffect>(true);
            SetRegistered<MasoGraze>(true);
            SetRegistered<SinisterIconDropsEffect>(true);
            SetRegistered<RainbowHealEffect>(true);
            SetRegistered<TribalCharmClickBonus>(true);
            SetRegistered<StabilizedGravity>(true);
            SetRegistered<PrecisionSealHurtbox>(true);

            SetRegistered<AgitatingLensInstall>(true);
            SetRegistered<FusedLensInstall>(true);

            SetRegistered<MiningHunt>(true);
            SetRegistered<MiningDanger>(true);
            SetRegistered<MiningSpelunk>(true);
            SetRegistered<MiningShine>(true);
            SetRegistered<RunSpeed>(true);
            SetRegistered<SupersonicRocketBoots>(true);
            SetRegistered<NoMomentum>(true);
            SetRegistered<MeteorMomentumEffect>(true);
            SetRegistered<FlightMasteryInsignia>(true);
            SetRegistered<FlightMasteryGravity>(true);
            SetRegistered<PaladinShieldEffect>(true);
            SetRegistered<ShimmerImmunityEffect>(true);
            SetRegistered<MasoAeolusFrog>(true);
            SetRegistered<TimsConcoctionEffect>(true);

        }

        public void SaveCustomPreset(int slot)
        {
            RefreshRegistry();
            if (!Initialized || Main.dedServ || slot < 1 || slot > CustomPresetCount)
                return;

            var togglesOff = new List<AccessoryEffect>();
            foreach (KeyValuePair<AccessoryEffect, Toggle> entry in Toggles
                .OrderBy(entry => entry.Value.Identity, StringComparer.Ordinal))
                if (!entry.Value.ToggleBool)
                    togglesOff.Add(entry.Key);

            CustomPresets[slot - 1] = togglesOff;
            //Save(); 
            Main.NewText(Language.GetTextValue("Mods.FargowiltasSouls.UI.SavedToSlot", slot), Color.Yellow);
        }

        public void LoadCustomPreset(int slot)
        {
            RefreshRegistry();
            if (!Initialized || Main.dedServ || slot < 1 || slot > CustomPresetCount)
                return;

            List<AccessoryEffect> togglesOff = CustomPresets[slot - 1];
            if (togglesOff == null)
            {
                Main.NewText(Language.GetTextValue("Mods.FargowiltasSouls.UI.NoTogglesFound", slot), Color.Yellow);
                return;
            }

            FargoSoulsPlayer modPlayer = Main.LocalPlayer.FargoSouls();
            List<AccessoryEffect> previous = modPlayer.disabledToggles;
            try
            {
                modPlayer.disabledToggles = new List<AccessoryEffect>(togglesOff);
                LoadPlayerToggles(modPlayer);
            }
            finally
            {
                modPlayer.disabledToggles = previous;
            }
        }
    }
}
