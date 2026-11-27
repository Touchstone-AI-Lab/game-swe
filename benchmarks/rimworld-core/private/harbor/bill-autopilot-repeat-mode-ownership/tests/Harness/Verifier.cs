using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using BillAutopilot;
using HarmonyLib;
using RimWorld;
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
            ScribeFixture.ProbeTransport();
            return Observe();
        }

        private static CaseObservation FixtureStateRestored() => Observe();

        private static CaseObservation ForeignModeRecognized() => Observe();

        private static CaseObservation TargetCountOwned() => Observe();

        private static CaseObservation ForeverOwned() => Observe();

        private static CaseObservation RepeatCountPreserved() => Observe();

        private static CaseObservation ForeignDriftNotFlattened() => Observe();

        private static CaseObservation ForeignModeRemembered() => Observe();

        private static CaseObservation ForeignModeRestored() => Observe();

        private static CaseObservation ForeignShouldDoNowTrue() => Observe();

        private static CaseObservation ForeignShouldDoNowFalse() => Observe();

        private static CaseObservation UnresolvedModeFallsBack() => Observe();

        private static CaseObservation BusyBillNotRetired() => Observe();

        private static CaseObservation BillNamePersisted() => Observe();

        private static CaseObservation LinkedGroupPersisted() => Observe();

        private static CaseObservation MemoryRoundtrip() => Observe();

        private static CaseObservation MissingFieldsDefault() => Observe();
    }

    public static class BillAutopilotFixtureSeam
    {
        public static void InstallBoundary()
        {
            FixtureState.Watch(() => !_probePatchesInstalled && !HasProbePatches());
            var initial0 = _probeDue;
            var initial1 = BillAutopilotState.Current;
            FixtureState.Watch(() => Equals(initial0, _probeDue)
                && Equals(initial1, BillAutopilotState.Current));
        }

        private static readonly Assembly Candidate = AppDomain.CurrentDomain.GetAssemblies()
            .Single(assembly => assembly.GetName().Name == "BillAutopilot");
        private static readonly Type SyncType = Candidate.GetType("BillAutopilot.AutoBillSync", true);
        private static readonly Type MemoryType = Candidate.GetType("BillAutopilot.BillMemory", true);
        public sealed class MemoryEnvelope : IExposable
        {
            private MemoryNode node = new MemoryNode();
            public BillMemory Memory => node?.Memory;
            public void ExposeData() => Scribe_Deep.Look(ref node, "memory");
        }
        // Own only the Scribe node: its payload is a fresh real BillMemory and
        // every field is saved/loaded by the candidate's actual ExposeData.
        public sealed class MemoryNode : IExposable
        {
            public readonly BillMemory Memory = new BillMemory();
            public void ExposeData() => ScribeFixture.ExposeCandidate(() => Memory.ExposeData());
        }

        private static MemoryEnvelope SaveMemory(Action<System.Xml.XmlDocument> edit = null)
        {
            var envelope = new MemoryEnvelope();
            envelope.Memory.name = "fixture name";
            envelope.Memory.linkedTo.Add(17);
            envelope.Memory.countAway = true;
            MemoryType.GetField("repeatModeDefName")?.SetValue(envelope.Memory, "RheniumForeignRepeatMode");
            MemoryEnvelope loaded = ScribeFixture.Roundtrip(envelope, edit);
            if (loaded.Memory == null || ReferenceEquals(loaded.Memory, envelope.Memory))
                throw new FixtureFailure("memory was not loaded into a fresh instance");
            return loaded;
        }

        private static bool HasProbePatches() => Harmony.GetAllPatchedMethods().Any(method =>
            Harmony.GetPatchInfo(method)?.Owners.Contains("rhenium.billautopilot.fixtures") == true);

        private static bool _probeDue;
        private static bool _probePatchesInstalled;

        private sealed class BillContext
        {
            public readonly ThingDef BenchDef = new ThingDef { defName = "RheniumBench" };
            // RimWorld 1.6 Bill construction copies the recipe's default ingredient filter.
            public readonly RecipeDef Recipe = new RecipeDef { defName = "RheniumRecipe", defaultIngredientFilter = new ThingFilter() };
            public readonly Bill_Production Bill;
            public readonly BillAutopilotState State = new BillAutopilotState();
            public readonly BenchProfile Profile = new BenchProfile();
            public readonly BillStamp Stamp = new BillStamp { mode = AutoMode.Maintain, targetCount = 10, floorCount = 5 };

            public BillContext()
            {
                Bill = Recipe.MakeNewBill() as Bill_Production
                    ?? throw new InvalidOperationException("fixture recipe did not create a production bill");
                State.Claim(Bill, Stamp);
            }
        }

        private static BillRepeatModeDef Foreign() => new BillRepeatModeDef
        {
            defName = "RheniumForeignRepeatMode",
            label = "fixture foreign repeat mode",
        };

        private static MethodInfo Method(string name) => SyncType.GetMethod(
            name, BindingFlags.Static | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(SyncType.FullName, name);

        private static bool IsForeign(BillRepeatModeDef mode)
        {
            MethodInfo method = SyncType.GetMethod("IsForeignMode", BindingFlags.Static | BindingFlags.NonPublic);
            return method != null && (bool)CandidateCall.Invoke(method, null, new object[] { mode });
        }

        private static bool ShouldRetire(BillContext context)
        {
            InstallProbePatches();
            _probeDue = true;
            return (bool)CandidateCall.Invoke(Method("ShouldRetire"), null, new object[]
            {
                new Building_WorkTable(), context.Recipe, context.Bill, context.Profile, AutoMode.Maintain,
            });
        }

        private static void CaptureDrift(BillContext context)
        {
            CandidateCall.Invoke(Method("CaptureDrift"), null, new object[]
            {
                context.State, context.BenchDef, context.Recipe, context.Bill, context.Profile,
            });
        }

        private static string MemoryField(object memory)
        {
            FieldInfo field = MemoryType.GetField("repeatModeDefName", BindingFlags.Instance | BindingFlags.Public);
            return field == null ? null : (string)field.GetValue(memory);
        }

        private static void InstallProbePatches()
        {
            if (_probePatchesInstalled) return;
            _probePatchesInstalled = true;
            var harmony = new Harmony("rhenium.billautopilot.fixtures");
            harmony.Patch(AccessTools.PropertyGetter(typeof(Thing), nameof(Thing.Map)),
                prefix: new HarmonyMethod(typeof(BillAutopilotFixtureSeam), nameof(MapPrefix)));
            harmony.Patch(AccessTools.Method(typeof(Bill_Production), nameof(Bill_Production.ShouldDoNow)),
                prefix: new HarmonyMethod(typeof(BillAutopilotFixtureSeam), nameof(ShouldDoNowPrefix)));
        }

        private static bool MapPrefix(ref Map __result)
        {
            // A bare RimWorld 1.6 Map has no pawn registry; the busy check reads its spawned pawns.
            var map = new Map();
            map.mapPawns = new MapPawns(map);
            __result = map;
            return false;
        }
        private static bool ShouldDoNowPrefix(ref bool __result) { __result = _probeDue; return false; }

        private static string ProbeForeignMode(bool due)
        {
            Type probe = Candidate.GetType("BillAutopilot.RecipeProbe", true);
            MethodInfo method = probe.GetMethod("TryShouldDoNow", BindingFlags.Static | BindingFlags.Public);
            if (method == null) return "missing";
            InstallProbePatches();
            _probeDue = due;
            var context = new BillContext();
            object memory = Activator.CreateInstance(MemoryType);
            object[] arguments =
            {
                new Building_WorkTable(), context.Recipe, memory, Foreign(), 10, 5, false,
            };
            bool invoked = (bool)CandidateCall.Invoke(method, null, arguments);
            bool observedDue = (bool)arguments[6];
            return invoked + ":" + observedDue;
        }

        public static string Observe(string fixture)
        {
            if (fixture != "FixtureStateRestored")
            {
                FixtureState.Require("bill-probe-state");
                var previous = BillAutopilotState.Current;
                bool due = _probeDue;
                BillAutopilotState.Current = new BillAutopilotState();
                FixtureState.OnRestore("bill-probe-state", () =>
                {
                    new Harmony("rhenium.billautopilot.fixtures").UnpatchAll("rhenium.billautopilot.fixtures");
                    _probePatchesInstalled = false;
                    _probeDue = due;
                    BillAutopilotState.Current = previous;
                }, () => ReferenceEquals(BillAutopilotState.Current, previous) && _probeDue == due
                    && !_probePatchesInstalled && !HasProbePatches(),
                    !ReferenceEquals(BillAutopilotState.Current, previous));
            }
            switch (fixture)
            {
                case "ForeignModeRecognized":
                    return IsForeign(Foreign()).ToString();
                case "TargetCountOwned":
                    return IsForeign(BillRepeatModeDefOf.TargetCount).ToString();
                case "ForeverOwned":
                    return IsForeign(BillRepeatModeDefOf.Forever).ToString();
                case "RepeatCountPreserved":
                {
                    var context = new BillContext();
                    context.Bill.repeatMode = BillRepeatModeDefOf.RepeatCount;
                    CaptureDrift(context);
                    return context.Bill.repeatMode?.defName ?? "null";
                }
                case "ForeignDriftNotFlattened":
                {
                    var context = new BillContext();
                    BillRepeatModeDef foreign = Foreign();
                    context.Bill.repeatMode = foreign;
                    CaptureDrift(context);
                    return (context.Bill.repeatMode?.defName ?? "null") + ":" + context.Stamp.mode;
                }
                case "ForeignModeRemembered":
                {
                    var context = new BillContext();
                    context.Bill.repeatMode = Foreign();
                    var table = new Building_WorkTable { def = context.BenchDef };
                    BillStack stack = table.billStack;
                    stack.AddBill(context.Bill);
                    CandidateCall.Invoke(Method("Remove"), null, new object[]
                    {
                        context.State, stack, context.BenchDef, context.Recipe, context.Bill,
                    });
                    object memory = context.State.MemoryFor(context.BenchDef, context.Recipe);
                    return memory == null ? "null" : MemoryField(memory) ?? "null-field";
                }
                case "ForeignModeRestored":
                {
                    var context = new BillContext();
                    object memory = Activator.CreateInstance(MemoryType);
                    MemoryType.GetField("repeatModeDefName", BindingFlags.Instance | BindingFlags.Public)
                        ?.SetValue(memory, BillRepeatModeDefOf.RepeatCount.defName);
                    context.State.Remember(context.BenchDef, context.Recipe, (BillMemory)memory);
                    var table = new Building_WorkTable { def = context.BenchDef };
                    CandidateCall.Invoke(Method("Create"), null, new object[]
                    {
                        context.State, table, context.Recipe, context.Profile, AutoMode.Maintain, false,
                    });
                    Bill_Production created = table.billStack.Bills.OfType<Bill_Production>().LastOrDefault();
                    return created?.repeatMode?.defName ?? "null";
                }
                case "ForeignShouldDoNowTrue":
                    return ProbeForeignMode(true);
                case "ForeignShouldDoNowFalse":
                    return ProbeForeignMode(false);
                case "UnresolvedModeFallsBack":
                {
                    var context = new BillContext();
                    object memory = Activator.CreateInstance(MemoryType);
                    MemoryType.GetField("repeatModeDefName")?.SetValue(memory, "RheniumMissingRepeatMode");
                    context.State.Remember(context.BenchDef, context.Recipe, (BillMemory)memory);
                    var table = new Building_WorkTable { def = context.BenchDef };
                    CandidateCall.Invoke(Method("Create"), null, new object[]
                    {
                        context.State, table, context.Recipe, context.Profile, AutoMode.Maintain, false,
                    });
                    Bill_Production created = table.billStack.Bills.OfType<Bill_Production>().LastOrDefault();
                    return (created?.repeatMode == BillRepeatModeDefOf.TargetCount).ToString();
                }
                case "BusyBillNotRetired":
                {
                    var context = new BillContext();
                    return ShouldRetire(context).ToString();
                }
                case "BillNamePersisted":
                    return SaveMemory().Memory.name ?? "null";
                case "LinkedGroupPersisted":
                {
                    var groups = SaveMemory().Memory.linkedTo;
                    return groups == null ? "null" : string.Join(",", groups);
                }
                case "MemoryRoundtrip":
                    return MemoryField(SaveMemory().Memory) ?? "null";
                case "MissingFieldsDefault":
                {
                    MemoryEnvelope loaded = SaveMemory(xml =>
                    {
                        var node = xml.SelectSingleNode("/RheniumFixture/payload/memory");
                        if (node == null) throw new FixtureFailure("missing memory save node");
                        foreach (string name in new[] { "repeatMode", "name", "linkedTo", "countAway" })
                        {
                            var child = node.SelectSingleNode(name);
                            if (child != null) node.RemoveChild(child);
                        }
                    });
                    return (MemoryField(loaded.Memory) == null) + ":" + (loaded.Memory.name == null)
                        + ":" + (loaded.Memory.linkedTo != null && loaded.Memory.linkedTo.Count == 0)
                        + ":" + !loaded.Memory.countAway;
                }
                case "FixtureStateRestored":
                    return FixtureState.VerifyAndReset("bill-probe-state", "scribe-temp");
                default:
                    throw new InvalidOperationException("unknown Bill Autopilot fixture");
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
            BillAutopilotFixtureSeam.InstallBoundary();
        }
    }
    // The disk transport sentinel verifies the fixture itself. Candidate field
    // observations are graded separately, so deleted Scribe calls are mismatches.
    public static class ScribeFixture
    {
        // Verse may catch ExposeData exceptions itself; keep the production fault
        // observable without interpreting missing candidate fields as transport faults.
        private static CandidateFailure candidateError;
        public static void ExposeCandidate(Action expose)
        {
            try { CandidateCall.Invoke(expose); }
            catch (CandidateFailure error) { candidateError = error; throw; }
        }
        public sealed class TransportPayload : IExposable
        {
            public int Value;
            public bool SawPostLoad;
            public void ExposeData()
            {
                Scribe_Values.Look(ref Value, "value");
                if (Scribe.mode == LoadSaveMode.PostLoadInit) SawPostLoad = true;
            }
        }
        public static void ProbeTransport()
        {
            var saved = new TransportPayload { Value = 27431 };
            TransportPayload loaded = Roundtrip(saved);
            if (loaded.Value != saved.Value || !loaded.SawPostLoad)
                throw new FixtureFailure("independent Scribe transport probe failed");
        }
        public static T Roundtrip<T>(T source, Action<System.Xml.XmlDocument> edit = null)
            where T : class, IExposable
        {
            if (Scribe.mode != LoadSaveMode.Inactive)
                throw new FixtureFailure("Scribe was already active");
            string directory = Path.Combine("/tmp", "rhenium-scribe-" + Guid.NewGuid().ToString("N"));
            string file = Path.Combine(directory, "fixture.xml");
            FixtureState.Require("scribe-temp");
            Directory.CreateDirectory(directory);
            FixtureState.OnRestore("scribe-temp", () =>
            {
                Scribe.ForceStop();
                if (Directory.Exists(directory)) Directory.Delete(directory, true);
            }, () => Scribe.mode == LoadSaveMode.Inactive && !Directory.Exists(directory),
                Directory.Exists(directory));
            candidateError = null;
            T saved = source;
            int sentinel = 73129;
            try
            {
                Scribe.saver.InitSaving(file, "RheniumFixture");
                Scribe_Values.Look(ref sentinel, "transportSentinel");
                Scribe_Deep.Look(ref saved, "payload");
                Scribe.saver.FinalizeSaving();
                if (candidateError != null) throw candidateError;
                if (!File.Exists(file) || new FileInfo(file).Length == 0)
                    throw new FixtureFailure("Scribe produced no save");
                if (edit != null)
                {
                    var xml = new System.Xml.XmlDocument { XmlResolver = null };
                    xml.Load(file);
                    edit(xml);
                    xml.Save(file);
                }
                // Scribe_Deep constructs the loaded root and its children. Never
                // read the saved instance as the result of this transport.
                T loaded = null;
                sentinel = -1;
                Scribe.loader.InitLoading(file);
                Scribe_Values.Look(ref sentinel, "transportSentinel");
                Scribe_Deep.Look(ref loaded, "payload");
                Scribe.loader.FinalizeLoading();
                if (candidateError != null) throw candidateError;
                if (sentinel != 73129 || loaded == null || ReferenceEquals(source, loaded)
                    || Scribe.mode != LoadSaveMode.Inactive)
                    throw new FixtureFailure("Scribe transport did not load a fresh object");
                return loaded;
            }
            catch (Exception error) when (CandidateCall.IsCandidateFailure(error)) { throw; }
            catch { throw new FixtureFailure("Scribe save/load fixture failed"); }
            finally { Scribe.ForceStop(); candidateError = null; }
        }
    }
}
