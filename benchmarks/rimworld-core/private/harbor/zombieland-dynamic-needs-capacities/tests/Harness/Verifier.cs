using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
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

        private static CaseObservation RuntimeDefsReady() => Observe();

        private static CaseObservation FixtureStateRestored() => Observe();

        private static CaseObservation MoodBenefitPreserved() => Observe();
        private static CaseObservation FoodBenefitPreserved() => Observe();
        private static CaseObservation RestBenefitPreserved() => Observe();
        private static CaseObservation NoPainPreserved() => Observe();
        private static CaseObservation UnrelatedPainPreserved() => Observe();
        private static CaseObservation NeedMaxOne() => Observe();

        private static CaseObservation NeedMaxTwo() => Observe();

        private static CaseObservation NeedMaxFractional() => Observe();

        private static CaseObservation NeedMaxChangeObserved() => Observe();

        private static CaseObservation UnrelatedNeedPreserved() => Observe();

        private static CaseObservation InfectedCapacityBelowOne() => Observe();

        private static CaseObservation InfectedCapacityEqualOne() => Observe();

        private static CaseObservation InfectedCapacityAboveOne() => Observe();

        private static CaseObservation SymbiantCapacityAboveOne() => Observe();

        private static CaseObservation DeadPawnCapacityPreserved() => Observe();

        private static CaseObservation UnrelatedPawnCapacityPreserved() => Observe();

        private static CaseObservation CapacityNegativeFloored() => Observe();
    }

    public static class ZombielandFixtureSeam
    {
        public static void InstallBoundary()
        {
            Pawn[] initial = Infected.ToArray();
            FixtureState.Watch(() => Infected.SetEquals(initial));
            Pawn[] mood = ZombieLand.ZombieSymbiant.MoodBenefit.ToArray();
            Pawn[] food = ZombieLand.ZombieSymbiant.FoodRestBenefit.ToArray();
            FixtureState.Watch(() => ZombieLand.ZombieSymbiant.MoodBenefit.SetEquals(mood)
                && ZombieLand.ZombieSymbiant.FoodRestBenefit.SetEquals(food));
        }

        private sealed class DynamicNeed : Need
        {
            public float DynamicMaximum;
            public DynamicNeed(Pawn pawn, float maximum) : base(pawn)
            {
                def = NeedDefOf.Food;
                DynamicMaximum = maximum;
            }
            public override float MaxLevel => DynamicMaximum;
            // RimWorld 1.6 declares NeedInterval abstract; the fixture never ticks this need.
            public override void NeedInterval() { }
        }

        private static Assembly Candidate => AppDomain.CurrentDomain.GetAssemblies()
            .Single(assembly => assembly.GetName().Name == "Zombieland");

        private static Type Patch(string nested) => Candidate.GetType(
            "ZombieLand.Patches+" + nested, true);

        private static HashSet<Pawn> Infected
        {
            get
            {
                FieldInfo field = Patch("Need_CurLevel_Patch").GetField(
                    "infectedColonists", BindingFlags.Public | BindingFlags.Static);
                return (HashSet<Pawn>)field.GetValue(null);
            }
        }

        private static Pawn NewPawn(bool symbiant = false)
        {
            Pawn pawn = symbiant ? new ZombieLand.ZombieSymbiant() : new Pawn();
            pawn.def = ThingDefOf.Human;
            pawn.kindDef = PawnKindDefOf.Colonist;
            var previousTracker = pawn.health;
            pawn.health = new Pawn_HealthTracker(pawn);
            var tracker = pawn.health;
            FieldInfo state = AccessTools.Field(typeof(Pawn_HealthTracker), "healthState");
            if (state == null) throw new FixtureFailure("pawn health-state API unavailable");
            object initial = state.GetValue(tracker);
            FixtureState.Require("zombieland-pawn-health");
            FixtureState.OnRestore("zombieland-pawn-health", () =>
            {
                pawn.health = previousTracker;
                state.SetValue(tracker, initial);
            }, () => ReferenceEquals(pawn.health, previousTracker) && Equals(state.GetValue(tracker), initial),
                !ReferenceEquals(previousTracker, pawn.health));
            return pawn;
        }

        private static float SetProtectedNeed(float maximum, float incoming)
        {
            Pawn pawn = NewPawn();
            Infected.Add(pawn);
            var need = new DynamicNeed(pawn, maximum);
            MethodInfo prefix = Patch("Need_CurLevel_Patch").GetMethod(
                "Prefix", BindingFlags.NonPublic | BindingFlags.Static);
            object[] arguments = { need, incoming };
            CandidateCall.Invoke(prefix, null, arguments);
            return (float)arguments[1];
        }

        private static float ApplyCapacity(Pawn pawn, float observed, bool infected)
        {
            if (infected) Infected.Add(pawn);
            Type patch = Patch("PawnCapacitiesHandler_GetLevel_Patch");
            MethodInfo prefix = patch.GetMethod("Prefix", BindingFlags.NonPublic | BindingFlags.Static);
            MethodInfo postfix = patch.GetMethod("Postfix", BindingFlags.NonPublic | BindingFlags.Static);
            if (prefix == null && postfix == null) throw new CandidateFailure(new MissingMethodException());
            object[] arguments = { pawn, observed };
            if (prefix != null) CandidateCall.Invoke(prefix, null, arguments);
            if (postfix != null) CandidateCall.Invoke(postfix, null, arguments);
            return (float)arguments[1];
        }

        private static bool Nearly(float left, float right) =>
            Math.Abs(left - right) <= 0.00001f;

        public static string Observe(string fixture)
        {
            if (fixture == "FixtureStateRestored")
                return FixtureState.VerifyAndReset("zombieland-membership", "zombieland-pawn-health");
            FixtureState.Require("zombieland-membership");
            var infectedBefore = Infected.ToArray();
            var mood = ZombieLand.ZombieSymbiant.MoodBenefit.ToArray();
            var food = ZombieLand.ZombieSymbiant.FoodRestBenefit.ToArray();
            Pawn sentinel = NewPawn();
            Infected.Add(sentinel);
            FixtureState.OnRestore("zombieland-membership", () =>
            {
                Infected.Clear(); Infected.UnionWith(infectedBefore);
                ZombieLand.ZombieSymbiant.MoodBenefit.Clear();
                ZombieLand.ZombieSymbiant.MoodBenefit.UnionWith(mood);
                ZombieLand.ZombieSymbiant.FoodRestBenefit.Clear();
                ZombieLand.ZombieSymbiant.FoodRestBenefit.UnionWith(food);
            }, () => Infected.SetEquals(infectedBefore)
                && ZombieLand.ZombieSymbiant.MoodBenefit.SetEquals(mood)
                && ZombieLand.ZombieSymbiant.FoodRestBenefit.SetEquals(food),
                Infected.Contains(sentinel) && !infectedBefore.Contains(sentinel));
            Infected.Remove(sentinel);
            switch (fixture)
            {
                case "MoodBenefitPreserved":
                case "FoodBenefitPreserved":
                case "RestBenefitPreserved":
                {
                    Pawn pawn = NewPawn();
                    bool moodCase = fixture == "MoodBenefitPreserved";
                    Need need = moodCase ? (Need)new Need_Mood(pawn) : new DynamicNeed(pawn, 2f);
                    need.def = moodCase ? DefDatabase<NeedDef>.GetNamed("Mood") : fixture == "RestBenefitPreserved"
                        ? DefDatabase<NeedDef>.GetNamed("Rest") : NeedDefOf.Food;
                    if (moodCase) ZombieLand.ZombieSymbiant.MoodBenefit.Add(pawn);
                    else ZombieLand.ZombieSymbiant.FoodRestBenefit.Add(pawn);
                    object[] arguments = { need, 0.17f };
                    CandidateCall.Invoke(Patch("Need_CurLevel_Patch").GetMethod("Prefix",
                        BindingFlags.NonPublic | BindingFlags.Static), null, arguments);
                    return Nearly((float)arguments[1], need.MaxLevel * 0.5f).ToString();
                }
                case "NoPainPreserved":
                case "UnrelatedPainPreserved":
                {
                    Pawn pawn = NewPawn();
                    if (fixture == "NoPainPreserved") Infected.Add(pawn);
                    object[] arguments = { pawn.health.hediffSet, 0.7f };
                    bool runOriginalPain = (bool)CandidateCall.Invoke(Patch("HediffSet_CalculatePain_Patch")
                        .GetMethod("Prefix", BindingFlags.NonPublic | BindingFlags.Static), null, arguments);
                    return runOriginalPain + ":" + ((float)arguments[1]).ToString("0.#####", CultureInfo.InvariantCulture);
                }
                case "NeedMaxOne":
                    return SetProtectedNeed(1f, 0.1f).ToString("0.0", CultureInfo.InvariantCulture);
                case "NeedMaxTwo":
                    return SetProtectedNeed(2f, 0.1f).ToString("0", CultureInfo.InvariantCulture);
                case "NeedMaxFractional":
                    return SetProtectedNeed(1.3f, 0.9f).ToString("0.#####", CultureInfo.InvariantCulture);
                case "NeedMaxChangeObserved":
                {
                    Pawn pawn = NewPawn();
                    Infected.Add(pawn);
                    var need = new DynamicNeed(pawn, 0.8f);
                    MethodInfo prefix = Patch("Need_CurLevel_Patch").GetMethod(
                        "Prefix", BindingFlags.NonPublic | BindingFlags.Static);
                    object[] first = { need, 0.2f };
                    CandidateCall.Invoke(prefix, null, first);
                    need.DynamicMaximum = 1.8f;
                    object[] second = { need, 0.2f };
                    CandidateCall.Invoke(prefix, null, second);
                    return ((float)first[1]).ToString("0.#####", CultureInfo.InvariantCulture)
                        + ":" + ((float)second[1]).ToString("0.#####", CultureInfo.InvariantCulture);
                }
                case "UnrelatedNeedPreserved":
                {
                    Pawn pawn = NewPawn();
                    var need = new DynamicNeed(pawn, 2f);
                    MethodInfo prefix = Patch("Need_CurLevel_Patch").GetMethod(
                        "Prefix", BindingFlags.NonPublic | BindingFlags.Static);
                    object[] arguments = { need, 0.37f };
                    CandidateCall.Invoke(prefix, null, arguments);
                    return ((float)arguments[1]).ToString("0.#####", CultureInfo.InvariantCulture);
                }
                case "InfectedCapacityBelowOne":
                case "CapacityNegativeFloored":
                    return ApplyCapacity(NewPawn(), fixture == "CapacityNegativeFloored" ? -2f : 0.2f, true)
                        .ToString("0.#####", CultureInfo.InvariantCulture);
                case "InfectedCapacityEqualOne":
                    return ApplyCapacity(NewPawn(), 1f, true).ToString("0.#####", CultureInfo.InvariantCulture);
                case "InfectedCapacityAboveOne":
                    return ApplyCapacity(NewPawn(), 1.4f, true).ToString("0.#####", CultureInfo.InvariantCulture);
                case "UnrelatedPawnCapacityPreserved":
                    return ApplyCapacity(NewPawn(), 0.4f, false).ToString("0.#####", CultureInfo.InvariantCulture);
                case "DeadPawnCapacityPreserved":
                {
                    Pawn pawn = NewPawn();
                    var healthState = AccessTools.Field(typeof(Pawn_HealthTracker), "healthState");
                    if (healthState == null) throw new FixtureFailure("health-state fixture API unavailable");
                    healthState.SetValue(pawn.health, PawnHealthState.Dead);
                    if (!pawn.Dead) throw new FixtureFailure("dead-pawn setup failed");
                    return ApplyCapacity(pawn, 0.4f, true).ToString("0.#####", CultureInfo.InvariantCulture);
                }
                case "SymbiantCapacityAboveOne":
                {
                    Pawn pawn = NewPawn(true);
                    return ApplyCapacity(pawn, 1.6f, false).ToString("0.#####", CultureInfo.InvariantCulture);
                }
                default:
                    throw new InvalidOperationException("unknown Zombieland fixture");
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
            ZombielandFixtureSeam.InstallBoundary();
        }
    }
}
