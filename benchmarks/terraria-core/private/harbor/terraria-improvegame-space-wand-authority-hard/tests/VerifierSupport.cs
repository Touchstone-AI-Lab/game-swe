global using System;
global using System.Collections.Generic;
global using System.Linq;
global using Microsoft.Xna.Framework;
global using Terraria;
global using Terraria.Enums;
global using Terraria.ID;
global using Terraria.ModLoader;
global using static ImproveGame.Helpers.ProjectionHelpers;

namespace Microsoft.Xna.Framework
{
    public struct Vector2
    {
        public float X, Y;
        public Vector2(float value) { X=value; Y=value; }
        public Vector2(float x, float y) { X=x; Y=y; }
        public static Vector2 operator -(Vector2 a, Vector2 b) => new(a.X-b.X,a.Y-b.Y);
        public float ToRotation() => MathF.Atan2(Y,X);
        public float Distance(Vector2 other) => MathF.Sqrt((X-other.X)*(X-other.X)+(Y-other.Y)*(Y-other.Y));
        public Point ToTileCoordinates() => new((int)MathF.Floor(X/16f),(int)MathF.Floor(Y/16f));
    }
    public struct Point : IEquatable<Point>
    {
        public int X, Y;
        public Point(int x,int y){X=x;Y=y;}
        public static Point operator +(Point a,Point b)=>new(a.X+b.X,a.Y+b.Y);
        public static Point operator -(Point a,Point b)=>new(a.X-b.X,a.Y-b.Y);
        public bool Equals(Point other)=>X==other.X&&Y==other.Y;
        public override bool Equals(object value)=>value is Point other&&Equals(other);
        public override int GetHashCode()=>HashCode.Combine(X,Y);
    }
    public static class MathHelper
    {
        public const float TwoPi=MathF.PI*2f, PiOver4=MathF.PI/4f;
    }
}

namespace Terraria.Enums { public enum BlockType : byte { Solid, HalfBlock, SlopeDownLeft, SlopeDownRight, SlopeUpLeft, SlopeUpRight } }

namespace Terraria.ID
{
    public static class NetmodeID { public const int SinglePlayer=0, MultiplayerClient=1, Server=2; }
    public static class ItemID { public const int None=0; }
    public static class TileID
    {
        public const int Grass=1,CorruptGrass=2,JungleGrass=3,MushroomGrass=4,ImmatureHerbs=5,HallowedGrass=6,CrimsonGrass=7,AshGrass=8,
            GreenMoss=9,BrownMoss=10,RedMoss=11,BlueMoss=12,PurpleMoss=13,LavaMoss=14,KryptonMoss=15,XenonMoss=16,ArgonMoss=17,
            VioletMoss=18,RainbowMoss=19,MinecartTrack=20,ClosedDoor=21,PlanterBox=22;
        public static class Sets { public static bool[] Platforms {get;}=new bool[512]; }
    }
}

