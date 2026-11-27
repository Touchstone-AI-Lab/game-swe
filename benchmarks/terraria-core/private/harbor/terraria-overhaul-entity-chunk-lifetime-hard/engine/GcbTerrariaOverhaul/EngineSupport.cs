using System;
using Microsoft.Xna.Framework;

namespace TerrariaOverhaul
{
    internal static class Program
    {
        public static bool IsMainThread => true;
    }
}

namespace TerrariaOverhaul.Core.Data
{
    internal struct PrefabInfo : IComponent
    {
    }
}

namespace TerrariaOverhaul.Core.Time
{
    internal static class TimeSystem
    {
        public static int LogicFramerate = 60;
        public static ulong UpdateCount;
    }
}

namespace TerrariaOverhaul.Utilities.Terraria
{
    internal static class WorldUtils
    {
        public const int TileSizeInPixels = 16;
    }
}

namespace TerrariaOverhaul.Utilities.Xna
{
    internal readonly struct Vector2Int
    {
        public readonly int X;
        public readonly int Y;

        public Vector2Int(int x, int y)
        {
            X = x;
            Y = y;
        }

        public static implicit operator Vector2Int(Point value) => new(value.X, value.Y);
    }

    internal readonly struct Vector4Int
    {
        public readonly int X;
        public readonly int Y;
        public readonly int Z;
        public readonly int W;

        public Vector4Int(int x, int y, int z, int w)
        {
            X = x;
            Y = y;
            Z = z;
            W = w;
        }
    }

    internal readonly struct RectFloat
    {
        public readonly float X;
        public readonly float Y;
        public readonly float Width;
        public readonly float Height;

        public RectFloat(float x, float y, float width, float height)
        {
            X = x;
            Y = y;
            Width = width;
            Height = height;
        }
    }

}
