using System;
using System.Collections.Generic;
using System.IO;

namespace Terraria.ID
{
    public static class NetmodeID
    {
        public const int SinglePlayer = 0;
        public const int MultiplayerClient = 1;
        public const int Server = 2;
    }

    public static class NPCID { public const int None = 0; }
    public static class ProjectileID { public const int None = 0; }
}

namespace Terraria.ModLoader
{
    public abstract class ModSystem
    {
        public virtual void PreUpdateEntities() { }
        public virtual void NetSend(BinaryWriter writer) { }
        public virtual void NetReceive(BinaryReader reader) { }
        public virtual void ClearWorld() { }
        public virtual void OnWorldUnload() { }
    }

    public static class NPCLoader { public static int NPCCount = 1000; }
    public static class ProjectileLoader { public static int ProjectileCount = 1000; }
}

namespace Terraria
{
    public static class Main
    {
        public static int maxNPCs = 8;
        public static int maxProjectiles = 8;
        public static int maxPlayers = 8;
        public static NPC[] npc = new NPC[maxNPCs];
        public static Projectile[] projectile = new Projectile[maxProjectiles];
        public static ulong GameUpdateCount;
        public static int netMode = ID.NetmodeID.SinglePlayer;
    }

    public sealed class NPC
    {
        private readonly Dictionary<Type, object> globals = [];
        public bool active;
        public int whoAmI;
        public int type;

        public T GetGlobalNPC<T>() where T : new()
        {
            Type key = typeof(T);
            if (!globals.TryGetValue(key, out object value))
                globals[key] = value = new T();
            return (T)value;
        }
    }

    public sealed class Projectile
    {
        public bool active;
        public int owner;
        public int identity;
        public int type;
    }
}

namespace CalamityOverhaul
{
    public sealed class TestLogger
    {
        public readonly List<string> Warnings = [];
        public void Warn(string message) => Warnings.Add(message);
    }

    public sealed class CWRMod
    {
        public static CWRMod Instance { get; set; } = new();
        public TestLogger Logger { get; } = new();
    }
}

namespace CalamityOverhaul.Content.TimeFreezes
{
    internal sealed class TimeFreezeNPC
    {
        private static ulong nextGeneration;
        internal ulong NetworkGeneration { get; set; }

        internal ulong EnsureNetworkGeneration(Terraria.NPC npc)
        {
            if (NetworkGeneration == 0)
            {
                nextGeneration++;
                if (nextGeneration == 0) nextGeneration = 1;
                NetworkGeneration = nextGeneration;
            }
            return NetworkGeneration;
        }

        internal static void Reset() => nextGeneration = 0;
    }
}

namespace GameCodeBench
{
    public enum SnapshotWriteMode { Success, ReturnFalse, Throw }
    public enum SnapshotReadMode { Success, ReturnFalse, Throw }

    public static class SnapshotHarness
    {
        public static readonly Dictionary<int, SnapshotWriteMode> WriteModes = [];
        public static readonly Dictionary<int, SnapshotReadMode> ReadModes = [];
        public static readonly Dictionary<int, int> WriteSizes = [];
        public static readonly Dictionary<int, Action<BinaryWriter>> WriteHooks = [];
        public static readonly Dictionary<int, Action<BinaryReader>> ReadHooks = [];
        public static readonly List<int> ReadAttempts = [];
        public static readonly List<int> Applied = [];

        public static bool Write(int id, BinaryWriter writer)
        {
            if (WriteHooks.TryGetValue(id, out Action<BinaryWriter> hook)) hook(writer);
            SnapshotWriteMode mode = WriteModes.TryGetValue(id, out var value) ? value : SnapshotWriteMode.Success;
            if (mode == SnapshotWriteMode.Throw) throw new InvalidOperationException($"write {id}");
            if (mode == SnapshotWriteMode.ReturnFalse) return false;
            int size = WriteSizes.TryGetValue(id, out int configured) ? configured : 1;
            writer.Write(new byte[size]);
            return true;
        }

        public static bool Read(int id, BinaryReader reader)
        {
            ReadAttempts.Add(id);
            if (ReadHooks.TryGetValue(id, out Action<BinaryReader> hook)) hook(reader);
            SnapshotReadMode mode = ReadModes.TryGetValue(id, out var value) ? value : SnapshotReadMode.Success;
            if (mode == SnapshotReadMode.Throw) throw new InvalidDataException($"read {id}");
            if (mode == SnapshotReadMode.ReturnFalse) return false;
            reader.ReadBytes(checked((int)(reader.BaseStream.Length - reader.BaseStream.Position)));
            Applied.Add(id);
            return true;
        }

        public static void Reset()
        {
            WriteModes.Clear();
            ReadModes.Clear();
            WriteSizes.Clear();
            WriteHooks.Clear();
            ReadHooks.Clear();
            ReadAttempts.Clear();
            Applied.Clear();
        }
    }

    public static class TestHooks
    {
        public static void Reset()
        {
            Terraria.Main.maxNPCs = 8;
            Terraria.Main.maxProjectiles = 8;
            Terraria.Main.maxPlayers = 8;
            Terraria.Main.npc = new Terraria.NPC[8];
            Terraria.Main.projectile = new Terraria.Projectile[8];
            Terraria.Main.GameUpdateCount = 0;
            Terraria.Main.netMode = Terraria.ID.NetmodeID.SinglePlayer;
            Terraria.ModLoader.NPCLoader.NPCCount = 1000;
            Terraria.ModLoader.ProjectileLoader.ProjectileCount = 1000;
            CalamityOverhaul.CWRMod.Instance = new CalamityOverhaul.CWRMod();
            CalamityOverhaul.Content.TimeFreezes.TimeFreezeNPC.Reset();
            SnapshotHarness.Reset();
            new CalamityOverhaul.Content.TimeFreezes.TimeControlReplicationSystem().ClearWorld();
        }
    }
}

namespace CalamityOverhaul.Content.LegendWeapon.SHPCLegend.Cyberspaces.DomainFreeze
{
    internal static class CyberDomainFreeze
    {
        internal static bool WriteSnapshot(BinaryWriter writer) => GameCodeBench.SnapshotHarness.Write(1, writer);
        internal static bool ReadSnapshot(BinaryReader reader) => GameCodeBench.SnapshotHarness.Read(1, reader);
    }
}

namespace CalamityOverhaul.Content.LegendWeapon.SHPCLegend.Cyberspaces.Banish
{
    internal static class CyberBanish
    {
        internal static bool WriteSnapshot(BinaryWriter writer) => GameCodeBench.SnapshotHarness.Write(2, writer);
        internal static bool ReadSnapshot(BinaryReader reader) => GameCodeBench.SnapshotHarness.Read(2, reader);
    }

    internal static class CyberBossExecution
    {
        internal static bool WriteSnapshot(BinaryWriter writer) => GameCodeBench.SnapshotHarness.Write(3, writer);
        internal static bool ReadSnapshot(BinaryReader reader) => GameCodeBench.SnapshotHarness.Read(3, reader);
    }
}

namespace CalamityOverhaul.Content.HackTimes
{
    internal static class HackTimeNetSync
    {
        internal static bool WriteSnapshot(BinaryWriter writer) => GameCodeBench.SnapshotHarness.Write(4, writer);
        internal static bool ReadSnapshot(BinaryReader reader) => GameCodeBench.SnapshotHarness.Read(4, reader);
    }
}
