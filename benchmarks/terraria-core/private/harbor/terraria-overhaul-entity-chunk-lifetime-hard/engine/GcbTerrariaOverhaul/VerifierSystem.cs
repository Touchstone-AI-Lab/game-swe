using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Microsoft.Xna.Framework;
using Terraria.ModLoader;
using TerrariaOverhaul.Core.Chunks;
using TerrariaOverhaul.Core.Data;
using TerrariaOverhaul.Utilities.Xna;

namespace GcbTerrariaOverhaul;

public sealed class VerifierSystem : ModSystem
{
    private struct FilterA : IComponent
    {
    }

    private struct FilterB : IComponent
    {
    }

    private sealed record CaseOutcome(string Name, bool Passed, string? Error);

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath))
        {
            return;
        }

        Terraria.Main.maxTilesX = 256;
        Terraria.Main.maxTilesY = 192;

        var outcomes = new[]
        {
            Run("real_engine_active_query_snapshot", ActiveQuerySnapshot),
            Run("real_engine_world_coordinate_entrypoint", WorldCoordinateEntrypoint),
            Run("real_engine_creation_observer_transaction", CreationObserverTransaction),
        };
        bool passed = outcomes.All(outcome => outcome.Passed);
        var report = new
        {
            schemaVersion = 1,
            complete = true,
            passed,
            terrariaVersion = Terraria.Main.versionNumber,
            tModLoaderVersion = BuildInfo.tMLVersion.ToString(),
            dedicatedServer = Terraria.Main.dedServ,
            cases = outcomes.Select(outcome => new
            {
                name = outcome.Name,
                status = outcome.Passed ? "passed" : "failed",
                error = outcome.Error,
            }),
        };
        Directory.CreateDirectory(Path.GetDirectoryName(reportPath)!);
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report));
        Environment.Exit(passed && Terraria.Main.dedServ ? 0 : 90);
    }

    private static CaseOutcome Run(string name, Action test)
    {
        try
        {
            test();
            return new CaseOutcome(name, true, null);
        }
        catch (Exception error)
        {
            return new CaseOutcome(name, false, error.ToString());
        }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    private static int[] Indices(Query query)
    {
        var result = new List<int>();
        foreach (DataEntity entity in query)
        {
            result.Add((int)entity.Index);
        }
        return result.ToArray();
    }

    private static void ActiveQuerySnapshot()
    {
        Query query = DataStorage.CreateQuery().With<FilterA>();
        DataEntity entity = DataStorage.CreateEntity();
        entity.Add(new FilterA());
        entity.Add(new FilterB());
        Query.Iterator iterator = query.GetEnumerator();
        query.Without<FilterB>();
        Check(
            iterator.MoveNext() && iterator.Current.Index == entity.Index,
            "an active query observed a later filter mutation"
        );
        Check(
            !Indices(query).Contains((int)entity.Index),
            "a later query did not observe its updated exclusion filter"
        );
    }

    private static void WorldCoordinateEntrypoint()
    {
        new Chunks().Load();
        Check(
            Chunks.TryGetOrCreateChunkAtWorldPosition(new Vector2(65 * 16 + 1, 1), out Chunk created),
            "an in-bounds real-engine world position was rejected"
        );
        Check(
            Chunks.TryGetChunk(new Vector2Int(1, 0), out Chunk mapped),
            "the world position did not map to its containing chunk"
        );
        Check(
            mapped.Entity.Index == created.Entity.Index
                && !Chunks.TryGetChunk(new Vector2Int(0, 0), out _),
            "the world coordinate was converted more than once"
        );
    }

    private static void CreationObserverTransaction()
    {
        new Chunks().Load();
        int throwingCalls = 0;
        int laterCalls = 0;
        Chunks.OnChunkCreatedDelegate throwing = _ =>
        {
            throwingCalls++;
            throw new InvalidOperationException("expected observer failure");
        };
        Chunks.OnChunkCreatedDelegate later = _ => laterCalls++;
        Chunks.OnChunkCreated += throwing;
        Chunks.OnChunkCreated += later;
        try
        {
            bool accepted = Chunks.TryGetOrCreateChunk(new Vector2Int(1, 0), out Chunk created);
            Check(accepted && created.Entity.IsValid, "observer failure invalidated creation");
            Check(throwingCalls == 1 && laterCalls == 1, "observer isolation did not run every subscriber");
            Check(
                Chunks.TryGetChunk(new Vector2Int(1, 0), out Chunk mapped)
                    && mapped.Entity.Index == created.Entity.Index,
                "observer failure stranded the canonical chunk"
            );
        }
        finally
        {
            Chunks.OnChunkCreated -= throwing;
            Chunks.OnChunkCreated -= later;
        }
    }
}
