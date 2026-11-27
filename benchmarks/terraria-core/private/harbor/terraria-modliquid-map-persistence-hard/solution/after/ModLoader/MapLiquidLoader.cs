using System;
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.Localization;
using Terraria.Map;
using Terraria.ModLoader;

namespace ModLiquidLib.ModLoader
{
	internal static class MapLiquidLoader
	{
		internal static bool initialized;
		internal static readonly IDictionary<ushort, IList<MapEntry>> liquidEntries = new Dictionary<ushort, IList<MapEntry>>();
		internal static readonly IDictionary<ushort, ushort> entryToLiquid = new Dictionary<ushort, ushort>();
		public static ushort[] liquidLookup = new ushort[LiquidID.Count];

		private static readonly HashSet<ushort> publishedMapTypes = new HashSet<ushort>();

		internal static uint Generation { get; private set; }

		internal static int modTileOptions(ushort type) => MapLoader.tileEntries[type].Count;
		internal static int modWallOptions(ushort type) => MapLoader.wallEntries[type].Count;
		internal static int modLiquidOptions(ushort type) => liquidEntries[type].Count;

		internal static void FinishSetup()
		{
			if (!Main.dedServ)
				initialized = true;
		}

		internal static void PublishEntries(ref IList<Color> colors, ref IList<LocalizedText> names)
		{
			if (colors == null || names == null)
				throw new InvalidOperationException("The map color and name tables are required.");
			if (colors.Count != names.Count)
				throw new InvalidOperationException("The map color and name tables are misaligned.");
			if (LiquidLoader.LiquidCount < LiquidID.Count)
				throw new InvalidOperationException("The liquid registry count is below the vanilla range.");

			var stagedEntries = new List<KeyValuePair<ushort, IList<MapEntry>>>(liquidEntries.Count);
			foreach (KeyValuePair<ushort, IList<MapEntry>> pair in liquidEntries)
			{
				if (pair.Key < LiquidID.Count || pair.Key >= LiquidLoader.LiquidCount)
					throw new InvalidOperationException($"Liquid type {pair.Key} is outside the registered custom range.");
				if (pair.Value == null || pair.Value.Count == 0)
					throw new InvalidOperationException($"Liquid type {pair.Key} has no map entries.");

				var entries = new List<MapEntry>(pair.Value.Count);
				foreach (MapEntry entry in pair.Value)
				{
					if (entry.name == null || entry.getName == null)
						throw new InvalidOperationException($"Liquid type {pair.Key} has an incomplete map entry.");
					entries.Add(entry);
				}
				stagedEntries.Add(new KeyValuePair<ushort, IList<MapEntry>>(pair.Key, entries));
			}
			stagedEntries.Sort((left, right) => left.Key.CompareTo(right.Key));

			var stagedColors = new List<Color>(colors);
			var stagedNames = new List<LocalizedText>(names);
			var stagedLookup = new ushort[LiquidLoader.LiquidCount];
			if (liquidLookup != null)
				Array.Copy(liquidLookup, stagedLookup, Math.Min(LiquidID.Count, Math.Min(liquidLookup.Length, stagedLookup.Length)));
			var stagedEntryToLiquid = new Dictionary<ushort, ushort>();
			var stagedNameFuncs = new Dictionary<ushort, Func<string, int, int, string>>(MapLoader.nameFuncs);
			foreach (ushort mapType in publishedMapTypes)
				stagedNameFuncs.Remove(mapType);
			var stagedPublished = new HashSet<ushort>();

			long nextMapType = (long)MapHelper.modPosition + stagedColors.Count;
			foreach (KeyValuePair<ushort, IList<MapEntry>> pair in stagedEntries)
			{
				if (nextMapType > ushort.MaxValue)
					throw new InvalidOperationException("The custom liquid map range exceeds UInt16.");
				stagedLookup[pair.Key] = (ushort)nextMapType;

				foreach (MapEntry entry in pair.Value)
				{
					if (nextMapType > ushort.MaxValue)
						throw new InvalidOperationException("The custom liquid map range exceeds UInt16.");
					ushort mapType = (ushort)nextMapType;
					if (MapLoader.entryToTile.ContainsKey(mapType) ||
						MapLoader.entryToWall.ContainsKey(mapType) ||
						stagedNameFuncs.ContainsKey(mapType) ||
						!stagedEntryToLiquid.TryAdd(mapType, pair.Key))
						throw new InvalidOperationException($"Map type {mapType} collides with an existing map registration.");

					stagedNameFuncs.Add(mapType, entry.getName);
					stagedPublished.Add(mapType);
					stagedColors.Add(entry.color);
					stagedNames.Add(entry.name);
					nextMapType++;
				}
			}

			colors = stagedColors;
			names = stagedNames;
			liquidLookup = stagedLookup;
			Replace(entryToLiquid, stagedEntryToLiquid);
			Replace(MapLoader.nameFuncs, stagedNameFuncs);
			publishedMapTypes.Clear();
			foreach (ushort mapType in stagedPublished)
				publishedMapTypes.Add(mapType);
			unchecked { Generation++; }
		}

