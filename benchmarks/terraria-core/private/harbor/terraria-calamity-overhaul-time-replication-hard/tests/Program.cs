using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using CalamityOverhaul;
using CalamityOverhaul.Content.TimeFreezes;
using GameCodeBench;
using Terraria;
using Terraria.ID;

internal static class ContractProgram
{
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["npc_identity_rejects_wire_sentinel_index"] = NpcSentinel,
        ["npc_capture_assigns_generation"] = NpcCaptureGeneration,
        ["npc_capture_rejects_inactive"] = NpcCaptureInactive,
        ["npc_capture_rejects_unencodable_index"] = NpcCaptureUnencodable,
        ["npc_resolve_requires_generation"] = NpcResolveGeneration,
        ["npc_resolve_handles_short_array"] = NpcResolveShortArray,
        ["npc_invalid_write_is_canonical"] = NpcInvalidWrite,
        ["npc_codec_roundtrips"] = NpcRoundtrip,
        ["npc_codec_truncation_is_safe"] = NpcTruncated,
        ["npc_codec_unreadable_is_safe"] = NpcUnreadable,

        ["projectile_owner_upper_bound_is_exclusive"] = ProjectileOwnerBound,
        ["projectile_capture_rejects_inactive"] = ProjectileCaptureInactive,
        ["projectile_capture_rejects_unencodable_owner"] = ProjectileCaptureUnencodable,
        ["projectile_resolve_matches_exact_identity"] = ProjectileResolveExact,
        ["projectile_resolve_rejects_ambiguity"] = ProjectileResolveAmbiguous,
        ["projectile_resolve_handles_short_array"] = ProjectileResolveShortArray,
        ["projectile_invalid_write_is_canonical"] = ProjectileInvalidWrite,
        ["projectile_codec_roundtrips"] = ProjectileRoundtrip,
        ["projectile_codec_truncation_is_safe"] = ProjectileTruncated,
        ["projectile_codec_unreadable_is_safe"] = ProjectileUnreadable,

        ["npc_queue_rejects_nonpositive_activation"] = NpcQueueActivation,
        ["npc_queue_rejects_nonpositive_lifetime"] = NpcQueueLifetime,
        ["npc_queue_rejects_null_callback"] = NpcQueueNullCallback,
        ["npc_queue_applies_resolved_entity_immediately"] = NpcQueueImmediate,
        ["npc_queue_contains_immediate_callback_failure"] = NpcQueueImmediateFailure,
        ["npc_queue_applies_late_entity_once"] = NpcQueueLate,
        ["npc_queue_duplicate_refreshes_latest_work"] = NpcQueueRefresh,
        ["npc_immediate_request_consumes_older_pending"] = NpcImmediateSupersedes,
        ["npc_throwing_immediate_request_consumes_older_pending"] = NpcImmediateThrowSupersedes,
        ["npc_late_callback_preserves_reentrant_refresh"] = NpcQueueReentrantRefresh,

        ["projectile_queue_applies_resolved_entity_immediately"] = ProjectileQueueImmediate,
        ["projectile_queue_contains_immediate_callback_failure"] = ProjectileQueueImmediateFailure,
        ["projectile_queue_applies_late_entity_once"] = ProjectileQueueLate,
        ["projectile_queue_waits_for_unique_match"] = ProjectileQueueAmbiguous,
        ["projectile_immediate_request_consumes_older_pending"] = ProjectileImmediateSupersedes,
        ["pending_keys_isolate_source_and_activation"] = PendingKeyIsolation,
        ["projectile_throwing_late_callback_preserves_reentrant_refresh"] = ProjectileQueueReentrantRefresh,

        ["pending_tick_preserves_global_enqueue_order"] = PendingGlobalOrder,
        ["pending_tick_defers_cross_kind_reentrant_work"] = PendingCrossKindReentrant,
        ["pending_tick_defers_refreshed_later_key"] = PendingRefreshesLaterKey,
        ["pending_tick_defers_cancelled_and_requeued_key"] = PendingCancelRequeuesLaterKey,
        ["pending_tick_reresolves_each_entity"] = PendingReresolvesEachEntity,
        ["pending_tick_reentry_is_noop"] = PendingTickReentry,
        ["world_clear_aborts_batch_and_defers_requeued_work"] = PendingWorldClearRequeue,
        ["pending_tick_uses_one_frame_for_both_entity_kinds"] = PendingSingleFrame,

        ["pending_capacity_is_shared_across_entity_kinds"] = PendingSharedCapacity,
        ["pending_entry_expires_at_boundary"] = PendingExpiryBoundary,
        ["pending_expiry_saturates_at_ulong_max"] = PendingExpirySaturates,
        ["pending_drop_throttle_saturates_at_ulong_max"] = PendingDropThrottleSaturates,
        ["cancel_activation_removes_both_entity_kinds"] = CancelActivation,
        ["cancel_npc_removes_only_exact_identity"] = CancelNpc,
        ["cancel_projectile_removes_only_exact_identity"] = CancelProjectile,
        ["cancel_all_is_scoped_to_source_type"] = CancelAll,
        ["world_clear_and_unload_drop_pending_work"] = LifecycleClears,
        ["world_clear_resets_diagnostic_throttles"] = LifecycleResetsThrottles,

