using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using Fargowiltas.Common.Systems.Collections;
using Fargowiltas.Common.Systems.Recipes;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace GcbFargosTree;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);
    private const int Result = ItemID.RedPotion;
    private const int IncludedIngredient = ItemID.StoneBlock;
    private const int ExcludedIngredient = ItemID.DirtBlock;

    public override void AddRecipes()
    {
        ResetSets();
        FargoItemSets.DuplicatableItems[Result] = DupeType.MaterialsDupable;
        FargoItemSets.DuplicatableItems[IncludedIngredient] = DupeType.Direct;
        FargoItemSets.DuplicatableItems[ExcludedIngredient] = DupeType.NotDupableFromDupable;
        FargoItemSets.DuplicatableRecipes[-123] = new() { -456 };

        Recipe recipe = Recipe.Create(Result)
            .AddIngredient(IncludedIngredient)
            .AddIngredient(ExcludedIngredient);
        recipe.requiredItem.Add(new Item(IncludedIngredient));
        recipe.Register();
    }

    public override void PostSetupRecipes()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;
        var outcomes = new[]
        {
            Run("real_engine_recipe_graph_drops_stale_entries", RecipeGraphDropsStaleEntries),
            Run("real_engine_recipe_graph_deduplicates_ingredients", RecipeGraphDeduplicatesIngredients),
            Run("real_engine_recipe_graph_honors_not_from_dupable", RecipeGraphHonorsNotFromDupable),
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

    private static void ResetSets()
    {
        Array.Clear(FargoItemSets.DuplicatableItems);
        FargoItemSets.DuplicatableRecipes.Clear();
    }

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void RecipeGraphDropsStaleEntries()
    {
        Check(!FargoItemSets.DuplicatableRecipes.ContainsKey(-123), "stale recipe graph entry survived final setup");
        Check(FargoItemSets.DuplicatableRecipes.TryGetValue(Result, out var values) && values.Contains(IncludedIngredient),
            "real registered recipe was absent from the duplication graph");
    }

    private static void RecipeGraphDeduplicatesIngredients()
    {
        int count = FargoItemSets.DuplicatableRecipes[Result].Count(value => value == IncludedIngredient);
        Check(count == 1, "duplicate real recipe ingredients were retained");
    }

    private static void RecipeGraphHonorsNotFromDupable()
    {
        Check(FargoItemSets.DuplicatableRecipes.TryGetValue(Result, out var values),
            "real registered recipe was absent from the duplication graph");
        bool included = values.Contains(ExcludedIngredient);
        Check(!included, "NotDupableFromDupable ingredient leaked into the real recipe graph");
    }
}
