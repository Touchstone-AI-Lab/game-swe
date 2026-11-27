using System;
using System.Collections.Generic;
using System.IO;

namespace Microsoft.Xna.Framework
{
    public struct Point { public int X, Y; public Point(int x, int y) { X = x; Y = y; } }
    public struct Vector2
    {
        public float X, Y;
        public Vector2(float value) { X = value; Y = value; }
        public Vector2(float x, float y) { X = x; Y = y; }
        public static Vector2 Zero => new(0, 0);
        public static Vector2 One => new(1, 1);
        public static Vector2 operator +(Vector2 a, Vector2 b) => new(a.X + b.X, a.Y + b.Y);
        public static Vector2 operator -(Vector2 a, Vector2 b) => new(a.X - b.X, a.Y - b.Y);
        public static Vector2 operator *(Vector2 a, float b) => new(a.X * b, a.Y * b);
        public static Vector2 operator /(Vector2 a, float b) => new(a.X / b, a.Y / b);
        public static Vector2 Lerp(Vector2 a, Vector2 b, float amount) => a + (b - a) * amount;
        public float Distance(Vector2 other) => MathF.Sqrt((X - other.X) * (X - other.X) + (Y - other.Y) * (Y - other.Y));
        public float AngleTo(Vector2 other) => MathF.Atan2(other.Y - Y, other.X - X);
        public Point ToPoint() => new((int)X, (int)Y);
        public Vector2 RotatedBy(double radians) => new((float)(X * Math.Cos(radians) - Y * Math.Sin(radians)), (float)(X * Math.Sin(radians) + Y * Math.Cos(radians)));
    }
    public struct Rectangle
    {
        public int X, Y, Width, Height;
        public Rectangle(int x, int y, int width, int height) { X = x; Y = y; Width = width; Height = height; }
        public bool Contains(Point point) => point.X >= X && point.X < X + Width && point.Y >= Y && point.Y < Y + Height;
    }
    public struct Color
    {
        public static Color DarkGray => new(); public static Color White => new();
        public static Color operator *(Color color, float amount) => color;
    }
    public static class MathHelper
    {
        public static float Lerp(float a, float b, float amount) => a + (b - a) * amount;
        public static float ToRadians(float degrees) => degrees * MathF.PI / 180f;
    }
}

namespace Microsoft.Xna.Framework.Graphics
{
    using Microsoft.Xna.Framework;
    public class Texture2D { public int Width => 16; public int Height => 16; }
    public class SpriteBatch
    {
        public void Begin(SpriteSortMode sortMode, BlendState blend, object sampler, DepthStencilState depth, object rasterizer, object effect = null, Matrix? transformMatrix = null) { }
        public void End() { }
    }
    public enum SpriteSortMode { Immediate }
    public enum SpriteEffects { None }
    public class BlendState { public static BlendState AlphaBlend { get; } = new(); }
    public class DepthStencilState { public static DepthStencilState None { get; } = new(); }
    public struct Matrix { }
}

namespace ReLogic.Content { public class Asset<T> { public T Value { get; set; } = Activator.CreateInstance<T>(); } }

namespace Terraria.DataStructures
{
    using Microsoft.Xna.Framework;
    public readonly struct Point16 : IEquatable<Point16>
    {
        public readonly short X, Y;
        public Point16(int x, int y) { X = (short)x; Y = (short)y; }
        public bool Equals(Point16 other) => X == other.X && Y == other.Y;
        public override bool Equals(object obj) => obj is Point16 other && Equals(other);
        public override int GetHashCode() => HashCode.Combine(X, Y);
        public static bool operator ==(Point16 a, Point16 b) => a.Equals(b);
        public static bool operator !=(Point16 a, Point16 b) => !a.Equals(b);
        public Vector2 ToWorldCoordinates() => new(X * 16, Y * 16);
        public Vector2 ToVector2() => new(X, Y);
    }
    public class TileDrawInfo { }
}

