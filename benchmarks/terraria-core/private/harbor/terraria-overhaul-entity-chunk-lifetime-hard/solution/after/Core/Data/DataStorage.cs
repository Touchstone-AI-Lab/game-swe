using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.Linq;
using System.Numerics;
using System.Reflection;
using System.Runtime.CompilerServices;
using Terraria;
using Terraria.ModLoader;
using Terraria.ModLoader.Core;
using BitMask64 = TerrariaOverhaul.Utilities.BitMask<ulong>;

namespace TerrariaOverhaul.Core.Data;

internal interface IComponent { }

internal readonly struct Component
{
	public static readonly Component Invalid = default;

	public readonly uint Id;
	public readonly bool IsValid => Id != 0;

	internal Component(uint id) => Id = id;

	public Type GetComponentType() => DataStorage.GetComponentType(this);
}

internal unsafe readonly ref struct ComponentMask
{
	public readonly Span<BitMask64> Span;

	public static int ExpectedLength => (int)DataStorage.ComponentMasksPerEntity;

	private ComponentMask(Span<BitMask64> span) => Span = span;

	public void Set<T>() where T : IComponent
	{
		var (div, rem) = Math.DivRem(DataStorage.GetComponentIndex<T>(), BitMask64.BitSize);
		Span[(int)div].Set((int)rem);
	}
	public void Unset<T>() where T : IComponent
	{
		var (div, rem) = Math.DivRem(DataStorage.GetComponentIndex<T>(), BitMask64.BitSize);
		Span[(int)div].Unset((int)rem);
	}

	public static ComponentMask InSpan(Span<BitMask64> span) => new(span);
	public static ComponentMask InDynamicArray(BitMask64[] arr, uint entryIndex)
		=> new(new Span<BitMask64>(arr, (int)(entryIndex * ExpectedLength), (int)ExpectedLength));
}

internal readonly struct DataEntity
{
	public static readonly DataEntity Invalid = default;

	public readonly uint Index;
	public readonly uint Version;
	public readonly bool IsValid => DataStorage.IsEntityValid(this);

	internal DataEntity(uint index, uint version) => (Index, Version) = (index, version);

	public bool Has<T>() where T : IComponent => DataStorage.HasComponent<T>(this);
	public ref T Get<T>() where T : IComponent => ref DataStorage.GetComponent<T>(this);
	public ref T Add<T>(in T value) where T : IComponent => ref DataStorage.AddComponent(this, in value);
	public void Remove<T>() where T : IComponent => DataStorage.RemoveComponent<T>(this);
	public bool HasAll(ComponentMask mask) => DataStorage.HasAllComponents(this, mask);
	public bool HasAny(ComponentMask mask) => DataStorage.HasAnyComponents(this, mask);
	public void AddByHandle(Component component, object value) => DataStorage.AddComponent(this, component, value);
	public void Clear() => DataStorage.ClearEntity(this);
	public void Destroy() => DataStorage.DestroyEntity(this);
}

