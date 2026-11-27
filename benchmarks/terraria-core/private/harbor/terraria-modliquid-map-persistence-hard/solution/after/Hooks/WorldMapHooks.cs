using System;
using ModLiquidLib.IO;
using MonoMod.Cil;

namespace ModLiquidLib.Hooks
{
	internal class WorldMapHooks
	{
		internal static void InitaliseTLMap(ILContext il)
		{
			(int textVar, int cloudSaveVar) = FindUniqueReadAnchor(il);
			ILCursor cursor = new(il);
			cursor.GotoNext(MoveType.After,
				i => i.MatchLdloc(textVar),
				i => i.MatchLdloc(cloudSaveVar),
				i => i.MatchCall("Terraria.ModLoader.IO.MapIO", "ReadModFile"));
			cursor.EmitLdloc(textVar);
			cursor.EmitLdloc(cloudSaveVar);
			cursor.EmitDelegate((string text, bool isCloudSave) =>
			{
				MapLiquidIO.ReadModFile(text, isCloudSave);
			});
		}

		private static (int TextVar, int CloudSaveVar) FindUniqueReadAnchor(ILContext il)
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
					i => i.MatchCall("Terraria.ModLoader.IO.MapIO", "ReadModFile")))
					break;

				count++;
				textVar = candidateText;
				cloudSaveVar = candidateCloud;
			}

			if (count != 1)
				throw new InvalidOperationException($"Expected exactly one MapIO.ReadModFile anchor, found {count}.");
			return (textVar, cloudSaveVar);
		}
	}
}