namespace Terraria.ID
{
    public static class NetmodeID { public const int SinglePlayer = 0, MultiplayerClient = 1, Server = 2; }
    public static class MessageID { public const int SyncItem = 1, TileEntityPlacement = 2, TileEntitySharing = 3; }
    public static class DustID { public const int Stone = 1; }
    public static class ExtrasID { public const int FairyQueenLance = 0; }
    public static class RecipeGroupID { public const int Squirrels = 1; }
    public static class SoundID
    {
        public static Terraria.Audio.SoundStyle Item130 => new();
        public static Terraria.Audio.SoundStyle Item150 => new();
        public static Terraria.Audio.SoundStyle Item176 => new();
    }
    public static class TileID
    {
        public const int CookingPots=1, CrystalBall=2, DemonAltar=3, GlassKiln=4, HeavyWorkBench=5, LivingLoom=6, Loom=7,
            LunarCraftingStation=8, SkyMill=9, Solidifier=10, TinkerersWorkbench=11, Tombstones=12, WorkBenches=13;
    }
    public static class ItemID
    {
        public const int None=0, AbigailsFlower=1, Amber=2, AmberMosquito=3, Amethyst=4, AngelStatue=5, AnvilStatue=6,
            AxeStatue=7, BabyBirdStaff=8, BalloonHorseshoeFart=9, BatBanner=10, BatStatue=11, BeetleHusk=12, Bird=13,
            BloodZombieBanner=14, BloodZombieStatue=15, BlueHorseshoeBalloon=16, Bomb=17, BombStatue=18, BoneSkeletonStatue=19,
            BoomerangStatue=20, BootStatue=21, BowStatue=22, ChestStatue=23, ChlorophyteGreaves=24, ChlorophyteMask=25,
            ChlorophytePlateMail=26, CloudinaBalloon=27, CorruptStatue=28, CrabBanner=29, CrabStatue=30, CrossStatue=31,
            Deathweed=32, DemonEyeBanner=33, Diamond=34, DripplerBanner=35, DripplerStatue=36, EaterofSoulsBanner=37,
            Emerald=38, EnchantedSword=39, EyeballStatue=40, FallenStar=41, FamiliarPants=42, FamiliarShirt=43,
            FamiliarWig=44, FartInABalloon=45, Firefly=46, FireImpBanner=47, FishingSeaweed=48, FlowerBoots=49,
            GargoyleStatue=50, GarlandHat=51, GemSquirrelAmber=52, GemSquirrelAmethyst=53, GemSquirrelDiamond=54,
            GemSquirrelEmerald=55, GemSquirrelRuby=56, GemSquirrelSapphire=57, GemSquirrelTopaz=58, Glass=59,
            GloomStatue=60, GlowingMushroom=61, GoblinPeonBanner=62, GoblinStatue=63, GraniteGolemBanner=64,
            GraniteGolemStatue=65, GrassSeeds=66, GreekSkeletonBanner=67, HammerStatue=68, HarpyBanner=69,
            HarpyStatue=70, HealingPotion=71, HeartStatue=72, Hook=73, HopliteStatue=74, HornetBanner=75,
            HornetStatue=76, IceBlade=77, ImpStatue=78, JellyfishBanner=79, JellyfishStatue=80, JungleSpores=81,
            KingStatue=82, LifeCrystal=83, LihzahrdBanner=84, LihzahrdBrick=85, LihzahrdGuardianStatue=86,
            LihzahrdStatue=87, LihzahrdWatcherStatue=88, LivingLoom=89, Loom=90, LunarBar=91, MagicalPumpkinSeed=92,
            ManaCrystal=93, MedusaBanner=94, MedusaStatue=95, MimicBanner=96, MusicBox=97, OldShoe=98,
            PickaxeStatue=99, PigronBanner=100, PigronStatue=101, PillarStatue=102, PiranhaBanner=103,
            PiranhaStatue=104, PlatinumCoin=105, PotionStatue=106, PotStatue=107, Pumpkin=108, QueenStatue=109,
            ReaperStatue=110, Ruby=111, SailfishBoots=112, Sapphire=113, Seaweed=114, SharkBanner=115,
            SharkFin=116, SharkStatue=117, ShieldStatue=118, ShimmerBlock=119, Silk=120, SkeletonBanner=121,
            SkeletonStatue=122, SlimeBanner=123, SlimeStatue=124, SpearStatue=125, SpiderBanner=126, StarStatue=127,
            StoneBlock=128, Sundial=129, SunflowerStatue=130, SunplateBlock=131, SwordStatue=132,
            TeleportationPotion=133, TeleportationPylonDesert=134, TeleportationPylonHallow=135,
            TeleportationPylonJungle=136, TeleportationPylonMushroom=137, TeleportationPylonOcean=138,
            TeleportationPylonPurity=139, TeleportationPylonSnow=140, TeleportationPylonUnderground=141,
            TeleportationPylonVictory=142, Terragrim=143, Throne=144, Tombstone=145, Topaz=146, TreeStatue=147,
            TurtleHelmet=148, TurtleLeggings=149, TurtleScaleMail=150, UndeadVikingBanner=151,
            UndeadVikingStatue=152, UnicornBanner=153, UnicornStatue=154, Vine=155, WallCreeperStatue=156,
            WaterBucket=157, WebRopeCoil=158, WebSlinger=159, WetBomb=160, WhoopieCushion=161, WomanStatue=162,
            Wood=163, WraithBanner=164, WraithStatue=165, ZombieArmStatue=166, ZombieBanner=167;
    }
}

