namespace ImproveGame.Content.Items;

public partial class SpaceWand
{
    private static bool IsFinite(Vector2 point)
        => float.IsFinite(point.X) && float.IsFinite(point.Y);

    private static Point ToClampedTileCoordinates(Vector2 point)
    {
        static int Convert(float coordinate)
        {
            double tile = Math.Floor((double)coordinate / 16d);
            return tile <= int.MinValue ? int.MinValue : tile >= int.MaxValue ? int.MaxValue : (int)tile;
        }

        return new Point(Convert(point.X), Convert(point.Y));
    }

    /// <summary>
    /// 根据鼠标到放置起始点的角度，判断放置的方向
    /// </summary>
    /// <returns></returns>
    public static Direction GetDirection(Vector2 startPoint, Vector2 mousePosition)
    {
        var centerToCursorVector = mousePosition - startPoint;
        var angle = centerToCursorVector.ToRotation();

        // 转换成只有正数的角度
        if (angle < 0)
            angle = MathHelper.TwoPi + angle;

        // 角度判断
        const float unitWidth = MathHelper.PiOver4; // 一个区域的角度是unitWidth
        const float unitWidthOver2 = unitWidth / 2f;
        return angle switch
        {
            < unitWidthOver2 or > MathHelper.TwoPi - unitWidthOver2 => Direction.Right,
            >= unitWidthOver2 + unitWidth * 0 and <= unitWidthOver2 + unitWidth * 1 => Direction.RightDown,
            >= unitWidthOver2 + unitWidth * 1 and <= unitWidthOver2 + unitWidth * 2 => Direction.Down,
            >= unitWidthOver2 + unitWidth * 2 and <= unitWidthOver2 + unitWidth * 3 => Direction.LeftDown,
            >= unitWidthOver2 + unitWidth * 3 and <= unitWidthOver2 + unitWidth * 4 => Direction.Left,
            >= unitWidthOver2 + unitWidth * 4 and <= unitWidthOver2 + unitWidth * 5 => Direction.LeftUp,
            >= unitWidthOver2 + unitWidth * 5 and <= unitWidthOver2 + unitWidth * 6 => Direction.Up,
            >= unitWidthOver2 + unitWidth * 6 and <= unitWidthOver2 + unitWidth * 7 => Direction.RightUp,
            _ => Direction.Right
        };
    }

    public static IEnumerable<Point> GetSelectedTiles(ShapeType shapeType, Vector2 startPoint, Vector2 mousePosition, bool lastControlLeft)
    {
        if (!IsFinite(startPoint) || !IsFinite(mousePosition))
            return [];

        var startTile = ToClampedTileCoordinates(startPoint);
        if (!WorldGen.InWorld(startTile.X, startTile.Y, 10))
            return [];

        switch (shapeType)
        {
            case ShapeType.Line:
                return GetLineTiles(startPoint, mousePosition);
            case ShapeType.Corner:
                return GetCornerTiles(startPoint, mousePosition, lastControlLeft);
            case ShapeType.SquareEmpty:
                return GetSquareTiles(startPoint, mousePosition, false);
            case ShapeType.SquareFilled:
                return GetSquareTiles(startPoint, mousePosition, true);
            case ShapeType.CircleEmpty:
                return GetCircleTiles(startPoint, mousePosition, false, lastControlLeft);
            case ShapeType.CircleFilled:
                return GetCircleTiles(startPoint, mousePosition, true, lastControlLeft);
            default:
                return [];
        }
    }

    public static IEnumerable<Point> GetLineTiles(Vector2 startPoint, Vector2 mousePosition)
    {
        if (!IsFinite(startPoint) || !IsFinite(mousePosition))
            yield break;

        var direction = GetDirection(startPoint, mousePosition);
        double distanceToMouseX = Math.Abs((double)startPoint.X - mousePosition.X) / 16d;
        double distanceToMouseY = Math.Abs((double)startPoint.Y - mousePosition.Y) / 16d;
        int distanceToMouse = (int)Math.Min(int.MaxValue, Math.Max(distanceToMouseX, distanceToMouseY));
        var position = ToClampedTileCoordinates(startPoint);

        if (!WorldGen.InWorld(position.X, position.Y, 10))
            yield break;

        _dataText = $"{Math.Min((long)distanceToMouse + 1, int.MaxValue)}";

        var increment = direction switch
        {
            Direction.Right => new Point(1, 0),
            Direction.Down => new Point(0, 1),
            Direction.Left => new Point(-1, 0),
            Direction.Up => new Point(0, -1),
            Direction.RightDown => new Point(1, 1),
            Direction.LeftDown => new Point(-1, 1),
            Direction.LeftUp => new Point(-1, -1),
            Direction.RightUp => new Point(1, -1),
            _ => throw new ArgumentOutOfRangeException()
        };

        for (int i = 0; i <= distanceToMouse; i++)
        {
            if (!WorldGen.InWorld(position.X, position.Y, 10))
                break;
            yield return position;
            position += increment;
        }
    }

