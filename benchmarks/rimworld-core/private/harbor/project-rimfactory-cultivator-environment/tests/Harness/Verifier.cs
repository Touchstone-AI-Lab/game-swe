using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using RimWorld;
using ProjectRimFactory;
using ProjectRimFactory.CultivatorTools;
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

        private static CaseObservation LocalSeasonAllows() => Observe();

        private static CaseObservation LocalSeasonRejects() => Observe();

        private static CaseObservation MapTemperatureNotAuthoritative() => Observe();

        private static CaseObservation SowabilityRejects() => Observe();

        private static CaseObservation AdjacentBlockerRejects() => Observe();

        private static CaseObservation VacuumResistantAllows() => Observe();

        private static CaseObservation VacuumSensitiveRejects() => Observe();

        private static CaseObservation VacuumBoundaryRejects() => Observe();

        private static CaseObservation SeedUnavailableRejects() => Observe();

        private static CaseObservation SinglePlacement() => Observe();

    }

    public static class ProjectRimFactoryFixtureSeam
    {
        public static void InstallBoundary()
        {
            var initial0 = _canPlant;
            var initial1 = _growthSeason;
            var initial2 = _blocked;
            var initial3 = _vacuum;
            var initial4 = _placements;
            var initial5 = _checkMapTemperatureDisabled;
            var initial6 = ProjectRimFactory_ModComponent.ModSupport_SeedsPlease;
            var initial7 = SeedsPleaseSupport.AllowPlanting;
            FixtureState.Watch(() => Equals(initial0, _canPlant)
                && Equals(initial1, _growthSeason)
                && Equals(initial2, _blocked)
                && Equals(initial3, _vacuum)
                && Equals(initial4, _placements)
                && Equals(initial5, _checkMapTemperatureDisabled)
                && Equals(initial6, ProjectRimFactory_ModComponent.ModSupport_SeedsPlease)
                && Equals(initial7, SeedsPleaseSupport.AllowPlanting));
            FixtureState.Watch(() => !_installed && !HasOwnedPatches());
        }

        private static readonly Assembly Candidate = AppDomain.CurrentDomain.GetAssemblies()
            .Single(assembly => assembly.GetName().Name == "ProjectRimFactory");
        private static readonly Type Cultivator = Candidate.GetType(
            "ProjectRimFactory.CultivatorTools.Building_Cultivator", true);
        private static readonly MethodInfo TryPlant = Cultivator.GetMethod(
            "TryPlantNew", BindingFlags.Instance | BindingFlags.NonPublic);

        private static bool _canPlant;
        private static bool _growthSeason;
        private static bool _blocked;
        private static float _vacuum;
        private static int _placements;
        private static bool _checkMapTemperatureDisabled;
        private static bool _installed;
        private const string HarmonyId = "rhenium.projectrimfactory.fixtures";
        private static readonly List<MethodBase> PatchedMethods = new List<MethodBase>();

        private static void Install()
        {
            if (_installed) return;
            _installed = true;
            var harmony = new Harmony(HarmonyId);
            foreach (Type type in GenTypes.AllTypes)
            {
                foreach (MethodInfo method in type.GetMethods(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
                {
                    if (method.Name == "CanEverPlantAt" && method.ReturnType == typeof(bool))
                        Patch(harmony, method, nameof(CanPlantPrefix));
                    else if (method.Name == "GrowthSeasonNow" && method.ReturnType == typeof(bool))
                        Patch(harmony, method, nameof(GrowthPrefix));
                    else if (method.Name == "AdjacentSowBlocker" && typeof(Thing).IsAssignableFrom(method.ReturnType))
                        Patch(harmony, method, nameof(BlockerPrefix));
                    else if (method.Name == "GetVacuum" && method.ReturnType == typeof(float))
                        Patch(harmony, method, nameof(VacuumPrefix));
                }
            }
            foreach (MethodInfo method in typeof(GenPlace).GetMethods(BindingFlags.Static | BindingFlags.Public)
                         .Where(method => method.Name == nameof(GenPlace.TryPlaceThing) && method.ReturnType == typeof(bool)))
                Patch(harmony, method, nameof(PlacementPrefix));
            Patch(harmony, AccessTools.PropertyGetter(typeof(Thing), nameof(Thing.Map)), nameof(MapPrefix));
        }

        private static void Patch(Harmony harmony, MethodInfo original, string prefixName)
        {
            MethodInfo prefix = typeof(ProjectRimFactoryFixtureSeam).GetMethod(
                prefixName, BindingFlags.Static | BindingFlags.NonPublic);
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

        private static bool CanPlantPrefix(ref bool __result, object[] __args)
        {
            _checkMapTemperatureDisabled = __args.OfType<bool>().Any(value => !value);
            __result = _canPlant;
            return false;
        }
        private static bool GrowthPrefix(ref bool __result) { __result = _growthSeason; return false; }
        private static bool BlockerPrefix(ref Thing __result)
        {
            __result = _blocked ? new ThingWithComps { def = new ThingDef { defName = "RheniumSowBlocker" } } : null;
            return false;
        }
        private static bool VacuumPrefix(ref float __result) { __result = _vacuum; return false; }
        private static bool PlacementPrefix(ref bool __result) { _placements++; __result = true; return false; }
        private static bool MapPrefix(ref Map __result) { __result = new Map(); return false; }

        private static int Run(bool canPlant = true, bool growth = true, bool blocked = false,
            float vacuum = 0f, bool resistant = false, bool seeds = true)
        {
            FixtureState.Require("owned-harmony-patches");
            FixtureState.Require("project-rimfactory-static-state");
            try { Install(); }
            finally
            {
                FixtureState.OnRestore("owned-harmony-patches", RemovePatches,
                    () => !_installed && !HasOwnedPatches(), _installed || HasOwnedPatches());
            }
            bool previousCanPlant = _canPlant;
            bool previousGrowthSeason = _growthSeason;
            bool previousBlocked = _blocked;
            float previousVacuum = _vacuum;
            int previousPlacements = _placements;
            bool previousTemperatureFlag = _checkMapTemperatureDisabled;
            bool previousSeedsSupport = ProjectRimFactory_ModComponent.ModSupport_SeedsPlease;
            bool previousAllowPlanting = SeedsPleaseSupport.AllowPlanting;
            _canPlant = canPlant;
            _growthSeason = growth;
            _blocked = blocked;
            _vacuum = vacuum;
            _placements = 0;
            _checkMapTemperatureDisabled = false;
            ProjectRimFactory_ModComponent.ModSupport_SeedsPlease = !seeds;
            SeedsPleaseSupport.AllowPlanting = seeds;
            bool mutationObserved = previousCanPlant != _canPlant
                || previousGrowthSeason != _growthSeason
                || previousBlocked != _blocked
                || previousVacuum != _vacuum
                || previousPlacements != _placements
                || previousTemperatureFlag != _checkMapTemperatureDisabled
                || previousSeedsSupport != ProjectRimFactory_ModComponent.ModSupport_SeedsPlease
                || previousAllowPlanting != SeedsPleaseSupport.AllowPlanting;
            FixtureState.OnRestore(
                "project-rimfactory-static-state",
                () =>
                {
                    _canPlant = previousCanPlant;
                    _growthSeason = previousGrowthSeason;
                    _blocked = previousBlocked;
                    _vacuum = previousVacuum;
                    _placements = previousPlacements;
                    _checkMapTemperatureDisabled = previousTemperatureFlag;
                    ProjectRimFactory_ModComponent.ModSupport_SeedsPlease = previousSeedsSupport;
                    SeedsPleaseSupport.AllowPlanting = previousAllowPlanting;
                },
                () => _canPlant == previousCanPlant
                    && _growthSeason == previousGrowthSeason
                    && _blocked == previousBlocked
                    && _vacuum == previousVacuum
                    && _placements == previousPlacements
                    && _checkMapTemperatureDisabled == previousTemperatureFlag
                    && ProjectRimFactory_ModComponent.ModSupport_SeedsPlease == previousSeedsSupport
                    && SeedsPleaseSupport.AllowPlanting == previousAllowPlanting,
                mutationObserved);
            object cultivator = Activator.CreateInstance(Cultivator);
            ThingDef plant = new ThingDef
            {
                defName = "RheniumFixturePlant",
                category = ThingCategory.Plant,
                thingClass = typeof(Plant),
                plant = new PlantProperties { vacuumResistant = resistant },
            };
            if (!seeds)
                plant.blueprintDef = new ThingDef { defName = "RheniumFixtureSeed", category = ThingCategory.Item };
            CandidateCall.Invoke(TryPlant, cultivator, new object[] { new IntVec3(1, 0, 1), plant });
            return _placements;
        }

        public static string Observe(string fixture)
        {
            switch (fixture)
            {
                case "FixtureStateRestored":
                    RemovePatches();
                    if (HasOwnedPatches())
                        throw new InvalidOperationException("Project RimFactory fixture patches remain installed");
                    PatchedMethods.Clear();
                    return FixtureState.VerifyAndReset("project-rimfactory-static-state");
                case "LocalSeasonAllows": return Run().ToString();
                case "LocalSeasonRejects": return Run(growth: false).ToString();
                case "MapTemperatureNotAuthoritative":
                {
                    int placements = Run();
                    return placements + ":" + _checkMapTemperatureDisabled;
                }
                case "SowabilityRejects": return Run(canPlant: false).ToString();
                case "AdjacentBlockerRejects": return Run(blocked: true).ToString();
                case "VacuumResistantAllows": return Run(vacuum: 0.9f, resistant: true).ToString();
                case "VacuumSensitiveRejects": return Run(vacuum: 0.9f).ToString();
                case "VacuumBoundaryRejects": return Run(vacuum: 0.5f).ToString();
                case "SeedUnavailableRejects": return Run(seeds: false).ToString();
                case "SinglePlacement": return Run().ToString();
                default: throw new InvalidOperationException("unknown Project RimFactory fixture");
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
            ProjectRimFactoryFixtureSeam.InstallBoundary();
        }
    }
}