namespace Terraria.Audio
{
    using Microsoft.Xna.Framework;
    public record struct SoundStyle { public float Pitch { get; init; } }
    public static class SoundEngine { public static void PlaySound(SoundStyle style, Vector2 position) { } }
}

namespace Terraria.Localization
{
    public class LocalizedText { }
    public static class Language { public static string GetItemNameValue(int type) => $"Item{type}"; }
}

namespace Terraria.ModLoader.IO
{
    using Microsoft.Xna.Framework;
    public class ItemDefinition { public int Type { get; } public ItemDefinition(int type) { Type = type; } }
    public class TagCompound : Dictionary<string, object>
    {
        public T Get<T>(string key) => TryGetValue(key, out object value) ? (T)value : default;
        public int GetAsInt(string key) => Get<int>(key);
    }
    public static class BinaryExtensions
    {
        public static void WriteVector2(this BinaryWriter writer, Vector2 value) { writer.Write(value.X); writer.Write(value.Y); }
        public static Vector2 ReadVector2(this BinaryReader reader) => new(reader.ReadSingle(), reader.ReadSingle());
    }
}

namespace Terraria.ModLoader.Config { }

namespace Terraria.ModLoader
{
    using Microsoft.Xna.Framework;
    using Microsoft.Xna.Framework.Graphics;
    using Terraria.DataStructures;
    using Terraria.Localization;
    using Terraria.ModLoader.IO;
    public class Mod { public string Name { get; set; } = "TestMod"; }
    public class ModItem { public string Name { get; set; } = ""; public Mod Mod { get; set; } = new(); }
    public class GlobalItem { }
    public class ModSystem { public virtual void AddRecipes() { } public virtual void PostAddRecipes() { } public virtual void PostSetupRecipes() { } }
    public class ModTile
    {
        public int Type { get; set; } = 7; public int DustType { get; set; }
        public virtual void SetStaticDefaults() { } public virtual void RandomUpdate(int i, int j) { }
        public virtual void PlaceInWorld(int i, int j, Terraria.Item item) { }
        public virtual void KillMultiTile(int i, int j, int frameX, int frameY) { }
        public virtual void DrawEffects(int i, int j, SpriteBatch spriteBatch, ref TileDrawInfo drawData) { }
        public virtual void SpecialDraw(int i, int j, SpriteBatch spriteBatch) { }
        public virtual bool RightClick(int i, int j) => false;
        public virtual void NearbyEffects(int i, int j, bool closer) { }
        public LocalizedText CreateMapEntryName() => new(); public void AddMapEntry(Color color, LocalizedText text) { }
    }
    public class ModTileEntity
    {
        public int ID { get; set; } public int Type { get; set; } = 4; public Point16 Position { get; set; }
        public virtual void Update() { } public virtual bool IsTileValidForEntity(int x, int y) => true;
        public virtual int Hook_AfterPlacement(int i, int j, int type, int style, int direction, int alternate) => -1;
        public virtual void OnNetPlace() { } public virtual void SaveData(TagCompound tag) { } public virtual void LoadData(TagCompound tag) { }
        public virtual void NetSend(BinaryWriter writer) { } public virtual void NetReceive(BinaryReader reader) { }
        public int Place(int i, int j) { Position = new(i, j); return 0; } public void Kill(int i, int j) { }
        public int Generic_HookPostPlaceMyPlayer(int i, int j, int type, int style, int direction, int alternate) => Hook_AfterPlacement(i, j, type, style, direction, alternate);
    }
    public static class ModContent
    {
        private static readonly Dictionary<Type, object> Instances = new();
        public static T GetInstance<T>() where T : new() { if (!Instances.TryGetValue(typeof(T), out object value)) Instances[typeof(T)] = value = new T(); return (T)value; }
        public static int TileType<T>() => 7;
    }
    public static class ItemLoader { public static int ItemCount => 4096; }
}

