using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using SpiritMod.Mechanics.QuestSystem;
using SpiritMod.Mechanics.QuestSystem.Tasks;
using Terraria;
using Terraria.ModLoader;

namespace GcbSpiritQuest;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);

    private sealed class ProbeTask : QuestTask
    {
        internal int Value;
        internal ProbeTask(int id, int value = 0) { TaskID = id; Value = value; }
        public override void WriteData(BinaryWriter writer) => writer.Write(Value);
        public override void ReadData(BinaryReader reader) => Value = reader.ReadInt32();
    }

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;
        var outcomes = new[]
        {
            Run("real_engine_branch_constructor_snapshots_input", ConstructorSnapshotsInput),
            Run("real_engine_branch_rejects_null_child", RejectsNullChild),
            Run("real_engine_branch_frame_roundtrip", BranchFrameRoundtrip),
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

    private static void ConstructorSnapshotsInput()
    {
        var first = new ProbeTask(1);
        QuestTask[] input = { first };
        var branch = new BranchingTask(input);
        input[0] = new ProbeTask(2);
        Check(ReferenceEquals(branch.Tasks.Single(), first), "branch retained the caller's mutable task array");
    }

    private static void RejectsNullChild()
    {
        bool rejected = false;
        try { _ = new BranchingTask(new QuestTask[] { null! }); }
        catch (ArgumentException) { rejected = true; }
        Check(rejected, "null branch child was accepted");
    }

    private static void BranchFrameRoundtrip()
    {
        var left = new ProbeTask(10, 111) { Completed = true };
        var right = new ProbeTask(11, 222);
        var source = new BranchingTask(left, right);
        Check(source.CheckCompletion(), "source branch did not select its completed child");
        using var stream = new MemoryStream();
        source.WriteData(new BinaryWriter(stream));
        byte[] frame = stream.ToArray();
        Check(frame.Length >= 3 && frame[0] == 1 && frame[1] == 2 && frame[2] == 0, "branch frame header was not versioned");

        var targetLeft = new ProbeTask(10);
        var targetRight = new ProbeTask(11);
        var target = new BranchingTask(targetLeft, targetRight);
        target.ReadData(new BinaryReader(new MemoryStream(frame, writable: false)));
        Check(targetLeft.Value == 111 && targetRight.Value == 222, "branch child payloads did not roundtrip");
        Check(targetLeft.Completed && target.taskSlotForMP == 0, "branch selection metadata did not roundtrip");
    }
}
