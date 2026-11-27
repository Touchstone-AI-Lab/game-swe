using System;
using System.Collections.Generic;

namespace Microsoft.Xna.Framework
{
    public struct Vector2
    {
        public float X, Y;
        public Vector2(float x, float y) { X=x; Y=y; }
    }
    public struct Vector4
    {
        public float X, Y, Z, W;
        public Vector4(float x, float y, float z, float w) { X=x; Y=y; Z=z; W=w; }
    }
    public struct Rectangle
    {
        public int X, Y, Width, Height;
        public Rectangle(int x, int y, int width, int height) { X=x; Y=y; Width=width; Height=height; }
    }
}

namespace Terraria
{
    using Microsoft.Xna.Framework;
    public static class Main
    {
        public static int maxTilesX = 256, maxTilesY = 192;
        public static int screenWidth = 128, screenHeight = 128;
        public static Vector2 screenPosition;
    }
}

namespace Terraria.ModLoader
{
    public abstract class ModSystem
    {
        public virtual void Load() { }
        public virtual void Unload() { }
        public virtual void PostUpdateEverything() { }
    }
}

namespace Terraria.ModLoader.Core
{
    using System;
    using System.Collections.Generic;
    using System.Reflection;
    public static class AssemblyManager
    {
        public static IEnumerable<Type> GetLoadableTypes(Assembly assembly) => assembly.GetTypes();
    }
}

namespace TerrariaOverhaul
{
    internal static class Program { public static bool IsMainThread => true; }
}

namespace TerrariaOverhaul.Core.Data
{
    internal struct PrefabInfo : IComponent { }
}

namespace TerrariaOverhaul.Core.Time
{
    internal static class TimeSystem
    {
        public static int LogicFramerate = 1;
        public static ulong UpdateCount;
    }
}

namespace TerrariaOverhaul.Utilities.Terraria
{
    internal static class WorldUtils { public const int TileSizeInPixels = 16; }
}

namespace TerrariaOverhaul.Utilities.Xna
{
    using Microsoft.Xna.Framework;
    internal readonly struct Vector2Int
    {
        public readonly int X, Y;
        public Vector2Int(int x, int y) { X=x; Y=y; }
    }
    internal readonly struct Vector4Int
    {
        public readonly int X, Y, Z, W;
        public Vector4Int(int x, int y, int z, int w) { X=x; Y=y; Z=z; W=w; }
    }
    internal readonly struct RectFloat
    {
        public readonly float X, Y, Width, Height;
        public RectFloat(float x, float y, float width, float height) { X=x; Y=y; Width=width; Height=height; }
    }
    internal static class VectorExtensions
    {
        public static Vector2Int ToTileCoordinates(this Vector2 value)
            => new((int)MathF.Floor(value.X / 16f), (int)MathF.Floor(value.Y / 16f));
    }
}
