using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using NetEasy;
using StarlightRiver.Content.Abilities;
using StarlightRiver.Content.Abilities.ForbiddenWinds;
using StarlightRiver.Content.Packets;
using Terraria;
using Terraria.ModLoader;

namespace GcbStarlightAbility;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);
    private sealed class ProbeAbility : Ability { }

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;
        var outcomes = new[]
        {
            Run("real_server_start_rejects_invalid_player", StartRejectsInvalidPlayer),
            Run("real_server_start_rejects_spoofed_sender", StartRejectsSpoofedSender),
            Run("real_server_progress_rejects_spoofed_sender", ProgressRejectsSpoofedSender),
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

    private static void InvokeReceive(NetEasy.Module packet)
    {
        MethodInfo receive = packet.GetType().GetMethod("Receive", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(packet.GetType().FullName, "Receive");
        try { receive.Invoke(packet, null); }
        catch (TargetInvocationException error) { throw error.InnerException ?? error; }
    }

    private static Player PlayerZero()
        => Main.player.Length > 0 && Main.player[0] is not null
            ? Main.player[0]
            : throw new InvalidOperationException("real engine player slot zero is unavailable");

    private static void StartRejectsInvalidPlayer()
    {
        var packet = new StartAbility(Main.player.Length + 10, new ProbeAbility()) { Sender = 0 };
        InvokeReceive(packet);
        Check(packet.SendCount == 0, "invalid player packet was relayed");
    }

    private static void StartRejectsSpoofedSender()
    {
        AbilityHandler handler = PlayerZero().GetHandler();
        handler.ResetState();
        var ability = new ProbeAbility { User = handler };
        handler.unlockedAbilities.Add(typeof(ProbeAbility), ability);
        var packet = new StartAbility(0, ability) { Sender = 1 };
        InvokeReceive(packet);
        Check(handler.ActiveAbility is null && packet.SendCount == 0, "spoofed ability start mutated real server state");
    }

    private static void ProgressRejectsSpoofedSender()
    {
        AbilityHandler target = PlayerZero().GetHandler();
        target.ResetState();
        var source = new AbilityHandler();
        source.Shards.Add(17);
        source.Unlock<Dash>();
        var packet = new AbilityProgress(0, source) { Sender = 1 };
        InvokeReceive(packet);
        Check(target.Shards.Count == 0 && target.unlockedAbilities.Count == 0 && packet.SendCount == 0,
            "spoofed progress mutated real server state");
    }
}
