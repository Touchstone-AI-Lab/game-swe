global using System;
global using System.Collections.Generic;
global using Microsoft.Xna.Framework;
global using Terraria;
global using static ImproveGame.Helpers.EngineHelpers;

namespace ImproveGame
{
    internal static class PointExtensions
    {
        internal static Point Min(Point left, Point right) => new(Math.Min(left.X, right.X), Math.Min(left.Y, right.Y));
        internal static Point Abs(this Point value) => new(Math.Abs(value.X), Math.Abs(value.Y));
        internal static float DistanceSQ(this Point left, Point right)
        {
            long x = (long)left.X - right.X;
            long y = (long)left.Y - right.Y;
            return x * x + y * y;
        }
    }
}

namespace ImproveGame.Helpers
{
    internal static class EngineHelpers
    {
        internal static Point ModifySize(Point start, Point end, int width, int height)
        {
            width--;
            height--;
            end.X = Math.Clamp(end.X, start.X - width, start.X + width);
            end.Y = Math.Clamp(end.Y, start.Y - height, start.Y + height);
            return end;
        }
    }
}

namespace ImproveGame.Content.Items
{
    public enum ShapeType : byte { Line, Corner, SquareEmpty, SquareFilled, CircleEmpty, CircleFilled }

    public partial class SpaceWand
    {
        public enum Direction { Right, Down, Left, Up, RightDown, LeftDown, LeftUp, RightUp }
        private static string _dataText = string.Empty;
    }
}
