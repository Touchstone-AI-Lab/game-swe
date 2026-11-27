using StarlightRiver.Content.GUI;
using StarlightRiver.Content.Packets;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Terraria.DataStructures;
using Terraria.GameInput;
using Terraria.ID;
using Terraria.ModLoader.IO;

namespace StarlightRiver.Content.Abilities
{
	public class AbilityHandler : ModPlayer, IOrderedLoadable
	{
		private const int SHARDS_PER_VESSEL = 3;

		private InfusionItem[] infusions = new InfusionItem[Infusion.InfusionSlots];
		public Dictionary<Type, Ability> unlockedAbilities = new();
		private float staminaMaxBonus;
		private float stamina;
		private int staminaRegenCD;

		private Ability activeAbility;
		private Ability nextAbility;
		private bool transitionPending;
		private bool deactivationNotified;
		private bool transitionInProgress;
		private Ability deferredAbility;
		private bool deferredTransitionPending;
		private bool suppressTransitionRequests;

		public float Priority => 1;

		/// <summary>
		/// The players effective maximum stamina
		/// </summary>
		public float StaminaMax => StaminaMaxDefault + StaminaMaxBonus;
		public float StaminaMaxDefault => Shards.Count / SHARDS_PER_VESSEL + unlockedAbilities.Count;

		/// <summary>
		/// The rate at which the player regenerates stamina. One point is equal to 0.05 stamina per second.
		/// </summary>
		public int StaminaRegenRate { get; set; }

		/// <summary>
		/// The maximum amount of infusions the player can equip
		/// </summary>
		public int InfusionLimit { get; set; } = 0;

		/// <summary>
		/// Global stamina cost multiplier. Used to increase or decrease the cost of ALL abilities by a multiplicative value
		/// </summary>
		public float StaminaCostMultiplier { get; set; }

		/// <summary>
		/// Global stamina cost flat modifier. Used to increase or decrease the cost of ALL abilities by a flat value
		/// </summary>
		public float StaminaCostBonus { get; set; }

		/// <summary>
		/// The amount of stamina vessel shards the player has
		/// </summary>
		public int ShardCount => Shards.Count;

		/// <summary>
		/// If the player has unlocked any abilties or not. Used for UI visibility
		/// </summary>
		public bool AnyUnlocked => unlockedAbilities.Count > 0;

		/// <summary>
		/// The stamina vessel shards the player has collected, as each is unique
		/// </summary>
		public ShardSet Shards { get; private set; } = new ShardSet();

		/// <summary>
		/// The player's currently active ability
		/// </summary>
		public Ability ActiveAbility
		{
			get => activeAbility;
			set => QueueTransition(value, value != null);
		}

		/// <summary>
		/// A flat modifier to the player's max stamina. Can be used to increase or decrease it, but not lower than zero.
		/// </summary>
		public float StaminaMaxBonus
		{
			get => staminaMaxBonus;
			set =>
				// Can't have less than 0 max sp.
				staminaMaxBonus = float.IsFinite(value) ? Math.Max(value, -StaminaMaxDefault) : 0;
		}

		/// <summary>
		/// The player's base stamina, should only be effected by ability and vessel unlocks.
		/// </summary>
		public float Stamina
		{
			get => stamina;
			// Can't have less than 0 or more than max stamina.
			set => stamina = float.IsFinite(value) ? MathHelper.Clamp(value, 0, StaminaMax) : 0;
		}

		//for some reason without specifically setting these values to zero with cloneNewInstances => false and contructor,
		////on a server if someone unlocks or modifies these it will impact newly created characters from then on for that instance
		public override bool CloneNewInstances => false;

		public AbilityHandler()
		{
			infusions = new InfusionItem[Infusion.InfusionSlots];
			unlockedAbilities = new Dictionary<Type, Ability>();
		}

		public override ModPlayer Clone(Player newEntity)
		{
			var clone = (AbilityHandler)base.Clone(newEntity);
			CopyStateTo(clone);
			return clone;
		}

		public override void CopyClientState(ModPlayer clientClone)
		{
			if (clientClone is AbilityHandler clone)
				CopyStateTo(clone);
		}

