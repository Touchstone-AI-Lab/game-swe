global using Microsoft.Xna.Framework;
global using Microsoft.Xna.Framework.Graphics;
global using ReLogic.Content;
global using StarlightRiver;
global using Terraria;
global using Terraria.ModLoader;

using System;
using System.Collections.Generic;
using System.IO;
using StarlightRiver.Content.Abilities;

namespace Microsoft.Xna.Framework
{
    public struct Color { public static Color White => new(); }
    public struct Vector2
    {
        public float X; public float Y;
        public float LengthSquared() => X * X + Y * Y;
    }
    public static class MathHelper
    {
        public static float Clamp(float value, float min, float max) => Math.Min(Math.Max(value, min), max);
    }
}

namespace Microsoft.Xna.Framework.Graphics
{
    public sealed class Texture2D { }
    public sealed class SpriteBatch { }
}

namespace ReLogic.Content
{
    public sealed class Asset<T> where T : class { public T Value { get; set; } }
}

namespace Terraria.GameInput
{
    public sealed class TriggersSet { public string Pressed { get; set; } = ""; }
}

namespace Terraria.DataStructures
{
    public struct PlayerDrawSet { }
}

namespace Terraria.ID
{
    public static class NetmodeID { public const int SinglePlayer = 0; public const int MultiplayerClient = 1; public const int Server = 2; }
    public static class MessageID { public const int PlayerControls = 13; }
}

namespace Terraria
{
    public sealed class LocalizedText { public string Value { get; set; } = ""; }
    public static class Language { public static LocalizedText GetText(string key) => new() { Value = key }; }

    public sealed class Item
    {
        public static readonly Dictionary<int, Func<Terraria.ModLoader.ModItem>> Factories = new();
        public int type;
        public int stack;
        public int playerIndexTheItemIsReservedFor;
        public Terraria.ModLoader.ModItem ModItem { get; set; }
        public bool IsAir => type == 0;

        public Item() { }
        public Item(int type) => SetDefaults(type);

        public void SetDefaults(int value)
        {
            type = value;
            if (value == 0) { ModItem = null; return; }
            if (!Factories.TryGetValue(value, out var factory)) { ModItem = null; return; }
            ModItem = factory();
            ModItem.Item = this;
        }

        public Item Clone()
        {
            var clone = new Item { type = type, stack = stack, playerIndexTheItemIsReservedFor = playerIndexTheItemIsReservedFor };
            if (type != 0 && Factories.TryGetValue(type, out var factory))
            {
                clone.ModItem = factory();
                clone.ModItem.Item = clone;
            }
            return clone;
        }
    }

    public sealed class Player
    {
        private readonly Dictionary<Type, Terraria.ModLoader.ModPlayer> players = new();
        public int whoAmI;
        public bool noItems;
        public bool noBuilding;
        public bool canRocket;
        public int rocketBoots;
        public int wings;
        public Vector2 velocity;

        public T GetModPlayer<T>() where T : Terraria.ModLoader.ModPlayer, new()
        {
            if (!players.TryGetValue(typeof(T), out var value))
            {
                value = new T { Player = this };
                players[typeof(T)] = value;
            }
            return (T)value;
        }

        public void SetModPlayer<T>(T value) where T : Terraria.ModLoader.ModPlayer
        {
            value.Player = this;
            players[typeof(T)] = value;
        }
    }

    public static class Main
    {
        public static int netMode;
        public static bool gameMenu;
        public static Player[] player = Array.Empty<Player>();
        public static Player LocalPlayer { get; set; }
    }

    public static class NetMessage
    {
        public static readonly List<(int Message, int Number)> Sent = new();
        public static void SendData(int messageType, int remoteClient = -1, int ignoreClient = -1, object text = null, int number = 0) => Sent.Add((messageType, number));
    }
}

namespace Terraria.ModLoader
{
    public abstract class ModItem { public Terraria.Item Item { get; set; } = new(); }

