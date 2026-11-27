using System;
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using ModLiquidLib.ModLoader;
using MonoMod.Cil;
using Terraria.Localization;

namespace ModLiquidLib.Hooks
{
	internal class MapLoaderHooks
	{
		internal static void AddLiquidToFinishSetup(ILContext il)
		{
			(int colorLocal, int nameLocal) = FindUniqueFinishSetupAnchor(il);
			ILCursor cursor = new ILCursor(il);
			cursor.GotoNext(MoveType.After,
				i => i.MatchStloc(out _),
				i => i.MatchNewobj<List<LocalizedText>>(".ctor"),
				i => i.MatchStloc(out _));
			cursor.EmitLdloca(colorLocal);
			cursor.EmitLdloca(nameLocal);
			cursor.EmitDelegate((ref IList<Color> colors, ref IList<LocalizedText> names) =>
			{
				MapLiquidLoader.PublishEntries(ref colors, ref names);
			});
		}

		private static (int ColorLocal, int NameLocal) FindUniqueFinishSetupAnchor(ILContext il)
		{
			ILCursor probe = new ILCursor(il);
			int count = 0;
			int colorLocal = -1;
			int nameLocal = -1;
			while (true)
			{
				int candidateColor = -1;
				int candidateName = -1;
				if (!probe.TryGotoNext(MoveType.After,
					i => i.MatchStloc(out candidateColor),
					i => i.MatchNewobj<List<LocalizedText>>(".ctor"),
					i => i.MatchStloc(out candidateName)))
					break;
				count++;
				colorLocal = candidateColor;
				nameLocal = candidateName;
			}
			if (count != 1)
				throw new InvalidOperationException($"Expected exactly one map FinishSetup table anchor, found {count}.");
			return (colorLocal, nameLocal);
		}
	}
}