namespace Terraria.ObjectData
{
    using Terraria.DataStructures;
    public class TileObjectData
    {
        public static TileObjectData newTile { get; } = new(); public static TileObjectData Style3x4 { get; } = new();
        public int Width { get; set; } public int Height { get; set; } public int[] CoordinateHeights { get; set; }
        public Func<int,int,int,int,int,int,int> HookPostPlaceMyPlayer { get; set; } public bool UsesCustomCanPlace { get; set; }
        public Point16 Origin { get; set; } public void CopyFrom(TileObjectData other) { } public static void addTile(int type) { }
    }
}

namespace Terraria.GameContent
{
    using System.Collections.Generic;
    using Microsoft.Xna.Framework.Graphics;
    using ReLogic.Content;
    public static class TextureAssets
    {
        public static Asset<Texture2D>[] Item { get; } = Create(4096); public static Asset<Texture2D>[] Extra { get; } = Create(32);
        private static Asset<Texture2D>[] Create(int count) { var values = new Asset<Texture2D>[count]; for (int i=0;i<count;i++) values[i]=new(); return values; }
    }
}

namespace Terraria
{
    using System.Collections.Generic;
    using Microsoft.Xna.Framework;
    using Microsoft.Xna.Framework.Graphics;
    using Terraria.DataStructures;
    using Terraria.ModLoader;
    public class Tile { public bool HasTile { get; set; } public int TileType { get; set; } }
    public class Item
    {
        public int type, stack = 1, prefix, value; public bool favorited; public ModItem ModItem { get; set; }
        private readonly Dictionary<Type, GlobalItem> globals = new();
        public T GetGlobalItem<T>() where T : GlobalItem, new() { if (!globals.TryGetValue(typeof(T), out GlobalItem value)) globals[typeof(T)] = value = new T(); return (T)value; }
        public static object GetSource_NaturalSpawn() => new object();
        public static int NewItem(object source, Rectangle rectangle, int type, int stack=1, bool noBroadcast=false, int prefixGiven=0) => Main.SpawnItem(type, stack, prefixGiven);
        public static int NewItem(object source, Vector2 position, int type, int stack=1, bool noBroadcast=false, int prefixGiven=0) => Main.SpawnItem(type, stack, prefixGiven);
    }
    public class Player
    {
        public bool active=true, dead, mouseInterface, controlUseItem; public int whoAmI; public Item HeldItem { get; set; } = new();
        public Vector2 Center { get; set; } public int Money { get; set; } = int.MaxValue;
        public float Distance(Vector2 target) => Center.Distance(target);
        public bool BuyItem(int price) { if (price < 0 || Money < price) return false; Money -= price; return true; }
        public object GetSource_TileInteraction(int i, int j, string context=null) => new object();
    }
    public class Recipe
    {
        public static int numRecipes => Main.recipe.Count;
        public Item createItem { get; set; } = new(); public List<Item> requiredItem { get; } = new(); public List<int> acceptedGroups { get; } = new();
        public bool HasIngredient(int type) => requiredItem.Exists(x => x.type == type);
        public bool TryGetIngredient(int type, out Item item) { item = requiredItem.Find(x => x.type == type); return item != null; }
        public void RemoveIngredient(Item item) => requiredItem.Remove(item); public Recipe AddIngredient(int type, int amount=1) { requiredItem.Add(new Item { type=type, stack=amount }); return this; }
        public Recipe AddRecipeGroup(int id, int amount=1) => this; public Recipe AddTile(int type) => this; public void DisableDecraft() { } public void Register() => Main.recipe.Add(this);
        public static Recipe Create(int result, int amount=1) => new() { createItem = new Item { type=result, stack=amount } };
    }
    public class RecipeGroup { public static Dictionary<int, RecipeGroup> recipeGroups { get; } = new(); public List<int> ValidItems { get; } = new(); public int IconicItemId { get; set; } }
    public static class ContentSamples { public static Item[] ItemsByType { get; } = Create(); private static Item[] Create() { var x=new Item[4096]; for(int i=0;i<x.Length;i++) x[i]=new Item{type=i}; return x; } }
    public class TilesRenderer { public void AddSpecialLegacyPoint(int i, int j) { } }
    public class MainInstance { public TilesRenderer TilesRenderer { get; } = new(); public void MouseText(string text, int rare) { } }
    public class CameraData { public object Sampler { get; } = new(); public object Rasterizer { get; } = new(); public GameViewMatrixData GameViewMatrix { get; } = new(); }
    public class GameViewMatrixData { public Matrix TransformationMatrix { get; } = new(); }
    public static class Main
    {
        public static bool[] tileSolid=new bool[4096], tileMergeDirt=new bool[4096], tileBlockLight=new bool[4096], tileNoAttach=new bool[4096], tileFrameImportant=new bool[4096];
        public static Tile[,] tile = CreateTiles(); public static List<Recipe> recipe { get; } = new(); public static Item[] item { get; } = CreateItems();
        public static int netMode, myPlayer; public static bool dedServ, gameMenu, playerInventory, mouseRight, mouseRightRelease;
        public static Player LocalPlayer { get; set; } = new(); public static MainInstance instance { get; } = new(); public static Vector2 screenPosition, MouseWorld;
        public static Color DiscoColor => Color.White; public static SpriteBatch spriteBatch { get; } = new(); public static CameraData Camera { get; } = new();
        public static int SpawnItem(int type, int stack, int prefix) { for(int i=0;i<item.Length;i++) if(item[i].type==0){ item[i]=new Item{type=type,stack=stack,prefix=prefix}; return i;} return -1; }
        public static void GetItemDrawFrame(int type, out Texture2D texture, out Rectangle frame) { texture=new(); frame=new(0,0,16,16); }
        public static void EntitySpriteDraw(Texture2D texture, Vector2 position, Rectangle? source, Color color, float rotation, Vector2 origin, float scale, SpriteEffects effects, float layer=0) { }
        public static void EntitySpriteDraw(Texture2D texture, Vector2 position, Rectangle? source, Color color, float rotation, Vector2 origin, Vector2 scale, SpriteEffects effects, float layer=0) { }
        private static Tile[,] CreateTiles() { var x=new Tile[64,64]; for(int i=0;i<64;i++) for(int j=0;j<64;j++) x[i,j]=new(); return x; }
        private static Item[] CreateItems() { var x=new Item[256]; for(int i=0;i<x.Length;i++) x[i]=new(); return x; }
    }
    public static class NetMessage { public static List<(int,int,int)> Sent { get; } = new(); public static void SendTileSquare(int who, int i, int j, int width, int height) { } public static void SendData(int msgType, int remoteClient=-1, int ignoreClient=-1, object text=null, int number=0, float number2=0, float number3=0) => Sent.Add((msgType,remoteClient,number)); }
    public static class Lang { public static string GetItemNameValue(int type) => Localization.Language.GetItemNameValue(type); }
    public static class DrawingExtensions
    {
        public static int Width(this Texture2D texture) => texture.Width; public static int Height(this Texture2D texture) => texture.Height;
        public static int Width(this ReLogic.Content.Asset<Texture2D> texture) => texture.Value.Width;
        public static int Height(this ReLogic.Content.Asset<Texture2D> texture) => texture.Value.Height;
        public static Vector2 ToWorldCoordinates(this Vector2 tile) => tile * 16f;
    }
}

