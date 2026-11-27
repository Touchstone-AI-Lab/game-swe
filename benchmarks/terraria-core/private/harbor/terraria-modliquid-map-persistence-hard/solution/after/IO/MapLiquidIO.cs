using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Terraria.Map;
using Terraria.ModLoader;
using Terraria.Social;
using Terraria.Utilities;
using Terraria;
using Terraria.ModLoader.IO;
using ModLiquidLib.ModLoader;

namespace ModLiquidLib.IO
{
	internal class MapLiquidIO
	{
		private const byte LightFlag = 0x01;
		private const byte ColorFlag = 0x02;
		private const byte RunFlag = 0x04;
		private const byte Run16Flag = 0x08;
		private const byte Run32Flag = 0x10;
		private const byte ContinuationFlag = 0x20;
		private const byte KnownFlags = LightFlag | ColorFlag | RunFlag | Run16Flag | Run32Flag | ContinuationFlag;

		private readonly struct MapSnapshot
		{
			internal readonly int Width;
			internal readonly int Height;
			internal readonly MapTile[] Cells;

			internal MapSnapshot(int width, int height, MapTile[] cells)
			{
				Width = width;
				Height = height;
				Cells = cells;
			}
		}

		private readonly struct HeaderEntry
		{
			internal readonly ushort OldType;
			internal readonly bool IsTile;
			internal readonly string ModName;
			internal readonly string Name;
			internal readonly ushort Option;

			internal HeaderEntry(ushort oldType, bool isTile, string modName, string name, ushort option)
			{
				OldType = oldType;
				IsTile = isTile;
				ModName = modName;
				Name = name;
				Option = option;
			}
		}

		private readonly struct PendingCell
		{
			internal readonly int X;
			internal readonly int Y;
			internal readonly MapTile Tile;

			internal PendingCell(int x, int y, MapTile tile)
			{
				X = x;
				Y = y;
				Tile = tile;
			}
		}

		private readonly struct ParsedTile
		{
			internal readonly MapTile Tile;
			internal readonly uint RepeatedCells;
			internal readonly bool HasContinuation;

			internal ParsedTile(MapTile tile, uint repeatedCells, bool hasContinuation)
			{
				Tile = tile;
				RepeatedCells = repeatedCells;
				HasContinuation = hasContinuation;
			}
		}

		internal static void WriteModFile(string path, bool isCloudSave)
		{
			path = Path.ChangeExtension(path, ".tlmap");
			bool hasModData;
			byte[] data;
			using (MemoryStream stream = new MemoryStream())
			{
				using BinaryWriter writer = new BinaryWriter(stream);
				hasModData = WriteModMap(writer);
				writer.Flush();
				data = stream.ToArray();
			}
			if (hasModData)
			{
				FileUtilities.WriteAllBytes(path, data, isCloudSave);
			}
			else if (isCloudSave)
				SocialAPI.Cloud?.Delete(path);
			else
				File.Delete(path);
		}

		internal static void ReadModFile(string path, bool isCloudSave)
		{
			path = Path.ChangeExtension(path, ".tlmap");
			if (!FileUtilities.Exists(path, isCloudSave))
				return;

			using MemoryStream stream = new MemoryStream(FileUtilities.ReadAllBytes(path, isCloudSave), writable: false);
			using BinaryReader reader = new BinaryReader(stream);
			ReadModMap(reader);
		}