    public class ModPlayer
    {
        public Terraria.Player Player { get; set; } = new();
        public virtual bool CloneNewInstances => true;
        public virtual void Load() { }
        public virtual void Unload() { }
        public virtual void SaveData(Terraria.ModLoader.IO.TagCompound tag) { }
        public virtual void LoadData(Terraria.ModLoader.IO.TagCompound tag) { }
        public virtual void ResetEffects() { }
        public virtual void UpdateDead() { }
        public virtual void OnRespawn() { }
        public virtual void ProcessTriggers(Terraria.GameInput.TriggersSet triggersSet) { }
        public virtual void PreUpdate() { }
        public virtual void OnEnterWorld() { }
        public virtual void ModifyDrawInfo(ref Terraria.DataStructures.PlayerDrawSet drawInfo) { }
        public virtual ModPlayer Clone(Terraria.Player newEntity) { var clone = (ModPlayer)MemberwiseClone(); clone.Player = newEntity; return clone; }
        public virtual void CopyClientState(ModPlayer clientClone) { }
    }
}

namespace Terraria.ModLoader.IO
{
    public sealed class TagCompound : Dictionary<string, object>
    {
        public IList<T> GetList<T>(string key) => TryGetValue(key, out var raw) && raw is IList<T> list ? list : new List<T>();
        public int GetInt(string key) => TryGetValue(key, out var raw) && raw is int value ? value : 0;
    }
}

namespace NetEasy
{
    [Serializable]
    public abstract class Module
    {
        public static readonly List<(Module Packet, int To, int Ignore, bool RunLocally)> Sends = new();
        public int Sender { get; set; } = -1;
        public void Send(int to = -1, int ignore = -1, bool runLocally = true) => Sends.Add((this, to, ignore, runLocally));
        public void InvokeReceive() => Receive();
        protected abstract void Receive();
    }
}

namespace StarlightRiver
{
    public interface IOrderedLoadable { float Priority { get; } void Load(); void Unload(); }
    public sealed class TestLogger { public readonly List<string> DebugMessages = new(); public void Debug(string message) => DebugMessages.Add(message); }
    public sealed class StarlightRiver
    {
        public static StarlightRiver Instance { get; } = new();
        public global::StarlightRiver.Content.Abilities.AbilityHotkeys AbilityKeys { get; } = new();
        public TestLogger Logger { get; } = new();
    }
    public static class AssetDirectory { public const string Debug = "Debug"; }
    public sealed class StarlightPlayer
    {
        public static Action<Terraria.Player, SpriteBatch> PostDrawEvent;
        public static void ClearEvents() => PostDrawEvent = null;
    }
    public static class PlayerExtensions
    {
        public static AbilityHandler GetHandler(this Terraria.Player player) => player.GetModPlayer<AbilityHandler>();
    }
}

namespace StarlightRiver.Content.GUI { public static class Infusion { public const int InfusionSlots = 3; } }

namespace StarlightRiver.Content.Abilities
{
    public sealed class AbilityHotkeys { }

    public abstract class TrackedAbility : Ability
    {
        private static readonly Asset<Texture2D> texture = new() { Value = new() };
        public static int ActivationInvocations; public static int ResetInvocations;
        public int Activated; public int Deactivated; public int Exited; public int ResetCount; public int FixedUpdates; public int ActiveUpdates; public int EffectUpdates; public int DrawUpdates;
        public Action<TrackedAbility> ActivateCallback;
        public Action<TrackedAbility> DeactivateCallback;
        public Action<TrackedAbility> ExitCallback;
        public Action<TrackedAbility> ResetCallback;
        public Action<TrackedAbility> FixedCallback;
        public Action<TrackedAbility> ActiveCallback;
        public Action<TrackedAbility> EffectCallback;
        public Action<TrackedAbility> DrawCallback;
        public override Asset<Texture2D> Texture => texture;
        public override Asset<Texture2D> PreviewTexture => texture;
        public override Asset<Texture2D> PreviewTextureOff => texture;
        public override bool HotKeyMatch(Terraria.GameInput.TriggersSet triggers, AbilityHotkeys abilityKeys) => triggers.Pressed == GetType().Name;
        public override void Reset() { ResetCount++; ResetInvocations++; ResetCallback?.Invoke(this); }
        public override void OnActivate() { Activated++; ActivationInvocations++; ActivateCallback?.Invoke(this); }
        public override void OnDeactivate() { Deactivated++; DeactivateCallback?.Invoke(this); }
        public override void OnExit() { Exited++; ExitCallback?.Invoke(this); }
        public override void UpdateFixed() { FixedUpdates++; FixedCallback?.Invoke(this); }
        public override void UpdateActive() { ActiveUpdates++; ActiveCallback?.Invoke(this); }
        public override void UpdateActiveEffects() { EffectUpdates++; EffectCallback?.Invoke(this); }
        public override void DrawActiveEffects(SpriteBatch spriteBatch) { DrawUpdates++; DrawCallback?.Invoke(this); }
    }