namespace Fargowiltas.Common.Configs { public sealed class FargoServerConfig { public static FargoServerConfig Instance { get; } = new(); public bool MiscRecipes { get; set; } = true; } }
namespace Fargowiltas.Content.Items { }
namespace Fargowiltas.Content.Items.Misc { }
namespace Fargowiltas.Content.Items.Summons { public class BaseSummon : Terraria.ModLoader.ModItem { } public class BaseSpawnBooster : Terraria.ModLoader.ModItem { } }
namespace Fargowiltas.Content.Items.Summons.Mutant { public class FleshyDoll : Terraria.ModLoader.ModItem { } }
namespace Fargowiltas.Common.Systems { }
namespace Fargowiltas.Common.Systems.Collections
{
    using System.Collections.Generic;
    public enum DupeType { NotDupable, NotDupableFromDupable, Direct, MaterialsDupable }
    public static class FargoItemSets
    {
        public static DupeType[] DuplicatableItems { get; } = new DupeType[4096];
        public static Dictionary<int,List<int>> DuplicatableRecipes { get; } = new();
    }
}

namespace Fargowiltas.Utilities
{
    using Terraria;
    public static class RecipeHelper
    {
        public static Recipe CreateSimpleRecipe(int ingredient, int result, int tile, int ingredientAmount=1, bool disableDecraft=false, params object[] conditions) => Recipe.Create(result).AddIngredient(ingredient, ingredientAmount);
    }
}

