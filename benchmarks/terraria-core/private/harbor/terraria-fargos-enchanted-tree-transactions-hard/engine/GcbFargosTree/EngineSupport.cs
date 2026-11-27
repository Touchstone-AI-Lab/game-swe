using System.Collections.Generic;
using Terraria;
using Terraria.ModLoader;

namespace Fargowiltas.Common.Configs
{
    public sealed class FargoServerConfig
    {
        public static FargoServerConfig Instance { get; } = new();
        public bool MiscRecipes { get; set; } = true;
    }
}

namespace Fargowiltas.Common.Systems.Collections
{
    public enum DupeType { NotDupable, NotDupableFromDupable, Direct, MaterialsDupable }

    public static class FargoItemSets
    {
        public static DupeType[] DuplicatableItems { get; } = new DupeType[ItemLoader.ItemCount + 256];
        public static Dictionary<int, List<int>> DuplicatableRecipes { get; } = new();
    }
}

namespace Fargowiltas.Content.Items.Summons
{
    public class BaseSummon : ModItem
    {
        public override bool IsLoadingEnabled(Mod mod) => false;
    }
    public class BaseSpawnBooster : ModItem
    {
        public override bool IsLoadingEnabled(Mod mod) => false;
    }
}

namespace Fargowiltas.Content.Items.Summons.Mutant
{
    public sealed class FleshyDoll : ModItem
    {
        public override bool IsLoadingEnabled(Mod mod) => false;
    }
}

namespace Fargowiltas.Content.Items.Tiles
{
    using Fargowiltas.Common.Systems.Collections;

    public static class EnchantedTreeTileEntity
    {
        public static bool IsItemDupable(int type)
            => type > 0 && type < FargoItemSets.DuplicatableItems.Length
                && FargoItemSets.DuplicatableItems[type] != DupeType.NotDupable
                && FargoItemSets.DuplicatableItems[type] != DupeType.NotDupableFromDupable;
    }
}

namespace Fargowiltas.Utilities
{
    public static class RecipeHelper
    {
        public static Recipe CreateSimpleRecipe(int ingredient, int result, int tile,
            int ingredientAmount = 1, bool disableDecraft = false, params object[] conditions)
        {
            Recipe recipe = Recipe.Create(result).AddIngredient(ingredient, ingredientAmount).AddTile(tile);
            if (disableDecraft) recipe.DisableDecraft();
            recipe.Register();
            return recipe;
        }
    }
}

namespace Fargowiltas.Common.Systems.Recipes
{
    public static class RecipeGroups
    {
        public const int AnyCommonFish = 0;
        public const int AnyGoldBar = 1;
        public const int AnyEvilBar = 2;
    }
}

namespace Fargowiltas
{
    public sealed class FargoGlobalItem : GlobalItem
    {
        public override bool InstancePerEntity => true;
        public List<int>? RecipeGroupAnimationItems { get; set; }
    }
}

namespace Fargowiltas.Content.Items { }
