using System;
using System.Collections.Generic;

namespace Microsoft.Xna.Framework
{
    public readonly struct Color
    {
        public static Color White => new();
        public static Color Yellow => new();
    }
}

namespace Terraria.UI.Chat
{
    public class TextSnippet { public string Text { get; set; } = ""; }
    public static class ChatManager
    {
        public static List<TextSnippet> ParseMessage(string text, Microsoft.Xna.Framework.Color color) =>
            [new TextSnippet { Text = text ?? "" }];
    }
}

namespace Terraria
{
    public class Player
    {
        public FargowiltasSouls.FargoSoulsPlayer Souls { get; set; } = new();
    }

    public static class Main
    {
        public static string SavePath = "/save";
        public static bool dedServ;
        public static Player LocalPlayer = new();
        public static readonly List<string> Messages = [];
        public static void NewText(string text, Microsoft.Xna.Framework.Color color) => Messages.Add(text);
    }
}

namespace Terraria.IO
{
    public class Preferences
    {
        public static bool NextLoadResult = true;
        public static Dictionary<string, object> NextData = [];
        public static HashSet<string> ThrowOnGet = [];
        public static int TotalSaves;

        public string Path { get; }
        public Dictionary<string, object> Data { get; } = [];
        public int SaveCount { get; private set; }

        public Preferences(string path)
        {
            Path = path;
            foreach (var entry in NextData)
                Data[entry.Key] = entry.Value;
        }

        public bool Load() => NextLoadResult;

        public T Get<T>(string key, T defaultValue)
        {
            if (ThrowOnGet.Contains(key))
                throw new InvalidOperationException("malformed preference");
            return Data.TryGetValue(key, out object value) ? (T)value : defaultValue;
        }

        public void Put<T>(string key, T value) => Data[key] = value;

        public void Save()
        {
            SaveCount++;
            TotalSaves++;
        }
    }
}

namespace Terraria.Localization
{
    public static class Language
    {
        public static string GetTextValue(string key, object arg) => $"{key}:{arg}";
    }
}

namespace Terraria.ModLoader
{
    public static class ModContent
    {
        private static readonly Dictionary<Type, object> Instances = [];
        public static T GetInstance<T>() where T : class
        {
            Type type = typeof(T);
            if (!Instances.TryGetValue(type, out object value))
                Instances[type] = value = Activator.CreateInstance(type);
            return (T)value;
        }
        public static void Reset() => Instances.Clear();
    }
}

namespace FargowiltasSouls.Core.AccessoryEffectSystem
{
    public class Header
    {
        public string SortCategory { get; set; } = "General";
    }

    public class AccessoryEffect
    {
        public virtual string Name => GetType().Name;
        public virtual string FullName => GetType().FullName ?? Name;
        public virtual Header ToggleHeader { get; set; } = new();
        public virtual string ToggleDescription => Name;
        public virtual bool DefaultToggle => true;
        public virtual bool MutantsPresenceAffects => false;
        public virtual bool MinionEffect => false;
    }
}

namespace FargowiltasSouls
{
    using global::FargowiltasSouls.Core.AccessoryEffectSystem;
    using global::FargowiltasSouls.Core.Toggler;

    public sealed class TestLogger
    {
        public readonly List<string> Warnings = [];
        public void Warn(string message) => Warnings.Add(message);
    }

    public sealed class FargowiltasSouls
    {
        public static FargowiltasSouls Instance { get; } = new();
        public TestLogger Logger { get; } = new();
    }

    public class FargoSoulsPlayer
    {
        public List<AccessoryEffect> disabledToggles = [];
        public Dictionary<AccessoryEffect, bool> TogglesToSync = [];
        public ToggleBackend Toggler = new();
        public bool MutantPresence;
    }

    public static class PlayerExtensions
    {
        public static FargoSoulsPlayer FargoSouls(this Terraria.Player player) => player?.Souls;
    }
}

namespace FargowiltasSouls.Content.Items.Accessories.Masomode { public sealed class NamespaceMarker { } }
namespace FargowiltasSouls.Content.Items.Accessories.Souls { public sealed class NamespaceMarker { } }
namespace FargowiltasSouls.Content.Items.Armor { public sealed class NamespaceMarker { } }
namespace FargowiltasSouls.Content.Items.Consumables { public sealed class NamespaceMarker { } }