		internal static bool WriteModMap(BinaryWriter writer)
		{
			try
			{
				uint registryGeneration = MapLiquidLoader.Generation;
				MapSnapshot snapshot = CaptureSnapshot();
				SortedSet<ushort> types = new SortedSet<ushort>();
				foreach (MapTile tile in snapshot.Cells)
				{
					if (IsVisibleModTile(tile))
						types.Add(tile.Type);
				}

				if (types.Count == 0)
				{
					EnsureRegistryGeneration(registryGeneration);
					return false;
				}
				if (types.Count > ushort.MaxValue)
					throw new InvalidDataException("The map contains too many mod map types.");

				var tileEntries = new Dictionary<ushort, ushort>(MapLoader.entryToTile);
				var liquidEntries = new Dictionary<ushort, ushort>();
				foreach (KeyValuePair<ushort, ushort> pair in MapLiquidLoader.entryToLiquid)
					liquidEntries.Add(pair.Key, pair.Value);
				var wallEntries = new Dictionary<ushort, ushort>(MapLoader.entryToWall);
				var entries = new List<HeaderEntry>(types.Count);
				foreach (ushort type in types)
					entries.Add(DescribeHeader(type, tileEntries, liquidEntries, wallEntries));

				byte[] prepared;
				using (MemoryStream buffer = new MemoryStream())
				{
					using BinaryWriter staged = new BinaryWriter(buffer);
					staged.Write((ushort)entries.Count);
					foreach (HeaderEntry entry in entries)
					{
						staged.Write(entry.OldType);
						staged.Write(entry.IsTile);
						staged.Write(entry.ModName);
						staged.Write(entry.Name);
						staged.Write(entry.Option);
					}
					WriteSnapshotData(staged, snapshot);
					staged.Flush();
					prepared = buffer.ToArray();
				}

				EnsureRegistryGeneration(registryGeneration);
				writer.Write(prepared);
				return true;
			}
			catch (Exception error) when (ShouldWrapAsInvalidData(error))
			{
				throw new InvalidDataException("The mod map could not be serialized coherently.", error);
			}
		}

		private static MapSnapshot CaptureSnapshot()
		{
			int width = Main.maxTilesX;
			int height = Main.maxTilesY;
			WorldMap map = Main.Map;
			if (width < 0 || height < 0)
				throw new InvalidDataException("The map dimensions are invalid.");

			long total = (long)width * height;
			if (total > int.MaxValue)
				throw new InvalidDataException("The map is too large to snapshot.");
			MapTile[] cells = new MapTile[(int)total];
			int index = 0;
			for (int x = 0; x < width; x++)
				for (int y = 0; y < height; y++)
					cells[index++] = map[x, y];

			if (!ReferenceEquals(map, Main.Map) || width != Main.maxTilesX || height != Main.maxTilesY)
				throw new InvalidDataException("The map changed while its persistence snapshot was captured.");
			return new MapSnapshot(width, height, cells);
		}

		private static HeaderEntry DescribeHeader(
			ushort type,
			IDictionary<ushort, ushort> tileEntries,
			IDictionary<ushort, ushort> liquidEntries,
			IDictionary<ushort, ushort> wallEntries)
		{
			bool hasTile = tileEntries.TryGetValue(type, out ushort tileType);
			bool hasLiquid = liquidEntries.TryGetValue(type, out ushort liquidType);
			bool hasWall = wallEntries.TryGetValue(type, out ushort wallType);
			int matches = (hasTile ? 1 : 0) + (hasLiquid ? 1 : 0) + (hasWall ? 1 : 0);
			if (matches > 1)
				throw new InvalidDataException($"Map type {type} belongs to multiple content registries.");
			if (matches == 0)
				return new HeaderEntry(type, true, string.Empty, string.Empty, 0);

			if (hasTile)
			{
				ModTile tile = TileLoader.GetTile(tileType);
				ushort option = ValidateWriterIdentity(type, MapHelper.tileLookup[tile.Type], MapLiquidLoader.modTileOptions(tile.Type));
				return new HeaderEntry(type, true, RequireName(tile.Mod?.Name), RequireName(tile.Name), option);
			}
			if (hasLiquid)
			{
				ModLiquid liquid = LiquidLoader.GetLiquid(liquidType);
				ushort option = ValidateWriterIdentity(type, MapLiquidLoader.liquidLookup[liquid.Type], MapLiquidLoader.modLiquidOptions(liquid.Type));
				return new HeaderEntry(type, false, RequireName(liquid.Mod?.Name), RequireName(liquid.Name), option);
			}

			ModWall wall = WallLoader.GetWall(wallType);
			ushort wallOption = ValidateWriterIdentity(type, MapHelper.wallLookup[wall.Type], MapLiquidLoader.modWallOptions(wall.Type));
			return new HeaderEntry(type, false, RequireName(wall.Mod?.Name), RequireName(wall.Name), wallOption);
		}