namespace Terraria
{
    using Terraria.Enums;
    public class Item
    {
        public int type,stack,createTile=-1,tileWand=-1,placeStyle;
        public bool consumable=true;
        public Terraria.ModLoader.ModItem ModItem;
        public bool IsAir=>type==0||stack<=0;
        public void TurnToAir(){type=0;stack=0;createTile=-1;}
    }
    public class Tile
    {
        public bool HasTile,IsActuated;
        public ushort TileType;
        public short TileFrameX,TileFrameY;
        public byte TileColor;
        public BlockType BlockType;
    }
    public class Player
    {
        public bool active=true,TileReplacementEnabled=true,noBuilding,dead;
        public bool CanPick=true;
        public int whoAmI,selectedItem;
        public Item[] inventory=Enumerable.Range(0,58).Select(_=>new Item()).ToArray();
        public Item HeldItem=>inventory[selectedItem];
        public bool HasEnoughPickPowerToHurtTile(int x,int y)=>CanPick;
    }
    public static class Main
    {
        public static int netMode;
        public static Player[] player=Enumerable.Range(0,8).Select(i=>new Player{whoAmI=i}).ToArray();
        public static Tile[,] tile=CreateTiles();
        public static bool[] tileSolid=new bool[512],tileSolidTop=new bool[512],tileRope=new bool[512];
        public static Tile[,] CreateTiles(){var result=new Tile[256,256];for(int x=0;x<256;x++)for(int y=0;y<256;y++)result[x,y]=new();return result;}
    }
    public static class WorldGen
    {
        public static bool PlaceAllowed=true,ReplaceAllowed=true,CanPoundAllowed=true;
        public static bool MutateBeforePlaceFailure,MutateBeforeReplaceFailure;
        public static bool CommitBeforePlaceFailure,CommitBeforeReplaceFailure;
        public static bool ReportPlaceSuccessWithoutMutation,ReportReplaceSuccessWithoutMutation;
        public static bool MutateRightNeighborOnPlace,MutateFrameOnFrame;
        public static List<string> Calls {get;}=new();
        public static List<ushort> KillObservedTypes {get;}=new();
        public static bool InWorld(int x,int y,int fluff=0)=>x>=fluff&&y>=fluff&&x<256-fluff&&y<256-fluff;
        private static void MutateTile(int x,int y,int type,bool correct)
        {
            Tile tile=Main.tile[x,y];tile.HasTile=true;tile.TileType=(ushort)(correct?type:type+1);tile.BlockType=BlockType.HalfBlock;
            tile.TileFrameX=36;tile.TileFrameY=18;tile.TileColor=7;tile.IsActuated=true;
            if(MutateRightNeighborOnPlace){Tile neighbor=Main.tile[x+1,y];neighbor.TileFrameX++;neighbor.TileColor++;neighbor.IsActuated=!neighbor.IsActuated;}
        }
        public static bool PlaceTile(int x,int y,int type,bool mute=false,bool forced=false,int plr=-1,int style=0)
        {
            Calls.Add($"place:{x},{y}");
            if(ReportPlaceSuccessWithoutMutation)return true;
            if(!PlaceAllowed){if(CommitBeforePlaceFailure)MutateTile(x,y,type,true);else if(MutateBeforePlaceFailure)MutateTile(x,y,type,false);return false;}
            MutateTile(x,y,type,true);return true;
        }
        public static bool ReplaceTile(int x,int y,ushort type,int style)
        {
            Calls.Add($"replace:{x},{y}");
            if(ReportReplaceSuccessWithoutMutation)return true;
            if(!ReplaceAllowed){if(CommitBeforeReplaceFailure)MutateTile(x,y,type,true);else if(MutateBeforeReplaceFailure)MutateTile(x,y,type,false);return false;}
            MutateTile(x,y,type,true);return true;
        }
        public static void SlopeTile(int x,int y,bool noEffects=false){Calls.Add($"slope:{x},{y}");if(InWorld(x,y))Main.tile[x,y].BlockType=BlockType.Solid;}
        public static bool CanPoundTile(int x,int y)=>CanPoundAllowed;
        public static void SquareTileFrame(int x,int y,bool resetFrame=false){Calls.Add($"frame:{x},{y}");if(MutateFrameOnFrame)Main.tile[x,y].TileFrameX++;}
    }
    public static class NetMessage
    {
        public readonly record struct Sync(int X,int Y,int Width,int Height);
        public static List<Sync> Sent {get;}=new();
        public static void SendTileSquare(int who,int x,int y,int size)=>Sent.Add(new(x,y,size,size));
        public static void SendTileSquare(int who,int x,int y,int width,int height)=>Sent.Add(new(x,y,width,height));
    }
}

namespace Terraria.ModLoader
{
    public abstract class ModItem { }
    public static class TileLoader
    {
        public static bool Allowed=true,MutateBeforeReject;
        public static bool CanPlace(int x,int y,int type)
        {
            WorldGen.Calls.Add($"can-place:{x},{y}");
            if(!Allowed&&MutateBeforeReject)
            {
                Tile tile=Main.tile[x,y];tile.HasTile=!tile.HasTile;tile.TileType=(ushort)(type+1);tile.BlockType=BlockType.HalfBlock;
                tile.TileFrameX=99;tile.TileFrameY=77;tile.TileColor=11;tile.IsActuated=!tile.IsActuated;
                Main.tile[x+1,y].TileFrameX++;
            }
            return Allowed;
        }
    }
    public static class ItemLoader { public static bool ConsumeAllowed=true; public static bool ConsumeItem(Item item,Player player)=>ConsumeAllowed; }
}

namespace ImproveGame
{
    public static class PointExtensions
    {
        public static Point Min(Point a,Point b)=>new(Math.Min(a.X,b.X),Math.Min(a.Y,b.Y));
        public static Point Abs(this Point value)=>new(Math.Abs(value.X),Math.Abs(value.Y));
        public static float DistanceSQ(this Point a,Point b){int x=a.X-b.X,y=a.Y-b.Y;return x*x+y*y;}
    }
}

namespace ImproveGame.Helpers
{
    public static class ProjectionHelpers
    {
        public static Point ModifySize(Point start,Point end,int width,int height){width--;height--;end.X=Math.Clamp(end.X,start.X-width,start.X+width);end.Y=Math.Clamp(end.Y,start.Y-height,start.Y+height);return end;}
        public static void ForeachTile(IEnumerable<Point> points,Action<int,int> action){foreach(Point point in points)action(point.X,point.Y);}
        public static int EnoughItem(Player player,Func<Item,bool> condition,int amount=1){int first=-1,total=0;for(int i=0;i<50;i++){Item item=player.inventory[i];if(!item.IsAir&&condition(item)){if(first<0)first=i;if(!item.consumable)return first;total+=item.stack;}}return total>=amount?first:-1;}
        public static bool TryConsumeItem(ref Item item,Player player,bool ignoreConsumable=false){if(!item.IsAir&&(item.consumable||ignoreConsumable)&&ItemLoader.ConsumeItem(item,player)){if(--item.stack<1)item.TurnToAir();return true;}return false;}
        public static bool ValidReplacementAllowed=true;
        public static bool ValidTileForReplacement(Item item,int x,int y)=>ValidReplacementAllowed&&Main.tile[x,y].TileType!=item.createTile;
        public static bool TryKillTile(int x,int y,Player player){WorldGen.Calls.Add($"kill:{x},{y}");WorldGen.KillObservedTypes.Add(Main.tile[x,y].TileType);if(!player.CanPick)return false;Main.tile[x,y].HasTile=false;return true;}
    }
}

