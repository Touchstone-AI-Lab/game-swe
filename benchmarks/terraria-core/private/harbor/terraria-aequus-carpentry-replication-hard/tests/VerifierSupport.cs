global using Microsoft.Xna.Framework;
global using Terraria;
global using Terraria.ID;
global using Terraria.ModLoader;

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace Microsoft.Xna.Framework
{
    public struct Vector2 { public float X; public float Y; public Vector2(float x,float y){X=x;Y=y;} }
    public struct Rectangle
    {
        public int X,Y,Width,Height;
        public Rectangle(int x,int y,int width,int height){X=x;Y=y;Width=width;Height=height;}
        public bool Contains(int x,int y)=>x>=X&&x<X+Width&&y>=Y&&y<Y+Height;
        public bool Intersects(Rectangle o)=>o.X<X+Width&&X<o.X+o.Width&&o.Y<Y+Height&&Y<o.Y+o.Height;
    }
}

namespace Terraria.ID { public static class NetmodeID { public const int SinglePlayer=0, MultiplayerClient=1, Server=2; } }

namespace Terraria
{
    public static class Main { public static int netMode; public static int myPlayer; public static ulong GameUpdateCount; }
    public class NPC
    {
        public static bool Danger;
        public static bool AnyDanger(bool quickBossNPCCheck=true,bool ignorePillarsAndMoonlordCountdown=true)=>Danger;
    }
    public class Player
    {
        public int whoAmI;
        public Microsoft.Xna.Framework.Vector2 Center;
        public Aequus.AequusPlayer AequusData=new();
        public readonly List<(int,int)> Buffs=new();
        public Action<int,int> OnAddBuff;
        public Aequus.AequusPlayer Aequus()=>AequusData;
        public void AddBuff(int type,int time){Buffs.Add((type,time));OnAddBuff?.Invoke(type,time);}
    }
}

namespace Terraria.ModLoader
{
    [AttributeUsage(AttributeTargets.Class)] public sealed class LegacyNameAttribute:Attribute { public LegacyNameAttribute(string value){} }
    public class ModSystem
    {
        public virtual void Load(){} public virtual void ClearWorld(){}
        public virtual void SaveWorldData(Terraria.ModLoader.IO.TagCompound tag){}
        public virtual void LoadWorldData(Terraria.ModLoader.IO.TagCompound tag){}
        public virtual void NetSend(BinaryWriter writer){} public virtual void NetReceive(BinaryReader reader){}
    }
    public class ModPlayer
    {
        public Terraria.Player Player {get;set;}=new();
        public virtual void Initialize(){} public virtual void SaveData(Terraria.ModLoader.IO.TagCompound tag){}
        public virtual void LoadData(Terraria.ModLoader.IO.TagCompound tag){}
        public virtual ModPlayer Clone(Terraria.Player newEntity){var clone=(ModPlayer)MemberwiseClone();clone.Player=newEntity;return clone;}
        public virtual void CopyClientState(ModPlayer clientClone){} public virtual void SendClientChanges(ModPlayer clientPlayer){}
        public virtual void PostUpdate(){}
    }
}

namespace Terraria.ModLoader.IO
{
    public sealed class TagCompound:Dictionary<string,object>
    {
        public bool TryGet<T>(string key,out T value){if(TryGetValue(key,out object raw)&&raw is T t){value=t;return true;}value=default;return false;}
        public T Get<T>(string key,T defaultValue=default)=>TryGet<T>(key,out var value)?value:defaultValue;
    }
}

namespace Aequus.Common.Carpentry.Results
{
    public enum StepResultType { Fail,Almost,Success }
    public interface IScanResults { StepResultType ResultType {get;} }
    public sealed class ScanResult:IScanResults { public StepResultType ResultType {get;set;} }
}

namespace Aequus.Common.Carpentry
{
    using Microsoft.Xna.Framework;
    using global::Aequus.Common.Carpentry.Results;
    public sealed class HighlightInfo { public Rectangle Area; public HighlightInfo(Rectangle area)=>Area=area; }
    public readonly struct ScanInfo { public readonly Rectangle Area; public ScanInfo(Rectangle area)=>Area=area; }
    public class BuildChallenge
    {
        public int Type {get;set;} public string FullName {get;set;} public object[] Steps {get;set;}=Array.Empty<object>();
        public int BuildBuffType {get;set;}
        public Action<IScanResults[],Rectangle> PopulateAction {get;set;}
        public virtual void PopulateScanResults(IScanResults[] results,ref HighlightInfo highlightInfo,in ScanInfo scanInfo)=>PopulateAction?.Invoke(results,scanInfo.Area);
    }
    public static class BuildChallengeLoader
    {
        public static readonly List<BuildChallenge> registeredBuildChallenges=new();
        public static int BuildChallengeCount=>registeredBuildChallenges.Count;
        public static bool TryFind(string name,out BuildChallenge challenge){challenge=registeredBuildChallenges.FirstOrDefault(x=>x.FullName==name);return challenge!=null;}
    }
    public static class ListExtensions { public static bool ContainsAny<T>(this List<T> list,Predicate<T> predicate)=>list.Exists(predicate); }
}

namespace Aequus
{
    public enum PacketType:byte { AddBuilding,RemoveBuilding,CarpenterBountiesCompleted,ResetCarpenterBounties,CompleteCarpenterBounty }
    public sealed class LoggerStub { public readonly List<string> Errors=new(); public void Error(string value)=>Errors.Add(value); }
    public sealed class PacketStub:BinaryWriter
    {
        private readonly MemoryStream stream;
        public PacketType Type {get;} public bool Sent {get;private set;}
        public PacketStub(PacketType type):this(type,new MemoryStream()){}
        private PacketStub(PacketType type,MemoryStream stream):base(stream){this.stream=stream;Type=type;}
        public byte[] Bytes {get{Flush();return stream.ToArray();}}
        public void Send()=>Sent=true;
    }
    public sealed class Aequus
    {
        public static Aequus Instance {get;}=new();
        public LoggerStub Logger {get;}=new();
        public static readonly List<PacketStub> Packets=new();
        public static PacketStub GetPacket(PacketType type){var p=new PacketStub(type);Packets.Add(p);return p;}
    }
    public sealed class AequusPlayer { public int buildingBuffRange=10; }
}

internal static class TestHooks
{
    public static void Reset()
    {
        Terraria.Main.netMode=Terraria.ID.NetmodeID.SinglePlayer; Terraria.Main.myPlayer=0; Terraria.Main.GameUpdateCount=0; Terraria.NPC.Danger=false;
        Aequus.Common.Carpentry.BuildChallengeLoader.registeredBuildChallenges.Clear();
        Aequus.Common.Carpentry.CarpentrySystem.CompletedBounties.Clear();
        Aequus.Common.Carpentry.CarpentrySystem.BuildingBuffs.Clear();
        Aequus.Aequus.Packets.Clear(); Aequus.Aequus.Instance.Logger.Errors.Clear();
    }
}
