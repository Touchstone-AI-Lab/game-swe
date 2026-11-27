using System;
using System.Collections.Generic;
using System.IO;

namespace Terraria.Map
{
    public struct MapTile
    {
        public ushort Type;
        public byte Light;
        public byte Color;
        public static MapTile Create(ushort type, byte light, byte color) => new() { Type = type, Light = light, Color = color };
        public bool Equals(ref MapTile other) => Type == other.Type && Light == other.Light && Color == other.Color;
        public bool Equals(MapTile other) => Type == other.Type && Light == other.Light && Color == other.Color;
    }

    public class WorldMap
    {
        private readonly MapTile[,] _tiles;
        public int SetCalls { get; private set; }
        public int SetAttempts { get; private set; }
        public int FailOnSetAttempt { get; set; } = -1;
        public bool MutateBeforeSetFailure { get; set; }
        public WorldMap(int width, int height) => _tiles = new MapTile[width, height];
        public MapTile this[int x, int y] { get => _tiles[x, y]; set => _tiles[x, y] = value; }
        public void SetTile(int x, int y, ref MapTile tile)
        {
            SetAttempts++;
            bool fail = SetAttempts == FailOnSetAttempt;
            if (fail && !MutateBeforeSetFailure) throw new IOException("injected SetTile failure");
            _tiles[x, y] = tile;
            if (fail) throw new IOException("injected post-mutation SetTile failure");
            SetCalls++;
        }
        public MapTile[] Snapshot()
        {
            var result = new List<MapTile>();
            for (int x = 0; x < _tiles.GetLength(0); x++)
                for (int y = 0; y < _tiles.GetLength(1); y++) result.Add(_tiles[x, y]);
            return result.ToArray();
        }
    }

    public sealed class MapStorage : WorldMap
    {
        public MapStorage(int width, int height) : base(width, height) { }
    }

    public static class MapHelper
    {
        public static ushort modPosition = 1000;
        public static ushort liquidPosition;
        public static int[] tileLookup = new int[ushort.MaxValue + 1];
        public static int[] wallLookup = new int[ushort.MaxValue + 1];
        public static int TileToLookup(int type, int option) => tileLookup[type] + option;
    }
}

namespace Terraria
{
    public static class Main
    {
        public static bool dedServ;
        public static int maxTilesX;
        public static int maxTilesY;
        public static Terraria.Map.WorldMap Map = new Terraria.Map.MapStorage(1, 1);
    }
}

namespace Terraria.ModLoader
{
    public sealed class Mod { public string Name { get; set; } }
    public class ModTile { public ushort Type { get; set; } public Mod Mod { get; set; } public string Name { get; set; } }
    public class ModWall { public ushort Type { get; set; } public Mod Mod { get; set; } public string Name { get; set; } }

    public static class MapLoader
    {
        public static Dictionary<ushort, ushort> entryToTile = new();
        public static Dictionary<ushort, ushort> entryToWall = new();
        public static Dictionary<ushort, IList<object>> tileEntries = new();
        public static Dictionary<ushort, IList<object>> wallEntries = new();
        public static Dictionary<ushort, Func<string, int, int, string>> nameFuncs = new();
    }

    public static class TileLoader
    {
        public static Dictionary<int, ModTile> Tiles = new();
        public static Action<int> BeforeGetTile;
        public static ModTile GetTile(int type) { BeforeGetTile?.Invoke(type); return Tiles[type]; }
    }

    public static class WallLoader
    {
        public static Dictionary<int, ModWall> Walls = new();
        public static Action<int> BeforeGetWall;
        public static ModWall GetWall(int type) { BeforeGetWall?.Invoke(type); return Walls[type]; }
    }

    public static class ModContent
    {
        private static readonly Dictionary<(Type, string, string), object> Values = new();
        public static Action<Type, string, string> BeforeTryFind;
        public static void Register<T>(string mod, string name, T value) => Values[(typeof(T), mod, name)] = value;
        public static bool TryFind<T>(string mod, string name, out T value)
        {
            BeforeTryFind?.Invoke(typeof(T), mod, name);
            if (Values.TryGetValue((typeof(T), mod, name), out object raw)) { value = (T)raw; return true; }
            value = default; return false;
        }
        public static void Clear() => Values.Clear();
    }
}