namespace ImproveGame.Content.Items
{
    public enum PlaceType : byte { Platform,Soild,Rope,Rail,GrassSeed,PlantPot }
    public enum ShapeType : byte { Line,Corner,SquareEmpty,SquareFilled,CircleEmpty,CircleFilled }
    public partial class SpaceWand : Terraria.ModLoader.ModItem
    {
        public enum Direction { Right,Down,Left,Up,RightDown,LeftDown,LeftUp,RightUp }
        private static string _dataText="";
        public static Func<Item,bool> GetConditions(PlaceType type)=>type switch
        {
            PlaceType.Platform=>item=>item.createTile>=0&&TileID.Sets.Platforms[item.createTile],
            PlaceType.Soild=>item=>item.createTile>TileID.RainbowMoss&&!Main.tileSolidTop[item.createTile]&&Main.tileSolid[item.createTile]&&item.createTile!=TileID.ClosedDoor,
            PlaceType.Rope=>item=>item.createTile>=0&&Main.tileRope[item.createTile],
            PlaceType.Rail=>item=>item.createTile==TileID.MinecartTrack,
            PlaceType.GrassSeed=>item=>item.createTile is >=TileID.Grass and <=TileID.RainbowMoss,
            PlaceType.PlantPot=>item=>item.createTile==TileID.PlanterBox,
            _=>_=>false
        };
    }
}

namespace ImproveGame.Packets
{
    public sealed class AutoSyncAttribute : Attribute { }
    public abstract class NetModule { public int Sender; public int SendCount; public virtual void Receive(){ } public void Send(){SendCount++;} }
    public static class NetModuleLoader { private static readonly Dictionary<Type,NetModule> Values=new(); public static T Get<T>() where T:NetModule,new(){if(!Values.TryGetValue(typeof(T),out NetModule value))Values[typeof(T)]=value=new T();return (T)value;} }
    public static class PlaySoundPacket { public static List<(int,Vector2)> Sent {get;}=new(); public static void PlaySound(int id,Vector2 position)=>Sent.Add((id,position)); }
    public static class LegacySoundIDs { public const int Dig=1; }
}

namespace ImproveGame.Packets.Items
{
    public static class ConsumeItemPacket
    {
        public static List<(Dictionary<int,int> Items,int Sender)> Sent {get;}=new();
        public static void Proceed(Dictionary<int,int> items,int sender)=>Sent.Add((new Dictionary<int,int>(items),sender));
    }
}

internal static class TestHooks
{
    public static void Reset()
    {
        Terraria.Main.netMode=Terraria.ID.NetmodeID.SinglePlayer;
        Terraria.Main.player=Enumerable.Range(0,8).Select(i=>new Terraria.Player{whoAmI=i}).ToArray();
        Terraria.Main.tile=Terraria.Main.CreateTiles();
        Array.Clear(Terraria.Main.tileSolid); Array.Clear(Terraria.Main.tileSolidTop); Array.Clear(Terraria.Main.tileRope); Array.Clear(Terraria.ID.TileID.Sets.Platforms);
        Terraria.WorldGen.PlaceAllowed=true; Terraria.WorldGen.ReplaceAllowed=true; Terraria.WorldGen.CanPoundAllowed=true;
        Terraria.WorldGen.MutateBeforePlaceFailure=false; Terraria.WorldGen.MutateBeforeReplaceFailure=false;
        Terraria.WorldGen.CommitBeforePlaceFailure=false; Terraria.WorldGen.CommitBeforeReplaceFailure=false;
        Terraria.WorldGen.ReportPlaceSuccessWithoutMutation=false; Terraria.WorldGen.ReportReplaceSuccessWithoutMutation=false;
        Terraria.WorldGen.MutateRightNeighborOnPlace=false; Terraria.WorldGen.MutateFrameOnFrame=false;
        Terraria.WorldGen.Calls.Clear(); Terraria.WorldGen.KillObservedTypes.Clear();
        ImproveGame.Helpers.ProjectionHelpers.ValidReplacementAllowed=true;
        Terraria.ModLoader.TileLoader.Allowed=true; Terraria.ModLoader.TileLoader.MutateBeforeReject=false; Terraria.ModLoader.ItemLoader.ConsumeAllowed=true;
        Terraria.NetMessage.Sent.Clear(); ImproveGame.Packets.PlaySoundPacket.Sent.Clear(); ImproveGame.Packets.Items.ConsumeItemPacket.Sent.Clear();
    }
}
