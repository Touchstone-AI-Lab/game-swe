using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;

namespace Terraria {
	public static class ItemDefinitions {
		private static readonly Dictionary<int, int> MaxStacks = [];
		private static readonly Dictionary<int, Action<Item>> Initializers = [];

		public static void SetMaxStack(int type, int maxStack) => MaxStacks[type] = maxStack;

		public static int GetMaxStack(int type) => MaxStacks.TryGetValue(type, out int value) ? value : 9999;

		public static void SetInitializer(int type, Action<Item> initializer) => Initializers[type] = initializer;

		public static void Initialize(Item item) {
			if (Initializers.TryGetValue(item.type, out Action<Item> initializer))
				initializer(item);
		}
	}

	public class Item {
		public const int CommonMaxStack = 9999;

		public int type;
		public int netID;
		public int prefix;
		public int stack = 1;
		public int maxStack = CommonMaxStack;
		public bool favorited;
		public bool IsFailure;
		public Terraria.ModLoader.ModItem ModItem;
		public List<Terraria.ModLoader.GlobalItem> Globals { get; } = [];

		public bool IsAir => type == 0;

		public Item() { }

		public Item(int type, int stack = 1, int prefix = 0) {
			netDefaults(type);
			this.stack = stack;
			this.prefix = prefix;
		}

		public void netDefaults(int value) {
			type = netID = value;
			maxStack = ItemDefinitions.GetMaxStack(value);
			stack = 1;
			ModItem = null;
			Globals.Clear();
			ItemDefinitions.Initialize(this);
		}

		public void Prefix(int value) => prefix = value;

		public T GetGlobalItem<T>() where T : Terraria.ModLoader.GlobalItem, new() {
			T found = Globals.OfType<T>().FirstOrDefault();
			if (found is null) {
				found = new T();
				Globals.Add(found);
			}
			return found;
		}
	}
}

namespace Terraria.ModLoader {
	public class Mod {
		public string Name { get; set; } = "ProjectionMod";
	}

	public class ModItem {
		public string Name { get; set; } = "ProjectionItem";
		public Mod Mod { get; set; } = new();
		public virtual void NetSend(BinaryWriter writer) { }
		public virtual void NetReceive(BinaryReader reader) { }
	}

	public class GlobalItem {
		public string Name { get; set; } = "ProjectionGlobal";
		public Mod Mod { get; set; } = new();
		public virtual void NetSend(Terraria.Item item, BinaryWriter writer) { }
		public virtual void NetReceive(Terraria.Item item, BinaryReader reader) { }
	}

	public sealed class HookEnumeration : IEnumerable<GlobalItem> {
		public GlobalItem[] baseGlobals { get; }

		public HookEnumeration(IEnumerable<GlobalItem> globals) => baseGlobals = globals.ToArray();

		public IEnumerator<GlobalItem> GetEnumerator() => ((IEnumerable<GlobalItem>)baseGlobals).GetEnumerator();

		IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();
	}

	public sealed class GlobalHook {
		public HookEnumeration Enumerate(Terraria.Item item) => new(item.Globals);
	}

	public static class ItemLoader {
		public static int ItemCount { get; set; } = 4096;
		public static GlobalHook HookNetSend { get; } = new();
		public static GlobalHook HookNetReceive { get; } = new();
	}

	public static class PrefixLoader {
		public static int PrefixCount { get; set; } = 256;
	}

	public static class ModContent {
		private static readonly Dictionary<Type, object> Instances = [];

		public static T GetInstance<T>() where T : new() {
			if (!Instances.TryGetValue(typeof(T), out object value)) {
				value = new T();
				Instances[typeof(T)] = value;
			}
			return (T)value;
		}
	}
}

namespace Terraria.ModLoader.Default {
	public class UnloadedGlobalItem : Terraria.ModLoader.GlobalItem {
		public string ModPrefixMod;
		public string ModPrefixName;
	}
}

