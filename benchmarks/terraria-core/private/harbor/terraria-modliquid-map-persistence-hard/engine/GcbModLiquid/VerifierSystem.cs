using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Microsoft.Xna.Framework;
using ModLiquidLib.IO;
using ModLiquidLib.ModLoader;
using Terraria;
using Terraria.ID;
using Terraria.Localization;
using Terraria.Map;
using Terraria.ModLoader;
using LiquidMapEntry = ModLiquidLib.ModLoader.MapEntry;

namespace GcbModLiquid;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;

        var outcomes = new[]
        {
            Run("real_engine_dedicated_server_unload_clears_registry", DedicatedServerUnloadClearsRegistry),
            Run("real_engine_registry_collision_is_atomic", RegistryCollisionIsAtomic),
            Run("real_engine_map_decode_is_transactional", MapDecodeIsTransactional),
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

    private static void DedicatedServerUnloadClearsRegistry()
    {
        ushort customType = checked((ushort)LiquidID.Count);
        Func<string, int, int, string> ownedName = (name, _, _) => name;
        MapLiquidLoader.liquidEntries.Clear();
        MapLiquidLoader.entryToLiquid.Clear();
        LiquidLoader.LiquidCount = LiquidID.Count + 1;
        MapLiquidLoader.liquidEntries[customType] = new List<LiquidMapEntry>
        {
            new(Color.CornflowerBlue, Language.GetOrRegister("Mods.GcbModLiquid.Unload"), ownedName),
        };
        MapLiquidLoader.liquidLookup = new ushort[LiquidID.Count];
        IList<Color> colors = new List<Color> { Color.Black, Color.Gray };
        IList<LocalizedText> names = new List<LocalizedText>
        {
            Language.GetOrRegister("Mods.GcbModLiquid.Base0"),
            Language.GetOrRegister("Mods.GcbModLiquid.Base1"),
        };
        ushort mapType = checked((ushort)(MapHelper.modPosition + colors.Count));
        MapLoader.entryToTile.Remove(mapType);
        MapLoader.entryToWall.Remove(mapType);
        MapLoader.nameFuncs.Remove(mapType);
        MapLiquidLoader.PublishEntries(ref colors, ref names);
        MapLiquidLoader.initialized = true;
        uint generation = MapLiquidLoader.Generation;

        MapLiquidLoader.UnloadModMap();

        Check(MapLiquidLoader.liquidEntries.Count == 0, "liquid definitions survived dedicated-server unload");
        Check(MapLiquidLoader.entryToLiquid.Count == 0, "reverse liquid mappings survived dedicated-server unload");
        Check(MapLiquidLoader.liquidLookup.Length == LiquidID.Count, "liquid lookup was not truncated to vanilla range");
        Check(!MapLoader.nameFuncs.ContainsKey(mapType), "owned name callback survived dedicated-server unload");
        Check(!MapLiquidLoader.initialized, "registry remained initialized after dedicated-server unload");
        Check(MapLiquidLoader.Generation == unchecked(generation + 1), "unload did not advance exactly one generation");
    }

    private static void RegistryCollisionIsAtomic()
    {
        MapLiquidLoader.liquidEntries.Clear();
        MapLiquidLoader.entryToLiquid.Clear();
        LiquidLoader.LiquidCount = LiquidID.Count + 1;
        ushort customType = checked((ushort)LiquidID.Count);
        var colors = (IList<Color>)new List<Color> { Color.Black };
        var names = (IList<LocalizedText>)new List<LocalizedText>
        {
            Language.GetOrRegister("Mods.GcbModLiquid.Existing"),
        };
        MapLiquidLoader.liquidEntries[customType] = new List<LiquidMapEntry>
        {
            new(Color.Blue, Language.GetOrRegister("Mods.GcbModLiquid.Candidate")),
        };
        MapLiquidLoader.liquidLookup = new ushort[LiquidID.Count];
        ushort target = checked((ushort)(MapHelper.modPosition + colors.Count));
        Func<string, int, int, string> sentinel = (name, _, _) => "sentinel:" + name;
        MapLoader.entryToTile.Remove(target);
        MapLoader.entryToWall.Remove(target);
        MapLoader.nameFuncs[target] = sentinel;
        IList<Color> originalColors = colors;
        IList<LocalizedText> originalNames = names;
        Color[] colorsBefore = colors.ToArray();
        LocalizedText[] namesBefore = names.ToArray();
        uint generation = MapLiquidLoader.Generation;

        bool rejected = false;
        try { MapLiquidLoader.PublishEntries(ref colors, ref names); }
        catch (InvalidOperationException) { rejected = true; }

        Check(rejected, "colliding real MapLoader name callback was not rejected");
        Check(ReferenceEquals(colors, originalColors) && ReferenceEquals(names, originalNames),
            "failed publication replaced caller table references");
        Check(colors.SequenceEqual(colorsBefore) && names.SequenceEqual(namesBefore),
            "failed publication changed caller table contents");
        Check(MapLiquidLoader.entryToLiquid.Count == 0, "failed publication leaked reverse mappings");
        Check(MapLiquidLoader.liquidLookup.Length == LiquidID.Count, "failed publication replaced the liquid lookup");
        Check(MapLoader.nameFuncs.TryGetValue(target, out var callback) && ReferenceEquals(callback, sentinel),
            "failed publication changed an existing MapLoader callback");
        Check(MapLiquidLoader.Generation == generation, "failed publication advanced the registry generation");
    }

    private static void MapDecodeIsTransactional()
    {
        const ushort oldType = 700;
        const ushort resolvedType = 701;
        Main.maxTilesX = 2;
        Main.maxTilesY = 1;
        Main.Map = new WorldMap(Main.maxTilesX, Main.maxTilesY);
        MapTile originalFirst = MapTile.Create(11, 41, 3);
        MapTile originalSecond = MapTile.Create(12, 42, 4);
        Main.Map.SetTile(0, 0, ref originalFirst);
        Main.Map.SetTile(1, 0, ref originalSecond);

        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, leaveOpen: true))
        {
            writer.Write((byte)0);
            writer.Write((byte)0x20);
            writer.Write(oldType);
            writer.Write((byte)0);
            writer.Write((ushort)(oldType + 1));
        }
        stream.Position = 0;
        var table = new Dictionary<ushort, ushort> { [oldType] = resolvedType };
        bool invalidData = false;
        try
        {
            using var reader = new BinaryReader(stream, System.Text.Encoding.UTF8, leaveOpen: true);
            MapLiquidIO.ReadMapData(reader, table);
        }
        catch (InvalidDataException) { invalidData = true; }

        Check(invalidData, "malformed real WorldMap payload was not normalized to InvalidDataException");
        MapTile firstAfter = Main.Map[0, 0];
        MapTile secondAfter = Main.Map[1, 0];
        Check(firstAfter.Equals(ref originalFirst) && secondAfter.Equals(ref originalSecond),
            "malformed payload partially mutated the real WorldMap");
    }
}
