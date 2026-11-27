using System;
using System.Collections.Generic;
using System.IO;
using Terraria;
using Terraria.ModLoader;

namespace CalamityOverhaul
{
    internal sealed class EngineLogger
    {
        internal void Warn(string message) { }
    }

    internal sealed class CWRMod
    {
        internal static CWRMod Instance { get; } = new();
        internal EngineLogger Logger { get; } = new();
    }
}

namespace CalamityOverhaul.Content.TimeFreezes
{
    internal sealed class TimeFreezeNPC : GlobalNPC
    {
        private static ulong nextGeneration;
        public override bool InstancePerEntity => true;
        internal ulong NetworkGeneration { get; set; }

        internal ulong EnsureNetworkGeneration(NPC npc)
        {
            if (NetworkGeneration == 0)
            {
                nextGeneration++;
                if (nextGeneration == 0) nextGeneration = 1;
                NetworkGeneration = nextGeneration;
            }
            return NetworkGeneration;
        }
    }
}

namespace GcbCalamityTime
{
    internal enum SnapshotWriteMode { Success, ReturnFalse, Throw }

    internal static class SnapshotHarness
    {
        internal static readonly Dictionary<int, SnapshotWriteMode> WriteModes = new();

        internal static bool Write(int id, BinaryWriter writer)
        {
            SnapshotWriteMode mode = WriteModes.TryGetValue(id, out SnapshotWriteMode value)
                ? value : SnapshotWriteMode.Success;
            if (mode == SnapshotWriteMode.Throw) throw new InvalidOperationException($"write {id}");
            if (mode == SnapshotWriteMode.ReturnFalse) return false;
            writer.Write((byte)id);
            return true;
        }
    }
}

namespace CalamityOverhaul.Content.LegendWeapon.SHPCLegend.Cyberspaces.DomainFreeze
{
    internal static class CyberDomainFreeze
    {
        internal static bool WriteSnapshot(BinaryWriter writer) => GcbCalamityTime.SnapshotHarness.Write(1, writer);
        internal static bool ReadSnapshot(BinaryReader reader) => true;
    }
}

namespace CalamityOverhaul.Content.LegendWeapon.SHPCLegend.Cyberspaces.Banish
{
    internal static class CyberBanish
    {
        internal static bool WriteSnapshot(BinaryWriter writer) => GcbCalamityTime.SnapshotHarness.Write(2, writer);
        internal static bool ReadSnapshot(BinaryReader reader) => true;
    }

    internal static class CyberBossExecution
    {
        internal static bool WriteSnapshot(BinaryWriter writer) => GcbCalamityTime.SnapshotHarness.Write(3, writer);
        internal static bool ReadSnapshot(BinaryReader reader) => true;
    }
}

namespace CalamityOverhaul.Content.HackTimes
{
    internal static class HackTimeNetSync
    {
        internal static bool WriteSnapshot(BinaryWriter writer) => GcbCalamityTime.SnapshotHarness.Write(4, writer);
        internal static bool ReadSnapshot(BinaryReader reader) => true;
    }
}