        ["snapshot_send_is_server_only"] = SnapshotSendServerOnly,
        ["snapshot_send_writes_versioned_header"] = SnapshotSendHeader,
        ["snapshot_send_uses_deterministic_section_ids"] = SnapshotSendIds,
        ["snapshot_send_omits_false_section"] = SnapshotSendFalse,
        ["snapshot_send_omits_throwing_section"] = SnapshotSendThrow,
        ["snapshot_send_omits_unencodable_section"] = SnapshotSendOversize,
        ["snapshot_send_accepts_max_ushort_payload"] = SnapshotSendMaxPayload,
        ["snapshot_failure_throttle_saturates_at_ulong_max"] = SnapshotSendThrottleSaturates,
        ["snapshot_send_reentrant_call_is_noop"] = SnapshotSendReentrant,
        ["snapshot_send_world_transition_discards_frame"] = SnapshotSendWorldTransition,
        ["snapshot_send_mode_change_discards_frame"] = SnapshotSendModeChange,

        ["snapshot_receive_is_client_only"] = SnapshotReceiveClientOnly,
        ["snapshot_receive_rejects_bad_header"] = SnapshotReceiveBadHeader,
        ["snapshot_receive_truncation_has_no_partial_apply"] = SnapshotReceiveTruncated,
        ["snapshot_receive_duplicate_has_no_partial_apply"] = SnapshotReceiveDuplicate,
        ["snapshot_receive_skips_unknown_section"] = SnapshotReceiveUnknown,
        ["snapshot_receive_applies_known_sections"] = SnapshotReceiveKnown,
        ["snapshot_receive_false_section_logs_and_continues"] = SnapshotReceiveFalse,
        ["snapshot_receive_exception_logs_and_continues"] = SnapshotReceiveThrow,
        ["snapshot_receive_applies_in_canonical_id_order"] = SnapshotReceiveCanonicalOrder,
        ["snapshot_receive_reentrant_call_is_noop"] = SnapshotReceiveReentrant,
        ["snapshot_receive_world_transition_stops_later_sections"] = SnapshotReceiveWorldTransition,
        ["snapshot_receive_mode_change_stops_later_sections"] = SnapshotReceiveModeChange,
    };

    public static int Main(string[] args)
    {
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out Action test)) return 2;
        try { TestHooks.Reset(); test(); Console.WriteLine("PASS"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static NPC Npc(int index = 0, int type = 10, ulong generation = 1, bool active = true, bool install = true)
    {
        var npc = new NPC { active = active, whoAmI = index, type = type };
        npc.GetGlobalNPC<TimeFreezeNPC>().NetworkGeneration = generation;
        if (install && index >= 0 && index < Terraria.Main.npc.Length) Terraria.Main.npc[index] = npc;
        return npc;
    }

    private static Projectile Proj(int slot = 0, int owner = 1, int identity = 20, int type = 30, bool active = true, bool install = true)
    {
        var projectile = new Projectile { active = active, owner = owner, identity = identity, type = type };
        if (install && slot >= 0 && slot < Terraria.Main.projectile.Length) Terraria.Main.projectile[slot] = projectile;
        return projectile;
    }

    private static NetworkNPCIdentity NpcId(int index = 0, int type = 10, ulong generation = 1) => new(index, type, generation);
    private static NetworkProjectileIdentity ProjId(int owner = 1, int identity = 20, int type = 30) => new(owner, identity, type);
    private static void Tick() => new TimeControlReplicationSystem().PreUpdateEntities();

    private static byte[] Write(Action<BinaryWriter> action)
    {
        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, leaveOpen: true)) action(writer);
        return stream.ToArray();
    }

    private static BinaryReader Reader(byte[] bytes) => new(new MemoryStream(bytes, writable: false));

    private static void NpcSentinel()
    {
        Terraria.Main.maxNPCs = 70_000;
        Check(!new NetworkNPCIdentity(ushort.MaxValue, 1, 1).IsValid, "reserved wire sentinel was accepted");
    }

    private static void NpcCaptureGeneration()
    {
        NPC npc = Npc(generation: 0); Check(NetworkNPCIdentity.TryCapture(npc, out var id), "capture failed");
        Check(id.Generation != 0 && id.Index == 0 && id.Type == 10 && npc.GetGlobalNPC<TimeFreezeNPC>().NetworkGeneration == id.Generation, "generation was not assigned consistently");
    }

    private static void NpcCaptureInactive()
    {
        Check(!NetworkNPCIdentity.TryCapture(Npc(active: false), out var id) && id == default, "inactive NPC captured");
    }

    private static void NpcCaptureUnencodable()
    {
        Terraria.Main.maxNPCs = 70_000; NPC npc = Npc(index: ushort.MaxValue, install: false);
        Check(!NetworkNPCIdentity.TryCapture(npc, out _), "unencodable NPC index captured");
    }

    private static void NpcResolveGeneration()
    {
        Npc(generation: 2); Check(!NpcId(generation: 1).TryResolve(out _), "stale generation resolved");
    }

    private static void NpcResolveShortArray()
    {
        Terraria.Main.maxNPCs = 8; Terraria.Main.npc = new NPC[1];
        Check(!NpcId(index: 5).TryResolve(out _), "short engine array was indexed");
    }

    private static void NpcInvalidWrite()
    {
        byte[] bytes = Write(writer => Check(!default(NetworkNPCIdentity).Write(writer), "invalid identity reported success"));
        using BinaryReader reader = Reader(bytes);
        Check(reader.ReadUInt16() == ushort.MaxValue && reader.ReadInt32() == NPCID.None && reader.ReadUInt64() == 0 && reader.BaseStream.Position == reader.BaseStream.Length, "invalid NPC sentinel is not canonical");
        Check(!NetworkNPCIdentity.TryRead(Reader(bytes), out var decoded) && decoded == default, "invalid NPC sentinel leaked partial output");
    }

    private static void NpcRoundtrip()
    {
        NetworkNPCIdentity expected = NpcId(2, 50, 99); byte[] bytes = Write(writer => Check(expected.Write(writer), "write failed"));
        Check(NetworkNPCIdentity.TryRead(Reader(bytes), out var actual) && actual == expected, "NPC identity did not roundtrip");
    }

    private static void NpcTruncated()
    {
        Check(!NetworkNPCIdentity.TryRead(Reader(new byte[7]), out var id) && id == default, "truncated NPC identity escaped");
    }

    private static void NpcUnreadable()
    {
        BinaryReader reader = Reader(Array.Empty<byte>()); reader.Dispose();
        Check(!NetworkNPCIdentity.TryRead(reader, out var id) && id == default, "unreadable NPC identity escaped");
    }

    private static void ProjectileOwnerBound()
    {
        Check(!new NetworkProjectileIdentity(Terraria.Main.maxPlayers, 1, 1).IsValid, "owner at maxPlayers accepted");
    }

    private static void ProjectileCaptureInactive()
    {
        Check(!NetworkProjectileIdentity.TryCapture(Proj(active: false), out var id) && id == default, "inactive projectile captured");
    }

    private static void ProjectileCaptureUnencodable()
    {
        Terraria.Main.maxPlayers = 300; Projectile projectile = Proj(owner: byte.MaxValue, install: false);
        Check(!NetworkProjectileIdentity.TryCapture(projectile, out _), "reserved byte owner captured");
    }

    private static void ProjectileResolveExact()
    {
        Projectile expected = Proj(slot: 3); Check(ProjId().TryResolve(out var actual) && ReferenceEquals(expected, actual), "exact projectile did not resolve");
    }

    private static void ProjectileResolveAmbiguous()
    {
        Proj(slot: 1); Proj(slot: 4); Check(!ProjId().TryResolve(out _), "ambiguous projectile resolved");
    }

    private static void ProjectileResolveShortArray()
    {
        Terraria.Main.maxProjectiles = 8; Terraria.Main.projectile = new Projectile[1];
        Check(!ProjId().TryResolve(out _), "short projectile array was indexed");
    }

    private static void ProjectileInvalidWrite()
    {
        byte[] bytes = Write(writer => Check(!default(NetworkProjectileIdentity).Write(writer), "invalid identity reported success"));
        using BinaryReader reader = Reader(bytes);
        Check(reader.ReadByte() == byte.MaxValue && reader.ReadInt32() == -1 && reader.ReadInt32() == ProjectileID.None && reader.BaseStream.Position == reader.BaseStream.Length, "invalid projectile sentinel is not canonical");
        Check(!NetworkProjectileIdentity.TryRead(Reader(bytes), out var decoded) && decoded == default, "invalid projectile sentinel leaked partial output");
    }

    private static void ProjectileRoundtrip()
    {
        NetworkProjectileIdentity expected = ProjId(2, 50, 99); byte[] bytes = Write(writer => Check(expected.Write(writer), "write failed"));
        Check(NetworkProjectileIdentity.TryRead(Reader(bytes), out var actual) && actual == expected, "projectile identity did not roundtrip");
    }

    private static void ProjectileTruncated()
    {
        Check(!NetworkProjectileIdentity.TryRead(Reader(new byte[5]), out var id) && id == default, "truncated projectile identity escaped");
    }

    private static void ProjectileUnreadable()
    {
        BinaryReader reader = Reader(Array.Empty<byte>()); reader.Dispose();
        Check(!NetworkProjectileIdentity.TryRead(reader, out var id) && id == default, "unreadable projectile identity escaped");
    }

    private static void NpcQueueActivation()
    {
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(0, NpcId(), 2, _ => { }) == EntityResolutionResult.Rejected, "zero activation accepted");
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(-1, NpcId(), 2, _ => { }) == EntityResolutionResult.Rejected, "negative activation accepted");
    }

    private static void NpcQueueLifetime()
    {
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 0, _ => { }) == EntityResolutionResult.Rejected, "zero lifetime accepted");
    }

    private static void NpcQueueNullCallback()
    {
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 2, null) == EntityResolutionResult.Rejected, "null callback accepted");
    }

    private static void NpcQueueImmediate()
    {
        NPC npc = Npc(); int applied = 0; var result = TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 2, value => { Check(ReferenceEquals(value, npc), "wrong NPC"); applied++; });
        Check(result == EntityResolutionResult.Applied && applied == 1, "resolved NPC was not applied immediately");
    }

    private static void NpcQueueImmediateFailure()
    {
        Npc(); var result = TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 2, _ => throw new InvalidOperationException("boom"));
        Check(result == EntityResolutionResult.Rejected && CWRMod.Instance.Logger.Warnings.Count == 1, "immediate callback failure escaped or was accepted");
    }

    private static void NpcQueueLate()
    {
        int applied = 0; Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => applied++) == EntityResolutionResult.Queued, "unresolved NPC not queued");
        Npc(); Tick(); Tick(); Check(applied == 1, "late NPC did not apply exactly once");
    }

    private static void NpcQueueRefresh()
    {
        int first = 0, latest = 0; TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 1, _ => first++);
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => latest++); Terraria.Main.GameUpdateCount = 1; Npc(); Tick();
        Check(first == 0 && latest == 1, "duplicate did not refresh callback and expiry");
    }

    private static void NpcImmediateSupersedes()
    {
        int oldCalls = 0, newCalls = 0;
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => oldCalls++) == EntityResolutionResult.Queued, "old NPC work not queued");
        Npc();
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => newCalls++) == EntityResolutionResult.Applied, "new NPC work not applied immediately");
        Tick();
        Check(oldCalls == 0 && newCalls == 1, "old NPC pending callback replayed");
    }

    private static void NpcImmediateThrowSupersedes()
    {
        int oldCalls = 0;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => oldCalls++);
        Npc();
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => throw new InvalidOperationException("new callback failed")) == EntityResolutionResult.Rejected, "throwing new NPC work was not rejected");
        Tick();
        Check(oldCalls == 0, "old NPC pending callback replayed after new failure");
    }

    private static void NpcQueueReentrantRefresh()
    {
        int first = 0, latest = 0; NPC npc = null;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, value =>
        {
            first++; value.active = false;
            Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => latest++) == EntityResolutionResult.Queued, "reentrant NPC refresh was not queued");
        });
        npc = Npc(); Tick(); Check(first == 1 && latest == 0, "NPC callback did not defer its replacement");
        npc.active = true; Tick(); Check(first == 1 && latest == 1, "resolved NPC callback erased its reentrant replacement");
    }

    private static void ProjectileQueueImmediate()
    {
        Projectile projectile = Proj(); int applied = 0; var result = TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 2, value => { Check(ReferenceEquals(value, projectile), "wrong projectile"); applied++; });
        Check(result == EntityResolutionResult.Applied && applied == 1, "resolved projectile was not applied immediately");
    }

    private static void ProjectileQueueImmediateFailure()
    {
        Proj(); var result = TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 2, _ => throw new InvalidOperationException("boom"));
        Check(result == EntityResolutionResult.Rejected && CWRMod.Instance.Logger.Warnings.Count == 1, "projectile callback failure escaped or was accepted");
    }

    private static void ProjectileQueueLate()
    {
        int applied = 0; TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => applied++); Proj(); Tick(); Tick();
        Check(applied == 1, "late projectile did not apply exactly once");
    }

    private static void ProjectileQueueAmbiguous()
    {
        Proj(slot: 1); Proj(slot: 2); int applied = 0; TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => applied++); Tick(); Check(applied == 0, "ambiguous match applied");
        Terraria.Main.projectile[2].active = false; Tick(); Check(applied == 1, "queue did not wait for unique match");
    }

    private static void ProjectileImmediateSupersedes()
    {
        int oldCalls = 0, newCalls = 0;
        Check(TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => oldCalls++) == EntityResolutionResult.Queued, "old projectile work not queued");
        Proj();
        Check(TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => newCalls++) == EntityResolutionResult.Applied, "new projectile work not applied immediately");
        Tick();
        Check(oldCalls == 0 && newCalls == 1, "old projectile pending callback replayed");
    }

    private static void ProjectileQueueReentrantRefresh()
    {
        int first = 0, latest = 0; Projectile projectile = null;
        TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, value =>
        {
            first++; value.active = false;
            Check(TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => latest++) == EntityResolutionResult.Queued, "reentrant projectile refresh was not queued");
            throw new InvalidOperationException("current callback failed after refresh");
        });
        projectile = Proj(); Tick(); Check(first == 1 && latest == 0, "projectile callback did not defer its replacement");
        projectile.active = true; Tick();
        Check(first == 1 && latest == 1 && CWRMod.Instance.Logger.Warnings.Count == 1, "throwing projectile callback erased its reentrant replacement");
    }

    private static void PendingGlobalOrder()
    {
        var order = new List<string>();
        TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => order.Add("projectile"));
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => order.Add("npc"));
        Proj(); Npc(); Tick();
        Check(order.SequenceEqual(new[] { "projectile", "npc" }), "entity kind changed accepted enqueue order");
    }

    private static void PendingCrossKindReentrant()
    {
        int projectileCalls = 0;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ =>
        {
            Check(TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(2, ProjId(), 3, __ => projectileCalls++) == EntityResolutionResult.Queued, "reentrant projectile was not queued");
            Proj();
        });
        Npc(); Tick();
        Check(projectileCalls == 0, "cross-kind work created during the tick ran immediately");
        Tick(); Check(projectileCalls == 1, "deferred cross-kind work did not run next tick");
    }

    private static void PendingRefreshesLaterKey()
    {
        int oldCalls = 0, newCalls = 0;
        NetworkNPCIdentity secondId = NpcId(1, 11, 2);
        NPC second = null;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ =>
        {
            second.active = false;
            Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, secondId, 3, __ => newCalls++) == EntityResolutionResult.Queued, "later key refresh was not queued");
            second.active = true;
        });
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, secondId, 3, _ => oldCalls++);
        Npc(); second = Npc(1, 11, 2); Tick();
        Check(oldCalls == 0 && newCalls == 0, "refreshed later key ran from the stale tick batch");
        Tick(); Check(oldCalls == 0 && newCalls == 1, "refreshed later key did not run next tick");
    }

    private static void PendingCancelRequeuesLaterKey()
    {
        int oldCalls = 0, newCalls = 0;
        NetworkNPCIdentity secondId = NpcId(1, 11, 2);
        NPC second = null;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ =>
        {
            TimeControlReplicationSystem.CancelNPC<SourceA>(2, secondId);
            second.active = false;
            Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, secondId, 3, __ => newCalls++) == EntityResolutionResult.Queued, "cancelled key was not requeued");
            second.active = true;
        });
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, secondId, 3, _ => oldCalls++);
        Npc(); second = Npc(1, 11, 2); Tick();
        Check(oldCalls == 0 && newCalls == 0, "cancelled and requeued key ran from the stale tick batch");
        Tick(); Check(oldCalls == 0 && newCalls == 1, "requeued key did not run next tick");
    }

    private static void PendingReresolvesEachEntity()
    {
        int secondCalls = 0;
        NPC second = null;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => second.active = false);
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, NpcId(1, 11, 2), 3, _ => secondCalls++);
        Npc(); second = Npc(1, 11, 2); Tick();
        Check(secondCalls == 0, "later entity was not re-resolved after an earlier callback mutated it");
        second.active = true; Tick(); Check(secondCalls == 1, "still-pending entity did not resolve later");
    }

    private static void PendingTickReentry()
    {
        bool insideFirst = false, secondRanInside = false;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ =>
        {
            insideFirst = true; Tick(); insideFirst = false;
        });
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, NpcId(1, 11, 2), 3, _ => secondRanInside = insideFirst);
        Npc(); Npc(1, 11, 2); Tick();
        Check(!secondRanInside, "reentrant PreUpdateEntities processed the active batch recursively");
    }

    private static void PendingWorldClearRequeue()
    {
        int oldCalls = 0, newCalls = 0;
        var system = new TimeControlReplicationSystem();
        NetworkNPCIdentity secondId = NpcId(1, 11, 2);
        NPC second = null;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ =>
        {
            system.ClearWorld();
            second.active = false;
            Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, secondId, 3, __ => newCalls++) == EntityResolutionResult.Queued, "new-world work was not queued");
            second.active = true;
        });
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, secondId, 3, _ => oldCalls++);
        Npc(); second = Npc(1, 11, 2); Tick();
        Check(oldCalls == 0 && newCalls == 0, "world transition did not abort the old tick batch");
        Tick(); Check(oldCalls == 0 && newCalls == 1, "new-world work did not wait for the next tick");
    }

    private static void PendingSingleFrame()
    {
        int npcCalls = 0, projectileCalls = 0;
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => { npcCalls++; Terraria.Main.GameUpdateCount = 1; });
        TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 1, _ => projectileCalls++);
        Npc(); Proj(); Tick();
        Check(npcCalls == 1 && projectileCalls == 1, "NPC and projectile decisions used different frame snapshots");
    }

    private static void PendingKeyIsolation()
    {
        int applied = 0; TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => applied++); TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, NpcId(), 3, _ => applied++); TimeControlReplicationSystem.ResolveOrQueueNPC<SourceB>(1, NpcId(), 3, _ => applied++); Npc(); Tick();
        Check(applied == 3, "source or activation keys collided");
    }

    private static void PendingSharedCapacity()
    {
        Terraria.Main.maxNPCs = 1; Terraria.Main.maxProjectiles = 1; Terraria.Main.npc = new NPC[1]; Terraria.Main.projectile = new Projectile[1];
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => { }) == EntityResolutionResult.Queued, "first queue failed");
        Check(TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => { }) == EntityResolutionResult.Queued, "second queue failed");
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, NpcId(), 3, _ => { }) == EntityResolutionResult.Rejected, "shared capacity exceeded");
    }

    private static void PendingExpiryBoundary()
    {
        int applied = 0; TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 1, _ => applied++); Terraria.Main.GameUpdateCount = 1; Npc(); Tick();
        Check(applied == 0, "expired work applied at boundary");
    }

    private static void PendingExpirySaturates()
    {
        Terraria.Main.GameUpdateCount = ulong.MaxValue - 1; int applied = 0; TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 120, _ => applied++); Npc(); Tick();
        Check(applied == 1, "expiry overflow dropped live work");
    }

    private static void PendingDropThrottleSaturates()
    {
        Terraria.Main.maxNPCs = 1; Terraria.Main.maxProjectiles = 0; Terraria.Main.npc = new NPC[1]; Terraria.Main.projectile = Array.Empty<Projectile>(); Terraria.Main.GameUpdateCount = ulong.MaxValue - 1;
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 120, _ => { }) == EntityResolutionResult.Queued, "capacity seed was not queued");
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, NpcId(), 120, _ => { }) == EntityResolutionResult.Rejected, "first over-capacity request was accepted");
        Check(TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(3, NpcId(), 120, _ => { }) == EntityResolutionResult.Rejected, "second over-capacity request was accepted");
        Check(CWRMod.Instance.Logger.Warnings.Count == 1, "drop log throttle wrapped near ulong max");
    }

    private static void CancelActivation()
    {
        int applied = 0; TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => applied++); TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => applied++); TimeControlReplicationSystem.Cancel<SourceA>(1); Npc(); Proj(); Tick();
        Check(applied == 0, "activation cancellation left pending work");
    }

    private static void CancelNpc()
    {
        int first = 0, second = 0; var other = NpcId(1, 10, 2); TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => first++); TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, other, 3, _ => second++); TimeControlReplicationSystem.CancelNPC<SourceA>(1, NpcId()); Npc(); Npc(1, generation: 2); Tick();
        Check(first == 0 && second == 1, "NPC cancellation was not exact");
    }

    private static void CancelProjectile()
    {
        int first = 0, second = 0; var other = ProjId(identity: 21); TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, ProjId(), 3, _ => first++); TimeControlReplicationSystem.ResolveOrQueueProjectile<SourceA>(1, other, 3, _ => second++); TimeControlReplicationSystem.CancelProjectile<SourceA>(1, ProjId()); Proj(); Proj(1, identity: 21); Tick();
        Check(first == 0 && second == 1, "projectile cancellation was not exact");
    }

    private static void CancelAll()
    {
        int a = 0, b = 0; TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => a++); TimeControlReplicationSystem.ResolveOrQueueNPC<SourceB>(1, NpcId(), 3, _ => b++); TimeControlReplicationSystem.CancelAll<SourceA>(); Npc(); Tick();
        Check(a == 0 && b == 1, "CancelAll crossed source boundary");
    }

    private static void LifecycleClears()
    {
        int applied = 0; var system = new TimeControlReplicationSystem(); TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => applied++); system.ClearWorld(); Npc(); Tick();
        Terraria.Main.npc[0] = null; TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, NpcId(), 3, _ => applied++); system.OnWorldUnload(); Npc(); Tick();
        Check(applied == 0, "world lifecycle retained callbacks");
    }

    private static void LifecycleResetsThrottles()
    {
        var system = new TimeControlReplicationSystem(); Terraria.Main.GameUpdateCount = 10; Terraria.Main.maxNPCs = 1; Terraria.Main.maxProjectiles = 0; Terraria.Main.npc = new NPC[1]; Terraria.Main.projectile = Array.Empty<Projectile>();
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(1, NpcId(), 3, _ => { }); TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(2, NpcId(), 3, _ => { });
        Terraria.Main.netMode = NetmodeID.Server; SnapshotHarness.WriteModes[1] = SnapshotWriteMode.Throw; SendSnapshot();
        Check(CWRMod.Instance.Logger.Warnings.Count == 2, "initial diagnostics were not emitted");
        system.ClearWorld();
        TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(3, NpcId(), 3, _ => { }); TimeControlReplicationSystem.ResolveOrQueueNPC<SourceA>(4, NpcId(), 3, _ => { }); SendSnapshot();
        Check(CWRMod.Instance.Logger.Warnings.Count == 4, "world clear did not reset both diagnostic throttles");
    }

    private static byte[] SendSnapshot()
    {
        using var stream = new MemoryStream(); using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, true)) new TimeControlReplicationSystem().NetSend(writer); return stream.ToArray();
    }

    private static SnapshotFrame ParseSnapshot(byte[] bytes)
    {
        using BinaryReader reader = Reader(bytes); uint magic = reader.ReadUInt32(); byte version = reader.ReadByte(); int count = reader.ReadByte(); var ids = new List<byte>(); var lengths = new List<int>();
        for (int i = 0; i < count; i++) { ids.Add(reader.ReadByte()); int length = reader.ReadUInt16(); lengths.Add(length); reader.ReadBytes(length); }
        return new SnapshotFrame(magic, version, count, ids, lengths, reader.BaseStream.Position == reader.BaseStream.Length);
    }

    private static void SnapshotSendServerOnly()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; Check(SendSnapshot().Length == 0, "client emitted server snapshot");
    }

    private static void SnapshotSendHeader()
    {
        Terraria.Main.netMode = NetmodeID.Server; SnapshotFrame frame = ParseSnapshot(SendSnapshot());
        Check(frame.Magic == 0x31524354 && frame.Version == 1 && frame.Count == 4 && frame.Complete, "snapshot header/framing invalid");
    }

    private static void SnapshotSendIds()
    {
        Terraria.Main.netMode = NetmodeID.Server; Check(ParseSnapshot(SendSnapshot()).Ids.SequenceEqual(new byte[] { 1, 2, 3, 4 }), "section IDs are not deterministic");
    }

    private static void SnapshotSendFalse()
    {
        Terraria.Main.netMode = NetmodeID.Server; SnapshotHarness.WriteModes[2] = SnapshotWriteMode.ReturnFalse; SnapshotFrame frame = ParseSnapshot(SendSnapshot());
        Check(frame.Count == 3 && frame.Ids.SequenceEqual(new byte[] { 1, 3, 4 }) && frame.Complete, "false section emitted placeholder or corrupt count");
    }

    private static void SnapshotSendThrow()
    {
        Terraria.Main.netMode = NetmodeID.Server; SnapshotHarness.WriteModes[2] = SnapshotWriteMode.Throw; SnapshotFrame frame = ParseSnapshot(SendSnapshot());
        Check(frame.Count == 3 && !frame.Ids.Contains(2) && frame.Complete && CWRMod.Instance.Logger.Warnings.Count == 1, "throwing section was not isolated and omitted");
    }

    private static void SnapshotSendOversize()
    {
        Terraria.Main.netMode = NetmodeID.Server; SnapshotHarness.WriteSizes[1] = ushort.MaxValue + 1; SnapshotFrame frame = ParseSnapshot(SendSnapshot());
        Check(frame.Count == 3 && frame.Ids.SequenceEqual(new byte[] { 2, 3, 4 }) && frame.Complete, "unencodable payload wrapped or leaked");
    }

    private static void SnapshotSendMaxPayload()
    {
        Terraria.Main.netMode = NetmodeID.Server; SnapshotHarness.WriteSizes[1] = ushort.MaxValue; SnapshotFrame frame = ParseSnapshot(SendSnapshot());
        Check(frame.Count == 4 && frame.Lengths[0] == ushort.MaxValue && frame.Complete, "maximum encodable payload rejected");
    }

    private static void SnapshotSendThrottleSaturates()
    {
        Terraria.Main.netMode = NetmodeID.Server; Terraria.Main.GameUpdateCount = ulong.MaxValue - 1; SnapshotHarness.WriteModes[1] = SnapshotWriteMode.Throw;
        SendSnapshot(); SendSnapshot();
        Check(CWRMod.Instance.Logger.Warnings.Count == 1, "snapshot log throttle wrapped near ulong max");
    }

    private static void SnapshotSendReentrant()
    {
        Terraria.Main.netMode = NetmodeID.Server; byte[] nested = null;
        SnapshotHarness.WriteHooks[1] = _ => nested = SendSnapshot();
        SnapshotFrame outer = ParseSnapshot(SendSnapshot());
        Check(nested != null && nested.Length == 0 && outer.Count == 4 && outer.Complete, "reentrant snapshot send corrupted or duplicated the outer frame");
    }

    private static void SnapshotSendWorldTransition()
    {
        Terraria.Main.netMode = NetmodeID.Server;
        SnapshotHarness.WriteHooks[2] = _ => new TimeControlReplicationSystem().ClearWorld();
        Check(SendSnapshot().Length == 0, "snapshot from a superseded world was emitted");
    }

    private static void SnapshotSendModeChange()
    {
        Terraria.Main.netMode = NetmodeID.Server;
        SnapshotHarness.WriteHooks[2] = _ => Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        Check(SendSnapshot().Length == 0, "snapshot was emitted after server authority was lost");
    }

    private static byte[] Frame(uint magic = 0x31524354, byte version = 1, params (byte Id, byte[] Payload)[] sections)
    {
        return Write(writer => { writer.Write(magic); writer.Write(version); writer.Write((byte)sections.Length); foreach (var section in sections) { writer.Write(section.Id); writer.Write((ushort)section.Payload.Length); writer.Write(section.Payload); } });
    }

    private static void Receive(byte[] bytes) => new TimeControlReplicationSystem().NetReceive(Reader(bytes));

    private static void SnapshotReceiveClientOnly()
    {
        Terraria.Main.netMode = NetmodeID.Server; Receive(Frame(sections: new[] { ((byte)1, new byte[] { 1 }) })); Check(SnapshotHarness.Applied.Count == 0, "server consumed client snapshot");
    }

    private static void SnapshotReceiveBadHeader()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; Receive(Frame(7, 1, ((byte)1, new byte[] { 1 }))); Receive(Frame(0x31524354, 2, ((byte)1, new byte[] { 1 })));
        Check(SnapshotHarness.Applied.Count == 0, "bad snapshot header applied state");
    }

    private static void SnapshotReceiveTruncated()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; byte[] bytes = Write(writer => { writer.Write(0x31524354u); writer.Write((byte)1); writer.Write((byte)2); writer.Write((byte)1); writer.Write((ushort)1); writer.Write((byte)7); writer.Write((byte)2); writer.Write((ushort)4); writer.Write((byte)9); }); Receive(bytes);
        Check(SnapshotHarness.Applied.Count == 0, "earlier section applied before structural validation completed");
    }

    private static void SnapshotReceiveDuplicate()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; Receive(Frame(sections: new[] { ((byte)1, new byte[] { 1 }), ((byte)1, new byte[] { 2 }) }));
        Check(SnapshotHarness.Applied.Count == 0, "duplicate frame partially applied");
    }

    private static void SnapshotReceiveUnknown()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; Receive(Frame(sections: new[] { ((byte)99, new byte[] { 8, 9 }), ((byte)2, new byte[] { 1 }) }));
        Check(SnapshotHarness.ReadAttempts.SequenceEqual(new[] { 2 }) && SnapshotHarness.Applied.SequenceEqual(new[] { 2 }), "unknown section blocked or invoked known reader");
    }

    private static void SnapshotReceiveKnown()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; Receive(Frame(sections: new[] { ((byte)1, new byte[] { 1 }), ((byte)3, new byte[] { 3 }) }));
        Check(SnapshotHarness.Applied.SequenceEqual(new[] { 1, 3 }), "known sections were not applied");
    }

    private static void SnapshotReceiveFalse()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; SnapshotHarness.ReadModes[1] = SnapshotReadMode.ReturnFalse; Receive(Frame(sections: new[] { ((byte)1, new byte[] { 1 }), ((byte)2, new byte[] { 2 }) }));
        Check(SnapshotHarness.ReadAttempts.SequenceEqual(new[] { 1, 2 }) && SnapshotHarness.Applied.SequenceEqual(new[] { 2 }) && CWRMod.Instance.Logger.Warnings.Count == 1, "false section was ignored or blocked later section");
    }

    private static void SnapshotReceiveThrow()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; SnapshotHarness.ReadModes[1] = SnapshotReadMode.Throw; Receive(Frame(sections: new[] { ((byte)1, new byte[] { 1 }), ((byte)2, new byte[] { 2 }) }));
        Check(SnapshotHarness.ReadAttempts.SequenceEqual(new[] { 1, 2 }) && SnapshotHarness.Applied.SequenceEqual(new[] { 2 }) && CWRMod.Instance.Logger.Warnings.Count == 1, "throwing section was not isolated");
    }

    private static void SnapshotReceiveCanonicalOrder()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; Receive(Frame(sections: new[] { ((byte)4, new byte[] { 4 }), ((byte)1, new byte[] { 1 }), ((byte)2, new byte[] { 2 }) }));
        Check(SnapshotHarness.ReadAttempts.SequenceEqual(new[] { 1, 2, 4 }), "known sections followed attacker-controlled wire order");
    }

    private static void SnapshotReceiveReentrant()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        SnapshotHarness.ReadHooks[1] = _ => Receive(Frame(sections: new[] { ((byte)2, new byte[] { 2 }) }));
        Receive(Frame(sections: new[] { ((byte)1, new byte[] { 1 }), ((byte)3, new byte[] { 3 }) }));
        Check(SnapshotHarness.ReadAttempts.SequenceEqual(new[] { 1, 3 }) && SnapshotHarness.Applied.SequenceEqual(new[] { 1, 3 }), "reentrant receive interleaved another frame");
    }

    private static void SnapshotReceiveWorldTransition()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        SnapshotHarness.ReadHooks[1] = _ => new TimeControlReplicationSystem().ClearWorld();
        Receive(Frame(sections: new[] { ((byte)1, new byte[] { 1 }), ((byte)2, new byte[] { 2 }) }));
        Check(SnapshotHarness.ReadAttempts.SequenceEqual(new[] { 1 }) && SnapshotHarness.Applied.SequenceEqual(new[] { 1 }), "later section crossed a world transition");
    }

    private static void SnapshotReceiveModeChange()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        SnapshotHarness.ReadHooks[1] = _ => Terraria.Main.netMode = NetmodeID.Server;
        Receive(Frame(sections: new[] { ((byte)1, new byte[] { 1 }), ((byte)2, new byte[] { 2 }) }));
        Check(SnapshotHarness.ReadAttempts.SequenceEqual(new[] { 1 }) && SnapshotHarness.Applied.SequenceEqual(new[] { 1 }), "later section applied after client authority was lost");
    }

    private sealed class SourceA { }
    private sealed class SourceB { }
    private sealed record SnapshotFrame(uint Magic, byte Version, int Count, List<byte> Ids, List<int> Lengths, bool Complete);
}
