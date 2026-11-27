using NetEasy;
using StarlightRiver.Content.Abilities;
using System;

namespace StarlightRiver.Content.Packets
{
	[Serializable]
	public class StartAbility : Module
	{
		private readonly int fromWho;
		private readonly string abTypeName;

		public StartAbility(int fromWho, Ability ability)
		{
			this.fromWho = fromWho;
			abTypeName = ability?.GetType().FullName;
		}

		protected override void Receive()
		{
			if (fromWho < 0 || fromWho >= Main.player.Length || Main.player[fromWho] == null || string.IsNullOrWhiteSpace(abTypeName))
				return;
			if (Main.netMode == Terraria.ID.NetmodeID.Server && Sender != fromWho)
				return;

			Type abType = typeof(Ability).Assembly.GetType(abTypeName, throwOnError: false, ignoreCase: false);
			if (abType == null || abType.IsAbstract || !typeof(Ability).IsAssignableFrom(abType))
				return;

			AbilityHandler handler = Main.player[fromWho].GetHandler();
			if (!handler.unlockedAbilities.TryGetValue(abType, out Ability ability) || ability == null || !handler.TryActivate(ability))
				return;

			if (Main.netMode == Terraria.ID.NetmodeID.Server)
				Send(-1, Sender, false);
		}
	}
}
