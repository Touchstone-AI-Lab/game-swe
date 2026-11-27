using System;
using System.IO;
using System.Numerics;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace MagicStorage.Items.ErrorDisplay
{
    internal static class BaseErrorDummyItem
    {
        public static int NetReadFailItemType => ItemID.DirtBlock;
    }
}

namespace MagicStorage
{
    internal sealed class ProjectionLogger
    {
        public void Error(string message, Exception error)
        {
        }
    }

    internal sealed class MagicStorageMod
    {
        public static MagicStorageMod Instance { get; } = new();
        public ProjectionLogger Logger { get; } = new();
    }

    internal static class ProjectionItemExtensions
    {
        public static string IdentifierAndStack(this Item item) => $"{item.type} x{item.stack}";
    }

    partial class Utility
    {
        internal static void UnsafelyReceiveModData(Item item, BinaryReader reader)
            => item.ModItem?.NetReceive(reader);

        internal static void UnsafelyReceiveGlobalModData(
            Item item,
            MagicStorage.Common.IO.DeserializedNetItem readData,
            BinaryReader reader,
            out GlobalItem? lastReadGlobal
        )
        {
            lastReadGlobal = null;
            foreach (GlobalItem global in ItemLoader.HookNetReceive.Enumerate(item))
            {
                lastReadGlobal = global;
                global.NetReceive(item, reader);
            }
            lastReadGlobal = null;
        }

        internal static Item PrepareFailureItem(
            int type,
            object? data,
            MagicStorage.Common.IO.DeserializedNetItem readData
        ) => new(type, readData.stack, readData.prefix) { favorited = readData.favorite };
    }
}

namespace MagicStorage.Common.IO
{
    public class DeserializedNetItem
    {
        public int? type;
        public int prefix;
        public string? modPrefixMod;
        public string? modPrefixName;
        public int stack = 1;
        public bool favorite;
    }

    public sealed class ItemTypeTracker : ModType
    {
        public int BitCount => NetCompression.GetBitSize(ItemLoader.ItemCount) + 1;
        public override void Register() => ModTypeLookup<ItemTypeTracker>.Register(this);
        public override void SetupContent() => SetStaticDefaults();
        public void Receive(ref Item value, ValueReader reader) => value.netDefaults(reader.ReadInt32(BitCount));
        public void Send(Item value, ValueWriter writer) => writer.Write(value.netID, BitCount);
    }

    public sealed class ItemPrefixTracker : ModType
    {
        public int BitCount => NetCompression.GetBitSize(PrefixLoader.PrefixCount);
        public override void Register() => ModTypeLookup<ItemPrefixTracker>.Register(this);
        public override void SetupContent() => SetStaticDefaults();
        public void Receive(ref Item value, ValueReader reader) => value.Prefix((int)reader.ReadUInt32(BitCount - 1));
        public void Send(Item value, ValueWriter writer) => writer.Write((uint)value.prefix, BitCount - 1);
    }

    partial class NetCompression
    {
        public static int GetBitSize(byte value) => BitOperations.Log2(value) + 1;
        public static int GetBitSize(ushort value) => BitOperations.Log2(value) + 1;
        public static int GetBitSize(uint value) => BitOperations.Log2(value) + 1;
        public static int GetBitSize(int value) => BitOperations.Log2((uint)value) + 1;

        public static int GetBitSize<T>(T value)
        {
            if (typeof(T) == typeof(byte)) return GetBitSize((byte)(object)value!);
            if (typeof(T) == typeof(sbyte)) return GetBitSize((byte)(sbyte)(object)value!);
            if (typeof(T) == typeof(ushort)) return GetBitSize((ushort)(object)value!);
            if (typeof(T) == typeof(short)) return GetBitSize((ushort)(short)(object)value!);
            if (typeof(T) == typeof(uint)) return GetBitSize((uint)(object)value!);
            if (typeof(T) == typeof(int)) return GetBitSize((int)(object)value!);
            if (typeof(T) == typeof(ulong)) return BitOperations.Log2((ulong)(object)value!) + 1;
            if (typeof(T) == typeof(long)) return BitOperations.Log2((ulong)(long)(object)value!) + 1;
            throw new NotSupportedException($"Unsupported type: {typeof(T)}");
        }
    }
}