    public sealed class TestAbility : TrackedAbility { public override float ActivationCostDefault => 1; }
    public sealed class ExpensiveAbility : TrackedAbility { public override float ActivationCostDefault => 100; }
    public sealed class NegativeCostAbility : TrackedAbility { public override float ActivationCostDefault => -5; }
    public sealed class NonFiniteCostAbility : TrackedAbility { public override float ActivationCostDefault => float.NaN; }
    public sealed class ThrowingAbility : TrackedAbility
    {
        public ThrowingAbility() => throw new InvalidOperationException("constructor failed");
        public override float ActivationCostDefault => 1;
    }

    public sealed class DashInfusion : InfusionItem { public DashInfusion() => ability = new ForbiddenWinds.Dash(); public override InfusionTier Tier => InfusionTier.Bronze; public override Type AbilityType => typeof(global::StarlightRiver.Content.Abilities.ForbiddenWinds.Dash); }
    public sealed class AlternateDashInfusion : InfusionItem { public AlternateDashInfusion() => ability = new ForbiddenWinds.Dash(); public override InfusionTier Tier => InfusionTier.Silver; public override Type AbilityType => typeof(global::StarlightRiver.Content.Abilities.ForbiddenWinds.Dash); }
    public sealed class WhipInfusion : InfusionItem { public WhipInfusion() => ability = new Faewhip.Whip(); public override InfusionTier Tier => InfusionTier.Gold; public override Type AbilityType => typeof(global::StarlightRiver.Content.Abilities.Faewhip.Whip); }
    public sealed class UnequippableInfusion : InfusionItem { public override InfusionTier Tier => InfusionTier.Untiered; public override bool Equippable => false; }
    public sealed class PlainModItem : Terraria.ModLoader.ModItem { }
}

namespace StarlightRiver.Content.Abilities.Hint { public sealed class HintAbility : global::StarlightRiver.Content.Abilities.TrackedAbility { public override float ActivationCostDefault => 0; } }
namespace StarlightRiver.Content.Abilities.ForbiddenWinds { public sealed class Dash : global::StarlightRiver.Content.Abilities.TrackedAbility { public override float ActivationCostDefault => 1; } }
namespace StarlightRiver.Content.Abilities.Faewhip { public sealed class Whip : global::StarlightRiver.Content.Abilities.TrackedAbility { public override float ActivationCostDefault => 2; } }

namespace GameCodeBench
{
    public static class TestHooks
    {
        public static void Reset()
        {
            Terraria.Main.netMode = Terraria.ID.NetmodeID.SinglePlayer;
            Terraria.Main.gameMenu = false;
            Terraria.Main.player = new Terraria.Player[8];
            for (int i = 0; i < Terraria.Main.player.Length; i++) Terraria.Main.player[i] = new Terraria.Player { whoAmI = i };
            Terraria.Main.LocalPlayer = Terraria.Main.player[0];
            Terraria.NetMessage.Sent.Clear();
            NetEasy.Module.Sends.Clear();
            Terraria.Item.Factories.Clear();
            Terraria.Item.Factories[10] = () => new DashInfusion();
            Terraria.Item.Factories[11] = () => new AlternateDashInfusion();
            Terraria.Item.Factories[12] = () => new WhipInfusion();
            Terraria.Item.Factories[13] = () => new UnequippableInfusion();
            Terraria.Item.Factories[14] = () => throw new InvalidOperationException("item clone failed");
            Terraria.Item.Factories[15] = () => new PlainModItem();
            StarlightRiver.StarlightRiver.Instance.Logger.DebugMessages.Clear();
            StarlightRiver.StarlightPlayer.ClearEvents();
        }
    }
}