internal readonly struct Query
{
	public readonly uint Index;

	internal Query(uint index) => Index = index;

	public Iterator GetEnumerator() => new(GetIncludedMask(), GetExcludedMask());
	public ComponentMask GetIncludedMask() => DataStorage.GetQueryIncludedComponentMask(this);
	public ComponentMask GetExcludedMask() => DataStorage.GetQueryExcludedComponentMask(this);

	public Query With<T>() where T : IComponent
	{
		GetIncludedMask().Set<T>();
		return this;
	}
	public Query Without<T>() where T : IComponent
	{
		GetExcludedMask().Set<T>();
		return this;
	}

	public ref struct Iterator
	{
		private readonly BitMask64[] presenceMasks;
		private readonly uint[] entityVersions;
		private readonly BitMask64[] includedComponentMasks;
		private readonly BitMask64[] excludedComponentMasks;

		public readonly ComponentMask IncludedComponents;
		public readonly ComponentMask ExcludedComponents;
		public BitMask64 PresenceMask;
		public int PresenceMaskIndex = -1;
		public int BaseIndex = -BitMask64.BitSize;

		public DataEntity Current { get; private set; }

		public Iterator(ComponentMask includedComponents, ComponentMask excludedComponents) : this()
		{
			presenceMasks = DataStorage.EntityPresenceMasks.ToArray();
			entityVersions = DataStorage.EntityVersions.ToArray();
			includedComponentMasks = includedComponents.Span.ToArray();
			excludedComponentMasks = excludedComponents.Span.ToArray();
			IncludedComponents = ComponentMask.InSpan(includedComponentMasks);
			ExcludedComponents = ComponentMask.InSpan(excludedComponentMasks);
		}

		public bool MoveNext()
		{
			while (true) {
				if (PresenceMask.IsZero) {
					if (++PresenceMaskIndex >= presenceMasks.Length) {
						Current = default;
						return false;
					}
					BaseIndex += BitMask64.BitSize;
					PresenceMask = presenceMasks[PresenceMaskIndex];
					continue;
				}

				int bitIndex = PresenceMask.TrailingZeroCount();
				PresenceMask.Unset(bitIndex);

				uint entityIndex = (uint)(BaseIndex + bitIndex);
				Current = new DataEntity(entityIndex, entityVersions[entityIndex]);

				if (Current.IsValid && Current.HasAll(IncludedComponents) && !Current.HasAny(ExcludedComponents))
					return true;
			}
		}
	}
}

internal static class DataStorage
{
	private static class ComponentData<T> where T : IComponent
	{
		public static Component Handle = Component.Invalid;
		public static SparseSet<T> SparseSet = new();

		static ComponentData()
		{
			lock (operationLock) {
				Handle = CreateComponent();

				components[Handle.Id] = new() {
					Type = typeof(T),
					AddFromObject = Add,
					Remove = Remove,
				};
				componentByType[typeof(T)] = Handle;
				if (!componentByName.TryAdd(typeof(T).Name, Handle)) {
					componentByName[typeof(T).Name] = Component.Invalid;
				}
			}
		}

		public static void Add(DataEntity entity, object value) => AddComponent(entity, (T)value);
		public static void Remove(DataEntity entity) => RemoveComponent<T>(entity);
	}
	private struct ComponentInfo
	{
		public required Type Type;
		public required Action<DataEntity, object> AddFromObject;
		public required Action<DataEntity> Remove;
	}

	// These should have almost no cost unless a second thread kicks in.
	private static readonly object operationLock = new();
	// Components
	private static uint componentCount = 1;
	private static uint componentMasksPerEntity = 1;
	private static ComponentInfo[] components = [];
	private static readonly Dictionary<Type, Component> componentByType = [];
	private static readonly Dictionary<string, Component> componentByName = [];
	// Entities
	private static uint entityCount;
	private static uint[] entityVersions = [];
	private static BitMask64[] entityPresenceMasks = [];
	private static BitMask64[] entityComponentMasks = [];
	private static readonly Stack<uint> releasedEntityIndices = [];
	// Queries
	private static uint queryCount;
	private static BitMask64[] queryExcludedComponentMasks = [];
	private static BitMask64[] queryIncludedComponentMasks = [];

	public static uint EntityCount => entityCount;
	public static uint ComponentMasksPerEntity => componentMasksPerEntity;
	internal static uint[] EntityVersions => entityVersions;
	internal static BitMask64[] EntityPresenceMasks => entityPresenceMasks;

	// Components

