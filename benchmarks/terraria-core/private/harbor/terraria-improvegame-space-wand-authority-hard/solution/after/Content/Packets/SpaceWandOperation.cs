using ImproveGame.Content.Items;
using ImproveGame.Packets;
using ImproveGame.Packets.Items;

namespace ImproveGame.Content.Packets;

[AutoSync]
public class SpaceWandOperation : NetModule
{
    private Vector2 _startPoint;
    private Vector2 _mousePosition;
    private byte _shapeType;
    private byte _blockType;
    private byte _placeType;
    private bool _controlLeft;

    public static SpaceWandOperation Get(Vector2 startPoint, Vector2 mousePosition, ShapeType shapeType,
        BlockType blockType, PlaceType placeType, bool controlLeft)
    {
        var module = NetModuleLoader.Get<SpaceWandOperation>();
        module._startPoint = startPoint;
        module._mousePosition = mousePosition;
        module._shapeType = (byte)shapeType;
        module._blockType = (byte)blockType;
        module._placeType = (byte)placeType;
        module._controlLeft = controlLeft;
        return module;
    }

    public static void Proceed(Vector2 startPoint, Vector2 mousePosition, ShapeType shapeType,
        BlockType blockType, PlaceType placeType, bool controlLeft)
    {
        if (Main.netMode is NetmodeID.Server)
            return;
        var module = Get(startPoint, mousePosition, shapeType, blockType, placeType, controlLeft);
        module.Send();
    }

    public override void Receive()
    {
        if (Main.netMode is not NetmodeID.Server || Sender < 0 || Sender >= Main.player.Length)
            return;
        Player sender = Main.player[Sender];
        if (!sender.active || sender.dead || sender.noBuilding || sender.HeldItem.ModItem is not SpaceWand)
            return;
        if (!Enum.IsDefined(typeof(ShapeType), _shapeType) ||
            !Enum.IsDefined(typeof(BlockType), _blockType) ||
            !Enum.IsDefined(typeof(PlaceType), _placeType) ||
            !float.IsFinite(_startPoint.X) || !float.IsFinite(_startPoint.Y) ||
            !float.IsFinite(_mousePosition.X) || !float.IsFinite(_mousePosition.Y))
            return;

        bool playSound = false;
        var itemsConsumed = new Dictionary<int, int>();
        var shapeType = (ShapeType)_shapeType;
        var tiles = SpaceWand.GetSelectedTiles(shapeType, _startPoint, _mousePosition, _controlLeft);
        var tilesHashSet = tiles.ToHashSet();
        var sortedTiles = tilesHashSet.OrderByDescending(point => point.Y).ThenBy(point => point.X);
        var mutationLedger = SpaceWand.TileMutationJournal.CaptureNeighborhoods(tilesHashSet);
        ForeachTile(sortedTiles, (x, y) =>
        {
            SpaceWand.OperateTile(sender, x, y, tilesHashSet, (PlaceType)_placeType, (BlockType)_blockType,
                ref playSound, itemsConsumed);
        });
        var changedTiles = mutationLedger.GetChangedTiles().ToHashSet();

        if (changedTiles.Count > 0)
        {
            SendTiles(changedTiles);
            if (playSound)
                PlaySoundPacket.PlaySound(LegacySoundIDs.Dig, _startPoint);
            if (itemsConsumed.Count > 0)
                ConsumeItemPacket.Proceed(itemsConsumed, Sender);
        }
    }

    private void SendTiles(HashSet<Point> tilesHashSet)
    {
        var shapeType = (ShapeType)_shapeType;
        switch (shapeType)
        {
            case ShapeType.Line:
            case ShapeType.Corner:
            case ShapeType.SquareEmpty:
            case ShapeType.CircleEmpty:
                ForeachTile(tilesHashSet.OrderByDescending(point => point.Y).ThenBy(point => point.X), (x, y) =>
                {
                    // NetMessage.SendTileSquare(-1, x, y);
                    NetMessage.SendTileSquare(-1, x - 1, y - 1, 3, 3);
                });
                break;
            case ShapeType.SquareFilled:
            case ShapeType.CircleFilled:
            {
                if (tilesHashSet.Count == 0)
                    break;
                int minX = tilesHashSet.Min(point => point.X);
                int minY = tilesHashSet.Min(point => point.Y);
                int maxX = tilesHashSet.Max(point => point.X);
                int maxY = tilesHashSet.Max(point => point.Y);
                NetMessage.SendTileSquare(-1, minX - 1, minY - 1, maxX - minX + 3, maxY - minY + 3);
                break;
            }
            default:
                throw new ArgumentOutOfRangeException();
        }
    }
}
