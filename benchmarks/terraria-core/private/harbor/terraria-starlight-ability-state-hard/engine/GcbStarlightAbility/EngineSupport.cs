global using Terraria;

using System;
using System.Collections.Generic;
using Terraria.ModLoader;

namespace NetEasy
{
    public abstract class Module
    {
        public int Sender { get; set; } = -1;
        public int SendCount { get; private set; }
        protected abstract void Receive();
        public void Send(int toWho = -1, int ignoreWho = -1, bool runLocally = true) => SendCount++;
    }
}

namespace StarlightRiver.Content.Abilities
{
    public abstract class Ability
    {
        public AbilityHandler? User { get; internal set; }
    }

    public sealed class AbilityHandler : ModPlayer
    {
        public Dictionary<Type, Ability> unlockedAbilities = new();
        public ShardSet Shards { get; private set; } = new();
        public Ability? ActiveAbility { get; set; }

        public bool Unlocked<T>() where T : Ability => unlockedAbilities.ContainsKey(typeof(T));

        public void Unlock<T>() where T : Ability, new()
        {
            if (!unlockedAbilities.ContainsKey(typeof(T)))
            {
                var ability = new T { User = this };
                unlockedAbilities.Add(typeof(T), ability);
            }
        }

        public bool TryActivate(Ability ability)
        {
            if (!unlockedAbilities.TryGetValue(ability.GetType(), out Ability? registered)
                || !ReferenceEquals(registered, ability)) return false;
            ActiveAbility = ability;
            return true;
        }

        public void ReplaceReplicatedProgress(IEnumerable<int> shards, IEnumerable<Type> types)
        {
            Shards.Clear();
            foreach (int id in shards) Shards.Add(id);
            unlockedAbilities.Clear();
            foreach (Type type in types)
            {
                var ability = (Ability)Activator.CreateInstance(type)!;
                ability.User = this;
                unlockedAbilities.Add(type, ability);
            }
        }

        internal void ResetState()
        {
            Shards.Clear();
            unlockedAbilities.Clear();
            ActiveAbility = null;
        }
    }

    public static class AbilityPlayerExtensions
    {
        private static readonly Dictionary<Player, AbilityHandler> Handlers = new();

        public static AbilityHandler GetHandler(this Player player)
        {
            if (!Handlers.TryGetValue(player, out AbilityHandler? handler))
            {
                handler = new AbilityHandler();
                Handlers.Add(player, handler);
            }
            return handler;
        }
    }
}

namespace StarlightRiver.Content.Abilities.Faewhip
{
    public sealed class Whip : StarlightRiver.Content.Abilities.Ability { }
}

namespace StarlightRiver.Content.Abilities.ForbiddenWinds
{
    public sealed class Dash : StarlightRiver.Content.Abilities.Ability { }
}

namespace StarlightRiver.Content.Abilities.Hint
{
    public sealed class HintAbility : StarlightRiver.Content.Abilities.Ability { }
}
