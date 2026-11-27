using Microsoft.Xna.Framework;
using System;
using System.Collections.Generic;
using System.IO;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;
using Terraria.ModLoader.IO;

namespace Aequus.Common.Carpentry;

public class CarpentrySystem : ModSystem {
    public static readonly BuildChallengeSaveData CompletedBounties = new("CompletedBounties");
    public static readonly BuildBuffsData BuildingBuffs = new("BuildingBuffs_{0}");

    public override void Load() {
        CompletedBounties.Clear();
        BuildingBuffs.Clear();
    }

    public override void ClearWorld() {
        CompletedBounties.Clear();
        BuildingBuffs.Clear();
    }

    public override void SaveWorldData(TagCompound tag) {
        BuildChallengeRegistrySnapshot registry = BuildChallengeRegistrySnapshot.Capture();
        var prepared = new TagCompound();
        CompletedBounties.SaveData(prepared);
        BuildingBuffs.WriteSaveData(prepared, BuildingBuffs.PrepareSaveData(registry));
        registry.RequireCurrent();
        foreach (var pair in prepared) {
            tag[pair.Key] = pair.Value;
        }
    }

    public override void LoadWorldData(TagCompound tag) {
        BuildChallengeRegistrySnapshot registry;
        try {
            registry = BuildChallengeRegistrySnapshot.Capture();
        }
        catch (InvalidOperationException ex) {
            throw new InvalidDataException("The carpentry registry is invalid.", ex);
        }

        List<string> completions = CompletedBounties.ReadSaveData(tag);
        Dictionary<string, List<Rectangle>> buildings = BuildingBuffs.ParseSaveData(tag);
        if (!registry.IsCurrent()) {
            throw new InvalidDataException("The carpentry registry changed while loading the world.");
        }
        CompletedBounties.Replace(completions);
        BuildingBuffs.ReplaceFromStable(registry, buildings);
    }

    public static bool AddBuildingBuffLocation(int buildChallengeId, Rectangle rectangle, bool quiet = false) {
        bool changed = BuildingBuffs.AddBuild(buildChallengeId, rectangle);
        if (changed && Main.netMode != NetmodeID.SinglePlayer && !quiet) {
            var packet = Aequus.GetPacket(PacketType.AddBuilding);
            packet.Write(buildChallengeId);
            packet.Write(rectangle.X);
            packet.Write(rectangle.Y);
            packet.Write(rectangle.Width);
            packet.Write(rectangle.Height);
            packet.Send();
        }
        return changed;
    }

    public static bool RemoveBuildingBuffLocation(int bountyID, int x, int y, bool quiet = false) {
        bool changed = BuildingBuffs.RemoveBuild(bountyID, x, y);
        if (changed && Main.netMode != NetmodeID.SinglePlayer && !quiet) {
            var packet = Aequus.GetPacket(PacketType.RemoveBuilding);
            packet.Write(bountyID);
            packet.Write(x);
            packet.Write(y);
            packet.Send();
        }
        return changed;
    }

    public override void NetSend(BinaryWriter writer) {
        BuildChallengeRegistrySnapshot registry = BuildChallengeRegistrySnapshot.Capture();
        byte[] completions = CompletedBounties.PrepareFrame(registry);
        byte[] buildings = BuildingBuffs.PrepareFrame(registry);
        registry.RequireCurrent();

        using var stream = new MemoryStream();
        stream.Write(completions, 0, completions.Length);
        stream.Write(buildings, 0, buildings.Length);
        writer.Write(stream.ToArray());
    }

    public override void NetReceive(BinaryReader reader) {
        BuildChallengeRegistrySnapshot registry;
        try {
            registry = BuildChallengeRegistrySnapshot.Capture();
        }
        catch (InvalidOperationException ex) {
            throw new InvalidDataException("The carpentry registry is invalid.", ex);
        }

        List<string> completions = CompletedBounties.ParseFrame(reader, registry);
        Dictionary<string, List<Rectangle>> buildings = BuildingBuffs.ParseFrame(reader, registry);
        if (!registry.IsCurrent()) {
            throw new InvalidDataException("The carpentry registry changed while receiving the world.");
        }
        CompletedBounties.Replace(completions);
        BuildingBuffs.ReplaceFromStable(registry, buildings);
    }

    public static void SendCompletedBounties() {
        if (Main.netMode == NetmodeID.SinglePlayer) {
            return;
        }
        if (Main.netMode == NetmodeID.MultiplayerClient) {
            Aequus.GetPacket(PacketType.CarpenterBountiesCompleted).Send();
            return;
        }

        BuildChallengeRegistrySnapshot registry = BuildChallengeRegistrySnapshot.Capture();
        byte[] frame = CompletedBounties.PrepareFrame(registry);
        registry.RequireCurrent();
        var packet = Aequus.GetPacket(PacketType.CarpenterBountiesCompleted);
        packet.Write(frame);
        packet.Send();
    }

    public static void ReceiveCompletedBounties(BinaryReader reader) {
        if (Main.netMode == NetmodeID.Server) {
            SendCompletedBounties();
            return;
        }
        CompletedBounties.RecieveData(reader);
    }

    public static void ResetBounties() {
        if (Main.netMode == NetmodeID.MultiplayerClient) {
            Aequus.GetPacket(PacketType.ResetCarpenterBounties).Send();
            return;
        }

        CompletedBounties.Clear();
        if (Main.netMode == NetmodeID.Server) {
            SendCompletedBounties();
        }
    }

    public static void Complete(BuildChallenge buildChallenge) {
        if (buildChallenge == null || !BuildChallengeRegistrySnapshot.TryCapture(out var registry) ||
            buildChallenge.Type < 0 || buildChallenge.Type >= registry.Count ||
            !ReferenceEquals(registry.ById[buildChallenge.Type], buildChallenge)) {
            return;
        }
        if (Main.netMode == NetmodeID.MultiplayerClient) {
            var packet = Aequus.GetPacket(PacketType.CompleteCarpenterBounty);
            packet.Write(buildChallenge.Type);
            packet.Send();
            return;
        }
        if (CompletedBounties.ContainsChallenge(buildChallenge)) {
            return;
        }
        CompletedBounties.Add(buildChallenge);
        if (Main.netMode == NetmodeID.Server) {
            SendCompletedBounties();
        }
    }
}
