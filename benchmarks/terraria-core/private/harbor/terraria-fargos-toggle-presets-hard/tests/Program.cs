using System;
using System.Collections.Generic;
using System.Linq;
using FargowiltasSouls;
using FargowiltasSouls.Content.Items.Accessories.Enchantments;
using FargowiltasSouls.Core.AccessoryEffectSystem;
using FargowiltasSouls.Core.Toggler;
using GameCodeBench;
using Terraria;
using Terraria.IO;

internal static class ContractProgram
{
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["registry_load_replaces_toggle_map"] = RegistryLoadToggles,
        ["registry_load_replaces_header_set"] = RegistryLoadHeaders,
        ["registry_unload_releases_maps"] = RegistryUnload,
        ["registry_rejects_null_toggle"] = RegistryNullToggle,
        ["registry_rejects_null_effect"] = RegistryNullEffect,
        ["registry_rejects_missing_header"] = RegistryMissingHeader,
        ["registry_rejects_duplicate_effect"] = RegistryDuplicateEffect,
        ["registry_rejects_duplicate_full_name"] = RegistryDuplicateName,
        ["registry_failed_add_is_atomic"] = RegistryAtomicFailure,
        ["registry_rejects_null_header"] = RegistryNullHeader,

        ["backend_clones_registry_dictionary"] = BackendClonesDictionary,
        ["backend_clones_toggle_objects"] = BackendClonesToggles,
        ["backend_preserves_effect_defaults"] = BackendDefaults,
        ["backend_instances_are_isolated"] = BackendIsolation,
        ["backend_tryload_is_idempotent"] = BackendIdempotent,
        ["backend_accepts_empty_registry"] = BackendEmptyRegistry,
        ["backend_dedicated_server_skips_disk_save"] = BackendDedicated,

        ["config_load_uses_full_identity"] = ConfigFullIdentity,
        ["config_load_disambiguates_same_short_name"] = ConfigCollidingNames,
        ["config_load_skips_unknown_identity"] = ConfigUnknown,
        ["config_load_keeps_slots_independent"] = ConfigSlots,
        ["config_malformed_slot_does_not_block_later_slot"] = ConfigMalformedContinues,
        ["config_load_canonicalizes_effect_order"] = ConfigCanonicalOrder,

        ["config_save_writes_every_slot"] = SaveEverySlot,
        ["config_save_uses_full_identity"] = SaveFullIdentity,
        ["config_save_is_deterministic"] = SaveDeterministic,
        ["config_save_deduplicates_effects"] = SaveDeduplicates,
        ["config_save_clears_stale_null_slot"] = SaveClearsNull,
        ["config_save_flushes_once"] = SaveOnce,
        ["config_save_is_server_noop"] = SaveServerNoop,

        ["player_load_restores_registered_defaults"] = PlayerDefaults,
        ["player_load_targets_argument_not_local_player"] = PlayerTarget,
        ["player_load_matches_full_identity"] = PlayerFullIdentity,
        ["player_load_ignores_unknown_disabled_effect"] = PlayerUnknown,
        ["player_load_replaces_sync_snapshot"] = PlayerSyncSnapshot,
        ["set_all_mutates_only_backend"] = SetAllBackend,
        ["some_effects_targets_receiving_backend"] = SomeEffectsBackend,
        ["minimal_effects_targets_receiving_backend"] = MinimalEffectsBackend,
        ["some_effects_disables_registered_pet_family"] = SomeEffectsPet,
        ["built_in_presets_ignore_absent_registry_entries"] = BuiltInMissing,
        ["built_in_presets_leave_custom_storage_untouched"] = BuiltInStorage,
        ["uninitialized_player_load_is_noop"] = PlayerUninitialized,

        ["preset_save_captures_disabled_effects"] = PresetSaveDisabled,
        ["preset_save_is_sorted_and_unique"] = PresetSaveCanonical,
        ["preset_save_is_a_snapshot"] = PresetSaveSnapshot,
        ["preset_save_rejects_invalid_slots"] = PresetSaveInvalid,
        ["preset_save_is_server_noop"] = PresetSaveServer,
        ["preset_load_applies_to_local_backend"] = PresetLoadApplies,
        ["preset_load_does_not_consume_preset"] = PresetLoadPreserves,
        ["preset_load_restores_persistence_list"] = PresetLoadRestoresList,
        ["preset_load_reports_missing_without_mutation"] = PresetLoadMissing,
        ["preset_load_rejects_invalid_slots"] = PresetLoadInvalid,

        ["lookup_missing_toggle_is_null"] = LookupMissing,
        ["lookup_missing_bool_is_false"] = LookupMissingBool,
        ["set_missing_toggle_warns_without_throwing"] = SetMissing,
        ["set_registered_toggle_changes_value"] = SetRegistered,
        ["mutant_presence_suppresses_affected_effect"] = MutantAffected,
        ["mutant_presence_suppresses_minion_effect"] = MutantMinion,
        ["skip_checks_bypasses_mutant_suppression"] = MutantSkipped,
        ["mutant_presence_keeps_unaffected_effect"] = MutantUnaffected,

        ["definition_snapshots_identity_and_default"] = DefinitionIdentityAndDefault,
        ["definition_snapshots_presence_policy"] = DefinitionPresencePolicy,
        ["definition_materialization_ignores_source_toggle_mutation"] = DefinitionSourceToggleMutation,
        ["registry_rejects_empty_stable_identity"] = RegistryEmptyIdentity,
        ["lookup_throwing_foreign_identity_is_safe"] = LookupThrowingIdentity,
        ["canonical_presence_policy_ignores_alias_flags"] = CanonicalPresencePolicy,