		private static string RequireName(string value)
		{
			if (string.IsNullOrEmpty(value))
				throw new InvalidDataException("Registered map content must have a nonempty identity.");
			return value;
		}

		private static ushort ValidateWriterIdentity(ushort oldType, int baseLookup, int optionCount)
		{
			long option = (long)oldType - baseLookup;
			if (baseLookup < MapHelper.modPosition || optionCount <= 0 || option < 0 || option >= optionCount || option > ushort.MaxValue)
				throw new InvalidDataException($"Map type {oldType} has an invalid lookup base or option range.");
			return (ushort)option;
		}

		internal static void ReadModMap(BinaryReader reader)
		{
			WorldMap targetMap = Main.Map;
			int width = Main.maxTilesX;
			int height = Main.maxTilesY;
			uint registryGeneration = MapLiquidLoader.Generation;
			try
			{
				IDictionary<ushort, ushort> table = ReadHeader(reader);
				if (table.Count == 0)
				{
					EnsureEndOfStream(reader);
					EnsureRegistryGeneration(registryGeneration);
					return;
				}

				List<PendingCell> pending = ParseMapData(reader, table, width, height);
				EnsureDestination(targetMap, width, height);
				EnsureRegistryGeneration(registryGeneration);
				CommitPending(targetMap, pending);
			}
			catch (Exception error) when (ShouldWrapAsInvalidData(error))
			{
				throw new InvalidDataException("The mod map stream is malformed.", error);
			}
		}

		private static IDictionary<ushort, ushort> ReadHeader(BinaryReader reader)
		{
			var table = new Dictionary<ushort, ushort>();
			ushort count = reader.ReadUInt16();
			ushort previousType = 0;
			for (int index = 0; index < count; index++)
			{
				ushort oldType = reader.ReadUInt16();
				if (oldType < MapHelper.modPosition || index > 0 && oldType <= previousType)
					throw new InvalidDataException("Map type definitions must be strictly ascending and in the mod range.");

				byte discriminator = reader.ReadByte();
				if (discriminator > 1)
					throw new InvalidDataException("The map entry discriminator is invalid.");
				string modName = reader.ReadString();
				string name = reader.ReadString();
				ushort option = reader.ReadUInt16();
				table.Add(oldType, ResolveType(discriminator == 1, modName, name, option));
				previousType = oldType;
			}
			return table;
		}

		private static ushort ResolveType(bool isTile, string modName, string name, ushort option)
		{
			if (isTile)
			{
				if (!ModContent.TryFind<ModTile>(modName, name, out var tile))
					return 0;
				return ResolveRegisteredType(MapHelper.tileLookup[tile.Type], MapLiquidLoader.modTileOptions(tile.Type), option);
			}

			bool hasLiquid = ModContent.TryFind<ModLiquid>(modName, name, out var liquid);
			bool hasWall = ModContent.TryFind<ModWall>(modName, name, out var wall);
			if (hasLiquid && hasWall)
				throw new InvalidDataException($"Nontile identity {modName}/{name} is ambiguous.");
			if (hasLiquid)
				return ResolveRegisteredType(MapLiquidLoader.liquidLookup[liquid.Type], MapLiquidLoader.modLiquidOptions(liquid.Type), option);
			if (hasWall)
				return ResolveRegisteredType(MapHelper.wallLookup[wall.Type], MapLiquidLoader.modWallOptions(wall.Type), option);
			return 0;
		}