	public static Component CreateComponent()
	{
		lock (operationLock) {
		var handle = new Component(componentCount++);
		if (handle.Id >= components.Length)
			Array.Resize(ref components, (int)BitOperations.RoundUpToPowerOf2(handle.Id + 1));

		uint newMasksPerEntity = (handle.Id / BitMask64.BitSize) + 1;
		if (newMasksPerEntity != componentMasksPerEntity) {
			void GrowComponentMasks(ref BitMask64[] masks, uint entryCount)
			{
				var oldMasks = masks;
				var newMasks = masks = new BitMask64[BitOperations.RoundUpToPowerOf2(entryCount + 1) * newMasksPerEntity];
				for (uint entry = 0; entry < entryCount; entry++) {
					for (uint mask = 0; mask < componentMasksPerEntity; mask++) {
						newMasks[entry * newMasksPerEntity + mask] = oldMasks[entry * componentMasksPerEntity + mask];
					}
				}
			}

			GrowComponentMasks(ref entityComponentMasks, entityCount);
			GrowComponentMasks(ref queryIncludedComponentMasks, queryCount);
			GrowComponentMasks(ref queryExcludedComponentMasks, queryCount);
			componentMasksPerEntity = newMasksPerEntity;
		}

		return handle;
		}
	}

	public static void RegisterComponent(Type type)
		=> RuntimeHelpers.RunClassConstructor(typeof(ComponentData<>).MakeGenericType(type).TypeHandle);

	public static void RegisterComponent<T>() where T : IComponent
		=> RuntimeHelpers.RunClassConstructor(typeof(ComponentData<T>).TypeHandle);

	public static Component GetComponentHandle<T>() where T : IComponent
		=> ComponentData<T>.Handle;

	public static uint GetComponentIndex<T>() where T : IComponent
		=> ComponentData<T>.Handle.Id;

	public static Type GetComponentType(Component component)
		=> components[component.Id].Type;

	public static bool TryGetComponentFromName(string name, [NotNullWhen(true)] out Component result)
	{
		lock (operationLock) {
			return componentByName.TryGetValue(name, out result) && result.IsValid;
		}
	}

	public static void RegisterTypesFromAssembly(Assembly assembly)
	{
		foreach (var type in AssemblyManager.GetLoadableTypes(assembly).Where(t => !t.IsAbstract && typeof(IComponent).IsAssignableFrom(t))) {
			RegisterComponent(type);
		}
	}

	// Entity component data

	public static bool HasComponent<T>(DataEntity entity) where T : IComponent
		=> IsEntityValid(entity) && ComponentData<T>.SparseSet.Has(entity.Index);

	public static bool HasAllComponents(DataEntity entity, ComponentMask mask)
	{
		if (!IsEntityValid(entity)) return false;
		//	if (componentMasksPerEntity == 1)
		//		return (mask.Span[0] & entityComponentMasks[entity.Index]) == mask.Span[0];

		uint baseIndex = entity.Index * componentMasksPerEntity;
		int comparableLength = Math.Min(mask.Span.Length, (int)componentMasksPerEntity);
		for (int i = 0; i < comparableLength; i++) {
			// Halt with a negative result if AND'ing the masks loses any expected bits.
			if ((mask.Span[i] & entityComponentMasks[baseIndex + i]) != mask.Span[i]) {
				return false;
			}
		}
		for (int i = comparableLength; i < mask.Span.Length; i++) {
			if (!mask.Span[i].IsZero) return false;
		}
		return true;
	}
	public static bool HasAnyComponents(DataEntity entity, ComponentMask mask)
	{
		if (!IsEntityValid(entity)) return false;
		//	if (componentMasksPerEntity == 1)
		//		return !(mask.Span[0] & entityComponentMasks[entity.Index]).IsZero;

		uint baseIndex = entity.Index * componentMasksPerEntity;
		int comparableLength = Math.Min(mask.Span.Length, (int)componentMasksPerEntity);
		for (int i = 0; i < comparableLength; i++) {
			// Halt with a positive result if AND'ing the masks results in anything but a zero.
			if (!(mask.Span[i] & entityComponentMasks[baseIndex + i]).IsZero) {
				return true;
			}
		}
		return false;
	}