namespace FargowiltasSouls.Content.Items.Accessories.Enchantments
{
    using global::FargowiltasSouls.Core.AccessoryEffectSystem;
    public class AgitatingLensEffect : AccessoryEffect { }
    public class AgitatingLensInstall : AccessoryEffect { }
    public class AncientCobaltEffect : AccessoryEffect { }
    public class AncientHallowMinion : AccessoryEffect { }
    public class AshWoodFireballs : AccessoryEffect { }
    public class BeeEffect : AccessoryEffect { }
    public class BeetleEffect : AccessoryEffect { }
    public class BorealEffect : AccessoryEffect { }
    public class BuilderEffect : AccessoryEffect { }
    public class CactusEffect : AccessoryEffect { }
    public class CelestialRuneAttacks : AccessoryEffect { }
    public class ChalicePotionEffect : AccessoryEffect { }
    public class ChloroMinion : AccessoryEffect { }
    public class CobaltEffect : AccessoryEffect { }
    public class CopperEffect : AccessoryEffect { }
    public class CrystalAssassinDash : AccessoryEffect { }
    public class CthulhuShield : AccessoryEffect { }
    public class DarkArtistMinion : AccessoryEffect { }
    public class DeerclawpsEffect : AccessoryEffect { }
    public class DeerSinewEffect : AccessoryEffect { }
    public class DefenseBeeEffect : AccessoryEffect { }
    public class DefenseStarEffect : AccessoryEffect { }
    public class DevianttHearts : AccessoryEffect { }
    public class EternityTin : AccessoryEffect { }
    public class FlightMasteryGravity : AccessoryEffect { }
    public class FlightMasteryInsignia : AccessoryEffect { }
    public class FossilBones : AccessoryEffect { }
    public class FusedLensInstall : AccessoryEffect { }
    public class GelicWingSpikes : AccessoryEffect { }
    public class GladiatorBanner : AccessoryEffect { }
    public class GladiatorSpears : AccessoryEffect { }
    public class GoldToPiggy : AccessoryEffect { }
    public class HuntressEffect : AccessoryEffect { }
    public class IronEffect : AccessoryEffect { }
    public class JungleDashEffect : AccessoryEffect { }
    public class JungleJump : AccessoryEffect { }
    public class LihzahrdBoulders : AccessoryEffect { }
    public class MasoAbom : AccessoryEffect { }
    public class MasoAeolusFlower : AccessoryEffect { }
    public class MasoAeolusFrog : AccessoryEffect { }
    public class MasoCarrotEffect : AccessoryEffect { }
    public class MasoGraze : AccessoryEffect { }
    public class MasoRing : AccessoryEffect { }
    public class MeteorEffect : AccessoryEffect { }
    public class MeteorMomentumEffect : AccessoryEffect { }
    public class MiningDanger : AccessoryEffect { }
    public class MiningHunt : AccessoryEffect { }
    public class MiningShine : AccessoryEffect { }
    public class MiningSpelunk : AccessoryEffect { }
    public class MoltenEffect : AccessoryEffect { }
    public class MythrilEffect : AccessoryEffect { }
    public class NebulaEffect : AccessoryEffect { }
    public class NecroEffect : AccessoryEffect { }
    public class NoMomentum : AccessoryEffect { }
    public class NymphPerfumeEffect : AccessoryEffect { }
    public class ObsidianProcEffect : AccessoryEffect { }
    public class PaladinShieldEffect : AccessoryEffect { }
    public class PalladiumEffect : AccessoryEffect { }
    public class PlantMinionEffect : AccessoryEffect { }
    public class PrecisionSealHurtbox : AccessoryEffect { }
    public class ProbeMinionEffect : AccessoryEffect { }
    public class PumpkinEffect : AccessoryEffect { }
    public class PungentMinion : AccessoryEffect { }
    public class RainbowHealEffect : AccessoryEffect { }
    public class RainbowSlimeMinion : AccessoryEffect { }
    public class RainInnerTubeEffect : AccessoryEffect { }
    public class RainUmbrellaEffect : AccessoryEffect { }
    public class RedRidingEffect : AccessoryEffect { }
    public class RunSpeed : AccessoryEffect { }
    public class ShadewoodEffect : AccessoryEffect { }
    public class ShadowBalls : AccessoryEffect { }
    public class ShimmerImmunityEffect : AccessoryEffect { }
    public class ShroomiteShroomEffect : AccessoryEffect { }
    public class SinisterIconDropsEffect : AccessoryEffect { }
    public class SkeleMinionEffect : AccessoryEffect { }
    public class SlimyShieldEffect : AccessoryEffect { }
    public class SpectreEffect : AccessoryEffect { }
    public class SpiderEffect : AccessoryEffect { }
    public class SpookyEffect : AccessoryEffect { }
    public class SquireMountJump : AccessoryEffect { }
    public class SquireMountSpeed : AccessoryEffect { }
    public class StabilizedGravity : AccessoryEffect { }
    public class SupersonicClimbing : AccessoryEffect { }
    public class SupersonicRocketBoots : AccessoryEffect { }
    public class SupersonicTabi : AccessoryEffect { }
    public class TimsConcoctionEffect : AccessoryEffect { }
    public class TrawlerSporeSac : AccessoryEffect { }
    public class TribalCharmClickBonus : AccessoryEffect { }
    public class UfoMinionEffect : AccessoryEffect { }
    public class ValhallaDash : AccessoryEffect { }
    public class WretchedPouchEffect : AccessoryEffect { }
    public class ZephyrJump : AccessoryEffect { }
}

namespace GameCodeBench
{
    public static class TestHooks
    {
        public static void Reset()
        {
            Terraria.Main.dedServ = false;
            Terraria.Main.LocalPlayer = new Terraria.Player();
            Terraria.Main.Messages.Clear();
            Terraria.IO.Preferences.NextLoadResult = true;
            Terraria.IO.Preferences.NextData = [];
            Terraria.IO.Preferences.ThrowOnGet = [];
            Terraria.IO.Preferences.TotalSaves = 0;
            Terraria.ModLoader.ModContent.Reset();
            global::FargowiltasSouls.FargowiltasSouls.Instance.Logger.Warnings.Clear();
            global::FargowiltasSouls.Core.Toggler.ToggleLoader.Load();
        }
    }
}
