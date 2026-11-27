using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Serialization;
using CRC_Reintegrated;
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
        private static CaseObservation HomeMapOverridesVanilla() => Observe();
        private static CaseObservation HomeMapQueriesArmouryOnce() => Observe();
        private static CaseObservation NonhomeMapPassesThrough() => Observe();
        private static CaseObservation NonhomeMapSkipsArmoury() => Observe();
        private static CaseObservation FixedWealthPassesThrough() => Observe();
        private static CaseObservation FixedWealthSkipsArmoury() => Observe();
        private static CaseObservation ZeroComponentsRemainZero() => Observe();
        private static CaseObservation ArmouryWealthStaysRaw() => Observe();
        private static CaseObservation BuildingPercentageStaysRaw() => Observe();
        private static CaseObservation WealthComponentsAdd() => Observe();
        private static CaseObservation ZeroBuildingPercentage() => Observe();
        private static CaseObservation FullBuildingPercentage() => Observe();
        private static CaseObservation FractionalBuildingPercentage() => Observe();
        private static CaseObservation AboveFullPercentagePreserved() => Observe();
    }

    public static class CombatReadinessFixtureSeam
    {
        public static void InstallBoundary()
        {
            var initial0 = _home;
            var initial1 = _buildingWealth;
            var initial2 = _storyteller;
            var initial3 = CRC_Loader.Settings.PercentOfValueForBuildings;
            var initial4 = ArmouryUtility.FixtureArmouryPoints;
            var initial5 = ArmouryUtility.Calls;
            var initial6 = MarvsStoryTellerUtility.PointsPerWealthCurve.Calls;
            FixtureState.Watch(() => Equals(initial0, _home)
                && Equals(initial1, _buildingWealth)
                && Equals(initial2, _storyteller)
                && Equals(initial3, CRC_Loader.Settings.PercentOfValueForBuildings)
                && Equals(initial4, ArmouryUtility.FixtureArmouryPoints)
                && Equals(initial5, ArmouryUtility.Calls)
                && Equals(initial6, MarvsStoryTellerUtility.PointsPerWealthCurve.Calls));
            FixtureState.Watch(() => !_installed && !HasOwnedPatches());
        }

        private sealed class ProbeResult
        {
            public bool UseOriginal;
            public float Result;
            public int ArmouryCalls;
            public int CurveCalls;
        }

        private static bool _home;
        private static float _buildingWealth;
        private static Storyteller _storyteller;
        private static bool _installed;
        private const string HarmonyId = "rhenium.combatreadiness.fixtures";
        private static readonly List<MethodBase> PatchedMethods = new List<MethodBase>();

        private static void InstallPatches()
        {
            if (_installed) return;
            _installed = true;
            var harmony = new Harmony(HarmonyId);
            PatchGetter(harmony, typeof(Map), "get_IsPlayerHome", nameof(HomePrefix));
            PatchGetter(harmony, typeof(WealthWatcher), "get_WealthBuildings", nameof(BuildingPrefix));
            PatchGetter(harmony, typeof(Find), "get_Storyteller", nameof(StorytellerPrefix));
        }

        private static void PatchGetter(Harmony harmony, Type type, string methodName, string prefixName)
        {
            MethodInfo original = AccessTools.Method(type, methodName)
                ?? throw new MissingMethodException(type.FullName, methodName);
            MethodInfo prefix = typeof(CombatReadinessFixtureSeam).GetMethod(
                prefixName, BindingFlags.NonPublic | BindingFlags.Static)
                ?? throw new MissingMethodException(typeof(CombatReadinessFixtureSeam).FullName, prefixName);
            if (!PatchedMethods.Contains(original)) PatchedMethods.Add(original);
            harmony.Patch(original, prefix: new HarmonyMethod(prefix));
        }

        private static void RemovePatches()
        {
            new Harmony(HarmonyId).UnpatchAll(HarmonyId);
            _installed = false;
        }

        private static bool HasOwnedPatches() => PatchedMethods.Any(method =>
            Harmony.GetPatchInfo(method)?.Owners.Contains(HarmonyId) == true);

        private static bool HomePrefix(ref bool __result) { __result = _home; return false; }
        private static bool BuildingPrefix(ref float __result) { __result = _buildingWealth; return false; }
        private static bool StorytellerPrefix(ref Storyteller __result) { __result = _storyteller; return false; }

        private static void SetMember(object instance, string name, object value)
        {
            Type type = instance.GetType();
            FieldInfo field = type.GetField(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field != null) { field.SetValue(instance, value); return; }
            PropertyInfo property = type.GetProperty(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (property == null || !property.CanWrite)
                throw new MissingMemberException(type.FullName, name);
            property.SetValue(instance, value, null);
        }

        private static object GetMember(object instance, string name)
        {
            Type type = instance.GetType();
            FieldInfo field = type.GetField(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field != null) return field.GetValue(instance);
            PropertyInfo property = type.GetProperty(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (property == null) throw new MissingMemberException(type.FullName, name);
            return property.GetValue(instance, null);
        }

        private static Storyteller StorytellerWithFixedWealth(bool fixedWealth)
        {
            var storyteller = (Storyteller)FormatterServices.GetUninitializedObject(typeof(Storyteller));
            MemberInfo difficultyMember = typeof(Storyteller).GetMember("difficulty",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).Single();
            Type difficultyType = difficultyMember is FieldInfo field
                ? field.FieldType
                : ((PropertyInfo)difficultyMember).PropertyType;
            object difficulty = FormatterServices.GetUninitializedObject(difficultyType);
            SetMember(difficulty, "fixedWealthMode", fixedWealth);
            SetMember(storyteller, "difficulty", difficulty);
            return storyteller;
        }

        private static Map MapWithWealthWatcher()
        {
            var map = (Map)FormatterServices.GetUninitializedObject(typeof(Map));
            object watcher = FormatterServices.GetUninitializedObject(typeof(WealthWatcher));
            SetMember(map, "wealthWatcher", watcher);
            return map;
        }

        private static ProbeResult Execute(
            bool home,
            bool fixedWealth,
            float armoury,
            float buildings,
            float percentage,
            float initial)
        {
            FixtureState.Require("owned-harmony-patches");
            FixtureState.Require("combat-readiness-static-state");
            try { InstallPatches(); }
            finally
            {
                FixtureState.OnRestore("owned-harmony-patches", RemovePatches,
                    () => !_installed && !HasOwnedPatches(), _installed || HasOwnedPatches());
            }
            bool previousHome = _home;
            float previousBuildingWealth = _buildingWealth;
            Storyteller previousStoryteller = _storyteller;
            float previousPercentage = CRC_Loader.Settings.PercentOfValueForBuildings;
            float previousArmouryPoints = ArmouryUtility.FixtureArmouryPoints;
            int previousArmouryCalls = ArmouryUtility.Calls;
            int previousCurveCalls = MarvsStoryTellerUtility.PointsPerWealthCurve.Calls;
            _home = home;
            _buildingWealth = buildings;
            _storyteller = StorytellerWithFixedWealth(fixedWealth);
            CRC_Loader.Settings.PercentOfValueForBuildings = percentage;
            ArmouryUtility.FixtureArmouryPoints = armoury;
            ArmouryUtility.Calls = 0;
            MarvsStoryTellerUtility.PointsPerWealthCurve.Calls = 0;
            bool mutationObserved = previousHome != _home
                || previousBuildingWealth != _buildingWealth
                || !ReferenceEquals(previousStoryteller, _storyteller)
                || previousPercentage != CRC_Loader.Settings.PercentOfValueForBuildings
                || previousArmouryPoints != ArmouryUtility.FixtureArmouryPoints
                || previousArmouryCalls != ArmouryUtility.Calls
                || previousCurveCalls != MarvsStoryTellerUtility.PointsPerWealthCurve.Calls;
            FixtureState.OnRestore(
                "combat-readiness-static-state",
                () =>
                {
                    _home = previousHome;
                    _buildingWealth = previousBuildingWealth;
                    _storyteller = previousStoryteller;
                    CRC_Loader.Settings.PercentOfValueForBuildings = previousPercentage;
                    ArmouryUtility.FixtureArmouryPoints = previousArmouryPoints;
                    ArmouryUtility.Calls = previousArmouryCalls;
                    MarvsStoryTellerUtility.PointsPerWealthCurve.Calls = previousCurveCalls;
                },
                () => _home == previousHome
                    && _buildingWealth == previousBuildingWealth
                    && ReferenceEquals(_storyteller, previousStoryteller)
                    && CRC_Loader.Settings.PercentOfValueForBuildings == previousPercentage
                    && ArmouryUtility.FixtureArmouryPoints == previousArmouryPoints
                    && ArmouryUtility.Calls == previousArmouryCalls
                    && MarvsStoryTellerUtility.PointsPerWealthCurve.Calls == previousCurveCalls,
                mutationObserved);
            float result = initial;
            Map map = MapWithWealthWatcher();
            bool useOriginal = false;
            CandidateCall.Invoke(() => useOriginal = MarvsMapWealthForStoryTeller.Prefix(map, ref result));
            return new ProbeResult
            {
                UseOriginal = useOriginal,
                Result = result,
                ArmouryCalls = ArmouryUtility.Calls,
                CurveCalls = MarvsStoryTellerUtility.PointsPerWealthCurve.Calls,
            };
        }

        private static string Number(float value) =>
            value.ToString("R", CultureInfo.InvariantCulture);

        private static string Full(ProbeResult probe) =>
            (probe.UseOriginal ? "pass:" : "override:") + Number(probe.Result)
            + ":curve=" + probe.CurveCalls.ToString(CultureInfo.InvariantCulture);

        public static string Observe(string fixture)
        {
            switch (fixture)
            {
                case "FixtureStateRestored":
                    RemovePatches();
                    if (HasOwnedPatches())
                        throw new InvalidOperationException("Combat Readiness fixture patches remain installed");
                    PatchedMethods.Clear();
                    return FixtureState.VerifyAndReset("combat-readiness-static-state");
                case "HomeMapOverridesVanilla":
                    return Execute(true, false, 1f, 1f, 100f, 99f).UseOriginal ? "pass" : "override";
                case "HomeMapQueriesArmouryOnce":
                    return Execute(true, false, 3f, 5f, 20f, 0f).ArmouryCalls.ToString(CultureInfo.InvariantCulture);
                case "NonhomeMapPassesThrough":
                    ProbeResult nonhome = Execute(false, false, 125f, 240f, 25f, 731.25f);
                    return (nonhome.UseOriginal ? "pass:" : "override:") + Number(nonhome.Result);
                case "NonhomeMapSkipsArmoury":
                    return Execute(false, false, 125f, 240f, 25f, 0f).ArmouryCalls.ToString(CultureInfo.InvariantCulture);
                case "FixedWealthPassesThrough":
                    ProbeResult fixedMode = Execute(true, true, 125f, 240f, 25f, 882f);
                    return (fixedMode.UseOriginal ? "pass:" : "override:") + Number(fixedMode.Result);
                case "FixedWealthSkipsArmoury":
                    return Execute(true, true, 125f, 240f, 25f, 0f).ArmouryCalls.ToString(CultureInfo.InvariantCulture);
                case "ZeroComponentsRemainZero":
                    return Full(Execute(true, false, 0f, 0f, 0f, 999f));
                case "ArmouryWealthStaysRaw":
                    return Full(Execute(true, false, 125f, 0f, 0f, 999f));
                case "BuildingPercentageStaysRaw":
                    return Full(Execute(true, false, 0f, 240f, 25f, 999f));
                case "WealthComponentsAdd":
                    return Full(Execute(true, false, 125f, 240f, 25f, 999f));
                case "ZeroBuildingPercentage":
                    return Full(Execute(true, false, 125f, 240f, 0f, 999f));
                case "FullBuildingPercentage":
                    return Full(Execute(true, false, 125f, 240f, 100f, 999f));
                case "FractionalBuildingPercentage":
                    return Full(Execute(true, false, 12.5f, 33f, 12.5f, 999f));
                case "AboveFullPercentagePreserved":
                    return Full(Execute(true, false, 125f, 240f, 125f, 999f));
                default:
                    throw new InvalidOperationException("unknown Combat Readiness fixture");
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
            CombatReadinessFixtureSeam.InstallBoundary();
        }
    }
}
