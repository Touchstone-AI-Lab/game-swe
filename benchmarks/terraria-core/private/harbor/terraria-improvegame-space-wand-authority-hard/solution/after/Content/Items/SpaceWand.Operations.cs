namespace ImproveGame.Content.Items;

public partial class SpaceWand
{
    private static readonly int[] GrassSeeds =
        [
        TileID.Grass,
        TileID.CorruptGrass,
        TileID.JungleGrass,
        TileID.MushroomGrass,
        TileID.ImmatureHerbs,
        TileID.HallowedGrass,
        TileID.CrimsonGrass,
        TileID.AshGrass,
        TileID.GreenMoss,
        TileID.BrownMoss,
        TileID.RedMoss,
        TileID.BlueMoss,
        TileID.PurpleMoss,
        TileID.LavaMoss,
        TileID.KryptonMoss,
        TileID.XenonMoss,
        TileID.ArgonMoss,
        TileID.VioletMoss,
        TileID.RainbowMoss
        ];

    internal readonly record struct TileState(bool HasTile, ushort TileType, BlockType BlockType,
        short TileFrameX, short TileFrameY, byte TileColor, bool IsActuated)
    {
        public static TileState Capture(Tile tile) => new(tile.HasTile, tile.TileType, tile.BlockType,
            tile.TileFrameX, tile.TileFrameY, tile.TileColor, tile.IsActuated);

        public void Restore(Tile tile)
        {
            tile.HasTile = HasTile;
            tile.TileType = TileType;
            tile.BlockType = BlockType;
            tile.TileFrameX = TileFrameX;
            tile.TileFrameY = TileFrameY;
            tile.TileColor = TileColor;
            tile.IsActuated = IsActuated;
        }
    }

    internal sealed class TileMutationJournal
    {
        private readonly Dictionary<Point, TileState> originalStates;

        private TileMutationJournal(Dictionary<Point, TileState> originalStates)
        {
            this.originalStates = originalStates;
        }

        public static TileMutationJournal CaptureNeighborhood(int x, int y)
            => CaptureNeighborhoods([new Point(x, y)]);

        public static TileMutationJournal CaptureNeighborhoods(IEnumerable<Point> centers)
        {
            var states = new Dictionary<Point, TileState>();
            foreach (var center in centers)
            {
                for (int offsetX = -1; offsetX <= 1; offsetX++)
                {
                    for (int offsetY = -1; offsetY <= 1; offsetY++)
                    {
                        var position = new Point(center.X + offsetX, center.Y + offsetY);
                        if (WorldGen.InWorld(position.X, position.Y) && !states.ContainsKey(position))
                            states[position] = TileState.Capture(Main.tile[position.X, position.Y]);
                    }
                }
            }
            return new TileMutationJournal(states);
        }

        public void Restore()
        {
            foreach (var pair in originalStates)
                pair.Value.Restore(Main.tile[pair.Key.X, pair.Key.Y]);
        }

        public IEnumerable<Point> GetChangedTiles()
        {
            foreach (var pair in originalStates)
            {
                if (TileState.Capture(Main.tile[pair.Key.X, pair.Key.Y]) != pair.Value)
                    yield return pair.Key;
            }
        }
    }

    private static bool HasRequestedTile(Tile tile, int tileType)
        => tile.HasTile && tile.TileType == tileType;