		private void CopyStateTo(AbilityHandler clone)
		{
			clone.Shards = new ShardSet();
			foreach (int id in Shards.ToList())
				clone.Shards.Add(id);

			clone.unlockedAbilities = new Dictionary<Type, Ability>();
			foreach (var pair in unlockedAbilities)
			{
				Ability copy = pair.Value.CopyFor(clone);
				clone.unlockedAbilities.Add(pair.Key, copy);
			}

			clone.infusions = new InfusionItem[Infusion.InfusionSlots];
			for (int i = 0; i < infusions.Length; i++)
			{
				if (infusions[i]?.Item?.Clone() is not Item item || item.ModItem is not InfusionItem infusion)
					continue;
				item.playerIndexTheItemIsReservedFor = clone.Player.whoAmI;
				if (infusion.ability != null)
					infusion.ability.User = clone;
				clone.infusions[i] = infusion;
			}

			clone.staminaMaxBonus = staminaMaxBonus;
			clone.staminaRegenCD = staminaRegenCD;
			clone.StaminaRegenRate = StaminaRegenRate;
			clone.InfusionLimit = InfusionLimit;
			clone.StaminaCostMultiplier = StaminaCostMultiplier;
			clone.StaminaCostBonus = StaminaCostBonus;
			clone.stamina = stamina;
			clone.activeAbility = MapAbilityToClone(activeAbility, clone);
			clone.nextAbility = MapAbilityToClone(nextAbility, clone);
			clone.transitionPending = transitionPending;
			clone.deactivationNotified = deactivationNotified;
			clone.transitionInProgress = false;
			clone.deferredAbility = null;
			clone.deferredTransitionPending = false;
			clone.suppressTransitionRequests = false;
		}

		private Ability MapAbilityToClone(Ability source, AbilityHandler clone)
		{
			if (source == null)
				return null;
			if (unlockedAbilities.TryGetValue(source.GetType(), out Ability registered) && ReferenceEquals(source, registered))
				return clone.unlockedAbilities[source.GetType()];
			for (int i = 0; i < infusions.Length; i++)
				if (infusions[i] != null && ReferenceEquals(infusions[i].ability, source))
					return clone.infusions[i]?.ability;
			return null;
		}

		internal void ReplaceReplicatedProgress(IEnumerable<int> shardIds, IEnumerable<Type> builtInUnlocks)
		{
			var replacementShards = new ShardSet();
			foreach (int id in shardIds)
				replacementShards.Add(id);

			var replacementAbilities = unlockedAbilities
				.Where(pair => !IsBuiltInAbility(pair.Key))
				.ToDictionary(pair => pair.Key, pair => pair.Value);
			foreach (Type type in builtInUnlocks.Distinct())
			{
				if (!IsBuiltInAbility(type) || Activator.CreateInstance(type) is not Ability ability)
					throw new InvalidDataException("The replicated ability type is invalid.");
				ability.User = this;
				replacementAbilities.Add(type, ability);
			}

			Shards = replacementShards;
			unlockedAbilities = replacementAbilities;
			Stamina = Math.Min(Stamina, StaminaMax);
		}

		internal static bool IsBuiltInAbility(Type type)
		{
			return type == typeof(global::StarlightRiver.Content.Abilities.Hint.HintAbility)
				|| type == typeof(global::StarlightRiver.Content.Abilities.ForbiddenWinds.Dash)
				|| type == typeof(global::StarlightRiver.Content.Abilities.Faewhip.Whip);
		}

		public override void Load()
		{
			StarlightPlayer.PostDrawEvent += PostDrawAbility;
		}

		public override void Unload() { }

		/// <summary>
		/// Internal method for handling an ability unlock, used by the publically exposed generic methods
		/// </summary>
		/// <param name="t"></param>
		/// <param name="ability"></param>
		private void Unlock(Type t, Ability ability)
		{
			if (t == null || ability == null || t != ability.GetType() || !typeof(Ability).IsAssignableFrom(t) || t.IsAbstract)
				throw new InvalidDataException("The ability type is invalid.");
			unlockedAbilities[t] = ability;
			ability.User = this;
		}

		/// <summary>
		/// Internal method for checking and retrieving an infusion if the player has it on.
		/// </summary>
		/// <param name="t"></param>
		/// <param name="infusion"></param>
		/// <returns></returns>
		private bool TryMatchInfusion(Type t, out InfusionItem infusion)
		{
			infusion = infusions.FirstOrDefault(i => i?.AbilityType == t);
			return infusion != null;
		}