		private static ushort ResolveRegisteredType(int baseLookup, int optionCount, ushort option)
		{
			if (optionCount <= 0)
				throw new InvalidDataException("Resolved map content has no map options.");
			if (option >= optionCount)
				option = 0;
			long result = (long)baseLookup + option;
			if (baseLookup < MapHelper.modPosition || result > ushort.MaxValue)
				throw new InvalidDataException("Resolved map content has an invalid lookup range.");
			return (ushort)result;
		}

		internal static void WriteMapData(BinaryWriter writer)
		{
			WriteSnapshotData(writer, CaptureSnapshot());
		}

		private static void WriteSnapshotData(BinaryWriter writer, MapSnapshot snapshot)
		{
			int position = 0;
			bool continuation = false;
			while (position < snapshot.Cells.Length)
			{
				if (!continuation)
				{
					byte skip = 0;
					while (position < snapshot.Cells.Length && !IsVisibleModTile(snapshot.Cells[position]) && skip < byte.MaxValue)
					{
						skip++;
						position++;
					}
					writer.Write(skip);
					if (position == snapshot.Cells.Length)
						return;
					if (skip == byte.MaxValue)
						continue;
				}
				else
					continuation = false;

				continuation = WriteSnapshotTile(writer, snapshot.Cells, ref position);
			}
		}

		private static bool WriteSnapshotTile(BinaryWriter writer, MapTile[] cells, ref int position)
		{
			MapTile tile = cells[position];
			uint sameCount = 0;
			while (position + 1 < cells.Length && tile.Equals(cells[position + 1]) && sameCount < uint.MaxValue)
			{
				sameCount++;
				position++;
			}

			bool continuation = position + 1 < cells.Length && IsVisibleModTile(cells[position + 1]);
			WriteTileRecord(writer, tile, sameCount, continuation);
			position++;
			return continuation;
		}

		private static void WriteTileRecord(BinaryWriter writer, MapTile tile, uint sameCount, bool continuation)
		{
			byte flags = 0;
			if (tile.Light < byte.MaxValue)
				flags |= LightFlag;
			if (tile.Color > 0)
				flags |= ColorFlag;
			if (sameCount > 0)
			{
				flags |= RunFlag;
				if (sameCount > byte.MaxValue)
				{
					flags |= Run16Flag;
					if (sameCount > ushort.MaxValue)
						flags |= Run32Flag;
				}
			}
			if (continuation)
				flags |= ContinuationFlag;

			writer.Write(flags);
			writer.Write(tile.Type);
			if ((flags & LightFlag) != 0)
				writer.Write(tile.Light);
			if ((flags & ColorFlag) != 0)
				writer.Write(tile.Color);
			if ((flags & Run32Flag) != 0)
				writer.Write(sameCount);
			else if ((flags & Run16Flag) != 0)
				writer.Write((ushort)sameCount);
			else if ((flags & RunFlag) != 0)
				writer.Write((byte)sameCount);
		}

		internal static void ReadMapData(BinaryReader reader, IDictionary<ushort, ushort> table)
		{
			WorldMap targetMap = Main.Map;
			int width = Main.maxTilesX;
			int height = Main.maxTilesY;
			try
			{
				List<PendingCell> pending = ParseMapData(reader, table, width, height);
				EnsureDestination(targetMap, width, height);
				CommitPending(targetMap, pending);
			}
			catch (Exception error) when (ShouldWrapAsInvalidData(error))
			{
				throw new InvalidDataException("The mod map payload is malformed.", error);
			}
		}

