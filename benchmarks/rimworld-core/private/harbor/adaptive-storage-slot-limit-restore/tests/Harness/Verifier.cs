using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Serialization;
using RimWorld;
using HarmonyLib;
using UnityEngine;
using Verse;
using Rhenium.RimWorld.TaskSupport;

namespace Rhenium.RimWorld.Verifier
{
    [Serializable] public sealed class MaterialObservation { public string defName; public int count; }
    [Serializable] public sealed class CostObservation { public string channel; public List<MaterialObservation> entries = new List<MaterialObservation>(); }
    [Serializable] public sealed class FactObservation { public string name; public string value; }
    [Serializable] public sealed class ScalarObservation { public string name; public float value; public string bits; }
    [Serializable] public sealed class CaseObservation
    {
        public string id;
        public string error;
        public List<FactObservation> facts = new List<FactObservation>();
        public List<ScalarObservation> scalars = new List<ScalarObservation>();
        public List<CostObservation> outputs = new List<CostObservation>();
    }
    [Serializable] public sealed class ObservationEnvelope
    {
        public int schema = 3;
        public string adapter = "rhenium-rimworld-observer-v3";
        public string evaluationId;
        public string nonce;
        public string taskKey;
        public bool realGame = true;
        public string fatal;
        public string gameVersion;
        public string unityVersion;
        public string terminalMarker;
        public List<CaseObservation> cases = new List<CaseObservation>();
    }

    [StaticConstructorOnStartup]
    public static partial class VerifierBootstrap
    {
        private const string OutputDirectory = "/logs/verifier";
        private sealed class AssertionDispatch
        {
            public readonly string Id;
            public readonly Func<CaseObservation> Observe;
            public readonly bool Gate;
            public AssertionDispatch(string id, Func<CaseObservation> observe, bool gate)
            { Id = id; Observe = observe; Gate = gate; }
        }

        static VerifierBootstrap() => LongEventHandler.ExecuteWhenFinished(Run);


        private static string Escape(string value)
        {
            if (value == null) return "\"\"";
            var text = new System.Text.StringBuilder("\"");
            foreach (char character in value)
            {
                if (character == '"' || character == '\\') text.Append('\\').Append(character);
                else if (character == '\n') text.Append("\\n");
                else if (character == '\r') text.Append("\\r");
                else if (character == '\t') text.Append("\\t");
                else if (character < ' ') text.Append("\\u").Append(((int)character).ToString("x4"));
                else text.Append(character);
            }
            return text.Append('"').ToString();
        }

        private static string Number(float value) =>
            value.ToString("R", CultureInfo.InvariantCulture);