	public static ref T GetComponent<T>(DataEntity entity) where T : IComponent
	{
		if (!IsEntityValid(entity) || !ComponentData<T>.SparseSet.Has(entity.Index))
			throw new InvalidOperationException("The entity is stale or does not own the requested component.");
		return ref ComponentData<T>.SparseSet.Get(entity.Index);
	}

	public static void AddComponent(DataEntity entity, Component component, object value)
	{
		lock (operationLock) {
			if (!IsEntityValid(entity)) throw new InvalidOperationException("Cannot mutate a stale entity.");
			if (!component.IsValid || component.Id >= components.Length || components[component.Id].Type == null)
				throw new ArgumentException("The component handle is invalid.", nameof(component));
			components[component.Id].AddFromObject(entity, value);
		}
	}
	public static ref T AddComponent<T>(DataEntity entity, in T value) where T : IComponent
	{
		lock (operationLock) {
			if (!IsEntityValid(entity)) throw new InvalidOperationException("Cannot mutate a stale entity.");
			ComponentMask.InDynamicArray(entityComponentMasks, entity.Index).Set<T>();
			return ref ComponentData<T>.SparseSet.Put(entity.Index, in value);
		}
	}
	public static void RemoveComponent<T>(DataEntity entity) where T : IComponent
	{
		Debug.Assert(Program.IsMainThread);
		if (!IsEntityValid(entity)) throw new InvalidOperationException("Cannot mutate a stale entity.");
		if (!ComponentData<T>.SparseSet.Has(entity.Index)) return;
		ComponentMask.InDynamicArray(entityComponentMasks, entity.Index).Unset<T>();
		ComponentData<T>.SparseSet.Remove(entity.Index);
	}
	public static void ClearEntity(DataEntity entity)
	{
		if (!IsEntityValid(entity)) throw new InvalidOperationException("Cannot clear a stale entity.");
		uint baseMask = entity.Index * componentMasksPerEntity;
		for (int maskIndex = 0, baseBit = 0; maskIndex < componentMasksPerEntity; maskIndex++, baseBit += BitMask64.BitSize) {
			foreach (int bitIndex in entityComponentMasks[baseMask + maskIndex]) {
				components[baseBit + bitIndex].Remove(entity);
			}
		}
	}

	// Entities

	public static DataEntity CreateEntity()
	{
		Debug.Assert(Program.IsMainThread);

		uint index;
		if (releasedEntityIndices.TryPop(out uint releasedIndex)) {
			index = releasedIndex;
		} else {
			index = entityCount++;
			uint oldLength = BitOperations.RoundUpToPowerOf2(index + 0);
			uint newLength = BitOperations.RoundUpToPowerOf2(index + 1);
			if (newLength != oldLength) {
				Array.Resize(ref entityVersions, (int)newLength);
				Array.Resize(ref entityPresenceMasks, (int)(newLength / BitMask64.BitSize) + 1);
				Array.Resize(ref entityComponentMasks, (int)(newLength * componentMasksPerEntity));
			}
		}

		var (div, rem) = Math.DivRem(index, BitMask64.BitSize);
		entityPresenceMasks[div].Set((int)rem);

		uint version = entityVersions[index];
		if (version == 0) version = ++entityVersions[index];
		
		return new(index, version);
	}
	public static void DestroyEntity(DataEntity entity)
	{
		Debug.Assert(Program.IsMainThread);
		if (!IsEntityValid(entity)) return;
		ClearEntity(entity);
		var (div, rem) = Math.DivRem(entity.Index, BitMask64.BitSize);
		entityPresenceMasks[div].Unset((int)rem);
		uint nextVersion = unchecked(entityVersions[entity.Index] + 1);
		entityVersions[entity.Index] = nextVersion;
		if (nextVersion == 0) return;
		releasedEntityIndices.Push(entity.Index);
	}

