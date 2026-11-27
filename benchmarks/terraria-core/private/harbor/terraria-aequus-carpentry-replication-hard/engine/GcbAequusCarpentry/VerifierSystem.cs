using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Aequus.Common.Carpentry;
using Terraria;
using Terraria.ModLoader;
using Terraria.ModLoader.IO;

namespace GcbAequusCarpentry;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;
        SeedRegistry();
        var outcomes = new[]
        {
            Run("real_engine_receive_failure_is_transactional", ReceiveFailureIsTransactional),
            Run("real_engine_registry_ids_are_serialized", RegistryIdsAreSerialized),
            Run("real_tml_tagcompound_save_is_detached", TagCompoundSaveIsDetached),
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

    private static void SeedRegistry()
    {
        BuildChallengeLoader.registeredBuildChallenges.Clear();
        for (int id = 0; id < 3; id++)
        {
            BuildChallengeLoader.registeredBuildChallenges.Add(new BuildChallenge
            {
                Type = id,
                FullName = $"Gcb/Challenge{id}",
                BuildBuffType = id + 1,
            });
        }
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

    private static void ReceiveFailureIsTransactional()
    {
        var data = new BuildChallengeSaveData("wire");
        data.Challenges.Add("Gcb/Challenge1");
        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, leaveOpen: true))
        {
            writer.Write(1);
            writer.Write(99);
        }
        stream.Position = 0;
        try { data.RecieveData(new BinaryReader(stream)); }
        catch (Exception) { }
        Check(data.Challenges.SequenceEqual(new[] { "Gcb/Challenge1" }), "failed receive destroyed the previous completion state");
    }

    private static void RegistryIdsAreSerialized()
    {
        var data = new BuildChallengeSaveData("wire");
        data.Challenges.Add("Gcb/Challenge2");
        data.Challenges.Add("Gcb/Challenge0");
        using var stream = new MemoryStream();
        data.SendData(new BinaryWriter(stream));
        stream.Position = 0;
        using var reader = new BinaryReader(stream);
        Check(reader.ReadInt32() == 2, "completion count changed");
        Check(reader.ReadInt32() == 0 && reader.ReadInt32() == 2, "list positions were serialized instead of registry ids");
        Check(stream.Position == stream.Length, "completion frame contained trailing bytes");
    }

    private static void TagCompoundSaveIsDetached()
    {
        var data = new BuildChallengeSaveData("saved");
        data.Challenges.Add("Gcb/Challenge1");
        var tag = new TagCompound();
        data.SaveData(tag);
        data.Challenges.Clear();
        List<string> saved = tag.Get<List<string>>("saved");
        Check(saved.SequenceEqual(new[] { "Gcb/Challenge1" }), "TagCompound save retained live completion state");
    }
}
