using System;
using Microsoft.Xna.Framework;
using ModLiquidLib.IO;
using ModLiquidLib.ModLoader;
using MonoMod.Cil;
using Terraria.ID;

namespace ModLiquidLib.Hooks
{
	internal class MapHelperHooks
	{
		internal static void SaveTLMap(ILContext il)
		{
			(int textVar, int cloudSaveVar) = FindUniqueWriteAnchor(il);
			ILCursor cursor = new(il);
			cursor.GotoNext(MoveType.After,
				i => i.MatchLdloc(textVar),
				i => i.MatchLdloc(cloudSaveVar),
				i => i.MatchCall("Terraria.ModLoader.IO.MapIO", "WriteModFile"));
			cursor.EmitLdloc(textVar);
			cursor.EmitLdloc(cloudSaveVar);
			cursor.EmitDelegate((string text, bool isCloudSave) =>
			{
				MapLiquidIO.WriteModFile(text, isCloudSave);
			});
		}

		private static (int TextVar, int CloudSaveVar) FindUniqueWriteAnchor(ILContext il)
		{
			ILCursor probe = new(il);
			int count = 0;
			int textVar = -1;
			int cloudSaveVar = -1;
			while (true)
			{
				int candidateText = -1;
				int candidateCloud = -1;
				if (!probe.TryGotoNext(MoveType.After,
					i => i.MatchLdloc(out candidateText),
					i => i.MatchLdloc(out candidateCloud),
					i => i.MatchCall("Terraria.ModLoader.IO.MapIO", "WriteModFile")))
					break;

				count++;
				textVar = candidateText;
				cloudSaveVar = candidateCloud;
			}

			if (count != 1)
				throw new InvalidOperationException($"Expected exactly one MapIO.WriteModFile anchor, found {count}.");
			return (textVar, cloudSaveVar);
		}

		internal static void AddLiquidMapEntrys(ILContext il)
		{
			(int mapTileLocal, int mapIndexLocal) = FindUniqueLiquidLookupAnchor(il);
			int mapTypeLocal = FindUniqueModMapOptionAnchor(il);
			EnsureLiquidLookupAnchorsOrdered(il, mapTileLocal, mapIndexLocal, mapTypeLocal);

			ILCursor cursor = new(il);
			cursor.GotoNext(MoveType.After,
				i => i.MatchLdsfld("Terraria.Map.MapHelper", "liquidPosition"),
				i => i.MatchLdloc(mapIndexLocal),
				i => i.MatchAdd(),
				i => i.MatchStloc(out _));
			cursor.EmitLdloca(mapTileLocal);
			cursor.EmitLdloc(mapIndexLocal);
			cursor.EmitDelegate((ref int num5, int num7) =>
			{
				num5 = MapLiquidLoader.liquidLookup[num7];
			});
			cursor.GotoNext(MoveType.After,
				i => i.MatchLdloca(out _),
				i => i.MatchLdarg(0),
				i => i.MatchLdarg(1),
				i => i.MatchCall("Terraria.ModLoader.MapLoader", "ModMapOption"));
			cursor.EmitLdloca(mapTypeLocal);
			cursor.EmitLdarg(0);
			cursor.EmitLdarg(1);
			cursor.EmitDelegate((ref ushort mapType, int i, int j) =>
			{
				MapLiquidLoader.ModMapOption(ref mapType, i, j);
			});
		}

		internal static void IncrimentLiquidMapEntries(ILContext il)
		{
			int mapChoiceIndexLocal = FindUniqueLiquidPositionAnchor(il);
			int mapChoiceLocal = FindUniqueColorCopyAnchor(il);
			FindUniqueVanillaLiquidCountAnchor(il, mapChoiceLocal);
			EnsureLiquidCountAnchorsOrdered(il, mapChoiceIndexLocal, mapChoiceLocal);

			ILCursor cursor = new(il);
			cursor.GotoNext(MoveType.After,
				i => i.MatchLdloc(mapChoiceIndexLocal),
				i => i.MatchStsfld("Terraria.Map.MapHelper", "liquidPosition"));
			cursor.EmitDelegate(() =>
			{
				MapLiquidLoader.liquidLookup = new ushort[LiquidID.Count];
			});
			cursor.GotoNext(MoveType.After,
				i => i.MatchLdloc(mapChoiceLocal),
				i => i.MatchLdelemAny<Color>(),
				i => i.MatchStelemAny<Color>());
			cursor.EmitLdloc(mapChoiceLocal);
			cursor.EmitLdloc(mapChoiceIndexLocal);
			cursor.EmitDelegate((int num18, ushort num13) =>
			{
				MapLiquidLoader.liquidLookup[num18] = num13;
			});
			cursor.GotoNext(MoveType.After,
				i => i.MatchLdloc(mapChoiceLocal),
				i => i.MatchLdcI4(4));
			cursor.EmitDelegate((int four) =>
			{
				return LiquidID.Count;
			});
		}

