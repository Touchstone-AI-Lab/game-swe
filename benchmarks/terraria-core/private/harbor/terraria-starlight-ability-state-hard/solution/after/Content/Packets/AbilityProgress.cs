using NetEasy;
using StarlightRiver.Content.Abilities;
using StarlightRiver.Content.Abilities.Faewhip;
using StarlightRiver.Content.Abilities.ForbiddenWinds;
using StarlightRiver.Content.Abilities.Hint;
using System;
using System.Collections.Generic;
using System.Linq;

namespace StarlightRiver.Content.Packets
{
	[Serializable]
	public class AbilityProgress : Module
	{
		private const byte DashMask = 0b10000000;
		private const byte WhipMask = 0b01000000;
		private const byte HintMask = 0b00100000;
		private const byte KnownMask = DashMask | WhipMask | HintMask;

		private readonly int fromWho;

		private readonly int[] shards;
		private readonly byte unlocks;

		public AbilityProgress(int fromWho, AbilityHandler handler)
		{
			this.fromWho = fromWho;

			shards = handler.Shards.ToList().Distinct().OrderBy(id => id).ToArray();

			if (handler.Unlocked<Dash>())
				unlocks |= DashMask;

			if (handler.Unlocked<Whip>())
				unlocks |= WhipMask;

			if (handler.Unlocked<HintAbility>())
				unlocks |= HintMask;
		}

		protected override void Receive()
		{
			if (fromWho < 0 || fromWho >= Main.player.Length || Main.player[fromWho] == null)
				return;
			if (Main.netMode == Terraria.ID.NetmodeID.Server && Sender != fromWho)
				return;
			if (shards == null || shards.Length > 4096 || shards.Any(id => id < 0) || shards.Distinct().Count() != shards.Length || (unlocks & ~KnownMask) != 0)
				return;

			var types = new List<Type>();
			if ((unlocks & DashMask) != 0)
				types.Add(typeof(Dash));
			if ((unlocks & WhipMask) != 0)
				types.Add(typeof(Whip));
			if ((unlocks & HintMask) != 0)
				types.Add(typeof(HintAbility));

			try
			{
				Main.player[fromWho].GetHandler().ReplaceReplicatedProgress(shards, types);
			}
			catch
			{
				return;
			}

			if (Main.netMode == Terraria.ID.NetmodeID.Server)
				Send(-1, Sender, false);
		}
	}
}
