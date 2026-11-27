using CalamityOverhaul.Content.HackTimes;
using CalamityOverhaul.Content.LegendWeapon.SHPCLegend.Cyberspaces.Banish;
using CalamityOverhaul.Content.LegendWeapon.SHPCLegend.Cyberspaces.DomainFreeze;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace CalamityOverhaul.Content.TimeFreezes
{
    internal enum EntityResolutionResult
    {
        Rejected,
        Applied,
        Queued,
    }

    internal sealed class TimeControlReplicationSystem : ModSystem
    {
        private readonly record struct SnapshotSection(
            byte Id, string Name, Func<BinaryWriter, bool> Write,
            Func<BinaryReader, bool> Read);

        private const uint SnapshotMagic = 0x31524354;
        private const byte SnapshotVersion = 1;
        private const int MaxSnapshotSections = 16;
        private const int MaxSectionBytes = ushort.MaxValue;

        private readonly record struct PendingNPCKey(
            Type SourceType, long ActivationId, NetworkNPCIdentity Identity);

        private readonly record struct PendingProjectileKey(
            Type SourceType, long ActivationId, NetworkProjectileIdentity Identity);

        private sealed record PendingNPC(ulong ExpiresAt, ulong Order, Action<NPC> Apply);
        private sealed record PendingProjectile(ulong ExpiresAt, ulong Order, Action<Projectile> Apply);
        private sealed record PendingBatchItem(ulong Order, Action<ulong, ulong> Process);

        private static readonly Dictionary<PendingNPCKey, PendingNPC> pendingNPCs = [];
        private static readonly Dictionary<PendingProjectileKey, PendingProjectile> pendingProjectiles = [];
        private static ulong nextDropLogFrame;
        private static ulong nextPendingOrder;
        private static ulong worldEpoch;
        private static bool processingPending;
        private static bool sendingSnapshot;
        private static bool receivingSnapshot;

        private static int Capacity => Main.maxNPCs + Main.maxProjectiles;

        internal static EntityResolutionResult ResolveOrQueueNPC<TSource>(
            long activationId, NetworkNPCIdentity identity, int remainingFrames,
            Action<NPC> apply) {
            if (activationId <= 0 || !identity.IsValid || remainingFrames <= 0
                || apply == null) {
                return EntityResolutionResult.Rejected;
            }
            PendingNPCKey key = new(typeof(TSource), activationId, identity);
            if (identity.TryResolve(out NPC npc)) {
                pendingNPCs.Remove(key);
                try {
                    apply(npc);
                    return EntityResolutionResult.Applied;
                } catch (Exception exception) {
                    LogApplyFailure(typeof(TSource), activationId, identity.ToString(), exception);
                    return EntityResolutionResult.Rejected;
                }
            }

            if (pendingNPCs.ContainsKey(key)) {
                pendingNPCs[key] = new PendingNPC(ComputeExpiry(remainingFrames),
                    NextPendingOrder(), apply);
                return EntityResolutionResult.Queued;
            }
            if (!HasCapacity()) {
                LogDrop(typeof(TSource), activationId, identity.ToString());
                return EntityResolutionResult.Rejected;
            }

            pendingNPCs.Add(key, new PendingNPC(
                ComputeExpiry(remainingFrames), NextPendingOrder(), apply));
            return EntityResolutionResult.Queued;
        }

        internal static EntityResolutionResult ResolveOrQueueProjectile<TSource>(
            long activationId, NetworkProjectileIdentity identity, int remainingFrames,
            Action<Projectile> apply) {
            if (activationId <= 0 || !identity.IsValid || remainingFrames <= 0
                || apply == null) {
                return EntityResolutionResult.Rejected;
            }
            PendingProjectileKey key = new(typeof(TSource), activationId, identity);
            if (identity.TryResolve(out Projectile projectile)) {
                pendingProjectiles.Remove(key);
                try {
                    apply(projectile);
                    return EntityResolutionResult.Applied;
                } catch (Exception exception) {
                    LogApplyFailure(typeof(TSource), activationId, identity.ToString(), exception);
                    return EntityResolutionResult.Rejected;
                }
            }

            if (pendingProjectiles.ContainsKey(key)) {
                pendingProjectiles[key] = new PendingProjectile(
                    ComputeExpiry(remainingFrames), NextPendingOrder(), apply);
                return EntityResolutionResult.Queued;
            }
            if (!HasCapacity()) {
                LogDrop(typeof(TSource), activationId, identity.ToString());
                return EntityResolutionResult.Rejected;
            }

            pendingProjectiles.Add(key, new PendingProjectile(
                ComputeExpiry(remainingFrames), NextPendingOrder(), apply));
            return EntityResolutionResult.Queued;
        }

        internal static void Cancel<TSource>(long activationId) {
            Type sourceType = typeof(TSource);
            pendingNPCs.RemoveWhere(pair => pair.Key.SourceType == sourceType
                && pair.Key.ActivationId == activationId);
            pendingProjectiles.RemoveWhere(pair => pair.Key.SourceType == sourceType
                && pair.Key.ActivationId == activationId);
        }

        internal static void CancelNPC<TSource>(long activationId,
            NetworkNPCIdentity identity) {
            pendingNPCs.Remove(new PendingNPCKey(typeof(TSource), activationId,
                identity));
        }

        internal static void CancelProjectile<TSource>(long activationId,
            NetworkProjectileIdentity identity) {
            pendingProjectiles.Remove(new PendingProjectileKey(typeof(TSource),
                activationId, identity));
        }

        internal static void CancelAll<TSource>() {
            Type sourceType = typeof(TSource);
            pendingNPCs.RemoveWhere(pair => pair.Key.SourceType == sourceType);
            pendingProjectiles.RemoveWhere(pair => pair.Key.SourceType == sourceType);
        }

        public override void PreUpdateEntities() {
            if (processingPending) {
                return;
            }

            processingPending = true;
            try {
                ulong startEpoch = worldEpoch;
                ulong now = Main.GameUpdateCount;
                List<PendingBatchItem> batch = [];
                foreach (KeyValuePair<PendingNPCKey, PendingNPC> pair in pendingNPCs) {
                    PendingNPCKey key = pair.Key;
                    PendingNPC pending = pair.Value;
                    batch.Add(new PendingBatchItem(pending.Order,
                        (frame, epoch) => ProcessNPC(key, pending, frame, epoch)));
                }
                foreach (KeyValuePair<PendingProjectileKey, PendingProjectile> pair in pendingProjectiles) {
                    PendingProjectileKey key = pair.Key;
                    PendingProjectile pending = pair.Value;
                    batch.Add(new PendingBatchItem(pending.Order,
                        (frame, epoch) => ProcessProjectile(key, pending, frame, epoch)));
                }
                batch.Sort((left, right) => left.Order.CompareTo(right.Order));
                for (int i = 0; i < batch.Count; i++) {
                    if (worldEpoch != startEpoch) {
                        break;
                    }
                    batch[i].Process(now, startEpoch);
                }
            } finally {
                processingPending = false;
            }
        }

        public override void NetSend(BinaryWriter writer) {
            if (writer == null || Main.netMode != NetmodeID.Server
                || sendingSnapshot) {
                return;
            }

            sendingSnapshot = true;
            try {
                ulong startEpoch = worldEpoch;
                SnapshotSection[] sections = GetSnapshotSections();
                List<(byte Id, byte[] Payload)> serialized = [];
                for (int i = 0; i < sections.Length && i < MaxSnapshotSections; i++) {
                    if (TrySerializeSnapshotSection(sections[i], out byte[] payload)) {
                        serialized.Add((sections[i].Id, payload));
                    }
                    if (worldEpoch != startEpoch
                        || Main.netMode != NetmodeID.Server) {
                        return;
                    }
                }

                writer.Write(SnapshotMagic);
                writer.Write(SnapshotVersion);
                writer.Write((byte)serialized.Count);
                for (int i = 0; i < serialized.Count; i++) {
                    writer.Write(serialized[i].Id);
                    writer.Write((ushort)serialized[i].Payload.Length);
                    writer.Write(serialized[i].Payload);
                }
            } finally {
                sendingSnapshot = false;
            }
        }

        public override void NetReceive(BinaryReader reader) {
            if (reader == null || Main.netMode != NetmodeID.MultiplayerClient
                || receivingSnapshot) {
                return;
            }

            receivingSnapshot = true;
            ulong startEpoch = worldEpoch;
            try {
                if (reader.ReadUInt32() != SnapshotMagic
                    || reader.ReadByte() != SnapshotVersion) {
                    return;
                }

                int count = reader.ReadByte();
                if (count < 0 || count > MaxSnapshotSections) {
                    return;
                }

                Dictionary<byte, SnapshotSection> sections = [];
                SnapshotSection[] known = GetSnapshotSections();
                for (int i = 0; i < known.Length; i++) {
                    sections[known[i].Id] = known[i];
                }

                HashSet<byte> seen = [];
                List<(SnapshotSection Section, byte[] Payload)> parsed = [];
                for (int i = 0; i < count; i++) {
                    byte id = reader.ReadByte();
                    int length = reader.ReadUInt16();
                    if (length > MaxSectionBytes || !seen.Add(id)) {
                        return;
                    }

                    byte[] payload = reader.ReadBytes(length);
                    if (payload.Length != length) {
                        return;
                    }
                    if (!sections.TryGetValue(id, out SnapshotSection section)) {
                        continue;
                    }

                    parsed.Add((section, payload));
                }

                parsed.Sort((left, right) => left.Section.Id.CompareTo(right.Section.Id));
                for (int i = 0; i < parsed.Count; i++) {
                    if (worldEpoch != startEpoch
                        || Main.netMode != NetmodeID.MultiplayerClient) {
                        break;
                    }
                    SnapshotSection section = parsed[i].Section;
                    try {
                        using MemoryStream stream = new(parsed[i].Payload, writable: false);
                        using BinaryReader sectionReader = new(stream,
                            Encoding.UTF8, leaveOpen: false);
                        if (!section.Read(sectionReader) || stream.Position != stream.Length) {
                            throw new InvalidDataException("snapshot section was not fully accepted");
                        }
                    } catch (Exception exception) {
                        LogSnapshotFailure(section.Name, exception);
                    }
                }
            } catch (EndOfStreamException) {
            } catch (IOException) {
            } finally {
                receivingSnapshot = false;
            }
        }

        public override void ClearWorld() => ClearPending();

        public override void OnWorldUnload() => ClearPending();

        private static void ProcessNPC(PendingNPCKey key, PendingNPC snapshot,
            ulong now, ulong startEpoch) {
            if (worldEpoch != startEpoch
                || !pendingNPCs.TryGetValue(key, out PendingNPC pending)
                || !ReferenceEquals(pending, snapshot)) {
                return;
            }
            if (now >= pending.ExpiresAt) {
                pendingNPCs.Remove(key);
                LogDrop(key.SourceType, key.ActivationId, key.Identity.ToString());
                return;
            }
            if (!key.Identity.TryResolve(out NPC npc)) {
                return;
            }
            // Consume the exact start-of-tick record before user code runs. A
            // callback may submit fresher work for any key or entity kind; all
            // such work belongs to a later update.
            pendingNPCs.Remove(key);
            try {
                pending.Apply(npc);
            } catch (Exception exception) {
                CWRMod.Instance?.Logger.Warn(
                    $"Time control NPC apply failed [{key.SourceType.Name}:{key.ActivationId}] {key.Identity}: {exception}");
            }
        }

        private static void ProcessProjectile(PendingProjectileKey key,
            PendingProjectile snapshot, ulong now, ulong startEpoch) {
            if (worldEpoch != startEpoch
                || !pendingProjectiles.TryGetValue(key,
                    out PendingProjectile pending)
                || !ReferenceEquals(pending, snapshot)) {
                return;
            }
            if (now >= pending.ExpiresAt) {
                pendingProjectiles.Remove(key);
                LogDrop(key.SourceType, key.ActivationId, key.Identity.ToString());
                return;
            }
            if (!key.Identity.TryResolve(out Projectile projectile)) {
                return;
            }
            pendingProjectiles.Remove(key);
            try {
                pending.Apply(projectile);
            } catch (Exception exception) {
                CWRMod.Instance?.Logger.Warn(
                    $"Time control projectile apply failed [{key.SourceType.Name}:{key.ActivationId}] {key.Identity}: {exception}");
            }
        }

        private static bool HasCapacity()
            => pendingNPCs.Count + pendingProjectiles.Count < Capacity;

        private static ulong NextPendingOrder() {
            nextPendingOrder++;
            if (nextPendingOrder == 0) {
                nextPendingOrder = 1;
            }
            return nextPendingOrder;
        }

        private static ulong ComputeExpiry(int remainingFrames) {
            int waitFrames = Math.Clamp(remainingFrames, 1, 120);
            ulong now = Main.GameUpdateCount;
            ulong wait = (ulong)waitFrames;
            return SaturatingAdd(now, wait);
        }

        private static ulong SaturatingAdd(ulong value, ulong amount)
            => ulong.MaxValue - value < amount ? ulong.MaxValue : value + amount;

        private static bool IsLogThrottled(ulong now, ulong nextLogFrame)
            => nextLogFrame != 0
                && (nextLogFrame == ulong.MaxValue || now < nextLogFrame);

        private static void LogApplyFailure(Type sourceType, long activationId,
            string identity, Exception exception) {
            CWRMod.Instance?.Logger.Warn(
                $"Time control entity apply failed [{sourceType?.Name}:{activationId}] {identity}: {exception.Message}");
        }

        private static void LogDrop(Type sourceType, long activationId,
            string identity) {
            ulong now = Main.GameUpdateCount;
            if (IsLogThrottled(now, nextDropLogFrame)) {
                return;
            }
            nextDropLogFrame = SaturatingAdd(now, 300);
            CWRMod.Instance?.Logger.Warn(
                $"Time control entity resolution dropped [{sourceType?.Name}:{activationId}] {identity}");
        }

        private static void ClearPending() {
            pendingNPCs.Clear();
            pendingProjectiles.Clear();
            nextPendingOrder = 0;
            worldEpoch++;
            if (worldEpoch == 0) {
                worldEpoch = 1;
            }
            nextDropLogFrame = 0;
            nextSnapshotLogFrame = 0;
        }

        private static SnapshotSection[] GetSnapshotSections() => [
            new(1, "CyberDomainFreeze", CyberDomainFreeze.WriteSnapshot,
                CyberDomainFreeze.ReadSnapshot),
            new(2, "CyberBanish", CyberBanish.WriteSnapshot,
                CyberBanish.ReadSnapshot),
            new(3, "CyberBossExecution", CyberBossExecution.WriteSnapshot,
                CyberBossExecution.ReadSnapshot),
            //中途加入者的骇入队列/效果全量同步
            new(4, "HackEffects", HackTimeNetSync.WriteSnapshot,
                HackTimeNetSync.ReadSnapshot),
        ];

        private static bool TrySerializeSnapshotSection(in SnapshotSection section,
            out byte[] payload) {
            payload = null;
            using MemoryStream stream = new();
            bool success = false;
            Exception failure = null;
            try {
                using (BinaryWriter sectionWriter = new(stream, Encoding.UTF8,
                    leaveOpen: true)) {
                    success = section.Write(sectionWriter);
                    sectionWriter.Flush();
                }
            } catch (Exception exception) {
                failure = exception;
            }

            if (!success || stream.Length > MaxSectionBytes) {
                LogSnapshotFailure(section.Name,
                    failure ?? new InvalidDataException("snapshot section rejected"));
                return false;
            }

            payload = stream.ToArray();
            return true;
        }

        private static ulong nextSnapshotLogFrame;

        private static void LogSnapshotFailure(string section, Exception exception) {
            ulong now = Main.GameUpdateCount;
            if (IsLogThrottled(now, nextSnapshotLogFrame)) {
                return;
            }
            nextSnapshotLogFrame = SaturatingAdd(now, 300);
            CWRMod.Instance?.Logger.Warn(
                $"Time control snapshot rejected [{section}] {exception.Message}");
        }
    }

    internal static class TimeControlPendingDictionaryExtensions
    {
        internal static void RemoveWhere<TKey, TValue>(
            this Dictionary<TKey, TValue> dictionary,
            Func<KeyValuePair<TKey, TValue>, bool> predicate) where TKey : notnull {
            if (dictionary.Count == 0) {
                return;
            }
            List<TKey> removed = [];
            foreach (KeyValuePair<TKey, TValue> pair in dictionary) {
                if (predicate(pair)) {
                    removed.Add(pair.Key);
                }
            }
            for (int i = 0; i < removed.Count; i++) {
                dictionary.Remove(removed[i]);
            }
        }
    }
}
