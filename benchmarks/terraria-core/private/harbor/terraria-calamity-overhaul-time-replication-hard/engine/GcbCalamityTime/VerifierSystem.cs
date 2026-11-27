using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using CalamityOverhaul.Content.TimeFreezes;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace GcbCalamityTime;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;
        var outcomes = new[]
        {
            Run("real_engine_projectile_owner_wire_bound", ProjectileOwnerWireBound),
            Run("real_engine_rejected_identity_is_canonical", RejectedIdentityIsCanonical),
            Run("real_server_snapshot_failure_is_omitted", SnapshotFailureIsOmitted),
        };
        bool passed = outcomes.All(outcome => outcome.Passed);
        var report = new
        {
            schemaVersion = 1,
            complete = true,
            passed,
            terrariaVersion = Main.versionNumber,
            tModLoaderVersion = BuildInfo.tMLVersion.ToString(),
            dedicatedServer = Main.dedServ,
            cases = outcomes.Select(outcome => new
            {
                name = outcome.Name,
                status = outcome.Passed ? "passed" : "failed",
                error = outcome.Error,
            }),
        };
        Directory.CreateDirectory(Path.GetDirectoryName(reportPath)!);
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report));
        Environment.Exit(passed && Main.dedServ ? 0 : 90);
    }

    private static CaseOutcome Run(string name, Action test)
    {
        try { test(); return new(name, true, null); }
        catch (Exception error) { return new(name, false, error.ToString()); }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void ProjectileOwnerWireBound()
    {
        var identity = new NetworkProjectileIdentity(Main.maxPlayers, 1, ProjectileID.WoodenArrowFriendly);
        Check(!identity.IsValid, "owner equal to Main.maxPlayers was accepted");
    }

    private static void RejectedIdentityIsCanonical()
    {
        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, leaveOpen: true))
        {
            writer.Write(ushort.MaxValue);
            writer.Write(NPCID.BlueSlime);
            writer.Write(1UL);
        }
        stream.Position = 0;
        using var reader = new BinaryReader(stream);
        Check(!NetworkNPCIdentity.TryRead(reader, out NetworkNPCIdentity identity), "invalid wire identity was accepted");
        Check(identity == default, "rejected wire identity leaked partial state");

        var disposed = new BinaryReader(new MemoryStream());
        disposed.Dispose();
        Check(!NetworkNPCIdentity.TryRead(disposed, out identity), "disposed reader was accepted");
        Check(identity == default, "disposed reader leaked partial state");
    }

    private static void SnapshotFailureIsOmitted()
    {
        Check(Main.netMode == NetmodeID.Server, "verifier did not run in server net mode");
        SnapshotHarness.WriteModes.Clear();
        SnapshotHarness.WriteModes[2] = SnapshotWriteMode.ReturnFalse;
        using var stream = new MemoryStream();
        new TimeControlReplicationSystem().NetSend(new BinaryWriter(stream));
        stream.Position = 0;
        using var reader = new BinaryReader(stream);
        Check(reader.ReadUInt32() == 0x31524354, "snapshot magic changed");
        Check(reader.ReadByte() == 1, "snapshot version changed");
        Check(reader.ReadByte() == 3, "rejected section remained in the server snapshot");
        byte[] expected = { 1, 3, 4 };
        foreach (byte id in expected)
        {
            Check(reader.ReadByte() == id, "snapshot section order changed");
            int length = reader.ReadUInt16();
            Check(length == 1 && reader.ReadByte() == id, "snapshot payload framing changed");
        }
        Check(stream.Position == stream.Length, "snapshot contained trailing bytes");
    }
}