	public static bool IsEntityValid(DataEntity entity)
	{
		if (entity.Version == 0
			|| entity.Index >= entityCount
			|| entity.Index >= entityVersions.Length
			|| entity.Version != entityVersions[entity.Index]) {
			return false;
		}

		var (div, rem) = Math.DivRem(entity.Index, BitMask64.BitSize);
		return div < entityPresenceMasks.Length && entityPresenceMasks[div].Get((int)rem);
	}

	// Queries

	public static Query CreateQuery()
	{
		lock (operationLock) {
			uint index = queryCount++;
			int masksArrayLength = (int)(BitOperations.RoundUpToPowerOf2(index + 1) * componentMasksPerEntity);
			Array.Resize(ref queryIncludedComponentMasks, masksArrayLength);
			Array.Resize(ref queryExcludedComponentMasks, masksArrayLength);
			return new(index);
		}
	}

	internal static ComponentMask GetQueryIncludedComponentMask(Query query) => ComponentMask.InDynamicArray(queryIncludedComponentMasks, query.Index);
	internal static ComponentMask GetQueryExcludedComponentMask(Query query) => ComponentMask.InDynamicArray(queryExcludedComponentMasks, query.Index);
}

#if DEBUG
internal sealed class DataTests : ModSystem
{
	public struct Cmp() : IComponent
	{
		public int Int = 123;
	}
	
	public override void OnModLoad()
	{
		Main.QueueMainThreadAction(Test);
	}

	public static void Test()
	{
		// Entity creation.
		var entA = DataStorage.CreateEntity();
		var entB = DataStorage.CreateEntity();
		var entX = new DataEntity();
		Debug.Assert(entA.IsValid);
		Debug.Assert(entB.IsValid);
		Debug.Assert(!entX.IsValid);
		entX = DataStorage.CreateEntity();
		Debug.Assert(entX.IsValid);

		// Component registration.
		var cmpA = new Component();
		Debug.Assert(!cmpA.IsValid);
		DataStorage.RegisterComponent<Cmp>();
		cmpA = DataStorage.GetComponentHandle<Cmp>();
		Debug.Assert(cmpA.IsValid);

		// Query creation.
		// var nilQuery = DataStorage.CreateQuery();
		// Debug.Assert(!nilQuery.GetEnumerator().MoveNext());
		var cmpQuery = DataStorage.CreateQuery().With<Cmp>();
		// Debug.Assert(!nilQuery.GetEnumerator().MoveNext());
		Debug.Assert(!cmpQuery.GetEnumerator().MoveNext());

		// Component mutation.
		Debug.Assert(!entX.Has<Cmp>());
		entX.Add(new Cmp { Int = 123 });
		Debug.Assert(entX.Has<Cmp>());
		Debug.Assert(!entA.Has<Cmp>());
		Debug.Assert(!entB.Has<Cmp>());
		// Debug.Assert(!nilQuery.GetEnumerator().MoveNext());

		var it = cmpQuery.GetEnumerator();
		Debug.Assert(it.MoveNext());
		Debug.Assert(!it.MoveNext());
		
		entB.Add(new Cmp { Int = 321 });
		Debug.Assert(entX.Has<Cmp>());
		Debug.Assert(!entA.Has<Cmp>());
		Debug.Assert(entB.Has<Cmp>());
		Debug.Assert(entX.Get<Cmp>().Int == 123);
		Debug.Assert(entB.Get<Cmp>().Int == 321);
		// Debug.Assert(!nilQuery.GetEnumerator().MoveNext());

		it = cmpQuery.GetEnumerator();
		Debug.Assert(it.MoveNext());
		Debug.Assert(it.MoveNext());
		Debug.Assert(!it.MoveNext());

		entX.Remove<Cmp>();
		Debug.Assert(!entX.Has<Cmp>());
		// Debug.Assert(!nilQuery.GetEnumerator().MoveNext());

		it = cmpQuery.GetEnumerator();
		Debug.Assert(it.MoveNext());
		Debug.Assert(!it.MoveNext());
	}
}
#endif