namespace Fargowiltas.Common.Systems.Recipes
{
    public static class RecipeGroups { public const int AnyCommonFish=100, AnyGoldBar=101, AnyEvilBar=102; }
}

namespace Fargowiltas
{
    using System.Collections.Generic;
    using Microsoft.Xna.Framework;
    using Terraria;
    using Terraria.DataStructures;
    using Terraria.ModLoader;
    using global::Fargowiltas.Content.Items.Tiles;
    public static class Fargowiltas { public static HashSet<string> SoulsMods { get; } = new() { "FargowiltasSouls", "FargowiltasSoulsDLC" }; }
    public class FargoGlobalItem : GlobalItem { public int Grabbed { get; set; } public bool FromEnchantedTree { get; set; } public List<int> RecipeGroupAnimationItems { get; set; } }
    public class FargoPlayerState { public EnchantedTreeTileEntity.Fruit grabbedFruit; }
    public static class FargoPlayerExtensions { private static readonly FargoPlayerState State = new(); public static FargoPlayerState FargoMutant(this Player player) => State; }
    public static class FargoNet { public static List<int> FruitPackets { get; } = new(); public static void SendEnchantedTreesListPacket() { } public static void SendEnchantedTreeFruitPacket(int index) => FruitPackets.Add(index); }
    public static class FargoUtils
    {
        public static readonly Dictionary<Point16, ModTileEntity> Entities = new();
        public static Point16 GetTopLeftTileInMultitile(int i, int j) => new(i - i % 3, j - j % 4);
        public static bool TryGetTileEntityAs<T>(int i, int j, out T value) where T : ModTileEntity { if (Entities.TryGetValue(GetTopLeftTileInMultitile(i,j), out ModTileEntity entity) && entity is T typed) { value=typed; return true; } value=null; return false; }
        public static bool TryGetTileEntityAs<T>(int i, int j, out T value, bool unused=false) where T : ModTileEntity => TryGetTileEntityAs(i,j,out value);
    }
    public static class ReforgeUtils { public static string GetPriceString(int price, bool a, bool b) => price.ToString(); }
}

public static class Condition { public static object InGraveyard { get; } = new(); }
