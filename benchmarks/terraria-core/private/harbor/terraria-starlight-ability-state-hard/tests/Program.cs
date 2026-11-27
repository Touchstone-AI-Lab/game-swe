using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using GameCodeBench;
using NetEasy;
using StarlightRiver.Content.Abilities;
using StarlightRiver.Content.Abilities.Faewhip;
using StarlightRiver.Content.Abilities.ForbiddenWinds;
using StarlightRiver.Content.Abilities.Hint;
using StarlightRiver.Content.Packets;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader.IO;
using NetModule = NetEasy.Module;

internal static class ContractProgram
{
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["save_sorts_unique_shards"] = SaveSortedShards,
        ["save_sorts_unique_ability_names"] = SaveSortedAbilities,
        ["save_preserves_sparse_infusion_slots"] = SaveSparseInfusions,
        ["save_uses_independent_item_snapshots"] = SaveIndependentItems,
        ["load_skips_unknown_ability_and_continues"] = LoadUnknownContinues,
        ["load_accepts_legacy_compact_infusions"] = LoadLegacyInfusions,
        ["load_preserves_positional_infusion_gaps"] = LoadPositionalGaps,
        ["load_defaults_missing_infusion_limit"] = LoadDefaultLimit,
        ["load_negative_shard_rolls_back"] = LoadNegativeShardRollback,
        ["load_excessive_shards_rolls_back"] = LoadExcessiveShardsRollback,
        ["load_excessive_abilities_rolls_back"] = LoadExcessiveAbilitiesRollback,
        ["load_throwing_ability_rolls_back"] = LoadThrowingAbilityRollback,
        ["load_locked_slot_rolls_back"] = LoadLockedSlotRollback,
        ["load_duplicate_infusion_rolls_back"] = LoadDuplicateInfusionRollback,
        ["load_bad_item_rolls_back"] = LoadBadItemRollback,
        ["infusion_rejects_negative_slot"] = InfusionNegativeSlot,
        ["infusion_rejects_high_slot"] = InfusionHighSlot,
        ["infusion_rejects_locked_slot"] = InfusionLockedSlot,
        ["infusion_removal_clears_slot"] = InfusionRemoval,
        ["infusion_replaces_same_slot_when_full"] = InfusionReplaceFull,
        ["infusion_rejects_duplicate_ability_family"] = InfusionDuplicateAbility,
        ["infusion_rejects_unequippable_item"] = InfusionUnequippable,
        ["infusion_install_clones_and_sets_owner"] = InfusionCloneOwner,
        ["infusion_clone_failure_rolls_back"] = InfusionCloneRollback,
        ["clone_has_independent_shards"] = CloneShards,
        ["clone_has_independent_ability_instances"] = CloneAbilities,
        ["clone_has_independent_positional_infusions"] = CloneInfusions,
        ["clone_maps_active_ability_without_hooks"] = CloneActive,
        ["client_state_copy_is_deep"] = CopyClientDeep,
        ["activation_is_queued_until_preupdate"] = ActivationQueued,
        ["activation_hooks_and_cost_run_once"] = ActivationHooksOnce,
        ["duplicate_pending_activation_is_ignored"] = ActivationDuplicatePending,
        ["deactivation_hooks_run_once_in_order"] = DeactivationHooks,
        ["cancelled_pending_activation_has_no_effect"] = ActivationCancelPending,
        ["insufficient_stamina_rejects_activation"] = ActivationInsufficient,
        ["negative_cost_rejects_activation"] = ActivationNegative,
        ["nonfinite_cost_rejects_activation"] = ActivationNonFinite,
        ["activation_bonus_is_consumed_once"] = ActivationBonus,
        ["activation_hook_observes_committed_state"] = ActivationHookObservesCommitted,
        ["activation_hook_failure_rolls_back"] = ActivationHookFailureRollback,
        ["failed_activation_discards_reentrant_request"] = FailedActivationDiscardsReentrant,
        ["deactivation_hook_failure_still_cleans_up"] = DeactivationHookFailureCleanup,
        ["exit_and_reset_failures_do_not_repeat"] = ExitResetFailuresDoNotRepeat,
        ["exit_reentrant_activation_waits_next_tick"] = ExitReentrantActivationDeferred,
        ["death_discards_cleanup_reentrant_activation"] = DeathDiscardsCleanupActivation,
        ["fixed_snapshot_defers_new_unlock"] = FixedSnapshotDefersNewUnlock,
        ["fixed_snapshot_skips_removed_instance"] = FixedSnapshotSkipsRemoved,
        ["fixed_failure_does_not_skip_later_instance"] = FixedFailureContinues,
        ["fixed_mutation_retires_before_active_update"] = FixedMutationRetiresBeforeActive,
        ["active_update_failure_retires_immediately"] = ActiveFailureRetires,
        ["active_deactivation_suppresses_effects_and_controls"] = ActiveDeactivationSuppressesEffects,
        ["visual_effect_failure_preserves_active_state"] = VisualFailurePreservesActive,
        ["draw_snapshot_isolates_mutation_and_failure"] = DrawSnapshotIsolates,
        ["lock_cancels_uncommitted_activation"] = LockCancelsPending,
        ["lock_retires_active_once"] = LockRetiresActive,
        ["load_retires_replaced_active_instance"] = LoadRetiresActive,
        ["infusion_removal_cancels_pending_instance"] = InfusionRemovalCancelsPending,
        ["infusion_replacement_retires_active_instance"] = InfusionReplacementRetiresActive,
        ["progress_replacement_retires_active_instance"] = ProgressReplacementRetiresActive,
        ["death_retires_active_immediately"] = DeathRetiresActive,
        ["death_cancels_pending_start_without_cost"] = DeathCancelsPending,
        ["death_finishes_prior_deactivation_once"] = DeathFinishesDeactivation,
        ["repeated_dead_ticks_do_not_repeat_hooks"] = DeathRepeated,
        ["respawn_requires_fresh_activation"] = RespawnFreshActivation,
        ["death_of_clone_does_not_retire_source"] = DeathCloneIndependent,
        ["progress_snapshot_is_sorted_and_complete"] = ProgressSnapshot,
        ["progress_receive_replaces_managed_state"] = ProgressReplace,
        ["progress_receive_preserves_custom_unlocks"] = ProgressPreserveCustom,
        ["progress_server_rejects_spoofed_sender"] = ProgressSpoof,
        ["progress_rejects_invalid_player"] = ProgressBadPlayer,
        ["progress_rejects_duplicate_shards"] = ProgressDuplicate,
        ["progress_rejects_negative_shard"] = ProgressNegative,
        ["progress_rejects_excessive_shards"] = ProgressExcessive,
        ["progress_rejects_reserved_mask_bits"] = ProgressReservedMask,
        ["progress_server_relays_valid_frame"] = ProgressRelay,
        ["start_server_queues_valid_unlocked_ability"] = StartValid,
        ["start_server_rejects_spoofed_sender"] = StartSpoof,
        ["start_rejects_invalid_player"] = StartBadPlayer,
        ["start_rejects_unknown_type"] = StartUnknownType,
        ["start_rejects_nonability_type"] = StartNonAbilityType,
        ["start_rejects_locked_ability"] = StartLocked,
        ["start_rejects_insufficient_stamina"] = StartInsufficient,
        ["start_duplicate_does_not_charge_or_relay_twice"] = StartDuplicate,
        ["start_client_applies_without_relay"] = StartClient,
    };

    public static int Main(string[] args)
    {
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out Action test)) return 2;
        try { TestHooks.Reset(); test(); Console.WriteLine("PASS"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static void Check(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
    private static AbilityHandler Handler(int player = 0) => MainPlayer(player).GetHandler();
    private static Player MainPlayer(int player) => Terraria.Main.player[player];
    private static T Unlock<T>(AbilityHandler handler) where T : Ability, new() { handler.Unlock<T>(); Check(handler.GetAbility(out T value), "unlock failed"); return value; }
    private static T Ready<T>(AbilityHandler handler) where T : Ability, new() { T value = Unlock<T>(handler); handler.Shards.Add(1); handler.Shards.Add(2); handler.Shards.Add(3); handler.ResetEffects(); handler.Stamina = handler.StaminaMax; return value; }
    private static InfusionItem Infusion(int type) => new Item(type).ModItem as InfusionItem;
    private static TagCompound Tag(IEnumerable<int> shards = null, IEnumerable<string> abilities = null, IEnumerable<Item> infusions = null, int? limit = null)
    {
        var tag = new TagCompound();
        if (shards != null) tag["Shards"] = shards.ToList();
        if (abilities != null) tag["unlockedAbilities"] = abilities.ToList();
        if (infusions != null) tag["infusions"] = infusions.ToList();
        if (limit.HasValue) tag["InfusionLimit"] = limit.Value;
        return tag;
    }
    private static T Field<T>(object value, string name) => (T)value.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic).GetValue(value);
    private static void SetField(object value, string name, object replacement) => value.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic).SetValue(value, replacement);
    private static AbilityProgress Progress(int player, AbilityHandler source, int sender = -1) => new(player, source) { Sender = sender };
    private static void Invoke(NetModule packet) => packet.InvokeReceive();
    private static void AssertInitialState(AbilityHandler handler)
    {
        Check(handler.Shards.Has(77), "shards were partially replaced");
        Check(handler.Unlocked<TestAbility>(), "abilities were partially replaced");
        Check(handler.GetInfusion(0)?.Item.type == 10, "infusions were partially replaced");
        Check(handler.InfusionLimit == 3, "limit was partially replaced");
    }
    private static AbilityHandler InitialState()
    {
        AbilityHandler handler = Handler();
        handler.Shards.Add(77);
        handler.Unlock<TestAbility>();
        handler.InfusionLimit = 3;
        Check(handler.SetInfusion(Infusion(10), 0), "initial infusion failed");
        return handler;
    }

    private static void SaveSortedShards()
    {
        AbilityHandler h = Handler(); h.Shards.Add(9); h.Shards.Add(1); h.Shards.Add(5); h.Shards.Add(1);
        var tag = new TagCompound(); h.SaveData(tag);
        Check(tag.GetList<int>("Shards").SequenceEqual(new[] { 1, 5, 9 }), "shards are not canonical");
    }
    private static void SaveSortedAbilities()
    {
        AbilityHandler h = Handler(); h.Unlock<Whip>(); h.Unlock<TestAbility>(); h.Unlock<Dash>(); h.Unlock<Dash>();
        var tag = new TagCompound(); h.SaveData(tag);
        var expected = new[] { typeof(Dash).FullName, typeof(TestAbility).FullName, typeof(Whip).FullName }.OrderBy(x => x, StringComparer.Ordinal);
        Check(tag.GetList<string>("unlockedAbilities").SequenceEqual(expected), "ability names are not canonical");
    }
    private static void SaveSparseInfusions()
    {
        AbilityHandler h = Handler(); h.InfusionLimit = 3; Check(h.SetInfusion(Infusion(12), 2), "install failed");
        var tag = new TagCompound(); h.SaveData(tag); IList<Item> items = tag.GetList<Item>("infusions");
        Check(items.Count == 3 && items[0].IsAir && items[1].IsAir && items[2].type == 12, "slot position was compacted");
    }
    private static void SaveIndependentItems()
    {
        AbilityHandler h = Handler(); h.InfusionLimit = 3; Check(h.SetInfusion(Infusion(10), 0), "install failed");
        var tag = new TagCompound(); h.SaveData(tag); h.GetInfusion(0).Item.type = 99;
        Check(tag.GetList<Item>("infusions")[0].type == 10, "saved item aliases live item");
    }
    private static void LoadUnknownContinues()
    {
        AbilityHandler h = Handler(); h.LoadData(Tag(abilities: new[] { "Missing.Mod.Ability", typeof(Dash).FullName }, limit: 1));
        Check(h.Unlocked<Dash>() && h.unlockedAbilities.Count == 1, "unknown entry stopped valid later entry");
    }
    private static void LoadLegacyInfusions()
    {
        AbilityHandler h = Handler(); h.LoadData(Tag(infusions: new[] { new Item(10), new Item(12) }, limit: 2));
        Check(h.GetInfusion(0)?.Item.type == 10 && h.GetInfusion(1)?.Item.type == 12, "legacy compact list failed");
    }
    private static void LoadPositionalGaps()
    {
        AbilityHandler h = Handler(); h.LoadData(Tag(infusions: new[] { new Item(), new Item(12), new Item() }, limit: 3));
        Check(h.GetInfusion(0) == null && h.GetInfusion(1)?.Item.type == 12 && h.GetInfusion(2) == null, "gaps not preserved");
    }
    private static void LoadDefaultLimit()
    {
        AbilityHandler h = Handler(); h.LoadData(Tag()); Check(h.InfusionLimit == 1, "missing limit default changed");
    }
    private static void LoadNegativeShardRollback()
    {
        AbilityHandler h = InitialState(); h.LoadData(Tag(shards: new[] { 1, -1 }, limit: 1)); AssertInitialState(h);
    }
    private static void LoadExcessiveShardsRollback()
    {
        AbilityHandler h = InitialState(); h.LoadData(Tag(shards: Enumerable.Range(0, 4097), limit: 1)); AssertInitialState(h);
    }
    private static void LoadExcessiveAbilitiesRollback()
    {
        AbilityHandler h = InitialState(); h.LoadData(Tag(abilities: Enumerable.Range(0, 257).Select(i => "Missing." + i), limit: 1)); AssertInitialState(h);
    }
    private static void LoadThrowingAbilityRollback()
    {
        AbilityHandler h = InitialState(); h.LoadData(Tag(abilities: new[] { typeof(Dash).FullName, typeof(ThrowingAbility).FullName }, limit: 1)); AssertInitialState(h);
    }
    private static void LoadLockedSlotRollback()
    {
        AbilityHandler h = InitialState(); h.LoadData(Tag(infusions: new[] { new Item(), new Item(12) }, limit: 1)); AssertInitialState(h);
    }
    private static void LoadDuplicateInfusionRollback()
    {
        AbilityHandler h = InitialState(); h.LoadData(Tag(infusions: new[] { new Item(10), new Item(11) }, limit: 2)); AssertInitialState(h);
    }
    private static void LoadBadItemRollback()
    {
        AbilityHandler h = InitialState(); var bad = new Item { type = 14, ModItem = new DashInfusion() }; bad.ModItem.Item = bad;
        h.LoadData(Tag(infusions: new[] { bad }, limit: 1)); AssertInitialState(h);
    }

    private static void InfusionNegativeSlot() { AbilityHandler h = Handler(); h.InfusionLimit = 3; Check(!h.SetInfusion(Infusion(10), -1) && h.GetInfusion(0) == null, "negative slot accepted"); }
    private static void InfusionHighSlot() { AbilityHandler h = Handler(); h.InfusionLimit = 3; Check(!h.SetInfusion(Infusion(10), 3) && h.GetInfusion(2) == null, "high slot accepted"); }
    private static void InfusionLockedSlot() { AbilityHandler h = Handler(); h.InfusionLimit = 1; Check(!h.SetInfusion(Infusion(10), 2) && h.GetInfusion(2) == null, "locked slot accepted"); }
    private static void InfusionRemoval() { AbilityHandler h = Handler(); h.InfusionLimit = 3; h.SetInfusion(Infusion(10), 2); Check(h.SetInfusion(null, 2) && h.GetInfusion(2) == null, "removal failed"); }
    private static void InfusionReplaceFull()
    {
        AbilityHandler h = Handler(); h.InfusionLimit = 1; Check(h.SetInfusion(Infusion(10), 0), "initial failed"); Check(h.SetInfusion(Infusion(12), 0) && h.GetInfusion(0).Item.type == 12, "same slot replacement failed");
    }
    private static void InfusionDuplicateAbility()
    {
        AbilityHandler h = Handler(); h.InfusionLimit = 3; Check(h.SetInfusion(Infusion(10), 0), "initial failed"); Check(!h.SetInfusion(Infusion(11), 1) && h.GetInfusion(1) == null, "duplicate family accepted");
    }
    private static void InfusionUnequippable() { AbilityHandler h = Handler(); h.InfusionLimit = 3; Check(!h.SetInfusion(Infusion(13), 0), "unequippable item accepted"); }
    private static void InfusionCloneOwner()
    {
        AbilityHandler h = Handler(2); h.InfusionLimit = 3; InfusionItem source = Infusion(10); Check(h.SetInfusion(source, 0), "install failed");
        Check(!ReferenceEquals(source, h.GetInfusion(0)) && h.GetInfusion(0).Item.playerIndexTheItemIsReservedFor == 2 && ReferenceEquals(h.GetInfusion(0).ability.User, h), "clone owner invalid");
    }
    private static void InfusionCloneRollback()
    {
        AbilityHandler h = Handler(); h.InfusionLimit = 3; h.SetInfusion(Infusion(10), 0); var bad = new DashInfusion(); var item = new Item { type = 14, ModItem = bad }; bad.Item = item;
        Check(!h.SetInfusion(bad, 0) && h.GetInfusion(0).Item.type == 10, "clone failure mutated slot");
    }

    private static void CloneShards()
    {
        AbilityHandler h = Handler(); h.Shards.Add(4); var clone = (AbilityHandler)h.Clone(MainPlayer(1)); clone.Shards.Add(5);
        Check(h.Shards.Has(4) && !h.Shards.Has(5) && clone.Shards.Has(4), "shards alias");
    }
    private static void CloneAbilities()
    {
        AbilityHandler h = Handler(); TestAbility source = Unlock<TestAbility>(h); source.ActivationCostBonus = 3; var clone = (AbilityHandler)h.Clone(MainPlayer(1)); clone.GetAbility(out TestAbility copy); copy.ActivationCostBonus = 8;
        Check(!ReferenceEquals(source, copy) && ReferenceEquals(copy.User, clone) && source.ActivationCostBonus == 3, "ability clone alias/owner");
    }
    private static void CloneInfusions()
    {
        AbilityHandler h = Handler(); h.InfusionLimit = 3; h.SetInfusion(Infusion(12), 2); var clone = (AbilityHandler)h.Clone(MainPlayer(3)); clone.GetInfusion(2).Item.type = 99;
        Check(h.GetInfusion(2).Item.type == 12 && clone.GetInfusion(0) == null && clone.GetInfusion(2).Item.playerIndexTheItemIsReservedFor == 3, "infusion clone alias/position/owner");
    }
    private static void CloneActive()
    {
        AbilityHandler h = Handler(); TestAbility source = Ready<TestAbility>(h); source.Activate(h); h.PreUpdate(); float stamina = h.Stamina;
        int activations = TrackedAbility.ActivationInvocations, resets = TrackedAbility.ResetInvocations;
        var clone = (AbilityHandler)h.Clone(MainPlayer(1));
        Check(clone.ActiveAbility is TestAbility copied && !ReferenceEquals(copied, source) && ReferenceEquals(copied.User, clone) && clone.Stamina == stamina && TrackedAbility.ActivationInvocations == activations && TrackedAbility.ResetInvocations == resets, "active clone ran hooks or aliased");
    }
    private static void CopyClientDeep()
    {
        AbilityHandler h = Handler(); h.Shards.Add(7); h.Unlock<TestAbility>(); h.InfusionLimit = 3; h.SetInfusion(Infusion(12), 1); var clone = new AbilityHandler { Player = MainPlayer(4) }; h.CopyClientState(clone); clone.Shards.Add(8); clone.GetInfusion(1).Item.type = 99;
        Check(clone.Shards.Has(7) && !h.Shards.Has(8) && h.GetInfusion(1).Item.type == 12 && clone.Unlocked<TestAbility>(), "client copy is shallow/incomplete");
    }

    private static void ActivationQueued()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); float before = h.Stamina; a.Activate(h); Check(h.ActiveAbility == null && a.Activated == 0 && h.Stamina == before, "activation was immediate"); h.PreUpdate(); Check(ReferenceEquals(h.ActiveAbility, a), "queued activation not applied");
    }
    private static void ActivationHooksOnce()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); float before = h.Stamina; a.Activate(h); h.PreUpdate(); h.PreUpdate(); Check(a.Activated == 1 && h.Stamina == before - 1, "hooks/cost repeated");
    }
    private static void ActivationDuplicatePending()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); a.Activate(h); a.Activate(h); Check(NetModule.Sends.Count == 1, "duplicate packet emitted"); h.PreUpdate(); Check(a.Activated == 1, "duplicate transition applied");
    }
    private static void DeactivationHooks()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); a.Activate(h); h.PreUpdate(); int resetBefore = a.ResetCount; a.Deactivate(); a.Deactivate(); Check(a.Deactivated == 1 && a.Exited == 0, "deactivation callback order"); h.PreUpdate(); Check(a.Exited == 1 && a.ResetCount == resetBefore + 1 && h.ActiveAbility == null, "exit/reset not once");
    }
    private static void ActivationCancelPending()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); float before = h.Stamina; a.Activate(h); a.Deactivate(); h.PreUpdate(); Check(h.ActiveAbility == null && a.Activated == 0 && a.Deactivated == 0 && h.Stamina == before, "cancelled transition had effects");
    }
    private static void ActivationInsufficient()
    {
        AbilityHandler h = Handler(); TestAbility a = Unlock<TestAbility>(h); h.ResetEffects(); h.Stamina = 0; a.Activate(h); h.PreUpdate(); Check(h.ActiveAbility == null && a.Activated == 0 && NetModule.Sends.Count == 0, "insufficient activation accepted");
    }
    private static void ActivationNegative()
    {
        AbilityHandler h = Handler(); NegativeCostAbility a = Ready<NegativeCostAbility>(h); float before = h.Stamina; a.Activate(h); h.PreUpdate(); Check(h.ActiveAbility == null && h.Stamina == before, "negative cost subsidized activation");
    }
    private static void ActivationNonFinite()
    {
        AbilityHandler h = Handler(); NonFiniteCostAbility a = Ready<NonFiniteCostAbility>(h); a.Activate(h); h.PreUpdate(); Check(h.ActiveAbility == null && float.IsFinite(h.Stamina), "nonfinite cost corrupted state");
    }
    private static void ActivationBonus()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); h.Shards.Add(4); h.Shards.Add(5); h.Shards.Add(6); h.Stamina = h.StaminaMax; a.ActivationCostBonus = 1; float before = h.Stamina; a.Activate(h); h.PreUpdate(); Check(h.Stamina == before - 2 && a.ActivationCostBonus == 0, "activation bonus not consumed once");
    }

    private static void ActivationHookObservesCommitted()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); bool observed = false;
        a.ActivateCallback = value => observed = value.Active && ReferenceEquals(h.ActiveAbility, value);
        a.Activate(h); h.PreUpdate();
        Check(observed && ReferenceEquals(h.ActiveAbility, a), "activation hook did not observe committed active state");
    }

    private static void ActivationHookFailureRollback()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); a.ActivationCostBonus = 0.5f;
        float stamina = h.Stamina; int reset = a.ResetCount;
        a.ActivateCallback = _ => throw new InvalidOperationException("activation failed");
        a.Activate(h); h.PreUpdate(); h.PreUpdate();
        Check(h.ActiveAbility == null && h.Stamina == stamina && a.ActivationCostBonus == 0.5f, "failed activation did not restore state");
        Check(a.Activated == 1 && a.Deactivated == 0 && a.Exited == 1 && a.ResetCount == reset + 1, "failed activation cleanup was not exact");
        Check(StarlightRiver.StarlightRiver.Instance.Logger.DebugMessages.Count >= 1, "activation failure was not logged");
    }

    private static void FailedActivationDiscardsReentrant()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); float stamina = h.Stamina; int reset = a.ResetCount;
        a.ActivateCallback = value => { value.Deactivate(); throw new InvalidOperationException("activation failed after deactivation request"); };
        a.Activate(h); h.PreUpdate(); h.PreUpdate();
        Check(h.ActiveAbility == null && h.Stamina == stamina && a.Activated == 1 && a.Deactivated == 1, "failed activation kept its reentrant request");
        Check(a.Exited == 1 && a.ResetCount == reset + 1, "failed activation cleanup repeated");
    }

    private static void DeactivationHookFailureCleanup()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); a.Activate(h); h.PreUpdate(); int reset = a.ResetCount;
        a.DeactivateCallback = _ => throw new InvalidOperationException("deactivation failed");
        a.Deactivate(); h.PreUpdate(); h.PreUpdate();
        Check(h.ActiveAbility == null && a.Deactivated == 1 && a.Exited == 1 && a.ResetCount == reset + 1, "deactivation failure blocked or repeated cleanup");
        Check(StarlightRiver.StarlightRiver.Instance.Logger.DebugMessages.Count >= 1, "deactivation failure was not logged");
    }

    private static void ExitResetFailuresDoNotRepeat()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); a.Activate(h); h.PreUpdate(); int reset = a.ResetCount;
        a.ExitCallback = _ => throw new InvalidOperationException("exit failed");
        a.ResetCallback = _ => throw new InvalidOperationException("reset failed");
        a.Deactivate(); h.PreUpdate(); h.PreUpdate();
        Check(h.ActiveAbility == null && a.Deactivated == 1 && a.Exited == 1 && a.ResetCount == reset + 1, "throwing retirement repeated or remained active");
        Check(StarlightRiver.StarlightRiver.Instance.Logger.DebugMessages.Count >= 2, "retirement failures were not isolated and logged");
    }

    private static void ExitReentrantActivationDeferred()
    {
        AbilityHandler h = Handler(); TestAbility a = Unlock<TestAbility>(h); Whip b = Unlock<Whip>(h);
        for (int id = 1; id <= 6; id++) h.Shards.Add(id);
        h.ResetEffects(); h.Stamina = h.StaminaMax; a.Activate(h); h.PreUpdate(); float before = h.Stamina;
        a.ExitCallback = _ => b.Activate(h);
        a.Deactivate(); h.PreUpdate();
        Check(h.ActiveAbility == null && b.Activated == 0 && h.Stamina >= before, "cleanup callback committed a second transition in the same tick");
        float afterRetirement = h.Stamina;
        h.PreUpdate();
        Check(ReferenceEquals(h.ActiveAbility, b) && b.Activated == 1 && h.Stamina == afterRetirement - 2, "cleanup callback activation was not deferred exactly once");
    }

    private static void DeathDiscardsCleanupActivation()
    {
        AbilityHandler h = Handler(); TestAbility a = Unlock<TestAbility>(h); Whip b = Unlock<Whip>(h);
        for (int id = 1; id <= 6; id++) h.Shards.Add(id);
        h.ResetEffects(); h.Stamina = h.StaminaMax; a.Activate(h); h.PreUpdate();
        a.ExitCallback = _ => b.Activate(h);
        h.UpdateDead(); h.OnRespawn(); h.PreUpdate();
        Check(h.ActiveAbility == null && b.Activated == 0, "death cleanup resurrected a callback-queued ability");
    }

    private static void FixedSnapshotDefersNewUnlock()
    {
        AbilityHandler h = Handler(); Dash first = Unlock<Dash>(h);
        first.FixedCallback = _ => h.Unlock<Whip>();
        h.PreUpdate(); Check(h.GetAbility(out Whip added) && added.FixedUpdates == 0, "new unlock ran in the current fixed snapshot");
        h.PreUpdate(); Check(added.FixedUpdates == 1, "new unlock did not run on the next tick");
    }

    private static void FixedSnapshotSkipsRemoved()
    {
        AbilityHandler h = Handler(); Whip first = Unlock<Whip>(h); Dash removed = Unlock<Dash>(h);
        first.FixedCallback = _ => h.Lock<Dash>();
        h.PreUpdate();
        Check(first.FixedUpdates == 1 && removed.FixedUpdates == 0 && !h.Unlocked<Dash>(), "removed snapshot instance still ran");
    }

    private static void FixedFailureContinues()
    {
        AbilityHandler h = Handler(); Whip first = Unlock<Whip>(h); Dash later = Unlock<Dash>(h);
        first.FixedCallback = _ => throw new InvalidOperationException("fixed failed");
        h.PreUpdate();
        Check(first.FixedUpdates == 1 && later.FixedUpdates == 1, "fixed failure skipped a later snapshot instance");
        Check(StarlightRiver.StarlightRiver.Instance.Logger.DebugMessages.Count >= 1, "fixed failure was not logged");
    }

    private static void FixedMutationRetiresBeforeActive()
    {
        AbilityHandler h = Handler(); Whip mutator = Unlock<Whip>(h); Dash active = Unlock<Dash>(h);
        for (int id = 1; id <= 6; id++) h.Shards.Add(id);
        h.ResetEffects(); h.Stamina = h.StaminaMax; active.Activate(h); h.PreUpdate(); int updates = active.ActiveUpdates; int reset = active.ResetCount;
        mutator.FixedCallback = _ => h.Lock<Dash>();
        h.PreUpdate();
        Check(h.ActiveAbility == null && active.ActiveUpdates == updates, "orphaned active ability updated after fixed mutation");
        Check(active.Deactivated == 1 && active.Exited == 1 && active.ResetCount == reset + 1, "fixed mutation did not retire exactly once");
    }

    private static void ActiveFailureRetires()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); a.Activate(h); h.PreUpdate(); int reset = a.ResetCount;
        a.ActiveCallback = _ => throw new InvalidOperationException("active failed");
        h.PreUpdate(); h.PreUpdate();
        Check(h.ActiveAbility == null && a.Deactivated == 1 && a.Exited == 1 && a.ResetCount == reset + 1, "active failure did not retire immediately and once");
        Check(StarlightRiver.StarlightRiver.Instance.Logger.DebugMessages.Count >= 1, "active failure was not logged");
    }

    private static void ActiveDeactivationSuppressesEffects()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); a.Activate(h); h.PreUpdate();
        int effects = a.EffectUpdates; Terraria.NetMessage.Sent.Clear();
        a.ActiveCallback = value => value.Deactivate();
        h.PreUpdate();
        Check(ReferenceEquals(h.ActiveAbility, a) && a.Deactivated == 1, "active callback did not queue deactivation");
        Check(a.EffectUpdates == effects && Terraria.NetMessage.Sent.Count == 0, "deactivating active callback still emitted effects or controls");
        h.PreUpdate(); Check(h.ActiveAbility == null, "queued active-callback deactivation did not commit");
    }

    private static void VisualFailurePreservesActive()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); a.Activate(h); h.PreUpdate();
        a.EffectCallback = _ => throw new InvalidOperationException("visual failed"); Terraria.NetMessage.Sent.Clear();
        h.PreUpdate();
        Check(ReferenceEquals(h.ActiveAbility, a) && a.Deactivated == 0 && Terraria.NetMessage.Sent.Count == 1, "visual failure ended gameplay state or controls");
        Check(StarlightRiver.StarlightRiver.Instance.Logger.DebugMessages.Count >= 1, "visual failure was not logged");
    }

    private static void DrawSnapshotIsolates()
    {
        AbilityHandler h = Handler(); Whip first = Unlock<Whip>(h); Dash removed = Unlock<Dash>(h);
        first.DrawCallback = _ => { h.Lock<Dash>(); throw new InvalidOperationException("draw failed"); };
        h.PostDrawAbility(MainPlayer(0), new Microsoft.Xna.Framework.Graphics.SpriteBatch());
        Check(first.DrawUpdates == 1 && removed.DrawUpdates == 0, "draw mutation invalidated snapshot or drew removed instance");
        Check(StarlightRiver.StarlightRiver.Instance.Logger.DebugMessages.Count >= 1, "draw failure was not logged");
    }

    private static void AssertRetired(AbilityHandler h, TrackedAbility old)
    {
        int reset = old.ResetCount;
        int activeUpdates = old.ActiveUpdates;
        h.PreUpdate();
        h.PreUpdate();
        Check(h.ActiveAbility == null && old.Deactivated == 1 && old.Exited == 1 && old.ResetCount == reset + 1, $"orphan was not retired exactly once: active={h.ActiveAbility != null}, deactivated={old.Deactivated}, exited={old.Exited}, resets={old.ResetCount - reset}");
        Check(old.ActiveUpdates == activeUpdates, "orphan ran an active update after ownership loss");
    }
    private static void LockCancelsPending()
    {
        AbilityHandler h = Handler(); TestAbility old = Ready<TestAbility>(h); float stamina = h.Stamina;
        old.Activate(h); h.Lock<TestAbility>(); h.PreUpdate();
        Check(h.ActiveAbility == null && old.Activated == 0 && old.Deactivated == 0 && old.Exited == 0 && h.Stamina == Math.Min(stamina, h.StaminaMax), $"revoked pending ability activated or charged: active={h.ActiveAbility != null}, activated={old.Activated}, deactivated={old.Deactivated}, exited={old.Exited}, stamina={h.Stamina}/{stamina}");
    }
    private static void LockRetiresActive()
    {
        AbilityHandler h = Handler(); TestAbility old = Ready<TestAbility>(h); old.Activate(h); h.PreUpdate();
        h.Lock<TestAbility>(); AssertRetired(h, old);
    }
    private static void LoadRetiresActive()
    {
        AbilityHandler h = Handler(); TestAbility old = Ready<TestAbility>(h); old.Activate(h); h.PreUpdate();
        h.LoadData(Tag(shards: new[] { 1, 2, 3 }, abilities: new[] { typeof(TestAbility).FullName }, infusions: Array.Empty<Item>(), limit: 1));
        Check(h.GetAbility(out TestAbility replacement) && !ReferenceEquals(old, replacement), "load did not replace ability instance");
        AssertRetired(h, old);
    }
    private static void InfusionRemovalCancelsPending()
    {
        AbilityHandler h = Handler(); h.InfusionLimit = 1; h.Shards.Add(1); h.Shards.Add(2); h.Shards.Add(3); h.ResetEffects(); h.Stamina = h.StaminaMax;
        Check(h.SetInfusion(Infusion(10), 0), "infusion install failed"); var old = (TrackedAbility)h.GetInfusion(0).ability; float stamina = h.Stamina;
        old.Activate(h); Check(h.SetInfusion(null, 0), "infusion removal failed"); h.PreUpdate();
        Check(h.ActiveAbility == null && old.Activated == 0 && old.Exited == 0 && h.Stamina == stamina, "removed pending infusion activated or charged");
    }
    private static void InfusionReplacementRetiresActive()
    {
        AbilityHandler h = Handler(); h.InfusionLimit = 1; h.Shards.Add(1); h.Shards.Add(2); h.Shards.Add(3); h.ResetEffects(); h.Stamina = h.StaminaMax;
        Check(h.SetInfusion(Infusion(10), 0), "infusion install failed"); var old = (TrackedAbility)h.GetInfusion(0).ability;
        old.Activate(h); h.PreUpdate(); Check(ReferenceEquals(h.ActiveAbility, old), "infusion activation failed");
        Check(h.SetInfusion(Infusion(12), 0), "replacement failed"); AssertRetired(h, old);
    }
    private static void ProgressReplacementRetiresActive()
    {
        AbilityHandler h = Handler(); Dash old = Ready<Dash>(h); old.Activate(h); h.PreUpdate();
        Invoke(Progress(0, Handler(1))); Check(!h.Unlocked<Dash>(), "progress did not revoke managed unlock");
        AssertRetired(h, old);
    }

    private static void DeathRetiresActive()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h);
        a.Activate(h); h.PreUpdate(); int reset = a.ResetCount; int activeUpdates = a.ActiveUpdates;
        h.UpdateDead();
        Check(h.ActiveAbility == null && a.Deactivated == 1 && a.Exited == 1 && a.ResetCount == reset + 1, "death did not retire active ability before return");
        h.PreUpdate();
        Check(a.ActiveUpdates == activeUpdates && a.Deactivated == 1 && a.Exited == 1 && a.ResetCount == reset + 1, "retired ability ran again");
    }

    private static void DeathCancelsPending()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h); float stamina = h.Stamina;
        a.Activate(h); int sent = NetModule.Sends.Count;
        h.UpdateDead(); h.PreUpdate();
        Check(h.ActiveAbility == null && a.Activated == 0 && a.Deactivated == 0 && a.Exited == 0 && h.Stamina == stamina, "dead pending activation had hooks or cost");
        Check(NetModule.Sends.Count == sent, "death sent an ability-start packet");
    }

    private static void DeathFinishesDeactivation()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h);
        a.Activate(h); h.PreUpdate(); int reset = a.ResetCount;
        a.Deactivate();
        Check(a.Deactivated == 1 && a.Exited == 0, "explicit deactivation was not queued");
        h.UpdateDead(); h.PreUpdate();
        Check(h.ActiveAbility == null && a.Deactivated == 1 && a.Exited == 1 && a.ResetCount == reset + 1, "death doubled deactivation or skipped exit");
    }

    private static void DeathRepeated()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h);
        a.Activate(h); h.PreUpdate(); int reset = a.ResetCount;
        h.UpdateDead(); h.UpdateDead(); h.UpdateDead(); h.PreUpdate();
        Check(h.ActiveAbility == null && a.Deactivated == 1 && a.Exited == 1 && a.ResetCount == reset + 1, "dead ticks repeated hooks");
    }

    private static void RespawnFreshActivation()
    {
        AbilityHandler h = Handler(); TestAbility a = Ready<TestAbility>(h);
        a.Activate(h); h.PreUpdate(); h.UpdateDead();
        h.OnRespawn(); float restored = h.Stamina;
        Check(restored == h.StaminaMax && h.ActiveAbility == null, "respawn kept stale active ability or stamina");
        h.PreUpdate(); Check(h.ActiveAbility == null && a.Activated == 1, "respawn replayed stale activation");
        a.Activate(h); h.PreUpdate();
        Check(ReferenceEquals(h.ActiveAbility, a) && a.Activated == 2 && h.Stamina == restored - 1, "fresh respawn activation failed or cost wrong");
    }

    private static void DeathCloneIndependent()
    {
        AbilityHandler h = Handler(); TestAbility source = Ready<TestAbility>(h);
        source.Activate(h); h.PreUpdate();
        var clone = (AbilityHandler)h.Clone(MainPlayer(1));
        Check(clone.ActiveAbility is TestAbility copied && !ReferenceEquals(copied, source), "clone did not own an independent active ability");
        TestAbility clonedAbility = (TestAbility)clone.ActiveAbility; int reset = clonedAbility.ResetCount;
        clone.UpdateDead();
        Check(clone.ActiveAbility == null && clonedAbility.Deactivated == 1 && clonedAbility.Exited == 1 && clonedAbility.ResetCount == reset + 1, "clone was not retired");
        Check(ReferenceEquals(h.ActiveAbility, source) && source.Deactivated == 0 && source.Exited == 0, "clone death affected source");
    }

    private static void ProgressSnapshot()
    {
        AbilityHandler h = Handler(); h.Shards.Add(9); h.Shards.Add(1); h.Unlock<HintAbility>(); h.Unlock<Dash>(); h.Unlock<Whip>(); var packet = Progress(0, h);
        Check(Field<int[]>(packet, "shards").SequenceEqual(new[] { 1, 9 }) && Field<byte>(packet, "unlocks") == 0b11100000, "snapshot not sorted/complete");
    }
    private static void ProgressReplace()
    {
        AbilityHandler target = Handler(0); target.Shards.Add(99); target.Unlock<Dash>(); AbilityHandler source = Handler(1); source.Shards.Add(2); source.Shards.Add(1); source.Unlock<HintAbility>(); source.Unlock<Whip>(); Invoke(Progress(0, source));
        Check(target.Shards.ToList().OrderBy(x => x).SequenceEqual(new[] { 1, 2 }) && !target.Unlocked<Dash>() && target.Unlocked<HintAbility>() && target.Unlocked<Whip>(), "managed progress not replaced");
    }
    private static void ProgressPreserveCustom()
    {
        AbilityHandler target = Handler(0); target.Unlock<TestAbility>(); AbilityHandler source = Handler(1); source.Unlock<Dash>(); Invoke(Progress(0, source)); Check(target.Unlocked<TestAbility>() && target.Unlocked<Dash>(), "custom unlock was removed");
    }
    private static void ProgressSpoof()
    {
        Terraria.Main.netMode = NetmodeID.Server; AbilityHandler target = Handler(0); target.Shards.Add(77); AbilityHandler source = Handler(1); source.Shards.Add(1); Invoke(Progress(0, source, sender: 1)); Check(target.Shards.Has(77) && !target.Shards.Has(1) && NetModule.Sends.Count == 0, "spoofed progress accepted");
    }
    private static void ProgressBadPlayer()
    {
        AbilityHandler source = Handler(); var packet = Progress(99, source); Invoke(packet); Check(NetModule.Sends.Count == 0, "invalid player relayed");
    }
    private static void ProgressDuplicate()
    {
        AbilityHandler target = Handler(); target.Shards.Add(77); var packet = Progress(0, target); SetField(packet, "shards", new[] { 1, 1 }); Invoke(packet); Check(target.Shards.Has(77) && !target.Shards.Has(1), "duplicate shards accepted");
    }
    private static void ProgressNegative()
    {
        AbilityHandler target = Handler(); target.Shards.Add(77); var packet = Progress(0, target); SetField(packet, "shards", new[] { -1 }); Invoke(packet); Check(target.Shards.ToList().SequenceEqual(new[] { 77 }), "negative shard accepted");
    }
    private static void ProgressExcessive()
    {
        AbilityHandler target = Handler(); target.Shards.Add(77); var packet = Progress(0, target); SetField(packet, "shards", Enumerable.Range(0, 4097).ToArray()); Invoke(packet); Check(target.Shards.ToList().SequenceEqual(new[] { 77 }), "excessive shards accepted");
    }
    private static void ProgressReservedMask()
    {
        AbilityHandler target = Handler(); target.Shards.Add(77); var packet = Progress(0, target); SetField(packet, "shards", new[] { 1 }); SetField(packet, "unlocks", (byte)1); Invoke(packet); Check(target.Shards.ToList().SequenceEqual(new[] { 77 }) && target.unlockedAbilities.Count == 0, "reserved mask accepted");
    }
    private static void ProgressRelay()
    {
        Terraria.Main.netMode = NetmodeID.Server; AbilityHandler h = Handler(); h.Shards.Add(1); var packet = Progress(0, h, sender: 0); Invoke(packet); Check(NetModule.Sends.Count == 1 && NetModule.Sends[0].Ignore == 0 && !NetModule.Sends[0].RunLocally, "valid progress relay invalid");
    }

    private static StartAbility StartPacket(int player, Ability ability, int sender = -1) => new(player, ability) { Sender = sender };
    private static void StartValid()
    {
        Terraria.Main.netMode = NetmodeID.Server; AbilityHandler h = Handler(); Dash dash = Ready<Dash>(h); float before = h.Stamina; Invoke(StartPacket(0, dash, 0)); Check(h.ActiveAbility == null && NetModule.Sends.Count == 1, "valid start not queued/relayed"); h.PreUpdate(); Check(ReferenceEquals(h.ActiveAbility, dash) && h.Stamina == before - 1, "valid start not applied");
    }
    private static void StartSpoof()
    {
        Terraria.Main.netMode = NetmodeID.Server; AbilityHandler h = Handler(); Dash dash = Ready<Dash>(h); Invoke(StartPacket(0, dash, 1)); h.PreUpdate(); Check(h.ActiveAbility == null && NetModule.Sends.Count == 0, "spoofed start accepted");
    }
    private static void StartBadPlayer()
    {
        Dash dash = Ready<Dash>(Handler()); Invoke(StartPacket(99, dash)); Check(NetModule.Sends.Count == 0, "bad player start relayed");
    }
    private static void StartUnknownType()
    {
        AbilityHandler h = Handler(); Dash dash = Ready<Dash>(h); var packet = StartPacket(0, dash); SetField(packet, "abTypeName", "Missing.Ability"); Invoke(packet); h.PreUpdate(); Check(h.ActiveAbility == null, "unknown type accepted");
    }
    private static void StartNonAbilityType()
    {
        AbilityHandler h = Handler(); Dash dash = Ready<Dash>(h); var packet = StartPacket(0, dash); SetField(packet, "abTypeName", typeof(string).FullName); Invoke(packet); h.PreUpdate(); Check(h.ActiveAbility == null, "non-ability type accepted");
    }
    private static void StartLocked()
    {
        AbilityHandler h = Handler(); h.Shards.Add(1); h.Shards.Add(2); h.Shards.Add(3); h.Stamina = h.StaminaMax; Invoke(StartPacket(0, new Dash())); h.PreUpdate(); Check(h.ActiveAbility == null, "locked ability accepted");
    }
    private static void StartInsufficient()
    {
        AbilityHandler h = Handler(); Dash dash = Unlock<Dash>(h); h.ResetEffects(); h.Stamina = 0; Invoke(StartPacket(0, dash)); h.PreUpdate(); Check(h.ActiveAbility == null && NetModule.Sends.Count == 0, "insufficient start accepted");
    }
    private static void StartDuplicate()
    {
        Terraria.Main.netMode = NetmodeID.Server; AbilityHandler h = Handler(); Dash dash = Ready<Dash>(h); float before = h.Stamina; var one = StartPacket(0, dash, 0); var two = StartPacket(0, dash, 0); Invoke(one); Invoke(two); h.PreUpdate(); Check(NetModule.Sends.Count == 1 && dash.Activated == 1 && h.Stamina == before - 1, "duplicate start charged/relayed twice");
    }
    private static void StartClient()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; AbilityHandler h = Handler(); Dash dash = Ready<Dash>(h); Invoke(StartPacket(0, dash)); h.PreUpdate(); Check(ReferenceEquals(h.ActiveAbility, dash) && NetModule.Sends.Count == 0, "client did not apply or relayed");
    }
}
