using Microsoft.Xna.Framework;
using ModLiquidLib.ModLoader;
using MonoMod.Cil;
using System;
using System.Collections.Generic;
using Terraria.Localization;
using Terraria.Map;
using Terraria.ModLoader;

namespace ModLiquidLib.Hooks
{
	internal class MapLoaderHooks
	{
		internal static void AddLiquidToFinishSetup(ILContext il)
		{
			ILCursor c = new(il);
			int colorArr_numVar = -1;
			int nameArr_numVar = -1;
			c.GotoNext(MoveType.After, i => i.MatchStloc(out colorArr_numVar), i => i.MatchNewobj<List<LocalizedText>>(".ctor"), i => i.MatchStloc(out nameArr_numVar));
			c.EmitLdloca(colorArr_numVar);
			c.EmitLdloca(nameArr_numVar);
			c.EmitDelegate((ref IList<Color> colors, ref IList<LocalizedText> names) =>
			{
				MapLiquidLoader.PublishEntries(ref colors, ref names);
			});
		}
	}
}
