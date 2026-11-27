using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using ImproveGame.Content.Items;
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ModLoader;

namespace GcbImproveGameSpaceWand;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;
        var outcomes = new[]
        {
            Run("real_worldgen_out_of_world_start_is_empty", OutOfWorldStartIsEmpty),
            Run("real_worldgen_square_is_clipped", SquareIsClipped),
            Run("real_worldgen_corner_stops_after_clipping", CornerStopsAfterClipping),
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

    private static Vector2 WorldPoint(int tileX, int tileY) => new(tileX * 16f, tileY * 16f);

    private static void RequireWorldBounds()
    {
        Check(Main.maxTilesX > 100 && Main.maxTilesY > 100, "real WorldGen bounds were not initialized");
    }

    private static void OutOfWorldStartIsEmpty()
    {
        RequireWorldBounds();
        var tiles = SpaceWand.GetLineTiles(WorldPoint(1, 1), WorldPoint(40, 1)).ToList();
        Check(tiles.Count == 0, "line emitted a tile outside the real WorldGen safety margin");
    }

    private static void SquareIsClipped()
    {
        RequireWorldBounds();
        var tiles = SpaceWand.GetSquareTiles(WorldPoint(11, 11), WorldPoint(-200, -200), true).ToList();
        Check(tiles.Count > 0, "clipped square unexpectedly became empty");
        Check(tiles.All(point => WorldGen.InWorld(point.X, point.Y, 10)), "square emitted out-of-world tiles");
    }

    private static void CornerStopsAfterClipping()
    {
        RequireWorldBounds();
        var tiles = SpaceWand.GetCornerTiles(WorldPoint(11, 11), WorldPoint(50, -20), false);
        Check(tiles.Count > 0, "corner unexpectedly became empty");
        Check(tiles.All(point => WorldGen.InWorld(point.X, point.Y, 10)), "corner continued after crossing the real world boundary");
    }
}
