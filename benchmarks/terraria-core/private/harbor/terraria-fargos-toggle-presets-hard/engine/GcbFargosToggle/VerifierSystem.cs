using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using FargowiltasSouls.Core.AccessoryEffectSystem;
using FargowiltasSouls.Core.Toggler;
using Terraria;
using Terraria.ModLoader;

namespace GcbFargosToggle;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);

    private sealed class ProbeEffect : AccessoryEffect
    {
        internal string StableName = "Gcb/Stable";
        internal string Description = "[i:1] Engine Toggle";
        internal bool Default = false;
        public override string FullName => StableName;
        public override string ToggleDescription => Description;
        public override bool DefaultToggle => Default;
    }

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;
        var outcomes = new[]
        {
            Run("real_engine_toggle_metadata_snapshot", ToggleMetadataSnapshot),
            Run("real_engine_registry_load_is_fresh", RegistryLoadIsFresh),
            Run("real_engine_duplicate_identity_is_rejected", DuplicateIdentityIsRejected),
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

    private static void ToggleMetadataSnapshot()
    {
        var effect = new ProbeEffect { ToggleHeader = new Header { SortCategory = "Original" } };
        var toggle = new Toggle(effect, "Gcb");
        effect.ToggleHeader = new Header { SortCategory = "Mutated" };
        Check(toggle.Category == "Original", "toggle category followed mutable effect metadata");
        Check(!toggle.ToggleBool, "toggle did not capture its registered default");
        Check(toggle.GetRawToggleName().Contains("Engine Toggle", StringComparison.Ordinal), "real Terraria chat parser lost the toggle label");
    }

    private static void RegistryLoadIsFresh()
    {
        ToggleLoader.LoadedToggles = null;
        ToggleLoader.LoadedHeaders = null;
        ToggleLoader.Load();
        Check(ToggleLoader.LoadedToggles is not null && ToggleLoader.LoadedHeaders is not null, "registry load left collections uninitialized");
    }

    private static void DuplicateIdentityIsRejected()
    {
        ToggleLoader.Load();
        ToggleLoader.RegisterToggle(new Toggle(new ProbeEffect(), "Gcb"));
        bool rejected = false;
        try { ToggleLoader.RegisterToggle(new Toggle(new ProbeEffect(), "Gcb")); }
        catch (InvalidOperationException) { rejected = true; }
        Check(rejected, "two effects with the same stable identity were registered");
    }
}