		private static List<PendingCell> ParseMapData(BinaryReader reader, IDictionary<ushort, ushort> table, int width, int height)
		{
			if (table == null)
				throw new InvalidDataException("The mod map type table is missing.");
			if (width < 0 || height < 0)
				throw new InvalidDataException("The map dimensions are invalid.");

			long totalCells = (long)width * height;
			var pending = new List<PendingCell>();
			long position = 0;
			bool continuation = false;
			if (totalCells == 0)
			{
				EnsureEndOfStream(reader);
				return pending;
			}

			while (position < totalCells)
			{
				if (!continuation)
				{
					byte skip;
					do
					{
						skip = reader.ReadByte();
						if (skip > totalCells - position)
							throw new InvalidDataException("A sparse skip exceeds the map bounds.");
						position += skip;
						if (position == totalCells)
						{
							EnsureEndOfStream(reader);
							return pending;
						}
					}
					while (skip == byte.MaxValue);
				}

				ParsedTile parsed = ParseMapTile(reader, table);
				long runLength = 1L + parsed.RepeatedCells;
				if (runLength > totalCells - position)
					throw new InvalidDataException("A map tile run exceeds the map bounds.");
				for (long offset = 0; offset < runLength; offset++)
				{
					long cell = position + offset;
					pending.Add(new PendingCell((int)(cell / height), (int)(cell % height), parsed.Tile));
				}
				position += runLength;
				continuation = parsed.HasContinuation;
				if (continuation && position == totalCells)
					throw new InvalidDataException("A continuation flag points beyond the map.");
			}

			EnsureEndOfStream(reader);
			return pending;
		}

		private static ParsedTile ParseMapTile(BinaryReader reader, IDictionary<ushort, ushort> table)
		{
			byte flags = reader.ReadByte();
			bool hasRun = (flags & RunFlag) != 0;
			bool hasRun16 = (flags & Run16Flag) != 0;
			bool hasRun32 = (flags & Run32Flag) != 0;
			if ((flags & ~KnownFlags) != 0 || !hasRun && (hasRun16 || hasRun32) || hasRun32 && !hasRun16)
				throw new InvalidDataException("The map tile contains invalid flags.");

			ushort oldType = reader.ReadUInt16();
			if (!table.TryGetValue(oldType, out ushort type))
				throw new InvalidDataException($"Map type {oldType} is not present in the header.");
			byte light = (flags & LightFlag) != 0 ? reader.ReadByte() : byte.MaxValue;
			byte color = (flags & ColorFlag) != 0 ? reader.ReadByte() : (byte)0;

			uint sameCount = 0;
			if (hasRun32)
			{
				sameCount = reader.ReadUInt32();
				if (sameCount <= ushort.MaxValue)
					throw new InvalidDataException("The map tile run uses a non-canonical length.");
			}
			else if (hasRun16)
			{
				sameCount = reader.ReadUInt16();
				if (sameCount <= byte.MaxValue)
					throw new InvalidDataException("The map tile run uses a non-canonical length.");
			}
			else if (hasRun)
			{
				sameCount = reader.ReadByte();
				if (sameCount == 0)
					throw new InvalidDataException("The map tile run cannot be empty.");
			}

			return new ParsedTile(MapTile.Create(type, light, color), sameCount, (flags & ContinuationFlag) != 0);
		}

		private static void EnsureDestination(WorldMap targetMap, int width, int height)
		{
			if (!ReferenceEquals(targetMap, Main.Map) || width != Main.maxTilesX || height != Main.maxTilesY)
				throw new InvalidDataException("The destination map changed while the sidecar was being decoded.");
		}

		private static void EnsureRegistryGeneration(uint generation)
		{
			if (generation != MapLiquidLoader.Generation)
				throw new InvalidDataException("The liquid map registry changed during sidecar processing.");
		}

		private static void CommitPending(WorldMap targetMap, List<PendingCell> pending)
		{
			var previous = new List<MapTile>(pending.Count);
			foreach (PendingCell cell in pending)
				previous.Add(targetMap[cell.X, cell.Y]);

			int committed = 0;
			try
			{
				for (; committed < pending.Count; committed++)
				{
					PendingCell cell = pending[committed];
					MapTile tile = cell.Tile;
					targetMap.SetTile(cell.X, cell.Y, ref tile);
				}
			}
			catch (Exception commitError)
			{
				Exception rollbackError = null;
				for (int index = Math.Min(committed, pending.Count - 1); index >= 0; index--)
				{
					try
					{
						PendingCell cell = pending[index];
						MapTile tile = previous[index];
						targetMap.SetTile(cell.X, cell.Y, ref tile);
					}
					catch (Exception error)
					{
						rollbackError ??= error;
					}
				}
				Exception inner = rollbackError == null ? commitError : new AggregateException(commitError, rollbackError);
				throw new InvalidDataException("The map commit failed and was rolled back.", inner);
			}
		}