namespace MagicStorage.Items.ErrorDisplay {
	internal static class BaseErrorDummyItem {
		public static int NetReadFailItemType => 900001;
	}
}

namespace MagicStorage {
	internal sealed class ProjectionLogger {
		public void Error(string message, Exception error) { }
	}

	internal sealed class MagicStorageMod {
		public static MagicStorageMod Instance { get; } = new();
		public ProjectionLogger Logger { get; } = new();
	}

	internal static class ProjectionItemExtensions {
		public static string IdentifierAndStack(this Terraria.Item item) => $"{item.type} x{item.stack}";
	}

	partial class Utility {
		internal static void UnsafelyReceiveModData(Terraria.Item item, BinaryReader reader) => item.ModItem?.NetReceive(reader);

		internal static void UnsafelyReceiveGlobalModData(
			Terraria.Item item,
			MagicStorage.Common.IO.DeserializedNetItem readData,
			BinaryReader reader,
			out Terraria.ModLoader.GlobalItem lastReadGlobal
		) {
			lastReadGlobal = null;
			foreach (Terraria.ModLoader.GlobalItem global in item.Globals) {
				lastReadGlobal = global;
				global.NetReceive(item, reader);
			}
			lastReadGlobal = null;
		}

		internal static Terraria.Item PrepareFailureItem(
			int type,
			object data,
			MagicStorage.Common.IO.DeserializedNetItem readData
		) => new(type, readData.stack, readData.prefix) { IsFailure = true, favorited = readData.favorite };
	}
}

namespace MagicStorage.Common.IO {
	public class DeserializedNetItem {
		public int? type;
		public int prefix;
		public string modPrefixMod;
		public string modPrefixName;
		public int stack = 1;
		public bool favorite;
	}

	public sealed class ItemTypeTracker {
		public int BitCount => NetCompression.GetBitSize(Terraria.ModLoader.ItemLoader.ItemCount) + 1;

		public void Receive(ref Terraria.Item value, ValueReader reader) => value.netDefaults(reader.ReadInt32(BitCount));

		public void Send(Terraria.Item value, ValueWriter writer) => writer.Write(value.netID, BitCount);
	}

	public sealed class ItemPrefixTracker {
		public int BitCount => NetCompression.GetBitSize(Terraria.ModLoader.PrefixLoader.PrefixCount);

		public void Receive(ref Terraria.Item value, ValueReader reader) => value.Prefix((int)reader.ReadUInt32(BitCount - 1));

		public void Send(Terraria.Item value, ValueWriter writer) => writer.Write((uint)value.prefix, BitCount - 1);
	}

	partial class NetCompression {
		public static int GetBitSize(byte value) => BitOperations.Log2(value) + 1;
		public static int GetBitSize(ushort value) => BitOperations.Log2(value) + 1;
		public static int GetBitSize(uint value) => BitOperations.Log2(value) + 1;
		public static int GetBitSize(int value) => BitOperations.Log2((uint)value) + 1;

		public static int GetBitSize<T>(T value) {
			if (typeof(T) == typeof(byte))
				return GetBitSize((byte)(object)value);
			if (typeof(T) == typeof(sbyte))
				return GetBitSize((byte)(sbyte)(object)value);
			if (typeof(T) == typeof(ushort))
				return GetBitSize((ushort)(object)value);
			if (typeof(T) == typeof(short))
				return GetBitSize((ushort)(short)(object)value);
			if (typeof(T) == typeof(uint))
				return GetBitSize((uint)(object)value);
			if (typeof(T) == typeof(int))
				return GetBitSize((int)(object)value);
			if (typeof(T) == typeof(ulong))
				return BitOperations.Log2((ulong)(object)value) + 1;
			if (typeof(T) == typeof(long))
				return BitOperations.Log2((ulong)(long)(object)value) + 1;
			throw new NotSupportedException($"Unsupported type: {typeof(T)}");
		}
	}
}
