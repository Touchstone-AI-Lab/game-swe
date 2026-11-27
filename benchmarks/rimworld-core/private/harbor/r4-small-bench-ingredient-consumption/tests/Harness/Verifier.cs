using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using RimWorld;
using RRRR;
using UnityEngine;
using Verse;
using MaterialUtility = RRRR.MaterialUtility;
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

        private static CaseObservation RuntimeDefsReady() => Observe();

        private static CaseObservation FixtureStateRestored() => Observe();

        private static CaseObservation EmptyCostNoop() => Observe();

        private static CaseObservation NullCostNoop() => Observe();

        private static CaseObservation StackCellFirst() => Observe();

        private static CaseObservation SmallBenchAdjacent() => Observe();

        private static CaseObservation InteractionCellOrigin() => Observe();

        private static CaseObservation DuplicateCostsAggregate() => Observe();

        private static CaseObservation PartialStackPreserved() => Observe();

        private static CaseObservation MultipleStacksExact() => Observe();

        private static CaseObservation UnrelatedDefPreserved() => Observe();

        private static CaseObservation NonItemPreserved() => Observe();

        private static CaseObservation ImpassableCellSkipped() => Observe();

        private static CaseObservation AlreadyVisitedNotRecounted() => Observe();

        private static CaseObservation RadiusBoundaryIncluded() => Observe();

        private static CaseObservation OutsideRadiusPreserved() => Observe();
    }

    public static class RRRRFixtureSeam
    {
        public static void InstallBoundary()
        {
            // Object/grid/holder snapshots are retained by FixtureState until the final gate.
        }

        private sealed class Scene
        {
            public readonly Map Map;
            public readonly Building_WorkTable Bench;
            public readonly ThingDef Material;
            private readonly List<Thing> _registeredThings = new List<Thing>();
            private readonly List<Building> _registeredEdifices = new List<Building>();
            private bool _cleanupRegistered;

            public Scene(bool interactionCell)
            {
                FixtureState.Require("r4-map-grid");
                Map = new Map();
                var info = new MapInfo { Size = new IntVec3(31, 1, 31) };
                SetMember(Map, "info", info);
                SetMember(Map, "cellIndices", new CellIndices(Map));
                SetMember(Map, "thingGrid", new ThingGrid(Map));
                SetMember(Map, "edificeGrid", new EdificeGrid(Map));

                Bench = new Building_WorkTable
                {
                    def = new ThingDef
                    {
                        defName = "RheniumFixtureBench",
                        category = ThingCategory.Building,
                        size = IntVec2.One,
                        passability = Traversability.Impassable,
                        hasInteractionCell = interactionCell,
                        interactionCellOffset = interactionCell ? new IntVec3(0, 0, -1) : IntVec3.Zero,
                    },
                    Position = new IntVec3(15, 0, 15),
                };
                Material = new ThingDef
                {
                    defName = "RheniumFixtureMaterial",
                    category = ThingCategory.Item,
                    stackLimit = 75,
                };
            }

            public Thing Add(IntVec3 cell, int count, ThingDef definition = null)
            {
                var item = new ThingWithComps
                {
                    def = definition ?? Material,
                    stackCount = count,
                    Position = cell,
                };
                Map.thingGrid.Register(item);
                _registeredThings.Add(item);
                RegisterCleanup();
                return item;
            }

            public void AddEdifice(Building edifice)
            {
                Map.edificeGrid.Register(edifice);
                _registeredEdifices.Add(edifice);
                RegisterCleanup();
            }

            private void RegisterCleanup()
            {
                if (_cleanupRegistered) return;
                _cleanupRegistered = true;
                FixtureState.OnRestore(
                    "r4-map-grid",
                    () =>
                    {
                        MethodInfo deregisterThing = typeof(ThingGrid).GetMethod(
                            "Deregister", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                            ?? typeof(ThingGrid).GetMethod(
                                "DeRegister", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                        MethodInfo deregisterEdifice = typeof(EdificeGrid).GetMethod(
                            "Deregister", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                            ?? typeof(EdificeGrid).GetMethod(
                                "DeRegister", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                        if (deregisterThing == null || deregisterEdifice == null)
                            throw new MissingMethodException("RimWorld grid deregistration API is unavailable");
                        foreach (Building edifice in _registeredEdifices)
                        {
                            if (Map.edificeGrid[edifice.Position] == edifice)
                                deregisterEdifice.Invoke(Map.edificeGrid, new object[] { edifice });
                        }
                        foreach (Thing thing in _registeredThings)
                        {
                            if (Map.thingGrid.ThingsListAtFast(thing.Position).Contains(thing))
                                // RimWorld 1.6 adds doEvenIfDespawned; the fixture things are never spawned.
                                deregisterThing.Invoke(Map.thingGrid, deregisterThing.GetParameters().Length == 2
                                    ? new object[] { thing, true }
                                    : new object[] { thing });
                        }
                    },
                    () => Map.AllCells.All(cell => Map.thingGrid.ThingsListAtFast(cell).Count == 0
                        && Map.edificeGrid[cell] == null),
                    _registeredThings.Any(thing => Map.thingGrid.ThingsListAtFast(thing.Position).Contains(thing))
                        || _registeredEdifices.Any(thing => Map.edificeGrid[thing.Position] == thing));
            }

            // RimWorld 1.6 resolves the interaction cell of a bench without one to an adjacent
            // standable cell of its spawned map. The fixture bench is never spawned, so a bench
            // without an interaction cell uses its own position, the origin consumption uses.
            public IntVec3 Origin => Bench.def.hasInteractionCell ? Bench.InteractionCell : Bench.Position;

            public IntVec3 AtRadius(float radius)
            {
                int index = Mathf.Max(0, GenRadial.NumCellsInRadius(radius) - 1);
                return Origin + GenRadial.RadialPattern[index];
            }
        }

        private static void SetMember(object target, string name, object value)
        {
            Type type = target.GetType();
            FieldInfo field = type.GetField(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field != null) { field.SetValue(target, value); return; }
            PropertyInfo property = type.GetProperty(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (property == null) throw new MissingMemberException(type.FullName, name);
            property.SetValue(target, value, null);
        }

        private static void Consume(Scene scene, List<ThingDefCountClass> costs) =>
            CandidateCall.Invoke(() => MaterialUtility.ConsumeIngredientsOnBench(scene.Bench, scene.Map, costs));

        private static bool Gone(Thing thing) => thing.Destroyed || thing.stackCount <= 0;

        public static string Observe(string fixture)
        {
            if (fixture == "FixtureStateRestored")
                return FixtureState.VerifyAndReset("r4-map-grid");

            var scene = new Scene(fixture == "InteractionCellOrigin");
            IntVec3 adjacent = scene.Origin + IntVec3.East;
            switch (fixture)
            {
                case "EmptyCostNoop":
                {
                    Thing item = scene.Add(adjacent, 4);
                    Consume(scene, new List<ThingDefCountClass>());
                    return item.stackCount.ToString();
                }
                case "NullCostNoop":
                {
                    Thing item = scene.Add(adjacent, 4);
                    Consume(scene, null);
                    return item.stackCount.ToString();
                }
                case "StackCellFirst":
                {
                    Thing onBench = scene.Add(scene.Bench.Position, 1);
                    Thing nearby = scene.Add(adjacent, 1);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 1) });
                    return Gone(onBench) + ":" + Gone(nearby);
                }
                case "SmallBenchAdjacent":
                case "InteractionCellOrigin":
                {
                    Thing item = scene.Add(adjacent, 1);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 1) });
                    return Gone(item).ToString();
                }
                case "DuplicateCostsAggregate":
                {
                    Thing item = scene.Add(adjacent, 5);
                    Consume(scene, new List<ThingDefCountClass>
                    {
                        new ThingDefCountClass(scene.Material, 2),
                        new ThingDefCountClass(scene.Material, 3),
                    });
                    return Gone(item).ToString();
                }
                case "PartialStackPreserved":
                {
                    Thing item = scene.Add(adjacent, 7);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 3) });
                    return item.stackCount.ToString();
                }
                case "MultipleStacksExact":
                {
                    Thing first = scene.Add(adjacent, 2);
                    Thing second = scene.Add(adjacent + IntVec3.East, 4);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 5) });
                    int remaining = (Gone(first) ? 0 : first.stackCount) + (Gone(second) ? 0 : second.stackCount);
                    return remaining.ToString();
                }
                case "UnrelatedDefPreserved":
                {
                    var unrelated = new ThingDef { defName = "RheniumUnrelated", category = ThingCategory.Item };
                    Thing item = scene.Add(adjacent, 2, unrelated);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 2) });
                    return item.stackCount.ToString();
                }
                case "NonItemPreserved":
                {
                    var nonItem = new ThingDef { defName = "RheniumNonItem", category = ThingCategory.Building };
                    Thing item = scene.Add(adjacent, 1, nonItem);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(nonItem, 1) });
                    return Gone(item).ToString();
                }
                case "ImpassableCellSkipped":
                {
                    var blocker = new Building
                    {
                        def = new ThingDef
                        {
                            defName = "RheniumBlocker", category = ThingCategory.Building,
                            passability = Traversability.Impassable, surfaceType = SurfaceType.None,
                        },
                        Position = adjacent,
                    };
                    scene.AddEdifice(blocker);
                    Thing item = scene.Add(adjacent, 1);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 1) });
                    return Gone(item).ToString();
                }
                case "AlreadyVisitedNotRecounted":
                {
                    Thing item = scene.Add(scene.Bench.Position, 2);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 3) });
                    return Gone(item).ToString();
                }
                case "RadiusBoundaryIncluded":
                {
                    Thing item = scene.Add(scene.AtRadius(6f), 1);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 1) });
                    return Gone(item).ToString();
                }
                case "OutsideRadiusPreserved":
                {
                    Thing item = scene.Add(scene.Origin + new IntVec3(7, 0, 0), 1);
                    Consume(scene, new List<ThingDefCountClass> { new ThingDefCountClass(scene.Material, 1) });
                    return Gone(item).ToString();
                }
                default:
                    throw new InvalidOperationException("unknown R4 consumption fixture");
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
            RRRRFixtureSeam.InstallBoundary();
        }
    }
}
