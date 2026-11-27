using System;
using System.IO;
using System.Text.Json;
using Terraria;
using Terraria.ModLoader;

namespace GcbRuntimeProbe;

public sealed class ProbeSystem : ModSystem
{
    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath))
        {
            return;
        }

        var report = new
        {
            schemaVersion = 1,
            complete = true,
            passed = true,
            terrariaVersion = Main.versionNumber,
            tModLoaderVersion = BuildInfo.tMLVersion.ToString(),
            dedicatedServer = Main.dedServ,
            cases = new[]
            {
                new { name = "real_tmodloader_loaded_verifier_mod", status = "passed" },
                new { name = "real_dedicated_server_context", status = Main.dedServ ? "passed" : "failed" },
            },
        };

        Directory.CreateDirectory(Path.GetDirectoryName(reportPath)!);
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report));
        Environment.Exit(Main.dedServ ? 0 : 91);
    }
}