        // Unity's JsonUtility drops the case list from this envelope, so the evidence is
        // written explicitly. The schema is the one the private supervisor validates.
        private static string Serialize(ObservationEnvelope envelope)
        {
            var text = new System.Text.StringBuilder();
            text.Append("{\"schema\":").Append(envelope.schema);
            text.Append(",\"adapter\":").Append(Escape(envelope.adapter));
            text.Append(",\"evaluationId\":").Append(Escape(envelope.evaluationId));
            text.Append(",\"nonce\":").Append(Escape(envelope.nonce));
            text.Append(",\"taskKey\":").Append(Escape(envelope.taskKey));
            text.Append(",\"realGame\":").Append(envelope.realGame ? "true" : "false");
            text.Append(",\"fatal\":").Append(Escape(envelope.fatal));
            text.Append(",\"gameVersion\":").Append(Escape(envelope.gameVersion));
            text.Append(",\"unityVersion\":").Append(Escape(envelope.unityVersion));
            text.Append(",\"terminalMarker\":").Append(Escape(envelope.terminalMarker));
            text.Append(",\"cases\":[");
            for (int index = 0; index < envelope.cases.Count; index++)
            {
                CaseObservation observed = envelope.cases[index];
                if (index > 0) text.Append(',');
                text.Append("{\"id\":").Append(Escape(observed.id));
                text.Append(",\"error\":").Append(Escape(observed.error));
                text.Append(",\"facts\":[");
                for (int fact = 0; fact < observed.facts.Count; fact++)
                {
                    if (fact > 0) text.Append(',');
                    text.Append("{\"name\":").Append(Escape(observed.facts[fact].name));
                    text.Append(",\"value\":").Append(Escape(observed.facts[fact].value)).Append('}');
                }
                text.Append("],\"scalars\":[");
                for (int scalar = 0; scalar < observed.scalars.Count; scalar++)
                {
                    if (scalar > 0) text.Append(',');
                    text.Append("{\"name\":").Append(Escape(observed.scalars[scalar].name));
                    text.Append(",\"value\":").Append(Number(observed.scalars[scalar].value));
                    text.Append(",\"bits\":").Append(Escape(observed.scalars[scalar].bits)).Append('}');
                }
                text.Append("],\"outputs\":[");
                for (int output = 0; output < observed.outputs.Count; output++)
                {
                    CostObservation cost = observed.outputs[output];
                    if (output > 0) text.Append(',');
                    text.Append("{\"channel\":").Append(Escape(cost.channel)).Append(",\"entries\":[");
                    for (int entry = 0; entry < cost.entries.Count; entry++)
                    {
                        if (entry > 0) text.Append(',');
                        text.Append("{\"defName\":").Append(Escape(cost.entries[entry].defName));
                        text.Append(",\"count\":").Append(cost.entries[entry].count).Append('}');
                    }
                    text.Append("]}");
                }
                text.Append("]}");
            }
            return text.Append("]}").ToString();
        }

        private static void Run()
        {
            string nonce = Environment.GetEnvironmentVariable("RHENIUM_EVALUATION_NONCE") ?? "";
            var envelope = new ObservationEnvelope
            {
                evaluationId = Environment.GetEnvironmentVariable("RHENIUM_EVALUATION_ID") ?? "",
                nonce = nonce,
                taskKey = Environment.GetEnvironmentVariable("RHENIUM_TASK_KEY") ?? "",
                fatal = "",
                gameVersion = VersionControl.CurrentVersionStringWithRev,
                unityVersion = Application.unityVersion,
            };
            try
            {
                TaskBoundary.Install();
                foreach (AssertionDispatch assertion in AssertionPlan)
                {
                    FixtureState.BeginCase(assertion.Id, !assertion.Gate);
                    object randBefore = FixtureRand.Capture();
                    Rand.PushState(0x5EED + envelope.cases.Count);
                    try
                    {
                        CaseObservation observed = assertion.Observe();
                        observed.id = assertion.Id;
                        observed.error = "";
                        envelope.cases.Add(observed);
                    }
                    catch (Exception error)
                    {
                        if (assertion.Gate || !CandidateCall.IsCandidateFailure(error)) throw;
                        envelope.cases.Add(new CaseObservation
                        { id = assertion.Id, error = "candidate operation failed" });
                    }
                    finally
                    {
                        Exception cleanupError = null;
                        try { FixtureState.Restore(); }
                        catch (Exception error) { cleanupError = error; }
                        try { Rand.PopState(); FixtureRand.Check(randBefore); }
                        catch (Exception error) { cleanupError = cleanupError ?? error; }
                        if (cleanupError != null)
                            throw new InvalidOperationException("fixture cleanup failed", cleanupError);
                    }
                }
            }
            catch (Exception error) { envelope.fatal = error.GetType().Name + ": " + error.Message; }
            envelope.terminalMarker = "RIMWORLD_OBSERVATIONS_COMPLETE:" + nonce;
            try
            {
                Directory.CreateDirectory(OutputDirectory);
                File.WriteAllText(Path.Combine(OutputDirectory, "observations.json"),
                    Serialize(envelope) + Environment.NewLine);
                Log.Message("[GCB_RIMWORLD] " + envelope.terminalMarker);
            }
            finally { Application.Quit(string.IsNullOrEmpty(envelope.fatal) ? 0 : 2); }
        }

        private static CaseObservation Observe([CallerMemberName] string fixture = null)
        {
            string value = BehaviorProbe.Observe(fixture);
            return new CaseObservation { facts = new List<FactObservation>
                { new FactObservation { name = "result", value = value } } };
        }