        ["rebase_preserves_value_by_identity"] = RebasePreservesValue,
        ["rebase_adds_new_effect_at_registered_default"] = RebaseAddsDefault,
        ["rebase_drops_removed_effect"] = RebaseDropsRemoved,
        ["rebase_rebinds_preset_instances"] = RebaseRebindsPresets,
        ["rebase_canonicalizes_preset_identities"] = RebaseCanonicalPresets,
        ["rebase_keeps_player_backends_isolated"] = RebaseKeepsIsolation,
        ["rebase_does_not_reload_preferences"] = RebaseNoPreferenceIo,
        ["lookup_reconciles_before_resolution"] = LookupReconciles,
        ["set_all_reconciles_before_mutation"] = SetAllReconciles,
        ["player_load_sync_uses_rebased_instances"] = PlayerLoadUsesRebasedInstances,
        ["rebase_preserves_disabled_list_reference"] = RebasePreservesDisabledList,
        ["rebase_discards_candidate_on_registry_reentrancy"] = RebaseDiscardsReentrantCandidate,
        ["rebase_retries_new_generation_on_next_entry"] = RebaseRetriesAfterReentrancy,
        ["unload_rebases_initialized_backend_to_empty"] = RebaseAfterUnload,
        ["live_registration_rebases_without_reload"] = RebaseAfterLiveRegistration,
        ["failed_registration_does_not_rebase_backend"] = FailedRegistrationDoesNotRebase,
    };

    public static int Main(string[] args)
    {
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out Action test)) return 2;
        try { TestHooks.Reset(); test(); Console.WriteLine("PASS"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void RejectRegistration(Action action)
    {
        try { action(); }
        catch (Exception) { }
    }

    private static Toggle Register(AccessoryEffect effect, string mod = "TestMod")
    {
        var toggle = new Toggle(effect, mod);
        ToggleLoader.RegisterToggle(toggle);
        return toggle;
    }

    private static ToggleBackend Backend(params AccessoryEffect[] effects)
    {
        foreach (AccessoryEffect effect in effects) Register(effect);
        var backend = new ToggleBackend();
        backend.TryLoad();
        return backend;
    }

    private static void ReplaceRegistry(params AccessoryEffect[] effects)
    {
        ToggleLoader.Load();
        foreach (AccessoryEffect effect in effects)
            Register(effect);
    }

    private static Dictionary<string, bool> Packed(params string[] names) =>
        names.ToDictionary(name => name, _ => false, StringComparer.Ordinal);

    private static IReadOnlyList<string> Keys(ToggleBackend backend, int slot) =>
        ((Dictionary<string, bool>)backend.Config.Data[$"CustomPresetsOff{slot}"]).Keys.ToList();

    private static void UseLocal(ToggleBackend backend)
    {
        Terraria.Main.LocalPlayer.Souls.Toggler = backend;
    }

    private static void RegistryLoadToggles()
    {
        Dictionary<AccessoryEffect, Toggle> previous = ToggleLoader.LoadedToggles;
        Register(new NamedEffect("A", "Mod.A"));
        ToggleLoader.Load();
        Check(!ReferenceEquals(previous, ToggleLoader.LoadedToggles) && ToggleLoader.LoadedToggles.Count == 0, "toggle registry was reused");
    }

    private static void RegistryLoadHeaders()
    {
        HashSet<Header> previous = ToggleLoader.LoadedHeaders;
        ToggleLoader.RegisterHeader(new Header());
        ToggleLoader.Load();
        Check(!ReferenceEquals(previous, ToggleLoader.LoadedHeaders) && ToggleLoader.LoadedHeaders.Count == 0, "header registry was reused");
    }

    private static void RegistryUnload()
    {
        Register(new NamedEffect("A", "Mod.A"));
        ToggleLoader.RegisterHeader(new Header());
        ToggleLoader.Unload();
        Check(ToggleLoader.LoadedToggles == null && ToggleLoader.LoadedHeaders == null, "unload retained global collections");
    }

    private static void RegistryNullToggle()
    {
        ToggleLoader.Unload();
        RejectRegistration(() => ToggleLoader.RegisterToggle(null));
        Check(ToggleLoader.LoadedToggles == null, "rejected toggle initialized the registry");
    }

    private static void RegistryNullEffect()
    {
        ToggleLoader.Unload();
        var toggle = new Toggle(new NamedEffect("A", "Mod.A"), "Mod") { Effect = null };
        RejectRegistration(() => ToggleLoader.RegisterToggle(toggle));
        Check(ToggleLoader.LoadedToggles == null, "null effect initialized the registry");
    }

    private static void RegistryMissingHeader()
    {
        ToggleLoader.Unload();
        RejectRegistration(() => Register(new NamedEffect("A", "Mod.A", header: false)));
        Check(ToggleLoader.LoadedToggles == null, "headerless effect initialized the registry");
    }

    private static void RegistryDuplicateEffect()
    {
        var effect = new NamedEffect("A", "Mod.A"); Toggle first = Register(effect);
        RejectRegistration(() => Register(effect));
        Check(ToggleLoader.LoadedToggles.Count == 1 && ReferenceEquals(ToggleLoader.LoadedToggles[effect], first), "same effect changed the registry");
    }

    private static void RegistryDuplicateName()
    {
        AccessoryEffect first = new NamedEffect("A", "Mod.A"); Register(first);
        RejectRegistration(() => Register(new NamedEffect("Other", "Mod.A")));
        Check(ToggleLoader.LoadedToggles.Count == 1 && ToggleLoader.LoadedToggles.ContainsKey(first), "duplicate full identity changed the registry");
    }

    private static void RegistryAtomicFailure()
    {
        AccessoryEffect first = new NamedEffect("A", "Mod.A"); Register(first);
        RejectRegistration(() => Register(new NamedEffect("B", "Mod.A")));
        Check(ToggleLoader.LoadedToggles.Count == 1 && ToggleLoader.LoadedToggles.ContainsKey(first), "failed registration mutated registry");
    }

    private static void RegistryNullHeader()
    {
        ToggleLoader.Unload();
        RejectRegistration(() => ToggleLoader.RegisterHeader(null));
        Check(ToggleLoader.LoadedHeaders == null, "rejected header initialized the registry");
    }

    private static void BackendClonesDictionary()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect);
        Check(!ReferenceEquals(backend.Toggles, ToggleLoader.LoadedToggles) && backend.Toggles.ContainsKey(effect), "backend aliases registry dictionary");
    }

    private static void BackendClonesToggles()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); Toggle original = Register(effect); var backend = new ToggleBackend(); backend.TryLoad();
        Check(!ReferenceEquals(original, backend.Toggles[effect]), "backend aliases registry toggle");
    }

    private static void BackendDefaults()
    {
        AccessoryEffect off = new NamedEffect("Off", "Mod.Off", defaultToggle: false); ToggleBackend backend = Backend(off);
        Check(!backend.Toggles[off].ToggleBool, "effect default was discarded");
    }

    private static void BackendIsolation()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); Register(effect); var first = new ToggleBackend(); var second = new ToggleBackend(); first.TryLoad(); second.TryLoad();
        first.Toggles[effect].ToggleBool = false;
        Check(second.Toggles[effect].ToggleBool && ToggleLoader.LoadedToggles[effect].ToggleBool, "toggle state leaked between owners");
    }

    private static void BackendIdempotent()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); Preferences config = backend.Config; Toggle toggle = backend.Toggles[effect];
        Preferences.NextData = new() { ["CustomPresetsOff1"] = Packed("Mod.A") }; backend.TryLoad();
        Check(ReferenceEquals(config, backend.Config) && ReferenceEquals(toggle, backend.Toggles[effect]) && backend.CustomPresets[0] == null, "second load replaced live state");
    }

    private static void BackendEmptyRegistry()
    {
        var backend = new ToggleBackend(); backend.TryLoad();
        Check(backend.Initialized && backend.Toggles.Count == 0, "empty registry failed initialization");
    }

    private static void BackendDedicated()
    {
        Terraria.Main.dedServ = true; Preferences.NextLoadResult = false; var backend = Backend(new NamedEffect("A", "Mod.A"));
        Check(backend.Initialized && Preferences.TotalSaves == 0 && backend.CustomPresets.All(slot => slot == null), "dedicated initialization touched disk-backed state");
    }

    private static void ConfigFullIdentity()
    {
        Preferences.NextData = new() { ["CustomPresetsOff1"] = Packed("Other.A", "Mod.A") };
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect);
        Check(backend.CustomPresets[0].SequenceEqual(new[] { effect }), "full identity was not loaded");
    }

    private static void ConfigCollidingNames()
    {
        Preferences.NextData = new() { ["CustomPresetsOff1"] = Packed("One.Shared") };
        AccessoryEffect one = new NamedEffect("Shared", "One.Shared"); AccessoryEffect two = new NamedEffect("Shared", "Two.Shared"); ToggleBackend backend = Backend(two, one);
        Check(backend.CustomPresets[0].SequenceEqual(new[] { one }), "short-name collision selected wrong mod effect");
    }

    private static void ConfigUnknown()
    {
        Preferences.NextData = new() { ["CustomPresetsOff1"] = Packed("Missing.Effect") };
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A"));
        Check(backend.CustomPresets[0] != null && backend.CustomPresets[0].Count == 0, "unknown identity polluted preset");
    }

    private static void ConfigSlots()
    {
        Preferences.NextData = new() { ["CustomPresetsOff1"] = Packed("Mod.A"), ["CustomPresetsOff2"] = Packed("Mod.B") };
        AccessoryEffect a = new NamedEffect("A", "Mod.A"); AccessoryEffect b = new NamedEffect("B", "Mod.B"); ToggleBackend backend = Backend(a, b);
        Check(backend.CustomPresets[0].SequenceEqual(new[] { a }) && backend.CustomPresets[1].SequenceEqual(new[] { b }) && !ReferenceEquals(backend.CustomPresets[0], backend.CustomPresets[1]), "preset slots were merged or aliased");
    }

    private static void ConfigMalformedContinues()
    {
        Preferences.ThrowOnGet.Add("CustomPresetsOff1"); Preferences.NextData = new() { ["CustomPresetsOff2"] = Packed("Mod.B") };
        AccessoryEffect b = new NamedEffect("B", "Mod.B"); ToggleBackend backend = Backend(b);
        Check(backend.CustomPresets[0] == null && backend.CustomPresets[1].SequenceEqual(new[] { b }), "one malformed slot aborted later slots");
    }

    private static void ConfigCanonicalOrder()
    {
        Preferences.NextData = new() { ["CustomPresetsOff1"] = Packed("Mod.C", "Mod.A", "Mod.B") };
        ToggleBackend backend = Backend(new NamedEffect("C", "Mod.C"), new NamedEffect("B", "Mod.B"), new NamedEffect("A", "Mod.A"));
        Check(backend.CustomPresets[0].Select(x => x.FullName).SequenceEqual(new[] { "Mod.A", "Mod.B", "Mod.C" }), "loaded preset is nondeterministic");
    }

    private static void SaveEverySlot()
    {
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A")); backend.Save();
        Check(Enumerable.Range(1, 3).All(i => backend.Config.Data.ContainsKey($"CustomPresetsOff{i}")), "not every slot was serialized");
    }

    private static void SaveFullIdentity()
    {
        AccessoryEffect effect = new NamedEffect("Short", "Mod.Long.Identity"); ToggleBackend backend = Backend(effect); backend.CustomPresets[0] = [effect]; backend.Save();
        Check(Keys(backend, 1).SequenceEqual(new[] { "Mod.Long.Identity" }), "save used unstable short name");
    }

    private static void SaveDeterministic()
    {
        AccessoryEffect c = new NamedEffect("C", "Mod.C"); AccessoryEffect a = new NamedEffect("A", "Mod.A"); AccessoryEffect b = new NamedEffect("B", "Mod.B"); ToggleBackend backend = Backend(c, a, b); backend.CustomPresets[0] = [c, a, b]; backend.Save();
        Check(Keys(backend, 1).SequenceEqual(new[] { "Mod.A", "Mod.B", "Mod.C" }), "serialized order is not canonical");
    }

    private static void SaveDeduplicates()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); backend.CustomPresets[0] = [effect, effect, new NamedEffect("Alias", "Mod.A")]; backend.Save();
        Check(Keys(backend, 1).SequenceEqual(new[] { "Mod.A" }), "duplicate identities were serialized");
    }

    private static void SaveClearsNull()
    {
        Preferences.NextData = new() { ["CustomPresetsOff1"] = Packed("Mod.A") };
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A")); backend.CustomPresets[0] = null; backend.Save();
        Check(Keys(backend, 1).Count == 0, "null slot left stale disk data");
    }

    private static void SaveOnce()
    {
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A")); int before = backend.Config.SaveCount; backend.Save();
        Check(backend.Config.SaveCount == before + 1, "save did not flush exactly once");
    }

    private static void SaveServerNoop()
    {
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A")); Terraria.Main.dedServ = true; int before = backend.Config.SaveCount; backend.Save();
        Check(backend.Config.SaveCount == before && backend.Config.Data.Count == 0, "server save mutated config");
    }

    private static void PlayerDefaults()
    {
        AccessoryEffect on = new NamedEffect("On", "Mod.On"); AccessoryEffect off = new NamedEffect("Off", "Mod.Off", defaultToggle: false); ToggleBackend backend = Backend(on, off); backend.SetAll(true); var player = new FargoSoulsPlayer(); backend.LoadPlayerToggles(player);
        Check(backend.Toggles[on].ToggleBool && !backend.Toggles[off].ToggleBool, "registered defaults were replaced by all-on");
    }

    private static void PlayerTarget()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend target = Backend(effect); var localBackend = new ToggleBackend(); localBackend.TryLoad(); Terraria.Main.LocalPlayer.Souls.Toggler = localBackend; var targetPlayer = new FargoSoulsPlayer { Toggler = target, disabledToggles = [effect] };
        target.LoadPlayerToggles(targetPlayer);
        Check(!target.Toggles[effect].ToggleBool && localBackend.Toggles[effect].ToggleBool, "load changed Main.LocalPlayer instead of argument backend");
    }

    private static void PlayerFullIdentity()
    {
        AccessoryEffect registered = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(registered); var player = new FargoSoulsPlayer { disabledToggles = [new NamedEffect("Renamed", "Mod.A")] }; backend.LoadPlayerToggles(player);
        Check(!backend.Toggles[registered].ToggleBool, "equivalent persisted identity was not applied");
    }

    private static void PlayerUnknown()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); var player = new FargoSoulsPlayer { disabledToggles = [new NamedEffect("Missing", "Other.Missing")] }; backend.LoadPlayerToggles(player);
        Check(backend.Toggles[effect].ToggleBool, "unknown disabled effect changed registered state");
    }

    private static void PlayerSyncSnapshot()
    {
        AccessoryEffect a = new NamedEffect("A", "Mod.A"); AccessoryEffect b = new NamedEffect("B", "Mod.B", defaultToggle: false); ToggleBackend backend = Backend(a, b); var stale = new NamedEffect("Stale", "Mod.Stale"); var player = new FargoSoulsPlayer(); player.TogglesToSync[stale] = true; backend.LoadPlayerToggles(player);
        Check(player.TogglesToSync.Count == 2 && player.TogglesToSync[a] && !player.TogglesToSync[b] && !player.TogglesToSync.ContainsKey(stale), "sync state was merged instead of replaced");
    }

    private static void SetAllBackend()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); var local = new ToggleBackend(); local.TryLoad(); Terraria.Main.LocalPlayer.Souls.Toggler = local; backend.SetAll(false);
        Check(!backend.Toggles[effect].ToggleBool && local.Toggles[effect].ToggleBool, "SetAll routed through local player");
    }

    private static void SomeEffectsBackend()
    {
        var boreal = new BorealEffect(); var mythril = new MythrilEffect(); ToggleBackend backend = Backend(boreal, mythril);
        var local = new ToggleBackend(); local.TryLoad(); UseLocal(local);
        backend.SetAll(false); backend.SomeEffects();
        Check(!backend.Toggles[boreal].ToggleBool && backend.Toggles[mythril].ToggleBool, "SomeEffects did not apply its listed choices to the receiving backend");
        Check(local.Toggles[boreal].ToggleBool && local.Toggles[mythril].ToggleBool, "SomeEffects changed the local player's separate backend");
    }

    private static void MinimalEffectsBackend()
    {
        var boreal = new BorealEffect(); var mythril = new MythrilEffect(); ToggleBackend backend = Backend(boreal, mythril);
        var local = new ToggleBackend(); local.TryLoad(); local.SetAll(false); UseLocal(local);
        backend.MinimalEffects();
        Check(!backend.Toggles[boreal].ToggleBool && backend.Toggles[mythril].ToggleBool, "MinimalEffects did not apply its listed choices to the receiving backend");
        Check(!local.Toggles[boreal].ToggleBool && !local.Toggles[mythril].ToggleBool, "MinimalEffects changed the local player's separate backend");
    }

    private static void SomeEffectsPet()
    {
        var pet = new NamedEffect("CutePet", "Mod.CutePet"); ToggleBackend backend = Backend(pet);
        var local = new ToggleBackend(); local.TryLoad(); UseLocal(local);
        backend.SomeEffects();
        Check(!backend.Toggles[pet].ToggleBool && local.Toggles[pet].ToggleBool, "registered Pet choice targeted the wrong backend");
    }

    private static void BuiltInMissing()
    {
        var mythril = new MythrilEffect(); ToggleBackend backend = Backend(mythril);
        var local = new ToggleBackend(); local.TryLoad(); UseLocal(local);
        backend.SomeEffects(); backend.MinimalEffects();
        Check(backend.Toggles.Count == 1 && local.Toggles.Count == 1, "built-in preset inserted absent effects");
        Check(global::FargowiltasSouls.FargowiltasSouls.Instance.Logger.Warnings.Count == 0, "absent built-in choices produced warnings");
    }

    private static void BuiltInStorage()
    {
        var mythril = new MythrilEffect(); ToggleBackend backend = Backend(mythril);
        var preset = new List<AccessoryEffect> { mythril }; var disabled = new List<AccessoryEffect> { mythril };
        backend.CustomPresets[0] = preset; Terraria.Main.LocalPlayer.Souls.disabledToggles = disabled;
        int saves = Preferences.TotalSaves; backend.SomeEffects(); backend.MinimalEffects();
        Check(ReferenceEquals(backend.CustomPresets[0], preset) && preset.SequenceEqual(new[] { mythril }), "built-in preset changed custom storage");
        Check(ReferenceEquals(Terraria.Main.LocalPlayer.Souls.disabledToggles, disabled) && disabled.SequenceEqual(new[] { mythril }), "built-in preset replaced disabled list");
        Check(Preferences.TotalSaves == saves, "built-in preset wrote preferences");
    }

    private static void PlayerUninitialized()
    {
        var backend = new ToggleBackend(); var effect = new NamedEffect("A", "Mod.A"); backend.Toggles[effect] = new Toggle(effect, "Mod"); var player = new FargoSoulsPlayer { disabledToggles = [effect] }; backend.LoadPlayerToggles(player);
        Check(backend.Toggles[effect].ToggleBool && player.TogglesToSync.Count == 0, "uninitialized backend mutated player state");
    }

    private static void PresetSaveDisabled()
    {
        AccessoryEffect a = new NamedEffect("A", "Mod.A"); AccessoryEffect b = new NamedEffect("B", "Mod.B"); ToggleBackend backend = Backend(a, b); backend.Toggles[b].ToggleBool = false; backend.SaveCustomPreset(1);
        Check(backend.CustomPresets[0].SequenceEqual(new[] { b }), "preset did not capture exactly disabled effects");
    }

    private static void PresetSaveCanonical()
    {
        AccessoryEffect c = new NamedEffect("C", "Mod.C"); AccessoryEffect a = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(c, a); backend.SetAll(false); backend.SaveCustomPreset(1);
        Check(backend.CustomPresets[0].Select(x => x.FullName).SequenceEqual(new[] { "Mod.A", "Mod.C" }), "captured preset is not canonical");
    }

    private static void PresetSaveSnapshot()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); backend.SetAll(false); backend.SaveCustomPreset(1); backend.SetAll(true);
        Check(backend.CustomPresets[0].SequenceEqual(new[] { effect }), "live toggle change rewrote preset snapshot");
    }

    private static void PresetSaveInvalid()
    {
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A")); backend.SaveCustomPreset(0); backend.SaveCustomPreset(4);
        Check(backend.CustomPresets.All(slot => slot == null) && Terraria.Main.Messages.Count == 0, "invalid save slot mutated state or emitted success");
    }

    private static void PresetSaveServer()
    {
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A")); backend.SetAll(false); Terraria.Main.dedServ = true; backend.SaveCustomPreset(1);
        Check(backend.CustomPresets[0] == null && Terraria.Main.Messages.Count == 0, "server captured client preset");
    }

    private static void PresetLoadApplies()
    {
        AccessoryEffect a = new NamedEffect("A", "Mod.A"); AccessoryEffect b = new NamedEffect("B", "Mod.B"); ToggleBackend backend = Backend(a, b); UseLocal(backend); backend.CustomPresets[0] = [b]; backend.LoadCustomPreset(1);
        Check(backend.Toggles[a].ToggleBool && !backend.Toggles[b].ToggleBool && Terraria.Main.LocalPlayer.Souls.TogglesToSync.Count == 2, "preset was not applied through player load path");
    }

    private static void PresetLoadPreserves()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); UseLocal(backend); var preset = new List<AccessoryEffect> { effect }; backend.CustomPresets[0] = preset; backend.LoadCustomPreset(1);
        Check(ReferenceEquals(backend.CustomPresets[0], preset) && preset.SequenceEqual(new[] { effect }), "load consumed or replaced saved preset");
    }

    private static void PresetLoadRestoresList()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); UseLocal(backend); var previous = new List<AccessoryEffect> { new NamedEffect("Old", "Mod.Old") }; Terraria.Main.LocalPlayer.Souls.disabledToggles = previous; backend.CustomPresets[0] = [effect]; backend.LoadCustomPreset(1);
        Check(ReferenceEquals(Terraria.Main.LocalPlayer.Souls.disabledToggles, previous), "temporary preset replaced persistence list");
    }

    private static void PresetLoadMissing()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); UseLocal(backend); backend.SetAll(false); backend.LoadCustomPreset(1);
        Check(!backend.Toggles[effect].ToggleBool && Terraria.Main.Messages.Count == 1 && Terraria.Main.LocalPlayer.Souls.TogglesToSync.Count == 0, "missing preset mutated toggles or was not reported");
    }

    private static void PresetLoadInvalid()
    {
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A")); UseLocal(backend); backend.LoadCustomPreset(0); backend.LoadCustomPreset(4);
        Check(Terraria.Main.Messages.Count == 0 && Terraria.Main.LocalPlayer.Souls.TogglesToSync.Count == 0, "invalid load slot had side effects");
    }

    private static void LookupMissing()
    {
        var player = new Player(); player.Souls.Toggler.TryLoad();
        Check(player.GetToggle(new NamedEffect("A", "Mod.A")) == null && ((Player)null).GetToggle(new NamedEffect("A", "Mod.A")) == null, "missing lookup did not return null");
    }

    private static void LookupMissingBool()
    {
        var player = new Player(); player.Souls.Toggler.TryLoad();
        Check(!player.GetPlayerBoolValue(new NamedEffect("A", "Mod.A")) && !player.GetToggleValue((AccessoryEffect)null), "missing bool lookup was not false");
    }

    private static void SetMissing()
    {
        var player = new Player(); player.Souls.Toggler.TryLoad(); player.SetToggleValue(new NamedEffect("A", "Mod.A"), false);
        Check(FargowiltasSouls.FargowiltasSouls.Instance.Logger.Warnings.Count == 1, "missing set did not emit one warning");
    }

    private static void SetRegistered()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); var player = new Player(); player.Souls.Toggler = backend; player.SetToggleValue(new NamedEffect("Alias", "Mod.A"), false);
        Check(!backend.Toggles[effect].ToggleBool, "stable-identity set did not update registered toggle");
    }

    private static void MutantAffected() => MutantCase(new NamedEffect("A", "Mod.A", mutant: true), false);
    private static void MutantMinion() => MutantCase(new NamedEffect("A", "Mod.A", minion: true), false);
    private static void MutantSkipped() => MutantCase(new NamedEffect("A", "Mod.A", mutant: true), true);

    private static void MutantUnaffected()
    {
        AccessoryEffect effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect); var player = new Player(); player.Souls.Toggler = backend; player.Souls.MutantPresence = true;
        Check(player.GetToggleValue(effect), "unaffected effect was suppressed");
    }

    private static void MutantCase(AccessoryEffect effect, bool skip)
    {
        ToggleBackend backend = Backend(effect); var player = new Player(); player.Souls.Toggler = backend; player.Souls.MutantPresence = true;
        Check(player.GetToggleValue(effect, skipChecks: skip) == skip, "mutant presence check produced wrong value");
    }

    private static void DefinitionIdentityAndDefault()
    {
        var effect = new MutableEffect("A", "Mod.A", defaultToggle: false);
        Header registeredHeader = effect.HeaderValue;
        Register(effect);
        effect.FullIdentity = "Changed.A";
        effect.DefaultValue = true;
        effect.HeaderValue = new Header { SortCategory = "Changed" };
        var backend = new ToggleBackend(); backend.TryLoad();
        Toggle materialized = backend.Toggles.Values.Single();
        var playerView = new Player(); playerView.Souls.Toggler = backend;
        Check(ReferenceEquals(playerView.GetToggle(new NamedEffect("Alias", "Mod.A")), materialized) &&
            playerView.GetToggle(new NamedEffect("Alias", "Changed.A")) == null && !materialized.ToggleBool,
            "backend resampled mutable identity or default metadata");
        Check(ReferenceEquals(materialized.Header, registeredHeader), "backend resampled mutable header metadata");
        var player = new FargoSoulsPlayer { Toggler = backend };
        materialized.ToggleBool = true;
        backend.LoadPlayerToggles(player);
        Check(!materialized.ToggleBool, "player restore resampled a changed default");
    }

    private static void DefinitionPresencePolicy()
    {
        var effect = new MutableEffect("A", "Mod.A", mutant: true);
        ToggleBackend backend = Backend(effect);
        effect.Mutant = false;
        var player = new Player(); player.Souls.Toggler = backend; player.Souls.MutantPresence = true;
        Check(!player.GetToggleValue(effect), "runtime policy resampled mutable registered metadata");
    }

    private static void DefinitionSourceToggleMutation()
    {
        var registered = new NamedEffect("A", "Mod.A");
        Toggle definition = Register(registered, "OriginalMod");
        definition.Effect = new NamedEffect("Other", "Other.Effect", defaultToggle: false);
        definition.Mod = "ChangedMod";
        var backend = new ToggleBackend(); backend.TryLoad();
        Toggle materialized = backend.Toggles[registered];
        var player = new Player(); player.Souls.Toggler = backend;
        Check(ReferenceEquals(materialized.Effect, registered) && materialized.Mod == "OriginalMod" &&
            ReferenceEquals(player.GetToggle(new NamedEffect("Alias", "Mod.A")), materialized) && materialized.ToggleBool,
            "backend trusted mutable source-toggle fields instead of the registered snapshot");
    }

    private static void RegistryEmptyIdentity()
    {
        ToggleLoader.Unload();
        RejectRegistration(() => Register(new MutableEffect("A", "")));
        Check(ToggleLoader.LoadedToggles == null, "empty stable identity initialized or mutated the registry");
    }

    private static void LookupThrowingIdentity()
    {
        ToggleBackend backend = Backend(new NamedEffect("A", "Mod.A"));
        var player = new Player(); player.Souls.Toggler = backend;
        var foreign = new ThrowingIdentityEffect();
        Check(player.GetToggle(foreign) == null && !player.GetToggleValue(foreign) && !player.GetPlayerBoolValue(foreign),
            "throwing foreign identity escaped a safe lookup boundary");
        player.SetToggleValue(foreign, false);
        Check(FargowiltasSouls.FargowiltasSouls.Instance.Logger.Warnings.Count == 0,
            "malformed foreign identity emitted a warning while being rejected");
    }

    private static void CanonicalPresencePolicy()
    {
        var registered = new NamedEffect("A", "Mod.A", mutant: true);
        ToggleBackend backend = Backend(registered);
        var player = new Player(); player.Souls.Toggler = backend; player.Souls.MutantPresence = true;
        var harmlessAlias = new NamedEffect("Alias", "Mod.A", mutant: false);
        Check(!player.GetToggleValue(harmlessAlias), "foreign alias bypassed registered suppression policy");

        registered = new NamedEffect("B", "Mod.B", mutant: false);
        ReplaceRegistry(registered); backend.TryLoad();
        var hostileAlias = new NamedEffect("Alias", "Mod.B", mutant: true);
        Check(player.GetToggleValue(hostileAlias), "foreign alias imposed unregistered suppression policy");
    }

    private static void RebasePreservesValue()
    {
        var oldEffect = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(oldEffect);
        backend.Toggles[oldEffect].ToggleBool = false;
        var replacement = new NamedEffect("New", "Mod.A"); ReplaceRegistry(replacement); backend.TryLoad();
        Check(backend.Toggles.Count == 1 && backend.Toggles.ContainsKey(replacement) &&
            !backend.Toggles[replacement].ToggleBool && !backend.Toggles.ContainsKey(oldEffect),
            "registry replacement lost value or retained the old effect instance");
    }

    private static void RebaseAddsDefault()
    {
        var oldEffect = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(oldEffect);
        var replacement = new NamedEffect("New", "Mod.A");
        var added = new NamedEffect("Added", "Mod.B", defaultToggle: false);
        ReplaceRegistry(replacement, added); backend.TryLoad();
        Check(!backend.Toggles[added].ToggleBool, "new generation ignored the registered default");
    }

    private static void RebaseDropsRemoved()
    {
        var a = new NamedEffect("A", "Mod.A"); var b = new NamedEffect("B", "Mod.B");
        ToggleBackend backend = Backend(a, b);
        var replacement = new NamedEffect("A2", "Mod.A"); ReplaceRegistry(replacement); backend.TryLoad();
        Check(backend.Toggles.Count == 1 && backend.Toggles.ContainsKey(replacement),
            "removed registry identity survived player-local rebase");
    }

    private static void RebaseRebindsPresets()
    {
        var old = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(old);
        backend.CustomPresets[0] = [old];
        var replacement = new NamedEffect("New", "Mod.A"); ReplaceRegistry(replacement); backend.TryLoad();
        Check(backend.CustomPresets[0].Count == 1 && ReferenceEquals(backend.CustomPresets[0][0], replacement),
            "preset retained a stale registry object after rebase");
    }

    private static void RebaseCanonicalPresets()
    {
        var a = new NamedEffect("A", "Mod.A"); var b = new NamedEffect("B", "Mod.B");
        ToggleBackend backend = Backend(a, b);
        backend.CustomPresets[0] = [b, a, new NamedEffect("Alias", "Mod.A"), b, new NamedEffect("Gone", "Mod.Gone")];
        var newB = new NamedEffect("B2", "Mod.B"); var newA = new NamedEffect("A2", "Mod.A");
        ReplaceRegistry(newB, newA); backend.TryLoad();
        Check(backend.CustomPresets[0].SequenceEqual(new AccessoryEffect[] { newA, newB }),
            "rebased preset was not filtered, unique, ordered, and rebound");
    }

    private static void RebaseKeepsIsolation()
    {
        var old = new NamedEffect("Old", "Mod.A"); Register(old);
        var first = new ToggleBackend(); var second = new ToggleBackend(); first.TryLoad(); second.TryLoad();
        first.Toggles[old].ToggleBool = false;
        var replacement = new NamedEffect("New", "Mod.A"); ReplaceRegistry(replacement);
        first.TryLoad(); second.TryLoad();
        Check(!first.Toggles[replacement].ToggleBool && second.Toggles[replacement].ToggleBool &&
            !ReferenceEquals(first.Toggles[replacement], second.Toggles[replacement]),
            "registry rebase aliased or merged player-local values");
    }

    private static void RebaseNoPreferenceIo()
    {
        var old = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(old);
        Preferences config = backend.Config; int saves = Preferences.TotalSaves; int ownSaves = config.SaveCount;
        Preferences.NextData = new() { ["CustomPresetsOff1"] = Packed("Mod.Other") };
        var replacement = new NamedEffect("New", "Mod.A"); ReplaceRegistry(replacement); backend.TryLoad();
        Check(ReferenceEquals(config, backend.Config) && Preferences.TotalSaves == saves && config.SaveCount == ownSaves,
            "live registry rebase reloaded or flushed preferences");
    }

    private static void LookupReconciles()
    {
        var old = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(old);
        var player = new Player(); player.Souls.Toggler = backend;
        var replacement = new NamedEffect("New", "Mod.A"); ReplaceRegistry(replacement);
        Toggle resolved = player.GetToggle(new NamedEffect("Alias", "Mod.A"));
        Check(resolved != null && ReferenceEquals(resolved.Effect, replacement) && backend.Toggles.ContainsKey(replacement),
            "runtime lookup observed stale registry generation");
    }

    private static void SetAllReconciles()
    {
        var old = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(old);
        var replacement = new NamedEffect("New", "Mod.A"); var added = new NamedEffect("Added", "Mod.B");
        ReplaceRegistry(replacement, added); backend.SetAll(false);
        Check(backend.Toggles.Count == 2 && backend.Toggles.Values.All(toggle => !toggle.ToggleBool),
            "bulk mutation ran against a stale generation");
    }

    private static void PlayerLoadUsesRebasedInstances()
    {
        var old = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(old);
        var replacement = new NamedEffect("New", "Mod.A"); ReplaceRegistry(replacement);
        var player = new FargoSoulsPlayer { Toggler = backend, disabledToggles = [new NamedEffect("Alias", "Mod.A")] };
        backend.LoadPlayerToggles(player);
        Check(player.TogglesToSync.Count == 1 && player.TogglesToSync.ContainsKey(replacement) && !player.TogglesToSync[replacement],
            "player snapshot retained an old-generation effect key");
    }

    private static void RebasePreservesDisabledList()
    {
        var old = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(old);
        var disabled = new List<AccessoryEffect> { old };
        Terraria.Main.LocalPlayer.Souls.Toggler = backend;
        Terraria.Main.LocalPlayer.Souls.disabledToggles = disabled;
        var replacement = new NamedEffect("New", "Mod.A"); ReplaceRegistry(replacement); backend.SetAll(false);
        Check(ReferenceEquals(Terraria.Main.LocalPlayer.Souls.disabledToggles, disabled) && disabled.SequenceEqual(new[] { old }),
            "registry rebase rewrote persistent player input state");
    }

    private static ToggleBackend ReentrantRebase(out Dictionary<AccessoryEffect, Toggle> before, out AccessoryEffect replacement, out AccessoryEffect injected)
    {
        var old = new NamedEffect("Old", "Mod.A"); ToggleBackend backend = Backend(old);
        before = backend.Toggles;
        replacement = new NamedEffect("New", "Mod.A");
        AccessoryEffect injectedEffect = new NamedEffect("Injected", "Mod.Injected");
        injected = injectedEffect;
        bool fired = false;
        backend.CustomPresets[0] = [new ReentrantIdentityEffect("Mod.A", () =>
        {
            if (!fired)
            {
                fired = true;
                Register(injectedEffect);
            }
        })];
        ReplaceRegistry(replacement);
        return backend;
    }

    private static void RebaseDiscardsReentrantCandidate()
    {
        ToggleBackend backend = ReentrantRebase(out Dictionary<AccessoryEffect, Toggle> before, out _, out _);
        backend.TryLoad();
        Check(ReferenceEquals(backend.Toggles, before) && backend.Toggles.Count == 1,
            "generation changed mid-rebase but the mixed candidate committed");
    }

    private static void RebaseRetriesAfterReentrancy()
    {
        ToggleBackend backend = ReentrantRebase(out Dictionary<AccessoryEffect, Toggle> before, out AccessoryEffect replacement, out AccessoryEffect injected);
        backend.TryLoad();
        Check(ReferenceEquals(backend.Toggles, before), "first reentrant candidate did not roll back");
        backend.TryLoad();
        Check(!ReferenceEquals(backend.Toggles, before) && backend.Toggles.ContainsKey(replacement) &&
            backend.Toggles.ContainsKey(injected) && backend.CustomPresets[0].SequenceEqual(new[] { replacement }),
            "next entry did not converge on the newer complete generation");
    }

    private static void RebaseAfterUnload()
    {
        var effect = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(effect);
        backend.CustomPresets[0] = [effect]; Preferences config = backend.Config; int saves = Preferences.TotalSaves;
        ToggleLoader.Unload(); backend.TryLoad();
        Check(backend.Toggles.Count == 0 && backend.CustomPresets[0] != null && backend.CustomPresets[0].Count == 0,
            "unloaded registry did not rebase the initialized backend to an empty generation");
        Check(ReferenceEquals(config, backend.Config) && Preferences.TotalSaves == saves,
            "unload rebase touched preference state");
    }

    private static void RebaseAfterLiveRegistration()
    {
        var a = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(a);
        backend.Toggles[a].ToggleBool = false;
        var b = new NamedEffect("B", "Mod.B", defaultToggle: false); Register(b); backend.TryLoad();
        Check(backend.Toggles.Count == 2 && !backend.Toggles[a].ToggleBool && !backend.Toggles[b].ToggleBool,
            "successful live registration did not preserve old state and add the new default");
    }

    private static void FailedRegistrationDoesNotRebase()
    {
        var a = new NamedEffect("A", "Mod.A"); ToggleBackend backend = Backend(a);
        Dictionary<AccessoryEffect, Toggle> before = backend.Toggles;
        RejectRegistration(() => Register(new NamedEffect("Alias", "Mod.A")));
        backend.TryLoad();
        Check(ReferenceEquals(before, backend.Toggles), "rejected registration advanced the visible generation");
    }

    private sealed class NamedEffect : AccessoryEffect
    {
        private readonly string name;
        private readonly string fullName;
        private readonly bool defaultToggle;
        private readonly bool mutant;
        private readonly bool minion;
        private readonly Header header;

        public NamedEffect(string name, string fullName, bool defaultToggle = true, bool mutant = false, bool minion = false, bool header = true)
        {
            this.name = name;
            this.fullName = fullName;
            this.defaultToggle = defaultToggle;
            this.mutant = mutant;
            this.minion = minion;
            this.header = header ? new Header() : null;
        }

        public override string Name => name;
        public override string FullName => fullName;
        public override bool DefaultToggle => defaultToggle;
        public override bool MutantsPresenceAffects => mutant;
        public override bool MinionEffect => minion;
        public override Header ToggleHeader { get => header; set { } }
    }

    private sealed class MutableEffect : AccessoryEffect
    {
        public string EffectName { get; set; }
        public string FullIdentity { get; set; }
        public bool DefaultValue { get; set; }
        public bool Mutant { get; set; }
        public bool Minion { get; set; }
        public Header HeaderValue { get; set; } = new();

        public MutableEffect(string name, string identity, bool defaultToggle = true, bool mutant = false, bool minion = false)
        {
            EffectName = name;
            FullIdentity = identity;
            DefaultValue = defaultToggle;
            Mutant = mutant;
            Minion = minion;
        }

        public override string Name => EffectName;
        public override string FullName => FullIdentity;
        public override bool DefaultToggle => DefaultValue;
        public override bool MutantsPresenceAffects => Mutant;
        public override bool MinionEffect => Minion;
        public override Header ToggleHeader { get => HeaderValue; set => HeaderValue = value; }
    }

    private sealed class ThrowingIdentityEffect : AccessoryEffect
    {
        public override string FullName => throw new InvalidOperationException("foreign identity failure");
    }

    private sealed class ReentrantIdentityEffect : AccessoryEffect
    {
        private readonly string identity;
        private readonly Action callback;

        public ReentrantIdentityEffect(string identity, Action callback)
        {
            this.identity = identity;
            this.callback = callback;
        }

        public override string FullName
        {
            get
            {
                callback();
                return identity;
            }
        }
    }
}