		/// <summary>
		/// Re-locks an ability for the player. Typically only used for debugging purposes.
		/// </summary>
		/// <typeparam name="T">The type of the ability to lock</typeparam>
		public void Lock<T>() where T : Ability
		{
			unlockedAbilities.Remove(typeof(T));
		}

		/// <summary>
		/// Unlocks the ability type for the Player.
		/// </summary>
		public void Unlock<T>() where T : Ability, new()
		{
			// Ensure we don't unlock the same thing twice
			if (!unlockedAbilities.ContainsKey(typeof(T)))
				Unlock(typeof(T), new T());
		}

		/// <summary>
		/// Tries to get an unlocked ability from the Player.
		/// </summary>
		/// <typeparam name="T">The type of ability.</typeparam>
		/// <param name="value">The ability.</param>
		/// <returns>Success or not.</returns>
		public bool GetAbility<T>(out T value) where T : Ability
		{
			bool r = unlockedAbilities.TryGetValue(typeof(T), out Ability a);
			value = a as T;
			return r;
		}

		public bool GetAbility(Type type, out Ability ability)
		{
			return unlockedAbilities.TryGetValue(type, out ability);
		}

		/// <summary>
		/// Checks if the given ability type is unlocked.
		/// </summary>
		/// <typeparam name="T"></typeparam>
		/// <returns></returns>
		public bool Unlocked<T>() where T : Ability
		{
			return GetAbility<T>(out _);
		}

		/// <summary>
		/// Checks if the given ability type is unlocked.
		/// </summary>
		public bool Unlocked(Type type)
		{
			return unlockedAbilities.ContainsKey(type);
		}

		/// <summary>
		/// Tries to add the matching infusion type.
		/// </summary>
		/// <param name="Item">The Item to add.</param>
		/// <returns>If the add was successful.</returns>
		public bool SetInfusion(InfusionItem Item, int slot)
		{
			if (slot < 0 || slot >= infusions.Length)
				return false;

			if (Item == null)
			{
				infusions[slot] = null;
				return true;
			}

			if (slot >= Math.Clamp(InfusionLimit, 0, infusions.Length) || !CanSetInfusion(Item, slot))
				return false;

			Terraria.Item newItem;
			try
			{
				newItem = Item.Item?.Clone();
			}
			catch
			{
				return false;
			}
			if (newItem?.ModItem is not InfusionItem cloned || !cloned.Equippable || cloned.GetType() != Item.GetType())
				return false;

			newItem.playerIndexTheItemIsReservedFor = Player.whoAmI;
			if (cloned.ability != null)
				cloned.ability.User = this;
			infusions[slot] = cloned;

			return true;
		}

		/// <summary>
		/// Checks if the infusion can be added.
		/// </summary>
		/// <param name="Item">The Item.</param>
		/// <returns>Whether the Item can be added.</returns>
		public bool CanSetInfusion(InfusionItem Item)
		{
			return CanSetInfusion(Item, -1);
		}

		private bool CanSetInfusion(InfusionItem Item, int replacedSlot)
		{
			if (Item == null)
				return true;

			if (!Item.Equippable)
				return false;

			for (int i = 0; i < infusions.Length; i++)
			{
				if (i == replacedSlot)
					continue;
				InfusionItem infusion = infusions[i];
				if (infusion is null)
					continue;

				if (Item.AbilityType != null && Item.AbilityType == infusion.AbilityType ||
					Item.GetType() == infusion.GetType())
				{
					return false;
				}
			}

			int occupied = infusions.Count(n => n != null) - (replacedSlot >= 0 && infusions[replacedSlot] != null ? 1 : 0);
			return occupied < Math.Clamp(InfusionLimit, 0, infusions.Length);
		}

		/// <summary>
		/// Retrieves the infusion item for the given infusion slot
		/// </summary>
		/// <param name="slot">The index of the slot to retrieve</param>
		/// <returns>The InfusionItem ModItem of the infusion in the given slot, or null if one is not there.</returns>
		public InfusionItem GetInfusion(int slot)
		{
			return slot < 0 || slot >= infusions.Length ? null : infusions[slot];
		}

		/// <summary>
		/// Sets the player's stamina regen delay, in ticks. Anything larger than 60 will prevent the player from regenerating stamina untill the time minus 60 expires.
		/// </summary>
		/// <param name="cooldownTicks">How long the player's stamina delay is set for</param>
		public void SetStaminaRegenCD(int cooldownTicks)
		{
			staminaRegenCD = Math.Max(staminaRegenCD, cooldownTicks);
		}