        private static CaseObservation RuntimeDefsReady()
        {
            AdaptiveStorageFixtureSeam.CheckCellAdapter();
            return Observe();
        }

        private static CaseObservation FixtureStateRestored() => Observe();

        private static CaseObservation SavedOneRestored() => Observe();

        private static CaseObservation SavedFiniteRestored() => Observe();

        private static CaseObservation SavedUnlimitedRestored() => Observe();

        private static CaseObservation PerCellRecomputed() => Observe();

        private static CaseObservation MultiCellCeiling() => Observe();

        private static CaseObservation SetterNotSkipped() => Observe();

        private static CaseObservation UnlimitedSentinelPreserved() => Observe();

        private static CaseObservation NearUnlimitedFiniteRestored() => Observe();

        private static CaseObservation ZeroLimitRestored() => Observe();

        private static CaseObservation InitializationNotificationsPreserved() => Observe();

        private static CaseObservation RepeatInitializeIdempotent() => Observe();

        private static CaseObservation InitializationBookkeepingPreserved() => Observe();

        private static CaseObservation DefaultLimitPreserved() => Observe();
    }

    public static class AdaptiveStorageFixtureSeam
    {
        private const string HarmonyId = "rhenium.adaptive.initialization-probe";
        private static readonly Type StorageType = typeof(AdaptiveStorage.ThingClass);
        private static readonly FieldInfo SlotField = RequiredField(StorageType, "_currentSlotLimit");
        private static readonly FieldInfo SlotsByCellField = RequiredField(StorageType, "_maxItemsByCell");
        private static readonly MethodInfo Initialize = StorageType.GetMethod(
            "PostInitialize", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly MethodInfo Setter = AccessTools.PropertySetter(StorageType, "CurrentSlotLimit");
        private static readonly MethodInfo CollectionUpdate = AccessTools.Method(
            typeof(AdaptiveStorage.ThingCollection), "UpdateAllValidStoredItems");
        private static readonly MethodInfo RendererDirty = AccessTools.Method(
            typeof(AdaptiveStorage.StorageRenderer), "SetAllPrintDatasDirty");
        private static readonly FieldInfo InitializedEvent = RequiredField(StorageType, "Initialized");
        private static readonly MethodInfo[] ObservedMethods = { Setter, CollectionUpdate, RendererDirty };
        private static Probe Active;

        private static FieldInfo RequiredField(Type type, string name)
        {
            for (; type != null; type = type.BaseType)
            {
                FieldInfo field = type.GetField(name, BindingFlags.Instance | BindingFlags.Static
                    | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (field != null) return field;
            }
            throw new FixtureFailure("required fixture observation API unavailable");
        }

        public static void InstallBoundary()
        {
            if (Initialize == null || ObservedMethods.Any(method => method == null))
                throw new FixtureFailure("required fixture method unavailable");
            object initializedBefore = InitializedEvent.GetValue(null);
            FixtureState.Watch(() => Active == null && !HasOwnedPatches()
                && Equals(InitializedEvent.GetValue(null), initializedBefore));
        }

        // This checks only the authored adapter against the public game rectangle API.
        // It does not invoke candidate initialization or infer an oracle result.
        public static void CheckCellAdapter()
        {
            foreach (var dimensions in new[] { new IntVec2(3, 2), IntVec2.One, new IntVec2(0, 2) })
            {
                var rectangle = new AdaptiveStorage.StorageCellRect(-2, -3, dimensions.x, dimensions.z);
                var actual = rectangle.ToArray();
                // Compare with the public Cells/Area pair. CellRect's own struct enumerator yields
                // one cell for a zero-width rectangle whose Cells and Area are empty, so no adapter
                // could agree with that enumerator and Area at once.
                var game = new CellRect(-2, -3, dimensions.x, dimensions.z);
                var vanilla = game.Cells.Select(cell => new IntVec2(cell.x, cell.z)).ToArray();
                if (!actual.SequenceEqual(vanilla) || rectangle.Area != game.Area)
                    throw new FixtureFailure("storage rectangle enumeration differs from game API");
                for (int x = -3; x <= 2; x++)
                    for (int z = -4; z <= 0; z++)
                        if (rectangle.Contains(new IntVec2(x, z)) != vanilla.Contains(new IntVec2(x, z)))
                            throw new FixtureFailure("storage rectangle boundary differs from game API");
            }
        }

        private sealed class Probe
        {
            public AdaptiveStorage.ThingClass Storage;
            public int Completed, Notifications, SettingsNotifications, SetterCalls;
            public int CollectionNotifications, RendererNotifications;
            public bool DifferentBeforeSetter = true;
            public bool Notifying;
        }

        // Provide stable color inputs for the real renderer's dirty-state path.
        // No textures or graphics definitions are required by this storage fixture.
        private sealed class FixtureStorage : AdaptiveStorage.ThingClass
        {
            public override Color DrawColor => Color.white;
            public override Color DrawColorTwo => Color.white;
        }

        private static bool HasOwnedPatches() => ObservedMethods.Any(method => method != null
            && Harmony.GetPatchInfo(method)?.Owners.Contains(HarmonyId) == true);

        private static void ObserveSetter(AdaptiveStorage.ThingClass __instance, int value)
        {
            if (Active == null || !ReferenceEquals(Active.Storage, __instance)) return;
            Active.SetterCalls++;
            Active.DifferentBeforeSetter &= (int)SlotField.GetValue(__instance) != value;
        }
        private static void ObserveCollection(AdaptiveStorage.ThingCollection __instance)
        {
            if (Active?.Notifying == true && ReferenceEquals(Active.Storage.StoredThings, __instance))
                Active.CollectionNotifications++;
        }
        private static void ObserveRenderer(AdaptiveStorage.StorageRenderer __instance)
        {
            if (Active?.Notifying == true && ReferenceEquals(Active.Storage.Renderer, __instance))
                Active.RendererNotifications++;
        }

        private static void InstallObservers(Probe probe)
        {
            if (Active != null || HasOwnedPatches()) throw new FixtureFailure("observer already active");
            FixtureState.Require("adaptive-observer");
            Active = probe;
            FixtureState.OnRestore("adaptive-observer", () =>
            {
                new Harmony(HarmonyId).UnpatchAll(HarmonyId);
                Active = null;
            }, () => Active == null && !HasOwnedPatches(), true);
            var harmony = new Harmony(HarmonyId);
            string[] prefixes = { nameof(ObserveSetter), nameof(ObserveCollection), nameof(ObserveRenderer) };
            for (int i = 0; i < ObservedMethods.Length; i++)
                harmony.Patch(ObservedMethods[i], prefix: new HarmonyMethod(
                    AccessTools.Method(typeof(AdaptiveStorageFixtureSeam), prefixes[i])));
            if (ObservedMethods.Any(method => Harmony.GetPatchInfo(method)?.Owners.Contains(HarmonyId) != true))
                throw new FixtureFailure("observer patch installation failed");
        }

        private static void Need(bool valid, string reason)
        {
            if (!valid) throw new CandidateFailure(new InvalidOperationException(reason));
        }

        private static void CheckInitialized(Probe probe, IntVec2 size, int previousCompleted)
        {
            var storage = probe.Storage;
            Need(probe.Completed == previousCompleted + 1, "candidate did not finish initialization");
            Need(SlotsByCellField.GetValue(storage) is int[] cells && cells.Length == size.Area,
                "candidate did not initialize cell bookkeeping");
            Need(storage.Size == size && storage.StoredThings != null && storage.Renderer != null,
                "candidate left partial initialization");
            // Fresh, empty storage must expose a collection for every cell and live renderer views.
            CandidateOperation(() =>
            {
                Need(ReferenceEquals(storage.StoredThings.Parent, storage)
                    && storage.StoredThings.Count == 0 && storage.StoredThings.CellWiseCount == 0
                    && storage.StoredThings.StorageCells.Area == size.Area
                    && storage.StoredThings.FreeStorageSlots.Count == size.Area
                    && storage.Renderer.Printables != null && storage.Renderer.Drawables != null
                    && ReferenceEquals(storage.Renderer.Parent, storage), "candidate collection or renderer invalid");
                for (int i = 0; i < size.Area; i++)
                {
                    var cell = new AdaptiveStorage.StorageCell(size.x, i);
                    Need(storage.StoredThings.ItemsAtStorageCell(in cell).Length == 0
                        && storage.StoredThings.ValidItemsAtStorageCell(in cell).Length == 0,
                        "candidate per-cell collection invalid");
                }
            });
        }

        private static void CandidateOperation(Action action)
        {
            try { action(); }
            catch (CandidateFailure) { throw; }
            catch (Exception error) { throw new CandidateFailure(error); }
        }

        private static Probe Run(int saved, IntVec2 size)
        {
            var probe = new Probe();
            InstallObservers(probe);
            FixtureStorage storage = null;
            CandidateOperation(() => storage = new FixtureStorage());
            probe.Storage = storage;
            FixtureState.Require("adaptive-storage-object-state");
            var fields = new List<FieldInfo>();
            for (Type type = StorageType; type != null; type = type.BaseType)
                fields.AddRange(type.GetFields(BindingFlags.Instance | BindingFlags.Public
                    | BindingFlags.NonPublic | BindingFlags.DeclaredOnly).Where(field => !field.IsInitOnly));
            object[] original = fields.Select(field => field.GetValue(storage)).ToArray();
            // Initial arrays are snapshotted by content as well as reference. New collection/renderer
            // instances are fixture-owned and disconnected when every original field is restored.
            Array[] arrays = original.Select(value => value is Array a ? (Array)a.Clone() : null).ToArray();
            Func<bool> restored = () => fields.Select((field, i) => Equals(field.GetValue(storage), original[i])
                && (arrays[i] == null || ((Array)original[i]).Cast<object>().SequenceEqual(arrays[i].Cast<object>())))
                .All(value => value);
            storage.def = new ThingDef
            {
                defName = "RheniumStorageFixture", category = ThingCategory.Building,
                size = size, building = new BuildingProperties { maxItemsInCell = 1 },
            };
            // Mirror a loaded Building_Storage's owned settings without running candidate PostMake.
            RequiredField(typeof(Building_Storage), "settings").SetValue(storage, new StorageSettings(storage));
            SlotField.SetValue(storage, saved);
            FixtureState.OnRestore("adaptive-storage-object-state", () =>
            {
                for (int i = 0; i < fields.Count; ++i)
                {
                    if (arrays[i] != null) Array.Copy(arrays[i], (Array)original[i], arrays[i].Length);
                    fields[i].SetValue(storage, original[i]);
                }
            }, restored, !restored());

            Action<Thing> completed = thing => { if (ReferenceEquals(thing, storage)) probe.Completed++; };
            Action changed = () => probe.Notifications++;
            Action settings = () => probe.SettingsNotifications++;
            FixtureState.Require("adaptive-initialized-event");
            object before = InitializedEvent.GetValue(null);
            FixtureState.OnRestore("adaptive-initialized-event", () =>
            {
                AdaptiveStorage.ThingClass.Initialized -= completed;
                storage.SlotLimitChanged -= changed;
                storage.StorageSettingsChanged -= settings;
            }, () => Equals(InitializedEvent.GetValue(null), before), true);
            AdaptiveStorage.ThingClass.Initialized += completed;
            storage.SlotLimitChanged += changed;
            storage.StorageSettingsChanged += settings;
            CandidateCall.Invoke(Initialize, storage, null);
            CandidateOperation(() => CheckInitialized(probe, size, 0));
            return probe;
        }

        private static string Cells(Probe probe) => string.Join(",", (int[])SlotsByCellField.GetValue(probe.Storage));

        public static string Observe(string fixture)
        {
            switch (fixture)
            {
                case "FixtureStateRestored":
                    // Object and static-event obligations are required at actual mutation sites.
                    // A candidate constructor can fail before either resource exists.
                    return FixtureState.VerifyAndReset("adaptive-observer");
                case "SavedOneRestored": return Run(1, new IntVec2(2, 2)).Storage.CurrentSlotLimit.ToString();
                case "SavedFiniteRestored":
                {
                    var result = Run(3, new IntVec2(2, 2));
                    return result.Storage.CurrentSlotLimit + ":" + SlotField.GetValue(result.Storage);
                }
                case "SavedUnlimitedRestored":
                {
                    var result = Run(int.MaxValue, new IntVec2(2, 2));
                    return SlotField.GetValue(result.Storage) + ":" + result.Notifications;
                }
                case "PerCellRecomputed": return Cells(Run(int.MaxValue, new IntVec2(2, 2)));
                case "MultiCellCeiling": return Cells(Run(3, new IntVec2(2, 2)));
                case "SetterNotSkipped":
                {
                    var result = Run(int.MaxValue, IntVec2.One);
                    return result.SetterCalls + ":" + result.DifferentBeforeSetter + ":"
                        + result.Notifications + ":" + result.SettingsNotifications;
                }
                case "UnlimitedSentinelPreserved":
                {
                    var result = Run(int.MaxValue, IntVec2.One);
                    return SlotField.GetValue(result.Storage) + ":" + result.Storage.CurrentSlotLimit;
                }
                case "NearUnlimitedFiniteRestored":
                {
                    var result = Run(int.MaxValue - 1, IntVec2.One);
                    return SlotField.GetValue(result.Storage) + ":" + result.Storage.CurrentSlotLimit;
                }
                case "ZeroLimitRestored": return Cells(Run(0, new IntVec2(2, 2)));
                case "RepeatInitializeIdempotent":
                {
                    var result = Run(int.MaxValue, new IntVec2(2, 2));
                    string first = Cells(result);
                    int previous = result.Completed;
                    CandidateCall.Invoke(Initialize, result.Storage, null);
                    CandidateOperation(() => CheckInitialized(result, new IntVec2(2, 2), previous));
                    return first + ":" + Cells(result);
                }
                case "InitializationBookkeepingPreserved":
                {
                    var result = Run(2, new IntVec2(2, 1));
                    return result.Storage.Size.x + "x" + result.Storage.Size.z + ":" + result.Storage.TotalSlots;
                }
                case "InitializationNotificationsPreserved":
                {
                    var result = Run(2, new IntVec2(2, 1));
                    result.Notifying = true;
                    CandidateOperation(() => result.Storage.Notify_SettingsChanged());
                    result.Notifying = false;
                    return (result.CollectionNotifications > 0) + ":" + (result.RendererNotifications > 0);
                }
                case "DefaultLimitPreserved": return SlotField.GetValue(Run(int.MaxValue, IntVec2.One).Storage).ToString();
                default: throw new FixtureFailure("unknown Adaptive Storage fixture");
            }
        }
    }

    public static class TaskBoundary
    {
        public static void Install()
        {
            // Capture global definitions independently of each case's restorers.
            FixtureState.Watch(() => Scribe.mode == LoadSaveMode.Inactive);
            var kinds = DefDatabase<PawnKindDef>.AllDefsListForReading.ToArray();
            var ranges = kinds.Select(def => def.gearHealthRange).ToArray();
            var defs = DefDatabase<ThingDef>.AllDefsListForReading.ToArray();
            var hitpoints = defs.Select(def => def.useHitPoints).ToArray();
            FixtureState.Watch(() => kinds.SequenceEqual(DefDatabase<PawnKindDef>.AllDefsListForReading)
                && kinds.Select(def => def.gearHealthRange).SequenceEqual(ranges)
                && defs.SequenceEqual(DefDatabase<ThingDef>.AllDefsListForReading)
                && defs.Select(def => def.useHitPoints).SequenceEqual(hitpoints));
            var abilities = DefDatabase<AbilityDef>.AllDefsListForReading.ToArray();
            FixtureState.Watch(() => abilities.SequenceEqual(DefDatabase<AbilityDef>.AllDefsListForReading));
            AdaptiveStorageFixtureSeam.InstallBoundary();
        }
    }
}
