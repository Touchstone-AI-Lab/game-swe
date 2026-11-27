using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Microsoft.Xna.Framework;
using TerrariaOverhaul.Core.Chunks;
using TerrariaOverhaul.Core.Data;
using TerrariaOverhaul.Core.Time;
using TerrariaOverhaul.Utilities.Xna;

internal static class ContractProgram
{
    private struct A : IComponent { public int Value; }
    private struct B : IComponent { public int Value; }
    private struct Marker<T> : IComponent { }
	private struct Alias<T> : IComponent { }
    private sealed class Pair<T, U> { }
    private static readonly Type[] AtomTypes =
    {
        typeof(byte), typeof(sbyte), typeof(short), typeof(ushort),
        typeof(int), typeof(uint), typeof(long), typeof(ulong),
        typeof(float), typeof(double), typeof(decimal), typeof(char),
        typeof(bool), typeof(string), typeof(object), typeof(DateTime),
    };

    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["component_handles_reserve_invalid_zero"] = ComponentHandlesReserveInvalidZero,
        ["component_handles_are_stable_and_unique"] = ComponentHandlesStableUnique,
        ["entity_masks_survive_first_growth"] = EntityMasksSurviveFirstGrowth,
        ["entity_masks_survive_second_growth"] = EntityMasksSurviveSecondGrowth,
        ["include_query_survives_mask_growth"] = IncludeQuerySurvivesGrowth,
        ["exclude_query_survives_mask_growth"] = ExcludeQuerySurvivesGrowth,
		["preallocation_registration_advances_mask_width"] = PreallocationRegistrationAdvancesMaskWidth,
		["preallocation_high_component_roundtrips"] = PreallocationHighComponentRoundtrips,
		["preallocation_include_query_survives_growth"] = PreallocationIncludeQuerySurvivesGrowth,
		["preallocation_exclude_query_survives_growth"] = PreallocationExcludeQuerySurvivesGrowth,
		["unique_component_name_resolves_stably"] = UniqueComponentNameResolvesStably,
		["ambiguous_component_name_is_rejected"] = AmbiguousComponentNameIsRejected,
        ["sparse_remove_first_preserves_second"] = SparseRemoveFirstPreservesSecond,
        ["sparse_remove_middle_preserves_neighbors"] = SparseRemoveMiddlePreservesNeighbors,
        ["sparse_remove_clears_membership"] = SparseRemoveClearsMembership,
        ["sparse_reinsert_reuses_dense_capacity"] = SparseReinsertReusesCapacity,
        ["sparse_overwrite_keeps_count"] = SparseOverwriteKeepsCount,
        ["default_entity_is_safely_invalid"] = DefaultEntitySafelyInvalid,
        ["out_of_range_entity_is_safely_invalid"] = OutOfRangeEntitySafelyInvalid,
        ["destroy_clears_owned_components"] = DestroyClearsOwnedComponents,
        ["destroy_is_idempotent"] = DestroyIsIdempotent,
        ["stale_entity_has_no_components"] = StaleEntityHasNoComponents,
        ["stale_entity_cannot_add"] = StaleEntityCannotAdd,
        ["stale_entity_cannot_get"] = StaleEntityCannotGet,
        ["remove_missing_component_is_noop"] = RemoveMissingComponentIsNoop,
        ["get_missing_component_is_rejected"] = GetMissingComponentIsRejected,
        ["clear_removes_components_but_preserves_entity"] = ClearRemovesComponentsButPreservesEntity,
        ["stale_entity_cannot_clear"] = StaleEntityCannotClear,
        ["invalid_component_handle_is_rejected"] = InvalidComponentHandleIsRejected,
        ["destroyed_slot_is_reused_before_growth"] = DestroyedSlotIsReusedBeforeGrowth,
        ["reused_slot_advances_generation"] = ReusedSlotAdvancesGeneration,
        ["generation_wrap_retires_exhausted_slot"] = GenerationWrapRetiresExhaustedSlot,
        ["reused_slot_has_no_component_or_query_leak"] = ReusedSlotHasNoComponentOrQueryLeak,
        ["multiple_released_slots_precede_high_water_growth"] = MultipleReleasedSlotsPrecedeHighWaterGrowth,
        ["repeated_destroy_publishes_slot_once"] = RepeatedDestroyPublishesSlotOnce,
        ["clear_does_not_release_live_slot"] = ClearDoesNotReleaseLiveSlot,
        ["reused_entity_joins_existing_query"] = ReusedEntityJoinsExistingQuery,
        ["entity_churn_keeps_high_water_stable"] = EntityChurnKeepsHighWaterStable,
        ["chunk_recreation_reuses_slot_with_fresh_state"] = ChunkRecreationReusesSlotWithFreshState,
        ["idle_observer_defers_old_slot_reuse"] = IdleObserverDefersOldSlotReuse,
        ["query_includes_only_matching_entities"] = QueryIncludesOnlyMatches,
        ["query_without_excludes_matching_entities"] = QueryWithoutExcludes,
        ["query_skips_destroyed_entities"] = QuerySkipsDestroyed,
        ["query_crosses_empty_presence_word"] = QueryCrossesEmptyWord,
        ["query_yields_each_entity_once"] = QueryYieldsOnce,
		["destroyed_generation_without_presence_is_invalid"] = DestroyedGenerationWithoutPresenceIsInvalid,
		["active_query_survives_component_growth"] = ActiveQuerySurvivesComponentGrowth,
		["active_query_freezes_filters"] = ActiveQueryFreezesFilters,
		["active_query_omits_later_entity"] = ActiveQueryOmitsLaterEntity,
		["active_query_omits_reused_generation"] = ActiveQueryOmitsReusedGeneration,
		["empty_query_skips_destroyed_cached_candidate"] = EmptyQuerySkipsDestroyedCachedCandidate,
        ["negative_world_coordinates_floor"] = NegativeWorldCoordinatesFloor,
        ["negative_tile_coordinates_floor"] = NegativeTileCoordinatesFloor,
        ["chunk_creation_rejects_world_bounds"] = ChunkCreationRejectsBounds,
        ["chunk_creation_is_canonical"] = ChunkCreationCanonical,
        ["chunk_keepalive_refreshes_tick"] = ChunkKeepAliveRefreshes,
		["world_creation_maps_positive_x_once"] = WorldCreationMapsPositiveXOnce,
		["world_creation_maps_positive_y_once"] = WorldCreationMapsPositiveYOnce,
		["world_tile_chunk_entrypoints_are_canonical"] = WorldTileChunkEntrypointsAreCanonical,
		["creation_observer_failure_is_isolated"] = CreationObserverFailureIsIsolated,
		["creation_observer_unload_invalidates_result"] = CreationObserverUnloadInvalidatesResult,
		["creation_observer_destroy_invalidates_result"] = CreationObserverDestroyInvalidatesResult,
		["stale_canonical_mapping_is_rebuilt"] = StaleCanonicalMappingIsRebuilt,
        ["idle_cleanup_destroys_expired_chunk"] = IdleCleanupDestroysExpired,
        ["idle_cleanup_preserves_valuable_chunk"] = IdleCleanupPreservesValuable,
        ["idle_cleanup_preserves_recent_chunk"] = IdleCleanupPreservesRecent,
        ["idle_cleanup_handles_tick_wrap"] = IdleCleanupHandlesWrap,
        ["unload_destroys_every_chunk_once"] = UnloadDestroysEveryChunkOnce,
        ["destroy_event_observes_removed_mapping"] = DestroyEventObservesRemovedMapping,
        ["idle_observer_failure_does_not_strand_entities"] = IdleObserverFailure,
        ["unload_observer_failure_finishes_all_chunks"] = UnloadObserverFailure,
        ["unload_reentrant_creation_is_rejected"] = UnloadReentrantCreation,
        ["idle_reentrant_replacement_survives_old_teardown"] = IdleReentrantReplacement,
        ["visible_iteration_uses_screen_y_for_bottom"] = VisibleIterationUsesScreenY,
        ["creation_event_observes_initialized_canonical_chunk"] = CreationEventObservesInitializedChunk,
        ["edge_chunk_rectangles_are_clamped_to_world"] = EdgeChunkRectanglesAreClamped,
		["all_chunk_iteration_ignores_later_creation"] = AllChunkIterationIgnoresLaterCreation,
		["all_chunk_iteration_survives_unload"] = AllChunkIterationSurvivesUnload,
    };

    public static int Main(string[] args)
    {
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out Action? test)) return 2;
        try { test(); Console.WriteLine("PASS"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static void Check(bool value, string message)
    {
        if (!value) throw new InvalidOperationException(message);
    }

    private static Component Register(Type type)
    {
        DataStorage.RegisterComponent(type);
        MethodInfo method = typeof(DataStorage).GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(x => x.Name == nameof(DataStorage.GetComponentHandle) && x.IsGenericMethodDefinition);
        return (Component)method.MakeGenericMethod(type).Invoke(null, null)!;
    }

    private static Type NextMarker(ref int seed)
    {
        int value = seed++;
        Type key = typeof(Pair<,>).MakeGenericType(AtomTypes[value % AtomTypes.Length], AtomTypes[value / AtomTypes.Length]);
        return typeof(Marker<>).MakeGenericType(key);
    }

    private static Component RegisterUntilWidth(uint width, ref int seed)
    {
        Component last = default;
        while (DataStorage.ComponentMasksPerEntity < width) last = Register(NextMarker(ref seed));
        return last;
    }

	private static (Type Type, Component Component) RegisterMarkers(int count, ref int seed)
	{
		Type type = typeof(Marker<byte>);
		Component component = default;
		for (int i = 0; i < count; i++) {
			type = NextMarker(ref seed);
			component = Register(type);
		}
		return (type, component);
	}

    private static Query With(Query query, Type type)
        => (Query)typeof(Query).GetMethod(nameof(Query.With))!.MakeGenericMethod(type).Invoke(query, null)!;

    private static Query Without(Query query, Type type)
        => (Query)typeof(Query).GetMethod(nameof(Query.Without))!.MakeGenericMethod(type).Invoke(query, null)!;

    private static int[] Indices(Query query)
    {
        var result = new List<int>();
        foreach (DataEntity entity in query) result.Add((int)entity.Index);
        return result.ToArray();
    }

    private static void ComponentHandlesReserveInvalidZero()
    {
        Check(!Component.Invalid.IsValid, "the sentinel must remain invalid");
        DataStorage.RegisterComponent<A>();
        Check(DataStorage.GetComponentHandle<A>().IsValid, "first registration received the invalid handle");
    }

    private static void ComponentHandlesStableUnique()
    {
        DataStorage.RegisterComponent<A>(); DataStorage.RegisterComponent<B>();
        Component a = DataStorage.GetComponentHandle<A>(), again = DataStorage.GetComponentHandle<A>(), b = DataStorage.GetComponentHandle<B>();
        Check(a.IsValid && b.IsValid && a.Id == again.Id && a.Id != b.Id, "handles are not stable and unique");
    }

    private static void EntityMasksSurviveFirstGrowth() => EntityMaskSurvivesGrowth(2);
    private static void EntityMasksSurviveSecondGrowth() => EntityMaskSurvivesGrowth(3);
    private static void EntityMaskSurvivesGrowth(uint targetWidth)
    {
        DataEntity entity = DataStorage.CreateEntity();
        int seed = 0;
        if (targetWidth >= 3) RegisterUntilWidth(2, ref seed);
        Type trackedType = NextMarker(ref seed);
        Component tracked = Register(trackedType);
        entity.AddByHandle(tracked, Activator.CreateInstance(trackedType)!);
        RegisterUntilWidth(targetWidth, ref seed);
        Query query = With(DataStorage.CreateQuery(), trackedType);
        Check(Indices(query).SequenceEqual(new[] { (int)entity.Index }), "entity component bit moved during mask growth");
    }

    private static void IncludeQuerySurvivesGrowth()
    {
        DataEntity entity = DataStorage.CreateEntity();
        int seed = 0; RegisterUntilWidth(2, ref seed);
        Type trackedType = NextMarker(ref seed);
        Component tracked = Register(trackedType);
        Query query = With(DataStorage.CreateQuery(), trackedType);
        entity.AddByHandle(tracked, Activator.CreateInstance(trackedType)!);
        RegisterUntilWidth(3, ref seed);
        Check(Indices(query).SequenceEqual(new[] { (int)entity.Index }), "include query bit moved during growth");
    }

    private static void ExcludeQuerySurvivesGrowth()
    {
        DataEntity included = DataStorage.CreateEntity();
        DataEntity excludedEntity = DataStorage.CreateEntity();
        int seed = 0; RegisterUntilWidth(2, ref seed);
        Type excludedType = NextMarker(ref seed);
        Component excluded = Register(excludedType);
        Query query = Without(DataStorage.CreateQuery(), excludedType);
        excludedEntity.AddByHandle(excluded, Activator.CreateInstance(excludedType)!);
        RegisterUntilWidth(3, ref seed);
        Check(Indices(query).SequenceEqual(new[] { (int)included.Index }), "exclude query bit moved during growth");
    }

	private static void PreallocationRegistrationAdvancesMaskWidth()
	{
		int seed = 0;
		RegisterMarkers(70, ref seed);
		Check(DataStorage.EntityCount == 0, "test allocated an entity before registration completed");
		Check(DataStorage.ComponentMasksPerEntity >= 2, "pre-allocation registration did not advance component-mask width");
	}

	private static void PreallocationHighComponentRoundtrips()
	{
		int seed = 0;
		(Type type, Component component) = RegisterMarkers(70, ref seed);
		DataEntity entity = DataStorage.CreateEntity();
		entity.AddByHandle(component, Activator.CreateInstance(type)!);
		Query query = With(DataStorage.CreateQuery(), type);
		Check(DataStorage.GetComponentType(component) == type, "high component handle lost its registered type");
		Check(Indices(query).SequenceEqual(new[] { (int)entity.Index }), "high component did not round-trip through a post-registration entity");
	}

	private static void PreallocationIncludeQuerySurvivesGrowth()
	{
		int seed = 0;
		(Type type, Component component) = RegisterMarkers(70, ref seed);
		Query query = With(DataStorage.CreateQuery(), type);
		RegisterMarkers(70, ref seed);
		DataEntity entity = DataStorage.CreateEntity();
		entity.AddByHandle(component, Activator.CreateInstance(type)!);
		Check(DataStorage.ComponentMasksPerEntity >= 3, "test did not cross the second mask boundary");
		Check(Indices(query).SequenceEqual(new[] { (int)entity.Index }), "pre-allocation include query lost its high component during growth");
	}

	private static void PreallocationExcludeQuerySurvivesGrowth()
	{
		int seed = 0;
		(Type type, Component component) = RegisterMarkers(70, ref seed);
		Query query = Without(DataStorage.CreateQuery(), type);
		RegisterMarkers(70, ref seed);
		DataEntity included = DataStorage.CreateEntity();
		DataEntity excluded = DataStorage.CreateEntity();
		excluded.AddByHandle(component, Activator.CreateInstance(type)!);
		Check(Indices(query).SequenceEqual(new[] { (int)included.Index }), "pre-allocation exclude query lost its high component during growth");
	}

	private static void UniqueComponentNameResolvesStably()
	{
		DataStorage.RegisterComponent<A>();
		Component expected = DataStorage.GetComponentHandle<A>();
		Check(DataStorage.TryGetComponentFromName(nameof(A), out Component first), "unique component name did not resolve");
		Check(DataStorage.TryGetComponentFromName(nameof(A), out Component second), "repeated unique component lookup failed");
		Check(first.Id == expected.Id && second.Id == expected.Id, "unique component name did not resolve to its stable handle");
	}

	private static void AmbiguousComponentNameIsRejected()
	{
		DataStorage.RegisterComponent<Alias<int>>();
		Component first = DataStorage.GetComponentHandle<Alias<int>>();
		DataStorage.RegisterComponent<Alias<string>>();
		Component second = DataStorage.GetComponentHandle<Alias<string>>();
		Check(first.IsValid && second.IsValid && first.Id != second.Id, "ambiguous component types did not retain distinct handles");
		Check(!DataStorage.TryGetComponentFromName(typeof(Alias<int>).Name, out Component resolved), "ambiguous simple name resolved nondeterministically");
		Check(!resolved.IsValid, "ambiguous simple name returned a usable component handle");
	}

    private static void SparseRemoveFirstPreservesSecond()
    {
        var set = new SparseSet<int>(); set.Put(2, 20); set.Put(7, 70); set.Remove(2);
        Check(!set.Has(2) && set.Has(7) && set.Get(7) == 70 && set.Count == 1, "first removal corrupted the second entry");
    }

    private static void SparseRemoveMiddlePreservesNeighbors()
    {
        var set = new SparseSet<int>(); set.Put(1, 10); set.Put(3, 30); set.Put(8, 80); set.Remove(3);
        Check(set.Get(1) == 10 && set.Get(8) == 80 && set.Count == 2, "middle removal corrupted a neighbor");
    }

    private static void SparseRemoveClearsMembership()
    {
        var set = new SparseSet<int>(); set.Put(4, 44); Check(set.Remove(4) == 44, "wrong removed value");
        Check(!set.Has(4) && set.Count == 0, "removed entry remains present");
    }

    private static void SparseReinsertReusesCapacity()
    {
        var set = new SparseSet<int>();
        for (uint i=0; i<40; i++) set.Put(i, (int)i);
        for (uint i=0; i<40; i++) set.Remove(i);
        for (uint i=40; i<80; i++) set.Put(i, (int)i);
        Check(set.Count == 40 && set.Dense.Length <= 64, "released dense capacity was not reused");
    }

    private static void SparseOverwriteKeepsCount()
    {
        var set = new SparseSet<int>(); set.Put(5, 1); set.Put(5, 2);
        Check(set.Count == 1 && set.Get(5) == 2, "overwrite allocated another dense entry");
    }

    private static void DefaultEntitySafelyInvalid()
    {
        DataEntity entity = default;
        Check(!entity.IsValid && !entity.Has<A>(), "default handle was not safely invalid");
    }

    private static void OutOfRangeEntitySafelyInvalid()
    {
        DataEntity entity = new(999, 1);
        Check(!entity.IsValid && !entity.Has<A>(), "out-of-range handle was not safely invalid");
    }

    private static void DestroyClearsOwnedComponents()
    {
        DataEntity entity = DataStorage.CreateEntity(); entity.Add(new A { Value=9 }); entity.Add(new B { Value=8 }); entity.Destroy();
        Check(!entity.IsValid && !entity.Has<A>() && !entity.Has<B>(), "destroy retained component membership");
    }

    private static void DestroyIsIdempotent()
    {
        DataEntity entity = DataStorage.CreateEntity(); entity.Add(new A()); entity.Destroy(); entity.Destroy();
        Check(!entity.IsValid, "destroyed entity became valid");
    }

    private static void StaleEntityHasNoComponents()
    {
        DataEntity entity = DataStorage.CreateEntity(); entity.Add(new A()); entity.Destroy();
        Check(!entity.Has<A>(), "stale handle can still observe a component");
    }

    private static void StaleEntityCannotAdd()
    {
        DataEntity entity = DataStorage.CreateEntity(); entity.Destroy();
        bool rejected=false; try { entity.Add(new A()); } catch (InvalidOperationException) { rejected=true; }
        Check(rejected && !entity.Has<A>(), "stale handle mutated storage");
    }

    private static void StaleEntityCannotGet()
    {
        DataEntity entity = DataStorage.CreateEntity(); entity.Add(new A()); entity.Destroy();
        bool rejected=false; try { _ = entity.Get<A>().Value; } catch (InvalidOperationException) { rejected=true; }
        Check(rejected, "stale handle read removed storage");
    }

    private static void RemoveMissingComponentIsNoop()
    {
        DataStorage.RegisterComponent<A>();
        DataEntity entity = DataStorage.CreateEntity();
        entity.Remove<A>();
        Check(entity.IsValid && !entity.Has<A>(), "removing an absent component changed or rejected the entity");
    }

    private static void GetMissingComponentIsRejected()
    {
        DataStorage.RegisterComponent<A>();
        DataEntity entity = DataStorage.CreateEntity();
        bool rejected = false;
        try { _ = entity.Get<A>().Value; }
        catch (InvalidOperationException) { rejected = true; }
        Check(rejected, "a missing component did not produce the documented invalid-operation rejection");
    }

    private static void ClearRemovesComponentsButPreservesEntity()
    {
        Query query = DataStorage.CreateQuery().With<A>();
        DataEntity entity = DataStorage.CreateEntity();
        entity.Add(new A { Value = 1 });
        entity.Add(new B { Value = 2 });
        entity.Clear();
        Check(entity.IsValid && !entity.Has<A>() && !entity.Has<B>(), "clear did not remove all components while preserving the entity");
        Check(!Indices(query).Contains((int)entity.Index), "a cleared entity remained in a component query");
    }

    private static void StaleEntityCannotClear()
    {
        DataEntity entity = DataStorage.CreateEntity();
        entity.Destroy();
        bool rejected = false;
        try { entity.Clear(); }
        catch (InvalidOperationException) { rejected = true; }
        Check(rejected, "a stale entity accepted Clear");
    }

    private static void InvalidComponentHandleIsRejected()
    {
        DataEntity entity = DataStorage.CreateEntity();
        bool rejected = false;
        try { entity.AddByHandle(Component.Invalid, new A()); }
        catch (ArgumentException) { rejected = true; }
        Check(rejected && entity.IsValid, "an invalid component handle was not rejected without damaging the entity");
    }

    private static void DestroyedSlotIsReusedBeforeGrowth()
    {
        DataEntity old = DataStorage.CreateEntity();
        uint highWater = DataStorage.EntityCount;
        old.Destroy();
        DataEntity replacement = DataStorage.CreateEntity();
        Check(replacement.Index == old.Index, "released slot was not reused first");
        Check(DataStorage.EntityCount == highWater, "reusing a slot advanced the entity high-water mark");
    }

    private static void ReusedSlotAdvancesGeneration()
    {
        DataEntity old = DataStorage.CreateEntity();
        old.Destroy();
        DataEntity replacement = DataStorage.CreateEntity();
        Check(replacement.Index == old.Index && replacement.Version != 0 && replacement.Version != old.Version, "replacement did not receive a fresh nonzero generation");
        Check(!old.IsValid && replacement.IsValid, "slot reuse revived a stale handle or invalidated its replacement");
    }

    private static void GenerationWrapRetiresExhaustedSlot()
    {
        DataEntity allocated = DataStorage.CreateEntity();
        uint highWater = DataStorage.EntityCount;
        DataStorage.EntityVersions[allocated.Index] = uint.MaxValue;
        DataEntity lastGeneration = new(allocated.Index, uint.MaxValue);
        Check(lastGeneration.IsValid, "test could not establish the final nonzero generation");
        lastGeneration.Destroy();
        Check(!allocated.IsValid && !lastGeneration.IsValid && DataStorage.EntityVersions[allocated.Index] == 0, "generation exhaustion revived an older handle or left the final handle valid");
        DataEntity replacement = DataStorage.CreateEntity();
        Check(replacement.Index != allocated.Index && replacement.Index == highWater, "generation-exhausted slot was reused instead of retired");
        Check(replacement.Version != 0 && replacement.IsValid && DataStorage.EntityCount == highWater + 1, "replacement after retirement did not extend the high-water domain safely");
    }

    private static void ReusedSlotHasNoComponentOrQueryLeak()
    {
        Query query = DataStorage.CreateQuery().With<A>();
        DataEntity old = DataStorage.CreateEntity();
        old.Add(new A { Value = 17 });
        old.Add(new B { Value = 29 });
        old.Destroy();
        DataEntity replacement = DataStorage.CreateEntity();
        Check(replacement.Index == old.Index, "test did not exercise a reused slot");
        Check(!replacement.Has<A>() && !replacement.Has<B>(), "replacement inherited a component or component-mask bit");
        Check(!Indices(query).Contains((int)replacement.Index), "replacement inherited old query membership");
    }

    private static void MultipleReleasedSlotsPrecedeHighWaterGrowth()
    {
        DataEntity first = DataStorage.CreateEntity();
        _ = DataStorage.CreateEntity();
        DataEntity third = DataStorage.CreateEntity();
        first.Destroy();
        third.Destroy();
        uint highWater = DataStorage.EntityCount;
        DataEntity reusedA = DataStorage.CreateEntity();
        DataEntity reusedB = DataStorage.CreateEntity();
        var reusedIndices = new HashSet<uint> { reusedA.Index, reusedB.Index };
        Check(reusedIndices.SetEquals(new[] { first.Index, third.Index }), "not every released slot was consumed before growth");
        Check(DataStorage.EntityCount == highWater, "high-water mark grew while released slots remained");
        DataEntity grown = DataStorage.CreateEntity();
        Check(grown.Index == highWater && DataStorage.EntityCount == highWater + 1, "allocation did not resume at the high-water boundary");
    }

    private static void RepeatedDestroyPublishesSlotOnce()
    {
        DataEntity old = DataStorage.CreateEntity();
        old.Destroy();
        old.Destroy();
        DataEntity replacement = DataStorage.CreateEntity();
        DataEntity next = DataStorage.CreateEntity();
        Check(replacement.Index == old.Index, "released slot was not reused");
        Check(next.Index != old.Index && next.IsValid && replacement.IsValid, "repeated destroy published one slot more than once");
    }

    private static void ClearDoesNotReleaseLiveSlot()
    {
        DataEntity cleared = DataStorage.CreateEntity();
        cleared.Add(new A { Value = 1 });
        cleared.Clear();
        DataEntity next = DataStorage.CreateEntity();
        Check(cleared.IsValid && next.Index != cleared.Index, "Clear released or invalidated a live slot");
    }

    private static void ReusedEntityJoinsExistingQuery()
    {
        Query query = DataStorage.CreateQuery().With<A>().Without<B>();
        DataEntity old = DataStorage.CreateEntity();
        old.Add(new A());
        old.Destroy();
        DataEntity replacement = DataStorage.CreateEntity();
        Check(replacement.Index == old.Index, "test did not exercise a reused slot");
        replacement.Add(new A { Value = 42 });
        var matches = new List<DataEntity>();
        foreach (DataEntity match in query) matches.Add(match);
        Check(matches.Count == 1 && matches[0].Index == replacement.Index && matches[0].Version == replacement.Version, "existing query did not yield the reused entity generation exactly once");
    }

    private static void EntityChurnKeepsHighWaterStable()
    {
        DataEntity current = DataStorage.CreateEntity();
        uint highWater = DataStorage.EntityCount;
        for (int i = 0; i < 512; i++) {
            DataEntity stale = current;
            current.Destroy();
            current = DataStorage.CreateEntity();
            Check(current.Index == stale.Index && current.Version != stale.Version && !stale.IsValid, "churn broke generation-safe reuse");
        }
        Check(DataStorage.EntityCount == highWater && current.IsValid, "historical churn grew the entity index domain");
    }

    private static void ChunkRecreationReusesSlotWithFreshState()
    {
        Chunks system = LoadedChunks();
        Vector2Int position = new(0, 0);
        TimeSystem.UpdateCount = 5;
        Chunks.TryGetOrCreateChunk(position, out Chunk old);
        old.Entity.Get<ChunkInfo>().ValuableComponentCount = 0;
        TimeSystem.UpdateCount = 100;
        system.PostUpdateEverything();
        Check(!old.Entity.IsValid, "old chunk entity survived cleanup");
        TimeSystem.UpdateCount = 123;
        Chunks.TryGetOrCreateChunk(position, out Chunk replacement);
        ChunkInfo info = replacement.Entity.Get<ChunkInfo>();
        Check(replacement.Entity.Index == old.Entity.Index && replacement.Entity.Version != old.Entity.Version, "recreated chunk did not use the released slot with a fresh generation");
        Check(info.LastKeepAliveTick == 123 && info.ValuableComponentCount == 0, "recreated chunk inherited stale ChunkInfo state");
    }

    private static void IdleObserverDefersOldSlotReuse()
    {
        Chunks system = LoadedChunks();
        Vector2Int oldPosition = new(0, 0);
        Chunks.TryGetOrCreateChunk(oldPosition, out Chunk old);
        Chunk observerReplacement = default;
        Chunks.OnChunkDestroyed += _ => Chunks.TryGetOrCreateChunk(new Vector2Int(1, 0), out observerReplacement);
        TimeSystem.UpdateCount = 100;
        system.PostUpdateEverything();
        Check(observerReplacement.Entity.IsValid && observerReplacement.Entity.Index != old.Entity.Index, "observer reused a slot whose old entity was still in its destruction event");
        Chunks.TryGetOrCreateChunk(new Vector2Int(2, 0), out Chunk later);
        Check(later.Entity.Index == old.Entity.Index && later.Entity.Version != old.Entity.Version, "old slot was not reusable after teardown completed");
    }

    private static void QueryIncludesOnlyMatches()
    {
        Query query = DataStorage.CreateQuery().With<A>().With<B>();
        DataEntity both=DataStorage.CreateEntity(); both.Add(new A()); both.Add(new B());
        DataEntity one=DataStorage.CreateEntity(); one.Add(new A());
        Check(Indices(query).SequenceEqual(new[] { (int)both.Index }), "include filter admitted a partial match");
    }

    private static void QueryWithoutExcludes()
    {
        Query query=DataStorage.CreateQuery().With<A>().Without<B>();
        DataEntity a=DataStorage.CreateEntity(); a.Add(new A());
        DataEntity ab=DataStorage.CreateEntity(); ab.Add(new A()); ab.Add(new B());
        Check(Indices(query).SequenceEqual(new[] { (int)a.Index }), "without filter did not exclude the component");
    }

    private static void QuerySkipsDestroyed()
    {
        Query query=DataStorage.CreateQuery().With<A>(); DataEntity entity=DataStorage.CreateEntity(); entity.Add(new A()); entity.Destroy();
        Check(Indices(query).Length == 0, "query yielded a destroyed entity");
    }

    private static void QueryCrossesEmptyWord()
    {
        Query query=DataStorage.CreateQuery().With<A>(); DataEntity target=default;
        for (int i=0; i<130; i++) { DataEntity entity=DataStorage.CreateEntity(); if (i==129) { entity.Add(new A()); target=entity; } }
        Check(Indices(query).SequenceEqual(new[] { (int)target.Index }), "iterator stopped at an empty presence word");
    }

    private static void QueryYieldsOnce()
    {
        Query query=DataStorage.CreateQuery().With<A>();
        for (int i=0; i<10; i++) DataStorage.CreateEntity().Add(new A { Value=i });
        int[] values=Indices(query); Check(values.Length==10 && values.Distinct().Count()==10, "query duplicated or lost a live entity");
    }

	private static void DestroyedGenerationWithoutPresenceIsInvalid()
	{
		DataEntity destroyed = DataStorage.CreateEntity();
		destroyed.Destroy();
		DataEntity absentGeneration = new(destroyed.Index, DataStorage.EntityVersions[destroyed.Index]);
		Check(!absentGeneration.IsValid, "the current generation was treated as live without a presence bit");
	}

	private static void ActiveQuerySurvivesComponentGrowth()
	{
		Query query = DataStorage.CreateQuery().With<A>();
		DataEntity entity = DataStorage.CreateEntity();
		entity.Add(new A { Value = 7 });
		var iterator = query.GetEnumerator();
		int seed = 0;
		RegisterMarkers(140, ref seed);
		Check(iterator.MoveNext(), "active iterator lost its candidate after component-mask growth");
		Check(iterator.Current.Index == entity.Index && iterator.Current.Version == entity.Version, "active iterator yielded the wrong generation after growth");
		Check(!iterator.MoveNext(), "active iterator duplicated its snapshot candidate after growth");
	}

	private static void ActiveQueryFreezesFilters()
	{
		Query query = DataStorage.CreateQuery().With<A>();
		DataEntity entity = DataStorage.CreateEntity();
		entity.Add(new A());
		entity.Add(new B());
		var iterator = query.GetEnumerator();
		query.Without<B>();
		Check(iterator.MoveNext() && iterator.Current.Index == entity.Index, "active iterator observed a later filter mutation");
		Check(!Indices(query).Contains((int)entity.Index), "a later enumerator did not observe the updated filter");
	}

	private static void ActiveQueryOmitsLaterEntity()
	{
		DataEntity first = DataStorage.CreateEntity();
		Query query = DataStorage.CreateQuery();
		var iterator = query.GetEnumerator();
		DataEntity later = DataStorage.CreateEntity();
		var observed = new List<DataEntity>();
		while (iterator.MoveNext()) observed.Add(iterator.Current);
		Check(observed.Count == 1 && observed[0].Index == first.Index, "active iterator admitted an entity created after enumeration began");
		Check(later.IsValid, "later entity was damaged while filtering the active iterator");
	}

	private static void ActiveQueryOmitsReusedGeneration()
	{
		DataEntity old = DataStorage.CreateEntity();
		Query query = DataStorage.CreateQuery();
		var iterator = query.GetEnumerator();
		old.Destroy();
		DataEntity replacement = DataStorage.CreateEntity();
		Check(replacement.Index == old.Index && replacement.Version != old.Version, "test did not reuse the captured slot");
		Check(!iterator.MoveNext(), "active iterator substituted a new slot generation for its captured candidate");
	}

	private static void EmptyQuerySkipsDestroyedCachedCandidate()
	{
		DataEntity candidate = DataStorage.CreateEntity();
		var iterator = DataStorage.CreateQuery().GetEnumerator();
		candidate.Destroy();
		Check(!iterator.MoveNext(), "empty-filter iterator yielded a candidate destroyed before visitation");
	}

    private static void NegativeWorldCoordinatesFloor()
    {
        Check(Chunks.WorldToChunkCoordinates(-0.5f)==-1 && Chunks.WorldToChunkCoordinates(-1024f)==-1 && Chunks.WorldToChunkCoordinates(-1024.5f)==-2, "world coordinates truncate toward zero");
    }

    private static void NegativeTileCoordinatesFloor()
    {
        Check(Chunks.TileToChunkCoordinates(-1)==-1 && Chunks.TileToChunkCoordinates(-64)==-1 && Chunks.TileToChunkCoordinates(-65)==-2, "tile coordinates truncate toward zero");
    }

    private static Chunks LoadedChunks() { var system=new Chunks(); system.Load(); return system; }

    private static void ChunkCreationRejectsBounds()
    {
        _=LoadedChunks();
        Check(!Chunks.TryGetOrCreateChunk(new Vector2Int(-1,0), out _) && !Chunks.TryGetOrCreateChunk(new Vector2Int(4,0), out _) && !Chunks.TryGetOrCreateChunk(new Vector2Int(0,3), out _), "out-of-world chunk was created");
    }

    private static void ChunkCreationCanonical()
    {
        _=LoadedChunks(); Chunks.TryGetOrCreateChunk(new Vector2Int(1,1), out Chunk first); Chunks.TryGetOrCreateChunk(new Vector2Int(1,1), out Chunk second);
        Check(first.Entity.Index==second.Entity.Index && Chunks.IterateAllChunks().Count()==1, "coordinate created duplicate chunks");
    }

    private static void ChunkKeepAliveRefreshes()
    {
        _=LoadedChunks(); TimeSystem.UpdateCount=44; Chunks.TryGetOrCreateChunk(new Vector2Int(0,0), out Chunk chunk);
        Check(chunk.Entity.Get<ChunkInfo>().LastKeepAliveTick==44, "creation did not set keep-alive");
        TimeSystem.UpdateCount=99; Chunks.KeepAlive(chunk); Check(chunk.Entity.Get<ChunkInfo>().LastKeepAliveTick==99, "keep-alive did not refresh");
    }

	private static void WorldCreationMapsPositiveXOnce()
	{
		_ = LoadedChunks();
		Check(Chunks.TryGetOrCreateChunkAtWorldPosition(new Vector2(65 * 16 + 1, 1), out Chunk created), "positive world position was rejected");
		Check(Chunks.TryGetChunk(new Vector2Int(1, 0), out Chunk mapped), "world position did not map to its containing chunk");
		Check(mapped.Entity.Index == created.Entity.Index && !Chunks.TryGetChunk(new Vector2Int(0, 0), out _), "world X coordinate was converted more than once");
	}

	private static void WorldCreationMapsPositiveYOnce()
	{
		_ = LoadedChunks();
		Check(Chunks.TryGetOrCreateChunkAtWorldPosition(new Vector2(1, 65 * 16 + 1), out Chunk created), "positive world position was rejected");
		Check(Chunks.TryGetChunk(new Vector2Int(0, 1), out Chunk mapped), "world position did not map to its containing chunk");
		Check(mapped.Entity.Index == created.Entity.Index && !Chunks.TryGetChunk(new Vector2Int(0, 0), out _), "world Y coordinate was converted more than once");
	}

	private static void WorldTileChunkEntrypointsAreCanonical()
	{
		_ = LoadedChunks();
		Check(Chunks.TryGetOrCreateChunkAtWorldPosition(new Vector2(65 * 16 + 1, 65 * 16 + 1), out Chunk world), "world entrypoint rejected an in-bounds position");
		Check(Chunks.TryGetOrCreateChunkAtTilePosition(new Vector2Int(65, 65), out Chunk tile), "tile entrypoint rejected an in-bounds position");
		Check(Chunks.TryGetOrCreateChunk(new Vector2Int(1, 1), out Chunk chunk), "chunk entrypoint rejected an in-bounds position");
		Check(world.Entity.Index == tile.Entity.Index && tile.Entity.Index == chunk.Entity.Index, "coordinate entrypoints did not converge on one canonical chunk");
		Check(Chunks.IterateAllChunks().Count() == 1, "coordinate entrypoints created duplicate chunks");
	}

	private static void CreationObserverFailureIsIsolated()
	{
		_ = LoadedChunks();
		int throwingCalls = 0, laterCalls = 0;
		Chunks.OnChunkCreated += _ => { throwingCalls++; throw new InvalidOperationException("observer failed"); };
		Chunks.OnChunkCreated += _ => laterCalls++;
		bool accepted = Chunks.TryGetOrCreateChunk(new Vector2Int(1, 0), out Chunk created);
		Check(accepted && created.Entity.IsValid, "observer failure invalidated an otherwise canonical creation");
		Check(throwingCalls == 1 && laterCalls == 1, "observer failure prevented a later creation subscriber");
		Check(Chunks.TryGetChunk(new Vector2Int(1, 0), out Chunk mapped) && mapped.Entity.Index == created.Entity.Index, "observer failure stranded the created chunk");
	}

	private static void CreationObserverUnloadInvalidatesResult()
	{
		Chunks system = LoadedChunks();
		Chunks.OnChunkCreated += _ => system.Unload();
		bool accepted = Chunks.TryGetOrCreateChunk(new Vector2Int(0, 0), out Chunk returned);
		Check(!accepted && !returned.Entity.IsValid, "creation returned success after its observer unloaded the chunk system");
		Check(!Chunks.IterateAllChunks().Any(), "observer unload left a canonical chunk behind");
	}

	private static void CreationObserverDestroyInvalidatesResult()
	{
		_ = LoadedChunks();
		Chunks.OnChunkCreated += created => created.Entity.Destroy();
		bool accepted = Chunks.TryGetOrCreateChunk(new Vector2Int(0, 0), out Chunk returned);
		Check(!accepted && !returned.Entity.IsValid, "creation returned success with an observer-destroyed entity");
		Check(!Chunks.TryGetChunk(new Vector2Int(0, 0), out _), "observer-destroyed chunk retained a stale canonical mapping");
	}

	private static void StaleCanonicalMappingIsRebuilt()
	{
		_ = LoadedChunks();
		Vector2Int position = new(1, 0);
		Chunks.TryGetOrCreateChunk(position, out Chunk stale);
		stale.Entity.Destroy();
		Check(!Chunks.TryGetChunk(position, out _), "lookup accepted a stale canonical mapping");
		Check(Chunks.TryGetOrCreateChunk(position, out Chunk rebuilt) && rebuilt.Entity.IsValid, "stale mapping prevented canonical rebuild");
		Check(rebuilt.Entity.Index == stale.Entity.Index && rebuilt.Entity.Version != stale.Entity.Version, "rebuilt chunk did not use a fresh entity generation");
		Check(Chunks.TryGetChunk(position, out Chunk mapped) && mapped.Entity.Version == rebuilt.Entity.Version, "rebuilt chunk is not canonical");
	}

    private static void IdleCleanupDestroysExpired()
    {
        Chunks system=LoadedChunks(); TimeSystem.UpdateCount=1; Chunks.TryGetOrCreateChunk(new Vector2Int(0,0), out Chunk chunk); TimeSystem.UpdateCount=100; system.PostUpdateEverything();
        Check(!chunk.Entity.IsValid && !Chunks.TryGetChunk(new Vector2Int(0,0), out _), "expired chunk survived cleanup");
    }

    private static void IdleCleanupPreservesValuable()
    {
        Chunks system=LoadedChunks(); Chunks.TryGetOrCreateChunk(new Vector2Int(0,0), out Chunk chunk); chunk.Entity.Get<ChunkInfo>().ValuableComponentCount=1; TimeSystem.UpdateCount=100; system.PostUpdateEverything();
        Check(chunk.Entity.IsValid && Chunks.TryGetChunk(new Vector2Int(0,0), out _), "valuable chunk was unloaded");
    }

    private static void IdleCleanupPreservesRecent()
    {
        Chunks system=LoadedChunks(); TimeSystem.UpdateCount=90; Chunks.TryGetOrCreateChunk(new Vector2Int(0,0), out Chunk chunk); TimeSystem.UpdateCount=100; system.PostUpdateEverything();
        Check(chunk.Entity.IsValid, "recent chunk was unloaded");
    }

    private static void IdleCleanupHandlesWrap()
    {
        Chunks system=LoadedChunks(); TimeSystem.UpdateCount=ulong.MaxValue-80; Chunks.TryGetOrCreateChunk(new Vector2Int(0,0), out Chunk chunk); TimeSystem.UpdateCount=20; system.PostUpdateEverything();
        Check(!chunk.Entity.IsValid, "expired pre-wrap chunk survived after counter wrap");
    }

    private static void UnloadDestroysEveryChunkOnce()
    {
        Chunks system=LoadedChunks(); Chunks.TryGetOrCreateChunk(new Vector2Int(0,0), out _); Chunks.TryGetOrCreateChunk(new Vector2Int(1,0), out _); int events=0; Chunks.OnChunkDestroyed += _ => events++;
        system.Unload(); Check(events==2 && !Chunks.IterateAllChunks().Any(), "unload did not destroy each chunk exactly once");
    }

    private static void DestroyEventObservesRemovedMapping()
    {
        Chunks system=LoadedChunks(); Vector2Int position=new(0,0); Chunks.TryGetOrCreateChunk(position, out _); bool absent=false; Chunks.OnChunkDestroyed += _ => absent=!Chunks.TryGetChunk(position, out _);
        TimeSystem.UpdateCount=100; system.PostUpdateEverything(); Check(absent, "destruction observer saw a stale canonical mapping");
    }

    private static void IdleObserverFailure()
    {
        Chunks system = LoadedChunks();
        Chunks.TryGetOrCreateChunk(new Vector2Int(0, 0), out Chunk first);
        Chunks.TryGetOrCreateChunk(new Vector2Int(1, 0), out Chunk second);
        int throwingCalls = 0, laterCalls = 0;
        Chunks.OnChunkDestroyed += _ => { throwingCalls++; throw new InvalidOperationException("observer failed"); };
        Chunks.OnChunkDestroyed += _ => laterCalls++;
        TimeSystem.UpdateCount = 100;
        system.PostUpdateEverything();
        Check(throwingCalls == 2 && laterCalls == 2, "observer failure stopped later subscribers or chunks");
        Check(!first.Entity.IsValid && !second.Entity.IsValid && !Chunks.IterateAllChunks().Any(), "observer failure stranded a removed live entity");
    }

    private static void UnloadObserverFailure()
    {
        Chunks system = LoadedChunks();
        Chunks.TryGetOrCreateChunk(new Vector2Int(0, 0), out Chunk first);
        Chunks.TryGetOrCreateChunk(new Vector2Int(1, 0), out Chunk second);
        int throwingCalls = 0, laterCalls = 0;
        Chunks.OnChunkDestroyed += _ => { throwingCalls++; throw new InvalidOperationException("observer failed"); };
        Chunks.OnChunkDestroyed += _ => laterCalls++;
        system.Unload();
        Check(throwingCalls == 2 && laterCalls == 2 && !first.Entity.IsValid && !second.Entity.IsValid, "unload stopped at a failed observer");
        Check(!Chunks.IterateAllChunks().Any(), "unload retained chunks after observer failure");
    }

    private static void UnloadReentrantCreation()
    {
        Chunks system = LoadedChunks(); Vector2Int position = new(0, 0);
        Chunks.TryGetOrCreateChunk(position, out Chunk old);
        bool accepted = true; Chunk attempted = default; int calls = 0;
        Chunks.OnChunkDestroyed += _ => { calls++; accepted = Chunks.TryGetOrCreateChunk(position, out attempted); };
        system.Unload();
        Check(calls == 1 && !accepted && !attempted.Entity.IsValid && !old.Entity.IsValid, "unload allowed reentrant chunk creation");
        system.Load();
        Check(Chunks.TryGetOrCreateChunk(position, out Chunk fresh) && fresh.Entity.IsValid, "creation did not resume after reload");
    }

    private static void IdleReentrantReplacement()
    {
        Chunks system = LoadedChunks(); Vector2Int position = new(0, 0);
        Chunks.TryGetOrCreateChunk(position, out Chunk old);
        Chunk replacement = default; int calls = 0;
        Chunks.OnChunkDestroyed += _ => { calls++; if (calls == 1) Chunks.TryGetOrCreateChunk(position, out replacement); };
        TimeSystem.UpdateCount = 100; system.PostUpdateEverything();
        Check(calls == 1 && !old.Entity.IsValid && replacement.Entity.IsValid, "idle replacement did not survive old teardown");
        Check(Chunks.TryGetChunk(position, out Chunk mapped) && mapped.Entity.Index == replacement.Entity.Index, "idle replacement is not canonical");
    }

    private static void VisibleIterationUsesScreenY()
    {
        _ = LoadedChunks();
        Terraria.Main.screenPosition = new Vector2(0, 2048);
        Terraria.Main.screenWidth = 128;
        Terraria.Main.screenHeight = 128;
        Chunks.TryGetOrCreateChunk(new Vector2Int(0, 0), out _);
        Chunks.TryGetOrCreateChunk(new Vector2Int(0, 2), out Chunk visible);
        Chunk[] result = Chunks.IterateVisibleChunks().ToArray();
        Check(result.Length == 1 && result[0].Entity.Index == visible.Entity.Index, "visible iteration used the horizontal origin for its bottom edge");
    }

    private static void CreationEventObservesInitializedChunk()
    {
        _ = LoadedChunks();
        TimeSystem.UpdateCount = 73;
        Vector2Int position = new(1, 1);
        bool observed = false;
        Chunks.OnChunkCreated += created => {
            bool canonical = Chunks.TryGetChunk(position, out Chunk mapped) && mapped.Entity.Index == created.Entity.Index;
            bool initialized = created.Entity.Has<ChunkInfo>() && created.Entity.Get<ChunkInfo>().LastKeepAliveTick == 73;
            observed = canonical && initialized;
        };
        Chunks.TryGetOrCreateChunk(position, out _);
        Check(observed, "creation observer ran before canonical insertion or initialization");
    }

    private static void EdgeChunkRectanglesAreClamped()
    {
        Terraria.Main.maxTilesX = 130;
        Terraria.Main.maxTilesY = 70;
        _ = LoadedChunks();
        Chunks.TryGetOrCreateChunk(new Vector2Int(2, 1), out Chunk chunk);
        ChunkInfo info = chunk.Entity.Get<ChunkInfo>();
        Check(info.TileRectangle.X == 128 && info.TileRectangle.Y == 64, "edge chunk origin is incorrect");
        Check(info.TileRectangle.Width == 2 && info.TileRectangle.Height == 6, "edge chunk tile rectangle extends past the world");
        Check(info.WorldRectangle.Width == 32f && info.WorldRectangle.Height == 96f, "edge chunk world rectangle is not derived from the clamped tile rectangle");
    }

	private static void AllChunkIterationIgnoresLaterCreation()
	{
		_ = LoadedChunks();
		Chunks.TryGetOrCreateChunk(new Vector2Int(0, 0), out Chunk first);
		IEnumerable<Chunk> snapshot = Chunks.IterateAllChunks();
		Chunks.TryGetOrCreateChunk(new Vector2Int(1, 0), out Chunk later);
		Chunk[] observed = snapshot.ToArray();
		Check(observed.Length == 1 && observed[0].Entity.Index == first.Entity.Index, "chunk iteration admitted a creation made after snapshot capture");
		Check(later.Entity.IsValid, "later chunk was damaged while preserving the snapshot");
	}

	private static void AllChunkIterationSurvivesUnload()
	{
		Chunks system = LoadedChunks();
		Chunks.TryGetOrCreateChunk(new Vector2Int(0, 0), out _);
		Chunks.TryGetOrCreateChunk(new Vector2Int(1, 0), out _);
		IEnumerable<Chunk> snapshot = Chunks.IterateAllChunks();
		system.Unload();
		Check(snapshot.Count() == 2, "unload mutated or invalidated an already captured chunk snapshot");
	}
}