		public override void SaveData(TagCompound tag)
		{
			tag[nameof(Shards)] = Shards.ToList().Distinct().OrderBy(id => id).ToList();
			tag[nameof(unlockedAbilities)] = unlockedAbilities
				.Where(pair => pair.Key != null && pair.Value != null && pair.Key == pair.Value.GetType())
				.Select(pair => pair.Key.FullName)
				.Where(name => name != null)
				.Distinct(StringComparer.Ordinal)
				.OrderBy(name => name, StringComparer.Ordinal)
				.ToList();

			var savedInfusions = new List<Item>(infusions.Length);
			foreach (InfusionItem infusion in infusions)
				savedInfusions.Add(infusion?.Item?.Clone() ?? new Item());
			tag[nameof(infusions)] = savedInfusions;
			tag[nameof(InfusionLimit)] = Math.Clamp(InfusionLimit, 0, infusions.Length);
		}

		public override void LoadData(TagCompound tag)
		{
			try
			{
				IList<int> shardsTemp = tag.GetList<int>(nameof(Shards));
				if (shardsTemp.Count > 4096 || shardsTemp.Any(id => id < 0))
					throw new InvalidDataException("The shard list is invalid.");
				var loadedShards = new ShardSet();
				foreach (int id in shardsTemp.Distinct().OrderBy(id => id))
					loadedShards.Add(id);

				IList<string> abilitiesTemp = tag.GetList<string>(nameof(unlockedAbilities));
				if (abilitiesTemp.Count > 256)
					throw new InvalidDataException("The ability list is invalid.");
				var loadedAbilities = new Dictionary<Type, Ability>();
				foreach (string abilityName in abilitiesTemp.Where(name => !string.IsNullOrWhiteSpace(name)).Distinct(StringComparer.Ordinal))
				{
					Type t = typeof(Ability).Assembly.GetType(abilityName, throwOnError: false, ignoreCase: false);
					if (t == null)
						continue;
					if (t.IsAbstract || !typeof(Ability).IsAssignableFrom(t))
						throw new InvalidDataException("A saved ability type is invalid.");
					if (Activator.CreateInstance(t) is not Ability ability)
						throw new InvalidDataException("A saved ability could not be created.");
					ability.User = this;
					loadedAbilities.Add(t, ability);
				}

				int loadedLimit = tag.ContainsKey(nameof(InfusionLimit)) ? tag.GetInt(nameof(InfusionLimit)) : 1;
				if (loadedLimit < 0 || loadedLimit > Infusion.InfusionSlots)
					throw new InvalidDataException("The infusion limit is invalid.");

				IList<Item> infusionsTemp = tag.GetList<Item>(nameof(infusions));
				if (infusionsTemp.Count > Infusion.InfusionSlots)
					throw new InvalidDataException("The infusion list is invalid.");
				var loadedInfusions = new InfusionItem[Infusion.InfusionSlots];
				for (int i = 0; i < infusionsTemp.Count; i++)
				{
					Item savedItem = infusionsTemp[i];
					if (savedItem == null || savedItem.IsAir)
						continue;
					if (i >= loadedLimit)
						throw new InvalidDataException("An infusion occupies a locked slot.");
					Item clonedItem = savedItem.Clone();
					if (clonedItem.ModItem is not InfusionItem infusion || !infusion.Equippable)
						throw new InvalidDataException("A saved infusion is invalid.");
					if (loadedInfusions.Any(other => other != null && (other.GetType() == infusion.GetType() || infusion.AbilityType != null && infusion.AbilityType == other.AbilityType)))
						throw new InvalidDataException("A saved infusion is duplicated.");
					clonedItem.playerIndexTheItemIsReservedFor = Player.whoAmI;
					if (infusion.ability != null)
						infusion.ability.User = this;
					loadedInfusions[i] = infusion;
				}

				Shards = loadedShards;
				unlockedAbilities = loadedAbilities;
				infusions = loadedInfusions;
				InfusionLimit = loadedLimit;
				Stamina = Math.Min(Stamina, StaminaMax);
			}
			catch (Exception e)
			{
				StarlightRiver.Instance.Logger.Debug("handled error loading Player: " + e);
			}
		}