namespace Terraria.ModLoader.IO
{
    public static class StreamExtensions
    {
        public static MemoryStream ToMemoryStream(this byte[] bytes) => new(bytes, writable: false);
    }
}

namespace Terraria.Utilities
{
    public static class FileUtilities
    {
        public static readonly Dictionary<(string, bool), byte[]> Files = new();
        public static int ExistsCalls;
        public static int ReadCalls;
        public static int WriteCalls;
        public static bool Exists(string path, bool cloud) { ExistsCalls++; return Files.ContainsKey((path, cloud)); }
        public static byte[] ReadAllBytes(string path, bool cloud) { ReadCalls++; return Files[(path, cloud)]; }
        public static void WriteAllBytes(string path, byte[] data, bool cloud) { WriteCalls++; Files[(path, cloud)] = data; }
        public static void Reset() { Files.Clear(); ExistsCalls = ReadCalls = WriteCalls = 0; }
    }
}

namespace Terraria.Social
{
    public sealed class CloudSocialModule
    {
        public readonly List<string> Deleted = new();
        public void Delete(string path) => Deleted.Add(path);
    }
    public static class SocialAPI { public static CloudSocialModule Cloud; }
}

namespace ModLiquidLib.ModLoader
{
    public class ModLiquid
    {
        public ushort Type { get; set; }
        public Terraria.ModLoader.Mod Mod { get; set; }
        public string Name { get; set; }
        public Func<int, int, ushort> MapOption { get; set; } = (_, _) => 0;
        public virtual ushort GetMapOption(int i, int j) => MapOption(i, j);
    }

    public static class LiquidLoader
    {
        public static Dictionary<int, ModLiquid> Liquids = new();
        public static Action<int> BeforeGetLiquid;
        public static int LiquidCount = Terraria.ID.LiquidID.Count;
        public static ModLiquid GetLiquid(int type) { BeforeGetLiquid?.Invoke(type); return Liquids[type]; }
    }
}

namespace Terraria.Localization
{
    public sealed class LocalizedText
    {
        public static readonly LocalizedText Empty = new("");
        public string Value { get; }
        public LocalizedText(string value) => Value = value;
    }
}

internal static class TestHooks
{
    public static void Reset(int width = 4, int height = 4)
    {
        Terraria.Main.dedServ = false;
        Terraria.Main.maxTilesX = width;
        Terraria.Main.maxTilesY = height;
        Terraria.Main.Map = new Terraria.Map.MapStorage(width, height);
        Terraria.Map.MapHelper.modPosition = 1000;
        Array.Clear(Terraria.Map.MapHelper.tileLookup);
        Array.Clear(Terraria.Map.MapHelper.wallLookup);
        Terraria.ModLoader.MapLoader.entryToTile.Clear();
        Terraria.ModLoader.MapLoader.entryToWall.Clear();
        Terraria.ModLoader.MapLoader.tileEntries.Clear();
        Terraria.ModLoader.MapLoader.wallEntries.Clear();
        Terraria.ModLoader.MapLoader.nameFuncs.Clear();
        Terraria.ModLoader.TileLoader.Tiles.Clear();
        Terraria.ModLoader.TileLoader.BeforeGetTile = null;
        Terraria.ModLoader.WallLoader.Walls.Clear();
        Terraria.ModLoader.WallLoader.BeforeGetWall = null;
        Terraria.ModLoader.ModContent.Clear();
        Terraria.ModLoader.ModContent.BeforeTryFind = null;
        ModLiquidLib.ModLoader.LiquidLoader.Liquids.Clear();
        ModLiquidLib.ModLoader.LiquidLoader.BeforeGetLiquid = null;
        ModLiquidLib.ModLoader.LiquidLoader.LiquidCount = Terraria.ID.LiquidID.Count;
        ModLiquidLib.ModLoader.MapLiquidLoader.liquidEntries.Clear();
        ModLiquidLib.ModLoader.MapLiquidLoader.entryToLiquid.Clear();
        ModLiquidLib.ModLoader.MapLiquidLoader.liquidLookup = new ushort[Terraria.ID.LiquidID.Count];
        ModLiquidLib.ModLoader.MapLiquidLoader.initialized = false;
        Terraria.Utilities.FileUtilities.Reset();
        Terraria.Social.SocialAPI.Cloud = null;
    }
}