		private static (int MapTileLocal, int MapIndexLocal) FindUniqueLiquidLookupAnchor(ILContext il)
		{
			ILCursor probe = new(il);
			int count = 0;
			int mapTileLocal = -1;
			int mapIndexLocal = -1;
			while (true)
			{
				int candidateTile = -1;
				int candidateIndex = -1;
				if (!probe.TryGotoNext(MoveType.After,
					i => i.MatchLdsfld("Terraria.Map.MapHelper", "liquidPosition"),
					i => i.MatchLdloc(out candidateIndex),
					i => i.MatchAdd(),
					i => i.MatchStloc(out candidateTile)))
					break;
				count++;
				mapTileLocal = candidateTile;
				mapIndexLocal = candidateIndex;
			}
			RequireUnique("liquid lookup", count);
			return (mapTileLocal, mapIndexLocal);
		}

		private static int FindUniqueModMapOptionAnchor(ILContext il)
		{
			ILCursor probe = new(il);
			int count = 0;
			int mapTypeLocal = -1;
			while (true)
			{
				int candidate = -1;
				if (!probe.TryGotoNext(MoveType.After,
					i => i.MatchLdloca(out candidate),
					i => i.MatchLdarg(0),
					i => i.MatchLdarg(1),
					i => i.MatchCall("Terraria.ModLoader.MapLoader", "ModMapOption")))
					break;
				count++;
				mapTypeLocal = candidate;
			}
			RequireUnique("MapLoader.ModMapOption", count);
			return mapTypeLocal;
		}

		private static int FindUniqueLiquidPositionAnchor(ILContext il)
		{
			ILCursor probe = new(il);
			int count = 0;
			int local = -1;
			while (true)
			{
				int candidate = -1;
				if (!probe.TryGotoNext(MoveType.After,
					i => i.MatchLdloc(out candidate),
					i => i.MatchStsfld("Terraria.Map.MapHelper", "liquidPosition")))
					break;
				count++;
				local = candidate;
			}
			RequireUnique("liquidPosition", count);
			return local;
		}

		private static int FindUniqueColorCopyAnchor(ILContext il)
		{
			ILCursor probe = new(il);
			int count = 0;
			int local = -1;
			while (true)
			{
				int candidate = -1;
				if (!probe.TryGotoNext(MoveType.After,
					i => i.MatchLdloc(out candidate),
					i => i.MatchLdelemAny<Color>(),
					i => i.MatchStelemAny<Color>()))
					break;
				count++;
				local = candidate;
			}
			RequireUnique("liquid color copy", count);
			return local;
		}

		private static void FindUniqueVanillaLiquidCountAnchor(ILContext il, int mapChoiceLocal)
		{
			ILCursor probe = new(il);
			int count = 0;
			while (probe.TryGotoNext(MoveType.After,
				i => i.MatchLdloc(mapChoiceLocal),
				i => i.MatchLdcI4(4)))
				count++;
			RequireUnique("vanilla liquid count", count);
		}

		private static void RequireUnique(string anchor, int count)
		{
			if (count != 1)
				throw new InvalidOperationException($"Expected exactly one {anchor} anchor, found {count}.");
		}

		private static void EnsureLiquidLookupAnchorsOrdered(ILContext il, int mapTileLocal, int mapIndexLocal, int mapTypeLocal)
		{
			ILCursor probe = new(il);
			bool ordered = probe.TryGotoNext(MoveType.After,
				i => i.MatchLdsfld("Terraria.Map.MapHelper", "liquidPosition"),
				i => i.MatchLdloc(mapIndexLocal),
				i => i.MatchAdd(),
				i => i.MatchStloc(out int foundTile) && foundTile == mapTileLocal) &&
				probe.TryGotoNext(MoveType.After,
					i => i.MatchLdloca(out int foundType) && foundType == mapTypeLocal,
					i => i.MatchLdarg(0),
					i => i.MatchLdarg(1),
					i => i.MatchCall("Terraria.ModLoader.MapLoader", "ModMapOption"));
			if (!ordered)
				throw new InvalidOperationException("The liquid lookup anchors are not in the required order.");
		}

		private static void EnsureLiquidCountAnchorsOrdered(ILContext il, int mapChoiceIndexLocal, int mapChoiceLocal)
		{
			ILCursor probe = new(il);
			bool ordered = probe.TryGotoNext(MoveType.After,
				i => i.MatchLdloc(mapChoiceIndexLocal),
				i => i.MatchStsfld("Terraria.Map.MapHelper", "liquidPosition")) &&
				probe.TryGotoNext(MoveType.After,
					i => i.MatchLdloc(mapChoiceLocal),
					i => i.MatchLdelemAny<Color>(),
					i => i.MatchStelemAny<Color>()) &&
				probe.TryGotoNext(MoveType.After,
					i => i.MatchLdloc(mapChoiceLocal),
					i => i.MatchLdcI4(4));
			if (!ordered)
				throw new InvalidOperationException("The liquid count anchors are not in the required order.");
		}
	}
}