		public override void ResetEffects()
		{
			//Resets the Player's stamina to prevent issues with gaining infinite stamina or stamina regeneration.
			staminaMaxBonus = 0;
			StaminaRegenRate = 5;
			StaminaCostMultiplier = 1;
			StaminaCostBonus = 0;

			if (ActiveAbility != null)
			{
				// The Player cant use Items while casting an ability.               
				Player.noItems = true;
				Player.noBuilding = true;
			}
		}

		public override void UpdateDead()
		{
			suppressTransitionRequests = true;
			transitionInProgress = true;
			deferredAbility = null;
			deferredTransitionPending = false;
			Ability retiring = activeAbility;
			bool notify = retiring != null && !deactivationNotified;
			nextAbility = null;
			transitionPending = false;
			try
			{
				if (retiring != null)
				{
					if (notify)
						InvokeHook(retiring, nameof(Ability.OnDeactivate), retiring.OnDeactivate);
					activeAbility = null;
					InvokeHook(retiring, nameof(Ability.OnExit), retiring.OnExit);
					InvokeHook(retiring, nameof(Ability.Reset), retiring.Reset);
				}
			}
			finally
			{
				activeAbility = null;
				nextAbility = null;
				transitionPending = false;
				deactivationNotified = false;
				deferredAbility = null;
				deferredTransitionPending = false;
				transitionInProgress = false;
				suppressTransitionRequests = false;
			}
		}

		public override void OnRespawn()
		{
			Stamina = StaminaMax;
		}

		public override void ProcessTriggers(TriggersSet triggersSet)
		{
			// Check infusions FIRST so they take precedence
			foreach (InfusionItem infusion in infusions)
			{
				if (infusion == null)
					continue;

				// If any of the infusions match, they take precedent. This prevents "falling through" to the default ability
				if (infusion.ability != null && infusion.ability.HotKeyMatch(triggersSet, StarlightRiver.Instance.AbilityKeys))
				{
					if (infusion.ability.Available)
						infusion.ability.Activate(this);

					return;
				}
			}

			// Then check the default abilities
			foreach (Ability ability in unlockedAbilities.Values)
			{
				if (ability.Available && ability.HotKeyMatch(triggersSet, StarlightRiver.Instance.AbilityKeys))
				{
					ability.Activate(this);
					break;
				}
			}
		}

		public override void PreUpdate()
		{
			ReconcileAbilityOwnership();
			ApplyPendingTransition();

			UpdateAbilities();

			if (ActiveAbility != null)
			{
				// Jank
				Player.velocity.Y += 0.01f;

				// Disable wings and rockets temporarily
				Player.canRocket = false;
				Player.rocketBoots = -1;
				Player.wings = -1;

				SetStaminaRegenCD(60);
			}
			else
			{
				UpdateStaminaRegen();
			}

			// To ensure fusions always have their owner set to a valid Player.
			for (int i = 0; i < infusions.Length; i++)
			{
				if (infusions[i] != null)
					infusions[i].Item.playerIndexTheItemIsReservedFor = Player.whoAmI;
			}
		}

		/// <summary>
		/// Handles updating the player's stamina values based on their regeneration stat
		/// </summary>
		private void UpdateStaminaRegen()
		{
			const int cooldownSmoothing = 10;

			// Faster regen while not moving much
			if (Player.velocity.LengthSquared() > 1)
				SetStaminaRegenCD(cooldownSmoothing);

			// Decrement cooldown
			if (staminaRegenCD > 0)
				staminaRegenCD--;

			// Regen stamina at a speed inversely proportional to the smoothed cooldown
			Stamina += StaminaRegenRate * 0.05f / 60f * (1 - staminaRegenCD / 60f);
		}

		/// <summary>
		/// This handles running the updates of the active ability/infusion, and properly dealing with those that have
		/// expired already.
		/// </summary>
		private void UpdateAbilities()
		{
			List<Ability> snapshot = SnapshotAbilities();
			foreach (Ability ability in snapshot)
				if (OwnsAbility(ability))
					ability.User = this;

			foreach (Ability ability in snapshot)
			{
				if (!OwnsAbility(ability))
					continue;
				InvokeHook(ability, nameof(Ability.UpdateFixed), ability.UpdateFixed);
			}

			ReconcileAbilityOwnership();
			Ability updating = activeAbility;
			if (updating == null || !snapshot.Contains(updating) || DeactivationIsPending())
				return;

			if (!InvokeHook(updating, nameof(Ability.UpdateActive), updating.UpdateActive))
			{
				RetireActiveAbility(notify: !deactivationNotified);
				return;
			}

			ReconcileAbilityOwnership();
			if (!ReferenceEquals(activeAbility, updating) || DeactivationIsPending())
				return;

			if (Main.netMode != NetmodeID.Server)
				InvokeHook(updating, nameof(Ability.UpdateActiveEffects), updating.UpdateActiveEffects);

			if (Main.netMode != NetmodeID.Server && Player == Main.LocalPlayer &&
				ReferenceEquals(activeAbility, updating) && !DeactivationIsPending())
				NetMessage.SendData(MessageID.PlayerControls, -1, -1, null, Main.LocalPlayer.whoAmI);
		}

