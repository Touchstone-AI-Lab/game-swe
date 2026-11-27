using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Fargowiltas;
using Fargowiltas.Common.Systems.Collections;
using Fargowiltas.Common.Systems.Recipes;
using Fargowiltas.Content.Items.Tiles;
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.DataStructures;
using Terraria.ID;
using Terraria.ModLoader.IO;

internal static class Program
{
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["insert-stores-held-type"] = () => Insert().Tree.ItemType.ShouldBe(300),
        ["insert-consumes-exactly-one"] = () => Insert(stack: 4).Player.HeldItem.stack.ShouldBe(3),
        ["insert-preserves-prefix"] = () => Insert(prefix: 71).Tree.Prefix.ShouldBe(71),
        ["insert-acknowledges-right-click"] = () => Insert().Result.ShouldBe(true),
        ["insert-arms-removal-cooldown"] = () => Insert().Tree.CursorInsertCooldown.ShouldBe(10),
        ["insert-creates-root-fruit-for-eligible-item"] = TestEligibleInsertionFruit,
        ["insert-does-not-create-fruit-for-ineligible-item"] = TestIneligibleInsertionFruit,
        ["insert-rejects-favorited-item-atomically"] = TestFavoritedInsertion,
        ["insert-rejects-occupied-tree-atomically"] = TestOccupiedInsertion,
        ["insert-rejects-server-authority"] = TestServerInsertion,
        ["insert-sync-uses-canonical-tree-index"] = TestCanonicalInsertSync,
        ["single-player-insert-does-not-send-tree-packet"] = TestSinglePlayerNoSync,
        ["removal-is-blocked-during-cooldown"] = TestRemovalBlocked,
        ["removal-ejects-stored-item-once"] = TestRemovalEjects,
        ["removal-preserves-stored-prefix"] = TestRemovalPrefix,
        ["removal-clears-stored-type"] = TestRemovalClears,
        ["removal-marks-all-live-fruit-for-despawn"] = TestRemovalMarksFruit,
        ["late-recipe-is-discovered-after-setup"] = TestLateRecipe,
        ["directly-duplicatable-ingredient-is-retained"] = TestDirectIngredient,
        ["material-policy-retains-ordinary-ingredient"] = TestMaterialIngredient,
        ["material-policy-rejects-not-dupable-from-dupable"] = TestForbiddenIngredient,
        ["recipe-branches-deduplicate-ingredients"] = TestRecipeDeduplication,
        ["recipe-branches-preserve-discovery-order"] = TestRecipeOrder,
        ["recipe-rebuild-removes-stale-result"] = TestRecipeRebuildRemovesStaleResult,
        ["recipe-rebuild-replaces-stale-ingredients"] = TestRecipeRebuildReplacesStaleIngredients,
        ["recipe-rebuild-preserves-dictionary-reference"] = TestRecipeRebuildPreservesReference,
        ["recipe-rebuild-is-idempotent"] = TestRecipeRebuildIdempotent,
        ["recipe-rebuild-drops-newly-ineligible-result"] = TestRecipeRebuildDropsIneligibleResult,
        ["network-roundtrip-preserves-header"] = TestNetworkHeader,
        ["network-roundtrip-preserves-fruit-state"] = TestNetworkFruit,
        ["network-receive-replaces-stale-fruit"] = TestNetworkReplacement,
        ["network-receive-negative-count-rolls-back"] = TestNegativeFruitCount,
        ["network-receive-excessive-count-rolls-back"] = TestExcessiveFruitCount,
        ["network-receive-truncated-header-rolls-back"] = TestTruncatedHeader,
        ["network-receive-truncated-fruit-rolls-back"] = TestTruncatedFruit,
        ["network-receive-nan-center-rolls-back"] = TestNanCenter,
        ["network-receive-infinite-target-rolls-back"] = TestInfiniteTarget,
        ["network-receive-infinite-velocity-rolls-back"] = TestInfiniteVelocity,
        ["network-receive-nonfinite-despawn-rolls-back"] = TestNonfiniteDespawn,
        ["network-receive-negative-despawn-rolls-back"] = TestNegativeDespawn,
        ["network-receive-negative-grab-cooldown-rolls-back"] = TestNegativeGrabCooldown,
        ["network-receive-root-layer-rolls-back"] = TestRootLayer,
        ["network-receive-forward-parent-rolls-back"] = TestForwardParent,
        ["network-receive-negative-parent-rolls-back"] = TestNegativeParent,
        ["network-receive-layer-mismatch-rolls-back"] = TestLayerMismatch,
        ["network-receive-valid-multilevel-forest"] = TestValidMultilevelForest,
        ["network-receive-valid-multiroot-forest"] = TestValidMultirootForest,
        ["network-send-invalid-topology-is-atomic"] = TestInvalidTopologySendAtomicity,
        ["network-send-invalid-scalar-is-atomic"] = TestInvalidScalarSendAtomicity,
        ["network-send-excessive-count-is-atomic"] = TestExcessiveCountSendAtomicity,
        ["network-receive-accepts-limit"] = TestFruitCountLimit,
        ["network-receive-leaves-following-field-aligned"] = TestNetworkFrameAlignment,
        ["save-load-roundtrip-preserves-item-and-prefix"] = TestSaveLoad,
        ["missing-tree-entry-does-not-block-later-cooldown"] = TestMissingTreeContinuation,
        ["adjacent-expired-fruit-are-all-removed"] = TestAdjacentFruitRemoval,
        ["expired-removal-rebases-later-parent"] = TestRemovalRebasesLaterParent,
        ["adjacent-expired-removal-rebases-deep-survivor"] = TestAdjacentRemovalRebasesSurvivor,
        ["removed-internal-parent-relinks-child"] = TestRemovedInternalParentRelinksChild,
        ["removed-root-promotes-direct-child"] = TestRemovedRootPromotesChild,
        ["removed-grabbed-fruit-clears-ownership"] = TestRemovedGrabbedFruitClearsOwnership,
        ["expired-removal-preserves-fruit-list-reference"] = TestRemovalPreservesListReference,
        ["branch-expansion-adds-recipe-children-in-order"] = TestBranchExpansionOrder,
        ["branch-expansion-links-parent-and-next-layer"] = TestBranchExpansionLinks,
        ["fading-direct-child-still-blocks-duplicate-expansion"] = TestFadingChildBlocksExpansion,
        ["revisiting-branch-despawns-deeper-live-fruit"] = TestBranchPrunesDescendants,
        ["revisiting-branch-preserves-unrelated-deep-fruit"] = TestBranchPreservesUnrelatedDescendant,
        ["revisiting-branch-prunes-through-fading-child"] = TestBranchPrunesThroughFadingChild,
        ["branch-mutation-syncs-on-multiplayer-client"] = TestBranchMutationSync,
        ["unchanged-branch-does-not-sync"] = TestUnchangedBranchNoSync,
        ["drag-release-clears-player-ownership"] = TestDragReleaseOwnership,
        ["drag-release-arms-grab-cooldown"] = TestDragReleaseCooldown,
        ["duplication-charges-double-item-value"] = TestDuplicationCost,
        ["successful-duplication-preserves-prefix-and-tags-item"] = TestDuplicationSpawnState,
        ["successful-duplication-syncs-spawned-item"] = TestDuplicationSync,
        ["failed-duplication-is-payment-atomic"] = TestDuplicationFailure,
        ["duplicate-tree-coordinate-decrements-cooldown-once"] = TestDuplicateCoordinateCooldown,
        ["duplicate-tree-coordinate-advances-despawn-once"] = TestDuplicateCoordinateDespawn,
        ["duplicate-tree-coordinate-does-not-consume-new-purchase-cooldown"] = TestDuplicateCoordinatePurchaseCooldown,
    };

    public static int Execute(string[] args)
    {
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out Action test))
        {
            Console.Error.WriteLine("unknown case");
            return 2;
        }
        try
        {
            test();
            Console.WriteLine("PASS");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"{error.GetType().Name}: {error.Message}");
            return 1;
        }
    }

    private static (EnchantedTreeSheet Sheet, EnchantedTreeTileEntity Tree, Player Player, bool Result) Insert(
        int stack = 2, int prefix = 5, bool favorite = false, int type = 300, int netMode = NetmodeID.MultiplayerClient)
    {
        Reset();
        FargoItemSets.DuplicatableItems[type] = DupeType.Direct;
        Player player = new() { active = true, dead = false, whoAmI = 2, HeldItem = new Item { type = type, stack = stack, prefix = prefix, favorited = favorite } };
        Main.LocalPlayer = player;
        Main.myPlayer = player.whoAmI;
        Main.netMode = netMode;
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        EnchantedTreeSheet sheet = new();
        bool result = sheet.RightClick(4, 6);
        return (sheet, tree, player, result);
    }

    private static void TestEligibleInsertionFruit()
    {
        var state = Insert();
        state.Tree.Fruits.Count.ShouldBe(1);
        state.Tree.Fruits[0].type.ShouldBe(300);
        state.Tree.Fruits[0].previousItem.ShouldBe(0);
    }

    private static void TestIneligibleInsertionFruit()
    {
        var state = Insert(type: 300);
        FargoItemSets.DuplicatableItems[300] = DupeType.NotDupable;
        Reset();
        Player player = new() { active = true, HeldItem = new Item { type = 300, stack = 2 } };
        Main.LocalPlayer = player;
        Main.netMode = NetmodeID.SinglePlayer;
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        new EnchantedTreeSheet().RightClick(4, 6);
        tree.Fruits.Count.ShouldBe(0);
    }

    private static void TestFavoritedInsertion()
    {
        var state = Insert(favorite: true);
        state.Result.ShouldBe(false);
        state.Tree.ItemType.ShouldBe(-1);
        state.Player.HeldItem.stack.ShouldBe(2);
        FargoNet.FruitPackets.Count.ShouldBe(0);
    }

    private static void TestOccupiedInsertion()
    {
        var state = Insert();
        state.Tree.CursorInsertCooldown = 5;
        state.Player.HeldItem = new Item { type = 301, stack = 2, prefix = 9 };
        bool result = state.Sheet.RightClick(4, 6);
        result.ShouldBe(false);
        state.Tree.ItemType.ShouldBe(300);
        state.Player.HeldItem.stack.ShouldBe(2);
    }

    private static void TestServerInsertion()
    {
        var state = Insert(netMode: NetmodeID.Server);
        state.Result.ShouldBe(false);
        state.Tree.ItemType.ShouldBe(-1);
        state.Player.HeldItem.stack.ShouldBe(2);
    }

    private static void TestCanonicalInsertSync()
    {
        Insert();
        FargoNet.FruitPackets.SequenceEqual(new[] { 0 }).ShouldBe(true);
    }

    private static void TestSinglePlayerNoSync()
    {
        Insert(netMode: NetmodeID.SinglePlayer);
        FargoNet.FruitPackets.Count.ShouldBe(0);
    }

    private static (EnchantedTreeSheet Sheet, EnchantedTreeTileEntity Tree, Player Player) Removal(int cooldown = 0, int prefix = 44)
    {
        Reset();
        Main.netMode = NetmodeID.SinglePlayer;
        Player player = new() { active = true, whoAmI = 3, HeldItem = new Item { type = 0, stack = 0 } };
        Main.LocalPlayer = player;
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        tree.ItemType = 320;
        tree.Prefix = prefix;
        tree.CursorInsertCooldown = cooldown;
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        return (new EnchantedTreeSheet(), tree, player);
    }

    private static void TestRemovalBlocked()
    {
        var state = Removal(cooldown: 1);
        state.Sheet.RightClick(4, 6).ShouldBe(false);
        state.Tree.ItemType.ShouldBe(320);
        Spawned().Count.ShouldBe(0);
    }

    private static void TestRemovalEjects()
    {
        var state = Removal();
        state.Sheet.RightClick(4, 6).ShouldBe(true);
        List<Item> spawned = Spawned();
        spawned.Count.ShouldBe(1);
        spawned[0].type.ShouldBe(320);
        spawned[0].stack.ShouldBe(1);
    }

    private static void TestRemovalPrefix()
    {
        var state = Removal(prefix: 87);
        state.Sheet.RightClick(4, 6);
        Spawned().Single().prefix.ShouldBe(87);
    }

    private static void TestRemovalClears()
    {
        var state = Removal();
        state.Sheet.RightClick(4, 6);
        state.Tree.ItemType.ShouldBe(-1);
    }

    private static void TestRemovalMarksFruit()
    {
        var state = Removal();
        state.Tree.Fruits.Add(Fruit(1, despawn: 0));
        state.Tree.Fruits.Add(Fruit(2, despawn: 7));
        state.Tree.Fruits.Add(Fruit(3, despawn: 0));
        state.Sheet.RightClick(4, 6);
        state.Tree.Fruits.Select(x => x.despawnTimer).SequenceEqual(new[] { 1f, 7f, 1f }).ShouldBe(true);
    }

    private static void TestLateRecipe()
    {
        Reset();
        ConfigurePolicy(350, DupeType.Direct, 351, DupeType.Direct);
        MiscRecipeSystem system = new();
        system.PostAddRecipes();
        Main.recipe.Add(MakeRecipe(350, 351));
        system.PostSetupRecipes();
        FargoItemSets.DuplicatableRecipes[350].SequenceEqual(new[] { 351 }).ShouldBe(true);
    }

    private static void TestDirectIngredient()
    {
        RunRecipes(MakeRecipeWithPolicy(352, DupeType.Direct, (353, DupeType.Direct)));
        FargoItemSets.DuplicatableRecipes[352].SequenceEqual(new[] { 353 }).ShouldBe(true);
    }

    private static void TestMaterialIngredient()
    {
        RunRecipes(MakeRecipeWithPolicy(354, DupeType.MaterialsDupable, (355, DupeType.NotDupable)));
        FargoItemSets.DuplicatableRecipes[354].SequenceEqual(new[] { 355 }).ShouldBe(true);
    }

    private static void TestForbiddenIngredient()
    {
        RunRecipes(MakeRecipeWithPolicy(356, DupeType.MaterialsDupable, (357, DupeType.NotDupableFromDupable)));
        FargoItemSets.DuplicatableRecipes[356].Count.ShouldBe(0);
    }

    private static void TestRecipeDeduplication()
    {
        Reset();
        ConfigurePolicy(358, DupeType.Direct, 359, DupeType.Direct);
        Main.recipe.Add(MakeRecipe(358, 359, 359));
        Main.recipe.Add(MakeRecipe(358, 359));
        MiscRecipeSystem system = new();
        system.PostAddRecipes();
        system.PostSetupRecipes();
        FargoItemSets.DuplicatableRecipes[358].SequenceEqual(new[] { 359 }).ShouldBe(true);
    }

    private static void TestRecipeOrder()
    {
        RunRecipes(MakeRecipeWithPolicy(360, DupeType.Direct, (361, DupeType.Direct), (362, DupeType.Direct), (363, DupeType.Direct)));
        FargoItemSets.DuplicatableRecipes[360].SequenceEqual(new[] { 361, 362, 363 }).ShouldBe(true);
    }

    private static void TestRecipeRebuildRemovesStaleResult()
    {
        Reset();
        ConfigurePolicy(364, DupeType.Direct, 365, DupeType.Direct);
        Main.recipe.Add(MakeRecipe(364, 365));
        MiscRecipeSystem system = new();
        system.PostSetupRecipes();
        FargoItemSets.DuplicatableRecipes.ContainsKey(364).ShouldBe(true);

        Main.recipe.Clear();
        system.PostSetupRecipes();
        FargoItemSets.DuplicatableRecipes.ContainsKey(364).ShouldBe(false);
    }

    private static void TestRecipeRebuildReplacesStaleIngredients()
    {
        Reset();
        ConfigurePolicy(366, DupeType.Direct, 367, DupeType.Direct);
        FargoItemSets.DuplicatableItems[368] = DupeType.Direct;
        Main.recipe.Add(MakeRecipe(366, 367));
        MiscRecipeSystem system = new();
        system.PostSetupRecipes();

        Main.recipe.Clear();
        Main.recipe.Add(MakeRecipe(366, 368));
        system.PostSetupRecipes();
        FargoItemSets.DuplicatableRecipes[366].SequenceEqual(new[] { 368 }).ShouldBe(true);
    }

    private static void TestRecipeRebuildPreservesReference()
    {
        Reset();
        Dictionary<int, List<int>> original = FargoItemSets.DuplicatableRecipes;
        ConfigurePolicy(369, DupeType.Direct, 370, DupeType.Direct);
        Main.recipe.Add(MakeRecipe(369, 370));
        new MiscRecipeSystem().PostSetupRecipes();
        ReferenceEquals(FargoItemSets.DuplicatableRecipes, original).ShouldBe(true);
    }

    private static void TestRecipeRebuildIdempotent()
    {
        Reset();
        ConfigurePolicy(371, DupeType.Direct, 372, DupeType.Direct);
        Main.recipe.Add(MakeRecipe(371, 372, 372));
        MiscRecipeSystem system = new();
        system.PostSetupRecipes();
        system.PostSetupRecipes();
        FargoItemSets.DuplicatableRecipes[371].SequenceEqual(new[] { 372 }).ShouldBe(true);
    }

    private static void TestRecipeRebuildDropsIneligibleResult()
    {
        Reset();
        ConfigurePolicy(373, DupeType.Direct, 374, DupeType.Direct);
        Main.recipe.Add(MakeRecipe(373, 374));
        MiscRecipeSystem system = new();
        system.PostSetupRecipes();
        FargoItemSets.DuplicatableItems[373] = DupeType.NotDupable;
        system.PostSetupRecipes();
        FargoItemSets.DuplicatableRecipes.ContainsKey(373).ShouldBe(false);
    }

    private static void TestNetworkHeader()
    {
        EnchantedTreeTileEntity clone = NetworkClone(TreeWithFruit());
        clone.ItemType.ShouldBe(390);
        clone.Prefix.ShouldBe(12);
    }

    private static void TestNetworkFruit()
    {
        EnchantedTreeTileEntity clone = NetworkClone(TreeWithFruit());
        clone.Fruits.Count.ShouldBe(1);
        EnchantedTreeTileEntity.Fruit fruit = clone.Fruits[0];
        fruit.type.ShouldBe(391);
        fruit.center.ShouldVector(1, 2);
        fruit.targetPosition.ShouldVector(3, 4);
        fruit.velocity.ShouldVector(5, 6);
        fruit.previousItem.ShouldBe(0);
        fruit.layer.ShouldBe(0);
        fruit.grabCooldown.ShouldBe(9);
        fruit.despawnTimer.ShouldBe(10.5f);
    }

    private static void TestNetworkReplacement()
    {
        EnchantedTreeTileEntity target = new();
        target.Fruits.Add(Fruit(999));
        using MemoryStream data = Serialize(TreeWithFruit());
        using BinaryReader reader = new(data);
        target.NetReceive(reader);
        target.Fruits.Count.ShouldBe(1);
        target.Fruits[0].type.ShouldBe(391);
    }

    private static void TestNegativeFruitCount() => RejectFrame(HeaderWithCount(-1));

    private static void TestExcessiveFruitCount() => RejectFrame(HeaderWithCount(4097));

    private static void TestTruncatedHeader() => RejectFrame(new byte[6]);

    private static void TestTruncatedFruit()
    {
        using MemoryStream data = Serialize(TreeWithFruit());
        RejectFrame(data.ToArray()[..^1]);
    }

    private static void TestNanCenter()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].center.X = float.NaN;
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestInfiniteTarget()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].targetPosition.Y = float.PositiveInfinity;
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestInfiniteVelocity()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].velocity.X = float.NegativeInfinity;
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestNonfiniteDespawn()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].despawnTimer = float.PositiveInfinity;
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestNegativeDespawn()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].despawnTimer = -0.5f;
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestNegativeGrabCooldown()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].grabCooldown = -1;
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestRootLayer()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].layer = 1;
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestForwardParent()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(392, Vector2.Zero, Vector2.Zero, Vector2.Zero, 2, 1));
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestNegativeParent()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(392, Vector2.Zero, Vector2.Zero, Vector2.Zero, -1, 1));
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestLayerMismatch()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(392, Vector2.Zero, Vector2.Zero, Vector2.Zero, 0, 2));
        using MemoryStream data = RawFrame(tree);
        RejectFrame(data.ToArray());
    }

    private static void TestValidMultilevelForest()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(392, Vector2.Zero, Vector2.Zero, Vector2.Zero, 0, 1));
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(393, Vector2.Zero, Vector2.Zero, Vector2.Zero, 1, 2));
        EnchantedTreeTileEntity clone = NetworkClone(tree);
        clone.Fruits.Select(fruit => (fruit.previousItem, fruit.layer))
            .SequenceEqual(new[] { (0, 0), (0, 1), (1, 2) }).ShouldBe(true);
    }

    private static void TestValidMultirootForest()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(392, Vector2.Zero, Vector2.Zero, Vector2.Zero, 1, 0));
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(393, Vector2.Zero, Vector2.Zero, Vector2.Zero, 1, 1));
        EnchantedTreeTileEntity clone = NetworkClone(tree);
        clone.Fruits.Select(fruit => (fruit.previousItem, fruit.layer))
            .SequenceEqual(new[] { (0, 0), (1, 0), (1, 1) }).ShouldBe(true);
    }

    private static void TestInvalidTopologySendAtomicity()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].previousItem = 2;
        AssertInvalidSendIsAtomic(tree);
    }

    private static void TestInvalidScalarSendAtomicity()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        tree.Fruits[0].despawnTimer = float.NaN;
        AssertInvalidSendIsAtomic(tree);
    }

    private static void TestExcessiveCountSendAtomicity()
    {
        EnchantedTreeTileEntity tree = new();
        for (int i = 0; i < 4097; i++)
            tree.Fruits.Add(Node(394, i, 0));
        AssertInvalidSendIsAtomic(tree);
    }

    private static void TestFruitCountLimit()
    {
        EnchantedTreeTileEntity tree = TreeWithFruit();
        for (int i = 1; i < 4096; i++)
        {
            EnchantedTreeTileEntity.Fruit fruit = Fruit(391);
            fruit.previousItem = i;
            tree.Fruits.Add(fruit);
        }
        NetworkClone(tree).Fruits.Count.ShouldBe(4096);
    }

    private static void TestNetworkFrameAlignment()
    {
        using MemoryStream data = new();
        using (BinaryWriter writer = new(data, System.Text.Encoding.UTF8, leaveOpen: true))
        {
            TreeWithFruit().NetSend(writer);
            writer.Write(0x1234abcd);
        }
        data.Position = 0;
        using BinaryReader reader = new(data);
        EnchantedTreeTileEntity target = new();
        target.NetReceive(reader);
        reader.ReadInt32().ShouldBe(0x1234abcd);
        data.Position.ShouldBe(data.Length);
    }

    private static byte[] HeaderWithCount(int count)
    {
        using MemoryStream data = new();
        using (BinaryWriter writer = new(data, System.Text.Encoding.UTF8, leaveOpen: true))
        {
            writer.Write(390);
            writer.Write(12);
            writer.Write(count);
        }
        return data.ToArray();
    }

    private static void RejectFrame(byte[] frame)
    {
        EnchantedTreeTileEntity target = new() { ItemType = 777, Prefix = 55 };
        target.Fruits.Add(Fruit(999));
        List<EnchantedTreeTileEntity.Fruit> original = target.Fruits;
        using MemoryStream data = new(frame);
        using BinaryReader reader = new(data);
        bool rejected = false;
        try { target.NetReceive(reader); }
        catch (InvalidDataException) { rejected = true; }
        rejected.ShouldBe(true);
        target.ItemType.ShouldBe(777);
        target.Prefix.ShouldBe(55);
        ReferenceEquals(target.Fruits, original).ShouldBe(true);
        target.Fruits.Count.ShouldBe(1);
        target.Fruits[0].type.ShouldBe(999);
    }

    private static void TestSaveLoad()
    {
        EnchantedTreeTileEntity source = new() { ItemType = 401, Prefix = 66 };
        TagCompound tag = new();
        source.SaveData(tag);
        EnchantedTreeTileEntity clone = new();
        clone.LoadData(tag);
        clone.ItemType.ShouldBe(401);
        clone.Prefix.ShouldBe(66);
    }

    private static void TestMissingTreeContinuation()
    {
        Reset();
        Main.dedServ = false;
        EnchantedTreeSheet.EnchantedTrees.Add(new Point16(0, 0));
        EnchantedTreeTileEntity valid = RegisterTree(3, 4);
        valid.CursorInsertCooldown = 2;
        EnchantedTreeSheet.EnchantedTrees.Add(valid.Position);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        valid.CursorInsertCooldown.ShouldBe(1);
    }

    private static void TestAdjacentFruitRemoval()
    {
        Reset();
        Main.dedServ = false;
        Main.MouseWorld = new Vector2(10000, 10000);
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        tree.Fruits.Add(Fruit(1, despawn: 21));
        tree.Fruits.Add(Fruit(2, despawn: 21));
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.Fruits.Count.ShouldBe(0);
    }

    private static void TestRemovalRebasesLaterParent()
    {
        EnchantedTreeTileEntity tree = UpdateTree(
            Node(610, 0, 0, despawn: 21),
            Node(611, 1, 0),
            Node(612, 1, 1));
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.Fruits.Select(fruit => (fruit.type, fruit.previousItem, fruit.layer))
            .SequenceEqual(new[] { (611, 0, 0), (612, 0, 1) }).ShouldBe(true);
    }

    private static void TestAdjacentRemovalRebasesSurvivor()
    {
        EnchantedTreeTileEntity tree = UpdateTree(
            Node(613, 0, 0, despawn: 21),
            Node(614, 1, 0, despawn: 21),
            Node(615, 1, 1));
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.Fruits.Select(fruit => (fruit.type, fruit.previousItem, fruit.layer))
            .SequenceEqual(new[] { (615, 0, 0) }).ShouldBe(true);
    }

    private static void TestRemovedInternalParentRelinksChild()
    {
        EnchantedTreeTileEntity tree = UpdateTree(
            Node(616, 0, 0),
            Node(617, 0, 1, despawn: 21),
            Node(618, 1, 2),
            Node(619, 2, 3),
            Node(620, 1, 2));
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.Fruits.Select(fruit => (fruit.type, fruit.previousItem, fruit.layer))
            .SequenceEqual(new[] { (616, 0, 0), (618, 0, 1), (619, 1, 2), (620, 0, 1) }).ShouldBe(true);
    }

    private static void TestRemovedRootPromotesChild()
    {
        EnchantedTreeTileEntity tree = UpdateTree(
            Node(621, 0, 0, despawn: 21),
            Node(622, 0, 1),
            Node(623, 1, 2),
            Node(624, 0, 1));
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.Fruits.Select(fruit => (fruit.type, fruit.previousItem, fruit.layer))
            .SequenceEqual(new[] { (622, 0, 0), (623, 0, 1), (624, 2, 0) }).ShouldBe(true);
    }

    private static void TestRemovedGrabbedFruitClearsOwnership()
    {
        EnchantedTreeTileEntity.Fruit removed = Node(621, 0, 0, despawn: 21);
        EnchantedTreeTileEntity tree = UpdateTree(removed);
        Main.LocalPlayer.FargoMutant().grabbedFruit = removed;
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.Fruits.Count.ShouldBe(0);
        Main.LocalPlayer.FargoMutant().grabbedFruit.ShouldBe(null);
    }

    private static void TestRemovalPreservesListReference()
    {
        EnchantedTreeTileEntity tree = UpdateTree(
            Node(622, 0, 0, despawn: 21),
            Node(623, 0, 1));
        List<EnchantedTreeTileEntity.Fruit> original = tree.Fruits;
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        ReferenceEquals(tree.Fruits, original).ShouldBe(true);
    }

    private static void TestBranchExpansionOrder()
    {
        var state = BranchState(500, 501, 502);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        state.Tree.Fruits.Select(fruit => fruit.type).SequenceEqual(new[] { 500, 501, 502 }).ShouldBe(true);
    }

    private static void TestBranchExpansionLinks()
    {
        Reset();
        Main.netMode = NetmodeID.SinglePlayer;
        Main.LocalPlayer = new Player { active = true, controlUseItem = true };
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(599, new Vector2(500, 500), new Vector2(500, 500), Vector2.Zero)
        { grabCooldown = 20, previousItem = 0, layer = 0 });
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(500, new Vector2(80, 80), new Vector2(80, 80), Vector2.Zero, 0, 1)
        { grabCooldown = 0 });
        FargoItemSets.DuplicatableRecipes[500] = new List<int> { 501, 502 };
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        Main.MouseWorld = new Vector2(80, 80);

        EnchantedTreeTileEntity.UpdateEnchantedTrees();

        tree.Fruits.Count.ShouldBe(4);
        tree.Fruits.Skip(2).All(fruit => fruit.previousItem == 1 && fruit.layer == 2).ShouldBe(true);
    }

    private static void TestFadingChildBlocksExpansion()
    {
        var state = BranchState(500, 501);
        state.Tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(501, new Vector2(90, 90), new Vector2(90, 90), Vector2.Zero, 0, 1)
        { grabCooldown = 0, despawnTimer = 5 });
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        state.Tree.Fruits.Count.ShouldBe(2);
    }

    private static void TestBranchPrunesDescendants()
    {
        var state = BranchState(500, 501);
        state.Tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(501, new Vector2(90, 90), new Vector2(90, 90), Vector2.Zero, 0, 1)
        { grabCooldown = 0 });
        state.Tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(502, new Vector2(100, 100), new Vector2(100, 100), Vector2.Zero, 1, 2)
        { grabCooldown = 0 });
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        state.Tree.Fruits[1].despawnTimer.ShouldBe(0f);
        state.Tree.Fruits[2].despawnTimer.ShouldBe(2f);
    }

    private static void TestBranchPreservesUnrelatedDescendant()
    {
        Reset();
        Main.netMode = NetmodeID.MultiplayerClient;
        Main.LocalPlayer = new Player { active = true, controlUseItem = true };
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(500, new Vector2(500, 500), new Vector2(500, 500), Vector2.Zero, 0, 0));
        tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(501, new Vector2(80, 80), new Vector2(80, 80), Vector2.Zero, 0, 1)
        { grabCooldown = 0 });
        tree.Fruits.Add(Node(502, 0, 1));
        tree.Fruits.Add(Node(503, 1, 2));
        tree.Fruits.Add(Node(504, 3, 3));
        tree.Fruits.Add(Node(505, 2, 2));
        tree.Fruits.Add(Node(506, 6, 0));
        tree.Fruits.Add(Node(507, 6, 1));
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        Main.MouseWorld = new Vector2(80, 80);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.Fruits[4].despawnTimer.ShouldBe(2f);
        tree.Fruits[5].despawnTimer.ShouldBe(0f);
        tree.Fruits[7].despawnTimer.ShouldBe(0f);
    }

    private static void TestBranchPrunesThroughFadingChild()
    {
        var state = BranchState(500, 501);
        state.Tree.Fruits.Add(Node(501, 0, 1, despawn: 5));
        state.Tree.Fruits.Add(Node(502, 1, 2));
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        state.Tree.Fruits[1].despawnTimer.ShouldBe(6f);
        state.Tree.Fruits[2].despawnTimer.ShouldBe(2f);
    }

    private static void TestBranchMutationSync()
    {
        BranchState(500, 501);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        FargoNet.FruitPackets.SequenceEqual(new[] { 0 }).ShouldBe(true);
    }

    private static void TestUnchangedBranchNoSync()
    {
        var state = BranchState(500, 501);
        state.Tree.Fruits.Add(new EnchantedTreeTileEntity.Fruit(501, new Vector2(90, 90), new Vector2(90, 90), Vector2.Zero, 0, 1)
        { grabCooldown = 0 });
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        FargoNet.FruitPackets.Count.ShouldBe(0);
    }

    private static void TestDragReleaseOwnership()
    {
        var state = DuplicationState(value: 100, money: 200);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        state.Fruit.grabbed.ShouldBe(false);
        Main.LocalPlayer.FargoMutant().grabbedFruit.ShouldBe(null);
    }

    private static void TestDragReleaseCooldown()
    {
        var state = DuplicationState(value: 100, money: 200);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        state.Fruit.grabCooldown.ShouldBe(30);
    }

    private static void TestDuplicationCost()
    {
        DuplicationState(value: 125, money: 1000);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        Main.LocalPlayer.Money.ShouldBe(750);
    }

    private static void TestDuplicationSpawnState()
    {
        DuplicationState(value: 100, money: 200, prefix: 77);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        Item item = Spawned().Single();
        item.type.ShouldBe(510);
        item.prefix.ShouldBe(77);
        item.GetGlobalItem<FargoGlobalItem>().Grabbed.ShouldBe(Main.myPlayer);
        item.GetGlobalItem<FargoGlobalItem>().FromEnchantedTree.ShouldBe(true);
    }

    private static void TestDuplicationSync()
    {
        DuplicationState(value: 100, money: 200);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        NetMessage.Sent.SequenceEqual(new[] { (MessageID.SyncItem, Main.myPlayer, 0) }).ShouldBe(true);
    }

    private static void TestDuplicationFailure()
    {
        var state = DuplicationState(value: 100, money: 199);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        Main.LocalPlayer.Money.ShouldBe(199);
        Spawned().Count.ShouldBe(0);
        NetMessage.Sent.Count.ShouldBe(0);
        state.Fruit.grabCooldown.ShouldBe(30);
        Main.LocalPlayer.FargoMutant().grabbedFruit.ShouldBe(null);
    }

    private static void TestDuplicateCoordinateCooldown()
    {
        Reset();
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        tree.CursorInsertCooldown = 2;
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.CursorInsertCooldown.ShouldBe(1);
    }

    private static void TestDuplicateCoordinateDespawn()
    {
        EnchantedTreeTileEntity tree = UpdateTree(Node(624, 0, 0, despawn: 1));
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        tree.Fruits[0].despawnTimer.ShouldBe(2f);
    }

    private static void TestDuplicateCoordinatePurchaseCooldown()
    {
        var state = DuplicationState(value: 100, money: 200);
        EnchantedTreeSheet.EnchantedTrees.Add(state.Tree.Position);
        EnchantedTreeTileEntity.UpdateEnchantedTrees();
        state.Fruit.grabCooldown.ShouldBe(30);
    }

    private static (EnchantedTreeTileEntity Tree, EnchantedTreeTileEntity.Fruit Fruit) BranchState(int rootType, params int[] ingredients)
    {
        Reset();
        Main.netMode = NetmodeID.MultiplayerClient;
        Main.LocalPlayer = new Player { active = true, controlUseItem = true };
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        EnchantedTreeTileEntity.Fruit root = new(rootType, new Vector2(80, 80), new Vector2(80, 80), Vector2.Zero)
        { grabCooldown = 0 };
        tree.Fruits.Add(root);
        FargoItemSets.DuplicatableRecipes[rootType] = ingredients.ToList();
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        Main.MouseWorld = new Vector2(80, 80);
        return (tree, root);
    }

    private static (EnchantedTreeTileEntity Tree, EnchantedTreeTileEntity.Fruit Fruit) DuplicationState(int value, int money, int prefix = 42)
    {
        Reset();
        Main.netMode = NetmodeID.MultiplayerClient;
        Main.myPlayer = 7;
        Main.LocalPlayer = new Player { active = true, controlUseItem = true, whoAmI = Main.myPlayer, Money = money };
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        tree.Prefix = prefix;
        EnchantedTreeTileEntity.Fruit fruit = new(510, new Vector2(200, 200), Vector2.Zero, Vector2.Zero)
        { grabCooldown = 0 };
        tree.Fruits.Add(fruit);
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        ContentSamples.ItemsByType[510].value = value;
        Main.MouseWorld = new Vector2(200, 200);
        return (tree, fruit);
    }

    private static void RunRecipes(Recipe recipe)
    {
        Reset();
        foreach (Item item in recipe.requiredItem.Prepend(recipe.createItem))
            FargoItemSets.DuplicatableItems[item.type] = (DupeType)item.value;
        recipe.createItem.value = 0;
        foreach (Item item in recipe.requiredItem) item.value = 0;
        Main.recipe.Add(recipe);
        MiscRecipeSystem system = new();
        system.PostAddRecipes();
        system.PostSetupRecipes();
    }

    private static Recipe MakeRecipeWithPolicy(int result, DupeType resultPolicy, params (int Type, DupeType Policy)[] ingredients)
    {
        Recipe recipe = new() { createItem = new Item { type = result, value = (int)resultPolicy } };
        foreach (var ingredient in ingredients) recipe.requiredItem.Add(new Item { type = ingredient.Type, value = (int)ingredient.Policy });
        return recipe;
    }

    private static Recipe MakeRecipe(int result, params int[] ingredients)
    {
        Recipe recipe = new() { createItem = new Item { type = result } };
        foreach (int ingredient in ingredients) recipe.requiredItem.Add(new Item { type = ingredient });
        return recipe;
    }

    private static void ConfigurePolicy(int result, DupeType resultPolicy, int ingredient, DupeType ingredientPolicy)
    {
        FargoItemSets.DuplicatableItems[result] = resultPolicy;
        FargoItemSets.DuplicatableItems[ingredient] = ingredientPolicy;
    }

    private static EnchantedTreeTileEntity TreeWithFruit()
    {
        EnchantedTreeTileEntity tree = new() { ItemType = 390, Prefix = 12 };
        EnchantedTreeTileEntity.Fruit fruit = new(391, new Vector2(1, 2), new Vector2(3, 4), new Vector2(5, 6), 0, 0)
        { grabCooldown = 9, despawnTimer = 10.5f };
        tree.Fruits.Add(fruit);
        return tree;
    }

    private static MemoryStream RawFrame(EnchantedTreeTileEntity tree)
    {
        MemoryStream data = new();
        using (BinaryWriter writer = new(data, System.Text.Encoding.UTF8, leaveOpen: true))
        {
            writer.Write(tree.ItemType);
            writer.Write(tree.Prefix);
            writer.Write(tree.Fruits.Count);
            foreach (EnchantedTreeTileEntity.Fruit fruit in tree.Fruits)
            {
                writer.Write(fruit.type);
                writer.Write(fruit.center.X);
                writer.Write(fruit.center.Y);
                writer.Write(fruit.targetPosition.X);
                writer.Write(fruit.targetPosition.Y);
                writer.Write(fruit.velocity.X);
                writer.Write(fruit.velocity.Y);
                writer.Write(fruit.previousItem);
                writer.Write(fruit.layer);
                writer.Write(fruit.grabCooldown);
                writer.Write(fruit.despawnTimer);
            }
        }
        data.Position = 0;
        return data;
    }

    private static void AssertInvalidSendIsAtomic(EnchantedTreeTileEntity tree)
    {
        byte[] original = { 17, 34, 51, 68 };
        using MemoryStream data = new();
        data.Write(original);
        data.Position = 2;
        using BinaryWriter writer = new(data, System.Text.Encoding.UTF8, leaveOpen: true);
        bool rejected = false;
        try { tree.NetSend(writer); }
        catch (InvalidDataException) { rejected = true; }
        writer.Flush();
        rejected.ShouldBe(true);
        data.Position.ShouldBe(2L);
        data.ToArray().SequenceEqual(original).ShouldBe(true);
    }

    private static MemoryStream Serialize(EnchantedTreeTileEntity tree)
    {
        MemoryStream data = new();
        using (BinaryWriter writer = new(data, System.Text.Encoding.UTF8, leaveOpen: true)) tree.NetSend(writer);
        data.Position = 0;
        return data;
    }

    private static EnchantedTreeTileEntity NetworkClone(EnchantedTreeTileEntity tree)
    {
        using MemoryStream data = Serialize(tree);
        using BinaryReader reader = new(data);
        EnchantedTreeTileEntity clone = new();
        clone.NetReceive(reader);
        return clone;
    }

    private static EnchantedTreeTileEntity.Fruit Fruit(int type, float despawn = 0)
        => new(type, Vector2.Zero, Vector2.Zero, Vector2.Zero) { grabCooldown = 0, despawnTimer = despawn };

    private static EnchantedTreeTileEntity.Fruit Node(int type, int parent, int layer, float despawn = 0)
        => new(type, Vector2.Zero, Vector2.Zero, Vector2.Zero, parent, layer)
        { grabCooldown = 0, despawnTimer = despawn };

    private static EnchantedTreeTileEntity UpdateTree(params EnchantedTreeTileEntity.Fruit[] fruits)
    {
        Reset();
        Main.MouseWorld = new Vector2(10000, 10000);
        EnchantedTreeTileEntity tree = RegisterTree(3, 4);
        tree.Fruits.AddRange(fruits);
        EnchantedTreeSheet.EnchantedTrees.Add(tree.Position);
        return tree;
    }

    private static EnchantedTreeTileEntity RegisterTree(int x, int y)
    {
        EnchantedTreeTileEntity tree = new() { Position = new Point16(x, y) };
        FargoUtils.Entities[tree.Position] = tree;
        return tree;
    }

    private static List<Item> Spawned() => Main.item.Where(item => item.type != 0).ToList();

    private static void Reset()
    {
        Main.recipe.Clear();
        Main.netMode = NetmodeID.SinglePlayer;
        Main.dedServ = false;
        Main.playerInventory = false;
        Main.mouseRight = false;
        Main.mouseRightRelease = false;
        Main.MouseWorld = Vector2.Zero;
        Main.LocalPlayer = new Player();
        FargoUtils.Entities.Clear();
        FargoNet.FruitPackets.Clear();
        NetMessage.Sent.Clear();
        EnchantedTreeSheet.EnchantedTrees.Clear();
        FargoItemSets.DuplicatableRecipes.Clear();
        Array.Fill(FargoItemSets.DuplicatableItems, DupeType.NotDupable);
        for (int i = 0; i < Main.item.Length; i++) Main.item[i] = new Item();
        for (int i = 0; i < ContentSamples.ItemsByType.Length; i++)
        {
            ContentSamples.ItemsByType[i].ModItem = null;
            ContentSamples.ItemsByType[i].value = 0;
        }
    }

    private static void ShouldBe<T>(this T actual, T expected)
    {
        if (!EqualityComparer<T>.Default.Equals(actual, expected))
            throw new InvalidOperationException($"expected {expected}, got {actual}");
    }

    private static void ShouldVector(this Vector2 actual, float x, float y)
    {
        actual.X.ShouldBe(x);
        actual.Y.ShouldBe(y);
    }
}

internal static class EntryPoint
{
    public static int Main(string[] args) => Program.Execute(args);
}