		internal static void WriteMapTile(ref int i, ref int j, BinaryWriter writer, ref bool nextModTile)
		{
			MapTile tile = Main.Map[i, j];
			int nextI = i;
			int nextJ = j;
			uint sameCount = 0;
			while (NextTile(ref nextI, ref nextJ))
			{
				MapTile nextTile = Main.Map[nextI, nextJ];
				if (tile.Equals(ref nextTile) && sameCount < uint.MaxValue)
				{
					sameCount++;
					i = nextI;
					j = nextJ;
					continue;
				}
				break;
			}

			bool continuation = nextI >= 0 && nextI < Main.maxTilesX && nextJ >= 0 && nextJ < Main.maxTilesY &&
				IsVisibleModTile(Main.Map[nextI, nextJ]);
			WriteTileRecord(writer, tile, sameCount, continuation);
			nextModTile = continuation;
		}

		internal static void ReadMapTile(ref int i, ref int j, IDictionary<ushort, ushort> table, BinaryReader reader, ref bool nextModTile)
		{
			if (table == null)
				throw new InvalidDataException("The mod map type table is missing.");
			if (i < 0 || i >= Main.maxTilesX || j < 0 || j >= Main.maxTilesY)
				throw new InvalidDataException("The map tile position is outside the map.");

			ParsedTile parsed;
			try
			{
				parsed = ParseMapTile(reader, table);
			}
			catch (Exception error) when (ShouldWrapAsInvalidData(error))
			{
				throw new InvalidDataException("The map tile record is malformed.", error);
			}

			long start = (long)i * Main.maxTilesY + j;
			long total = (long)Main.maxTilesX * Main.maxTilesY;
			long length = 1L + parsed.RepeatedCells;
			if (length > total - start || parsed.HasContinuation && start + length == total)
				throw new InvalidDataException("The map tile record exceeds the map.");
			var pending = new List<PendingCell>((int)length);
			for (long offset = 0; offset < length; offset++)
			{
				long cell = start + offset;
				pending.Add(new PendingCell((int)(cell / Main.maxTilesY), (int)(cell % Main.maxTilesY), parsed.Tile));
			}
			CommitPending(Main.Map, pending);
			long last = start + parsed.RepeatedCells;
			i = (int)(last / Main.maxTilesY);
			j = (int)(last % Main.maxTilesY);
			nextModTile = parsed.HasContinuation;
		}

		private static bool IsVisibleModTile(MapTile tile)
			=> tile.Type >= MapHelper.modPosition && tile.Light > 18;

		private static void EnsureEndOfStream(BinaryReader reader)
		{
			try
			{
				reader.ReadByte();
			}
			catch (EndOfStreamException)
			{
				return;
			}
			throw new InvalidDataException("The mod map stream has trailing bytes.");
		}

		private static bool ShouldWrapAsInvalidData(Exception error)
			=> error is not InvalidDataException &&
				(error is IOException ||
				 error is FormatException ||
				 error is ArgumentException ||
				 error is KeyNotFoundException ||
				 error is IndexOutOfRangeException ||
				 error is InvalidOperationException ||
				 error is NullReferenceException ||
				 error is OverflowException ||
				 error is DecoderFallbackException);

		private static bool NextTile(ref int i, ref int j)
		{
			j++;
			if (j >= Main.maxTilesY)
			{
				j = 0;
				i++;
				if (i >= Main.maxTilesX)
					return false;
			}
			return true;
		}
	}
}