		private List<Ability> SnapshotAbilities()
		{
			var called = new HashSet<Ability>();
			var replacedTypes = new HashSet<Type>();
			foreach (InfusionItem infusion in infusions)
			{
				if (infusion?.ability == null)
					continue;
				called.Add(infusion.ability);
				if (infusion.AbilityType != null)
					replacedTypes.Add(infusion.AbilityType);
			}
			foreach (var pair in unlockedAbilities)
				if (pair.Value != null && !replacedTypes.Contains(pair.Key))
					called.Add(pair.Value);
			return called
				.OrderBy(ability => ability.GetType().FullName, StringComparer.Ordinal)
				.ToList();
		}

		private bool DeactivationIsPending()
		{
			return transitionPending && nextAbility == null ||
				deferredTransitionPending && deferredAbility == null;
		}

		internal bool CanActivate(Ability ability)
		{
			if (ability == null || activeAbility != null || transitionPending ||
				deferredTransitionPending || suppressTransitionRequests || !OwnsAbility(ability))
				return false;
			return TryGetActivationCost(ability, out float cost) && Stamina >= cost;
		}

		private bool TryGetActivationCost(Ability ability, out float cost)
		{
			try
			{
				cost = ability.ActivationCost(this);
				return float.IsFinite(cost) && cost >= 0;
			}
			catch (Exception exception)
			{
				cost = 0;
				LogHookFailure(ability, "ActivationCost", exception);
				return false;
			}
		}

		private bool OwnsAbility(Ability ability)
		{
			if (unlockedAbilities.Values.Any(value => ReferenceEquals(value, ability)))
				return true;
			return infusions.Any(infusion => infusion != null && ReferenceEquals(infusion.ability, ability));
		}

		private void ReconcileAbilityOwnership()
		{
			if (activeAbility != null && !OwnsAbility(activeAbility))
			{
				RetireActiveAbility(notify: !deactivationNotified);
				return;
			}

			if (transitionPending && nextAbility != null && !OwnsAbility(nextAbility))
			{
				nextAbility = activeAbility;
				transitionPending = false;
			}
		}

		internal bool TryActivate(Ability ability)
		{
			return QueueTransition(ability, requireAvailable: true);
		}

		private bool QueueTransition(Ability target, bool requireAvailable)
		{
			if (suppressTransitionRequests || ReferenceEquals(target, activeAbility) ||
				transitionPending && ReferenceEquals(target, nextAbility) ||
				deferredTransitionPending && ReferenceEquals(target, deferredAbility))
				return false;
			if (requireAvailable && !CanActivate(target))
				return false;
			if (transitionInProgress)
			{
				deferredAbility = target;
				deferredTransitionPending = true;
			}
			else
			{
				nextAbility = target;
				transitionPending = true;
			}
			return true;
		}

		internal void RequestDeactivate(Ability ability)
		{
			if (ability == null || suppressTransitionRequests)
				return;
			if (deactivationNotified || transitionPending && nextAbility == null ||
				deferredTransitionPending && deferredAbility == null)
				return;
			if (activeAbility == null && transitionPending && ReferenceEquals(nextAbility, ability))
			{
				nextAbility = null;
				transitionPending = false;
				return;
			}
			if (activeAbility == null && deferredTransitionPending && ReferenceEquals(deferredAbility, ability))
			{
				deferredAbility = null;
				deferredTransitionPending = false;
				return;
			}
			if (!ReferenceEquals(activeAbility, ability))
				return;
			deactivationNotified = true;
			InvokeHook(ability, nameof(Ability.OnDeactivate), ability.OnDeactivate);
			QueueTransition(null, requireAvailable: false);
		}