		internal static void UnloadModMap()
		{
			liquidEntries.Clear();
			entryToLiquid.Clear();
			foreach (ushort mapType in publishedMapTypes)
				MapLoader.nameFuncs.Remove(mapType);
			publishedMapTypes.Clear();
			var vanillaLookup = new ushort[LiquidID.Count];
			if (liquidLookup != null)
				Array.Copy(liquidLookup, vanillaLookup, Math.Min(liquidLookup.Length, vanillaLookup.Length));
			liquidLookup = vanillaLookup;
			initialized = false;
			unchecked { Generation++; }
		}

		internal static void ModMapOption(ref ushort mapType, int i, int j)
		{
			ushort original = mapType;
			if (!entryToLiquid.TryGetValue(original, out ushort liquidType))
				return;

			uint generation = Generation;
			if (!liquidEntries.TryGetValue(liquidType, out IList<MapEntry> entries) || entries == null)
				throw new InvalidOperationException("The selected liquid has no published option table.");
			int optionCount = entries.Count;
			ushort baseLookup = ValidatePublishedTopology(liquidType, entries, optionCount);
			if (original < baseLookup || (long)original >= (long)baseLookup + optionCount)
				throw new InvalidOperationException("The selected map type is outside its owner's published option range.");

			ModLiquid liquid = LiquidLoader.GetLiquid(liquidType);
			if (liquid == null || liquid.Type != liquidType)
				throw new InvalidOperationException("The selected liquid registration changed.");
			EnsureStableSelection(original, liquidType, entries, optionCount, baseLookup, generation);
			ushort option = liquid.GetMapOption(i, j);

			EnsureStableSelection(original, liquidType, entries, optionCount, baseLookup, generation);

			if (option >= optionCount)
				throw new ArgumentOutOfRangeException(nameof(option), "The liquid returned an invalid map option.");
			long resolved = (long)baseLookup + option;
			if (resolved > ushort.MaxValue)
				throw new InvalidOperationException("The selected liquid map option exceeds UInt16.");
			mapType = (ushort)resolved;
		}

		private static void EnsureStableSelection(
			ushort original,
			ushort liquidType,
			IList<MapEntry> entries,
			int optionCount,
			ushort baseLookup,
			uint generation)
		{
			if (generation != Generation ||
				!entryToLiquid.TryGetValue(original, out ushort currentLiquid) || currentLiquid != liquidType ||
				!liquidEntries.TryGetValue(liquidType, out IList<MapEntry> currentEntries) ||
				!ReferenceEquals(entries, currentEntries) || currentEntries.Count != optionCount ||
				liquidLookup == null || liquidType >= liquidLookup.Length || liquidLookup[liquidType] != baseLookup)
				throw new InvalidOperationException("The liquid map registry changed during option selection.");
			ValidatePublishedTopology(liquidType, currentEntries, optionCount);
		}

		private static ushort ValidatePublishedTopology(ushort liquidType, IList<MapEntry> entries, int optionCount)
		{
			if (optionCount <= 0 || liquidLookup == null || liquidType >= liquidLookup.Length)
				throw new InvalidOperationException("The selected liquid has no published map range.");
			ushort baseLookup = liquidLookup[liquidType];
			long end = (long)baseLookup + optionCount - 1;
			if (baseLookup < MapHelper.modPosition || end > ushort.MaxValue)
				throw new InvalidOperationException("The selected liquid has an invalid published map range.");
			for (int option = 0; option < optionCount; option++)
			{
				ushort mapType = (ushort)(baseLookup + option);
				if (!entryToLiquid.TryGetValue(mapType, out ushort owner) || owner != liquidType)
					throw new InvalidOperationException("The selected liquid map range is not contiguous.");
			}
			return baseLookup;
		}

		private static void Replace<TKey, TValue>(IDictionary<TKey, TValue> destination, IDictionary<TKey, TValue> source)
		{
			destination.Clear();
			foreach (KeyValuePair<TKey, TValue> pair in source)
				destination.Add(pair);
		}
	}
}