    public static List<Point> GetCornerTiles(Vector2 startPoint, Vector2 mousePosition, bool lastControlLeft)
    {
        var tilePositions = new List<Point>();
        if (!IsFinite(startPoint) || !IsFinite(mousePosition))
            return tilePositions;

        var position = ToClampedTileCoordinates(startPoint);
        var destination = ToClampedTileCoordinates(mousePosition);
        if (!WorldGen.InWorld(position.X, position.Y, 10))
            return tilePositions;
        tilePositions.Add(position);

        bool clipped = false;

        // 尺寸+总共放置的物块数量
        long sizeX = Math.Abs((long)position.X - destination.X);
        long sizeY = Math.Abs((long)position.Y - destination.Y);
        _dataText = $"{sizeX + 1}x{sizeY + 1}";
        _dataText += $" ({sizeX + sizeY + 1})";

        // 类原版蓝图
        if (lastControlLeft)
        {
            DoHorizontal();
            if (clipped)
                return tilePositions;
            DoVertical();
        }
        else
        {
            DoVertical();
            if (clipped)
                return tilePositions;
            DoHorizontal();
        }

        return tilePositions;

        void DoVertical()
        {
            int tried = 0;
            while (position.Y != destination.Y)
            {
                int increment = Math.Sign(destination.Y - position.Y);
                var next = new Point(position.X, position.Y + increment);
                if (!WorldGen.InWorld(next.X, next.Y, 10))
                {
                    clipped = true;
                    break;
                }
                position = next;
                tilePositions.Add(position);

                // 令人“啊？”的情况
                tried++;
                if (tried > 10000)
                    break;
            }
        }

        void DoHorizontal()
        {
            int tried = 0;
            while (position.X != destination.X)
            {
                int increment = Math.Sign(destination.X - position.X);
                var next = new Point(position.X + increment, position.Y);
                if (!WorldGen.InWorld(next.X, next.Y, 10))
                {
                    clipped = true;
                    break;
                }
                position = next;
                tilePositions.Add(position);

                // 令人“啊？”的情况
                tried++;
                if (tried > 10000)
                    break;
            }
        }
    }

    public static IEnumerable<Point> GetSquareTiles(Vector2 startPoint, Vector2 mousePosition, bool filled)
    {
        if (!IsFinite(startPoint) || !IsFinite(mousePosition))
            yield break;

        var startingPoint = ToClampedTileCoordinates(startPoint);
        if (!WorldGen.InWorld(startingPoint.X, startingPoint.Y, 10))
            yield break;
        var nowPoint = ToClampedTileCoordinates(mousePosition);
        int maxSize = filled ? 60 : 160;
        nowPoint = ModifySize(startingPoint, nowPoint, maxSize, maxSize);
        var position = PointExtensions.Min(startingPoint, nowPoint);
        var size = (startingPoint - nowPoint).Abs();

        // 尺寸+总共放置的物块数量
        _dataText = $"{size.X + 1}x{size.Y + 1}";
        if (filled)
            _dataText += $" ({(size.X + 1) * (size.Y + 1)})";
        else
            _dataText += $" ({(size.X + 1) * 2 + (size.Y + 1) * 2 - 4})";

        for (int i = 0; i <= size.X; i++)
        {
            for (int j = 0; j <= size.Y; j++)
            {
                switch (filled)
                {
                    case false when (i == 0 || i == size.X || j == 0 || j == size.Y):
                    case true:
                        var tile = position + new Point(i, j);
                        if (WorldGen.InWorld(tile.X, tile.Y, 10))
                            yield return tile;
                        break;
                }
            }
        }
    }

    public static IEnumerable<Point> GetCircleTiles(Vector2 startPoint, Vector2 mousePosition, bool filled, bool lastControlLeft)
    {
        if (!IsFinite(startPoint) || !IsFinite(mousePosition))
            yield break;

        var center = ToClampedTileCoordinates(startPoint);
        if (!WorldGen.InWorld(center.X, center.Y, 10))
            yield break;
        float maxSize = filled ? 49.5f : 99.5f;
        double differenceX = (double)startPoint.X - mousePosition.X;
        double differenceY = (double)startPoint.Y - mousePosition.Y;
        double distanceInTiles = Math.Sqrt(differenceX * differenceX + differenceY * differenceY) / 16d;
        float radius = distanceInTiles >= maxSize ? maxSize : (int)distanceInTiles + 0.5f;
        float radiusSquared = radius * radius;
        bool fat = lastControlLeft; // 边缘像素连起来的空心圆
        int tileCount = 0;

        // 尺寸
        _dataText = $"{(int)(radius + 0.5f)}";

        bool IsInCircle(int x, int y)
        {
            var now = new Point(x, y);
            var distance = center.DistanceSQ(now);
            return distance < radiusSquared;
        }

        for (int i = -(int)radius; i <= radius; i++)
        {
            for (int j = -(int)radius; j <= radius; j++)
            {
                int x = center.X + i;
                int y = center.Y + j;
                if (!WorldGen.InWorld(x, y, 10))
                    continue;
                if (!IsInCircle(x, y))
                    continue;

                switch (filled)
                {
                    case false when fat && !(IsInCircle(x + 1, y) && IsInCircle(x - 1, y) &&
                                             IsInCircle(x, y + 1) && IsInCircle(x, y - 1)):
                    case false when !fat && !(IsInCircle(x + 1, y) && IsInCircle(x - 1, y) &&
                                              IsInCircle(x, y + 1) && IsInCircle(x, y - 1) &&
                                              IsInCircle(x + 1, y + 1) && IsInCircle(x - 1, y + 1) &&
                                              IsInCircle(x + 1, y - 1) && IsInCircle(x - 1, y - 1)):
                    case true:
                        yield return new Point(x, y);
                        tileCount++;
                        break;
                }
            }
        }

        // 总共放置的物块数量
        _dataText += $" ({tileCount})";
    }
}