    public static void OperateTile(Player player, int x, int y, HashSet<Point> tilesHashSet, PlaceType placeType,
        BlockType blockType, ref bool playSound, Dictionary<int, int> itemsConsumed)
    {
        if (!WorldGen.InWorld(x, y, 10))
            return;

        int oneIndex = EnoughItem(player, GetConditions(placeType));
        if (oneIndex <= -1)
            return;
        // 使用物块魔杖时，ignoreConsumable应为true，无论如何都消耗物品。这是原版的逻辑
        bool usingTileWand = false;
        int indexOfItemBeingConsumed = oneIndex;
        Item item = player.inventory[oneIndex];
        if (item.tileWand >= 0)
        {
            int actualItemIndex = EnoughItem(player, i => i.type == item.tileWand);
            if (actualItemIndex <= -1)
                return;

            usingTileWand = true;
            indexOfItemBeingConsumed = actualItemIndex;
        }

        var transaction = TileMutationJournal.CaptureNeighborhood(x, y);
        if (!TileLoader.CanPlace(x, y, item.createTile))
        {
            transaction.Restore();
            return;
        }

        Tile targetTile = Main.tile[x, y];

        if (GrassSeeds.Contains(item.createTile))
        {
            WorldGen.PlaceTile(x, y, item.createTile, true, false, player.whoAmI, item.placeStyle);
            if (HasRequestedTile(targetTile, item.createTile))
            {
                CommitPlacement(player, indexOfItemBeingConsumed, itemsConsumed, usingTileWand, false,
                    x, y, tilesHashSet, placeType, blockType, ref playSound);
            }
            else
            {
                transaction.Restore();
            }
        }
        else
        {
            if (targetTile.HasTile)
            {
                // 同种类，设置个斜坡就走
                if (targetTile.TileType == item.createTile)
                {
                    if (WorldGen.CanPoundTile(x, y))
                        SetSlopeFor(placeType, blockType, x, y, tilesHashSet);
                    else
                        transaction.Restore();
                    return;
                }

                if (!player.TileReplacementEnabled)
                {
                    transaction.Restore();
                    return;
                }

                // 物品放置的瓷砖就是位置对应的瓷砖则无需替换
                if (!ValidTileForReplacement(item, x, y))
                {
                    transaction.Restore();
                    return;
                }

                // 如果放的是绳子，且试图替换的是平台/铁轨，那就不放（笑点解析：绳子和平台/铁轨相交原理是判断上下有没有绳子，本身还是平台/铁轨）
                if (placeType == PlaceType.Rope && (TileID.Sets.Platforms[targetTile.TileType] || targetTile.TileType == TileID.MinecartTrack))
                {
                    transaction.Restore();
                    return;
                }

                // 有没有足够强大的镐子破坏瓷砖
                if (!player.HasEnoughPickPowerToHurtTile(x, y))
                {
                    transaction.Restore();
                    return;
                }

                // 开始替换
                WorldGen.ReplaceTile(x, y, (ushort)item.createTile, item.placeStyle);
                if (HasRequestedTile(targetTile, item.createTile))
                {
                    CommitPlacement(player, indexOfItemBeingConsumed, itemsConsumed, usingTileWand, true,
                        x, y, tilesHashSet, placeType, blockType, ref playSound);
                }
                else
                {
                    // Restore every exposed local mutation before the fallback so
                    // killing observes the original terrain and metadata.
                    transaction.Restore();
                    targetTile = Main.tile[x, y];

                    // 尝试破坏
                    TryKillTile(x, y, player);
                    if (!targetTile.HasTile)
                        WorldGen.PlaceTile(x, y, item.createTile, true, true, player.whoAmI, item.placeStyle);
                    if (HasRequestedTile(targetTile, item.createTile))
                    {
                        CommitPlacement(player, indexOfItemBeingConsumed, itemsConsumed, usingTileWand, true,
                            x, y, tilesHashSet, placeType, blockType, ref playSound);
                    }
                    else
                    {
                        transaction.Restore();
                    }
                }
            }
            else
            {
                WorldGen.PlaceTile(x, y, item.createTile, true, true, player.whoAmI, item.placeStyle);
                if (HasRequestedTile(targetTile, item.createTile))
                {
                    CommitPlacement(player, indexOfItemBeingConsumed, itemsConsumed, usingTileWand, true,
                        x, y, tilesHashSet, placeType, blockType, ref playSound);
                }
                else
                {
                    transaction.Restore();
                }
            }
        }

        // NetMessage.SendTileSquare(player.whoAmI, x, y);
    }

    private static void CommitPlacement(Player player, int itemIndex, Dictionary<int, int> itemsConsumed,
        bool usingTileWand, bool setSlope, int x, int y, HashSet<Point> selectedTiles, PlaceType placeType,
        BlockType blockType, ref bool playSound)
    {
        playSound = true;
        HandleItemConsumption(player, itemIndex, itemsConsumed, usingTileWand);
        if (setSlope)
            SetSlopeFor(placeType, blockType, x, y, selectedTiles);
    }

    private static void HandleItemConsumption(Player player, int index, Dictionary<int, int> itemsConsumed,
        bool ignoreConsumable)
    {
        if (index is -1)
            return;

        ref Item item = ref player.inventory[index];
        int type = item.type; // TurnToAir之后type就为0了，提前存好
        if (!TryConsumeItem(ref item, player, ignoreConsumable))
            return;

        if (!itemsConsumed.TryAdd(type, 1))
            itemsConsumed[type]++;
    }

    private static void SetSlopeFor(PlaceType placeType, BlockType blockType, int x, int y, HashSet<Point> positions)
    {
        var tile = Main.tile[x, y];
        if (WorldGen.CanPoundTile(x, y) && placeType is PlaceType.Soild or PlaceType.Platform)
        {
            tile.BlockType = blockType;
            WorldGen.SquareTileFrame(x, y, false);
        }

        // 仅当现在在放置实心块，且斜坡类型也为实心时，才重置下方物块的斜坡状态
        if (placeType is PlaceType.Soild && blockType is BlockType.Solid && !positions.Contains(new Point(x, y + 1)))
            WorldGen.SlopeTile(x, y + 1);
    }
}