		private void ApplyPendingTransition()
		{
			if (!transitionPending)
				return;
			Ability target = nextAbility;
			transitionPending = false;
			nextAbility = activeAbility;
			if (ReferenceEquals(target, activeAbility))
				return;

			transitionInProgress = true;
			deferredAbility = null;
			deferredTransitionPending = false;
			try
			{
				if (target == null)
				{
					Ability retiring = activeAbility;
					activeAbility = null;
					deactivationNotified = false;
					if (retiring != null)
					{
						InvokeHook(retiring, nameof(Ability.OnExit), retiring.OnExit);
						InvokeHook(retiring, nameof(Ability.Reset), retiring.Reset);
					}
					return;
				}

				if (activeAbility != null || !OwnsAbility(target) ||
					!TryGetActivationCost(target, out float cost) || Stamina < cost)
					return;

				float previousStamina = stamina;
				float previousBonus = target.ActivationCostBonus;
				target.User = this;
				activeAbility = target;
				nextAbility = target;
				deactivationNotified = false;
				Stamina -= cost;
				target.ActivationCostBonus = 0;
				if (!InvokeHook(target, nameof(Ability.OnActivate), target.OnActivate))
				{
					activeAbility = null;
					nextAbility = null;
					stamina = MathHelper.Clamp(previousStamina, 0, StaminaMax);
					target.ActivationCostBonus = previousBonus;
					deferredAbility = null;
					deferredTransitionPending = false;
					bool previousSuppression = suppressTransitionRequests;
					suppressTransitionRequests = true;
					InvokeHook(target, nameof(Ability.OnExit), target.OnExit);
					InvokeHook(target, nameof(Ability.Reset), target.Reset);
					suppressTransitionRequests = previousSuppression;
					deferredAbility = null;
					deferredTransitionPending = false;
				}
			}
			finally
			{
				transitionInProgress = false;
				PromoteDeferredTransition();
			}
		}

		private void RetireActiveAbility(bool notify)
		{
			Ability retiring = activeAbility;
			if (retiring == null)
				return;
			transitionInProgress = true;
			deferredAbility = null;
			deferredTransitionPending = false;
			nextAbility = null;
			transitionPending = false;
			try
			{
				if (notify)
					InvokeHook(retiring, nameof(Ability.OnDeactivate), retiring.OnDeactivate);
				activeAbility = null;
				deactivationNotified = false;
				InvokeHook(retiring, nameof(Ability.OnExit), retiring.OnExit);
				InvokeHook(retiring, nameof(Ability.Reset), retiring.Reset);
			}
			finally
			{
				activeAbility = null;
				transitionInProgress = false;
				PromoteDeferredTransition();
			}
		}

		private void PromoteDeferredTransition()
		{
			if (deferredTransitionPending)
			{
				nextAbility = deferredAbility;
				transitionPending = true;
			}
			else
			{
				nextAbility = activeAbility;
			}
			deferredAbility = null;
			deferredTransitionPending = false;
		}

		private bool InvokeHook(Ability ability, string hook, Action callback)
		{
			try
			{
				callback();
				return true;
			}
			catch (Exception exception)
			{
				LogHookFailure(ability, hook, exception);
				return false;
			}
		}

		private static void LogHookFailure(Ability ability, string hook, Exception exception)
		{
			StarlightRiver.Instance.Logger.Debug($"handled {ability?.GetType().FullName ?? "unknown"}.{hook} error: {exception}");
		}

		public override void OnEnterWorld()
		{
			var packet = new AbilityProgress(Player.whoAmI, Player.GetHandler());
			packet.Send();
		}

		public override void ModifyDrawInfo(ref PlayerDrawSet drawInfo)
		{
			ActiveAbility?.ModifyDrawInfo(ref drawInfo);
		}

		/// <summary>
		/// This handles calling the visual effect hooks of active abilities
		/// </summary>
		/// <param name="Player"></param>
		/// <param name="spriteBatch"></param>
		public void PostDrawAbility(Player Player, SpriteBatch spriteBatch)
		{
			AbilityHandler handler = Player.GetHandler();
			foreach (Ability ability in handler.SnapshotAbilities())
				if (handler.OwnsAbility(ability))
					handler.InvokeHook(ability, nameof(Ability.DrawActiveEffects), () => ability.DrawActiveEffects(spriteBatch));
		}
	}
}
