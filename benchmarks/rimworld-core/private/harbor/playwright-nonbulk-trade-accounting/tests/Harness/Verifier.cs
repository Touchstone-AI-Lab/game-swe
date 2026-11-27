using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Serialization;
using HarmonyLib;
using RimWorld;
using Rokk.Playwright.ScenParts;
using UnityEngine;
using Verse;
using Rhenium.RimWorld.TaskSupport;
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

        private static CaseObservation NonbulkSaleCaptured() => Observe();

        private static CaseObservation NonbulkSaleCounted() => Observe();

        private static CaseObservation BulkSaleCounted() => Observe();

        private static CaseObservation MultipleScenpartsNotified() => Observe();

        private static CaseObservation FactionPartNotified() => Observe();

        private static CaseObservation NullFactionSkipped() => Observe();

        private static CaseObservation PurchaseNotCounted() => Observe();

        private static CaseObservation ZeroTransferNotCounted() => Observe();

        private static CaseObservation EmptyTradeableNotCounted() => Observe();

        private static CaseObservation MissingScenarioNotCounted() => Observe();

        private static CaseObservation DefinitionPreservedAfterResolve() => Observe();

        private static CaseObservation SingleNotification() => Observe();
    }

    public static class PlaywrightFixtureSeam
    {
        public static void InstallBoundary()
        {
            var initial0 = _action;
            var initial1 = _colony;
            var initial2 = _trader;
            var initial3 = _definition;
            var initial4 = _count;
            var initial5 = _scenario;
            var initial6 = TradeSession.trader;
            FixtureState.Watch(() => Equals(initial0, _action)
                && Equals(initial1, _colony)
                && Equals(initial2, _trader)
                && Equals(initial3, _definition)
                && Equals(initial4, _count)
                && Equals(initial5, _scenario)
                && Equals(initial6, TradeSession.trader));
            FixtureState.Watch(() => !_installed && !HasOwnedPatches());
        }

        private static readonly Assembly Candidate = AppDomain.CurrentDomain.GetAssemblies()
            .Single(assembly => assembly.GetName().Name == "Playwright");
        private static readonly Type Patch = Candidate.GetType(
            "Rokk.Playwright.Patches.Tradeable_ResolveTradePatches", true);
        private static readonly MethodInfo Prefix = Patch.GetMethod(
            "Prefix", BindingFlags.NonPublic | BindingFlags.Static);
        private static readonly MethodInfo Postfix = Patch.GetMethod(
            "Postfix", BindingFlags.NonPublic | BindingFlags.Static);

        private static TradeAction _action;
        private static Thing _colony;
        private static Thing _trader;
        private static ThingDef _definition;
        private static int _count;
        private static Scenario _scenario;
        private static bool _installed;
        private const string HarmonyId = "rhenium.playwright.fixtures";
        private static readonly List<MethodBase> PatchedMethods = new List<MethodBase>();

        private sealed class StaticSnapshot
        {
            private readonly TradeAction _savedAction = _action;
            private readonly Thing _savedColony = _colony;
            private readonly Thing _savedTrader = _trader;
            private readonly ThingDef _savedDefinition = _definition;
            private readonly int _savedCount = _count;
            private readonly Scenario _savedScenario = _scenario;
            private readonly FieldInfo _tradeSessionTraderField = typeof(TradeSession).GetField(
                "trader", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
                ?? throw new MissingFieldException(typeof(TradeSession).FullName, "trader");
            private readonly object _savedSessionTrader;

            public StaticSnapshot() => _savedSessionTrader = _tradeSessionTraderField.GetValue(null);

            public void Register()
            {
                bool mutationObserved = _savedAction != _action
                    || !ReferenceEquals(_savedColony, _colony)
                    || !ReferenceEquals(_savedTrader, _trader)
                    || !ReferenceEquals(_savedDefinition, _definition)
                    || _savedCount != _count
                    || !ReferenceEquals(_savedScenario, _scenario)
                    || !ReferenceEquals(_savedSessionTrader, _tradeSessionTraderField.GetValue(null));
                FixtureState.OnRestore(
                    "playwright-trade-static-state",
                    () =>
                    {
                        _action = _savedAction;
                        _colony = _savedColony;
                        _trader = _savedTrader;
                        _definition = _savedDefinition;
                        _count = _savedCount;
                        _scenario = _savedScenario;
                        _tradeSessionTraderField.SetValue(null, _savedSessionTrader);
                    },
                    () => _savedAction == _action
                        && ReferenceEquals(_savedColony, _colony)
                        && ReferenceEquals(_savedTrader, _trader)
                        && ReferenceEquals(_savedDefinition, _definition)
                        && _savedCount == _count
                        && ReferenceEquals(_savedScenario, _scenario)
                        && ReferenceEquals(_savedSessionTrader, _tradeSessionTraderField.GetValue(null)),
                    mutationObserved);
            }
        }

        private static void InstallGetterPatches()
        {
            if (_installed) return;
            _installed = true;
            var harmony = new Harmony(HarmonyId);
            PatchGetter(harmony, typeof(Tradeable), "get_ActionToDo", nameof(ActionPrefix));
            PatchGetter(harmony, typeof(Tradeable), "get_FirstThingColony", nameof(ColonyPrefix));
            PatchGetter(harmony, typeof(Tradeable), "get_FirstThingTrader", nameof(TraderThingPrefix));
            PatchGetter(harmony, typeof(Tradeable), "get_ThingDef", nameof(DefinitionPrefix));
            // RimWorld 1.6 declares this getter on Transferable, and Harmony patches only declared methods.
            PatchGetter(harmony, typeof(Transferable), "get_CountToTransferToDestination", nameof(CountPrefix));
            PatchGetter(harmony, typeof(Find), "get_Scenario", nameof(ScenarioPrefix));
        }

        private static void PatchGetter(Harmony harmony, Type type, string methodName, string prefixName)
        {
            MethodInfo original = AccessTools.Method(type, methodName)
                ?? throw new MissingMethodException(type.FullName, methodName);
            MethodInfo prefix = typeof(PlaywrightFixtureSeam).GetMethod(
                prefixName, BindingFlags.NonPublic | BindingFlags.Static);
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

        private static bool ActionPrefix(ref TradeAction __result) { __result = _action; return false; }
        private static bool ColonyPrefix(ref Thing __result) { __result = _colony; return false; }
        private static bool TraderThingPrefix(ref Thing __result) { __result = _trader; return false; }
        private static bool DefinitionPrefix(ref ThingDef __result) { __result = _definition; return false; }
        private static bool CountPrefix(ref int __result) { __result = _count; return false; }
        private static bool ScenarioPrefix(ref Scenario __result) { __result = _scenario; return false; }

        private static object Capture(TradeAction action, bool colonyThing, bool traderThing, int count)
        {
            FixtureState.Require("owned-harmony-patches");
            try { InstallGetterPatches(); }
            finally
            {
                FixtureState.OnRestore("owned-harmony-patches", RemovePatches,
                    () => !_installed && !HasOwnedPatches(), _installed || HasOwnedPatches());
            }
            _action = action;
            _definition = new ThingDef { defName = "RheniumTradeGood", category = ThingCategory.Item };
            _colony = colonyThing ? new ThingWithComps { def = _definition } : null;
            _trader = traderThing ? new ThingWithComps { def = _definition } : null;
            _count = count;
            Type stateType = Patch.GetNestedType("SoldThing", BindingFlags.Public);
            if (Prefix == null || stateType == null) return null;
            object state = Activator.CreateInstance(stateType);
            object[] arguments = { FormatterServices.GetUninitializedObject(typeof(Tradeable)), state };
            CandidateCall.Invoke(Prefix, null, arguments);
            return arguments[1];
        }

        private static T Read<T>(object target, string name)
        {
            if (target == null) throw new CandidateFailure(new InvalidOperationException("candidate state absent"));
            FieldInfo field = target.GetType().GetField(name,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field == null || field.FieldType != typeof(T))
                throw new CandidateFailure(new MissingFieldException("candidate state contract"));
            return (T)field.GetValue(target);
        }

        private static Scenario ScenarioWith(params ScenPart[] parts)
        {
            var scenario = (Scenario)FormatterServices.GetUninitializedObject(typeof(Scenario));
            FieldInfo field = typeof(Scenario).GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .Single(candidate => typeof(List<ScenPart>).IsAssignableFrom(candidate.FieldType));
            field.SetValue(scenario, parts.ToList());
            // RimWorld 1.6 Scenario.AllParts yields the player-faction and surface-layer parts
            // before the list, and a real scenario always has them. Give the fixture scenario such
            // parts, with their own defs, so AllParts holds no null entries.
            foreach (FieldInfo single in typeof(Scenario).GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                         .Where(candidate => typeof(ScenPart).IsAssignableFrom(candidate.FieldType)))
            {
                var part = (ScenPart)FormatterServices.GetUninitializedObject(single.FieldType);
                part.def = new ScenPartDef { defName = "RheniumFixtureScenario_" + single.Name };
                single.SetValue(scenario, part);
            }
            return scenario;
        }

        private static void InvokePostfix(object state)
        {
            if (Postfix == null) throw new CandidateFailure(new MissingMethodException("candidate Postfix"));
            if (Postfix.GetParameters().Length == 1)
            {
                ParameterInfo parameter = Postfix.GetParameters()[0];
                CandidateCall.Invoke(Postfix, null, parameter.ParameterType == typeof(Tradeable)
                    ? new[] { FormatterServices.GetUninitializedObject(typeof(Tradeable)) }
                    : new[] { state });
            }
            else
                CandidateCall.Invoke(Postfix, null, new[] { FormatterServices.GetUninitializedObject(typeof(Tradeable)) });
        }

        private static void SetTradeSessionTrader(object trader)
        {
            FieldInfo field = typeof(TradeSession).GetField("trader",
                BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
                ?? throw new MissingFieldException(typeof(TradeSession).FullName, "trader");
            field.SetValue(null, trader);
        }

        private static TradeShip NewTradeShip(Faction faction)
        {
            var ship = (TradeShip)FormatterServices.GetUninitializedObject(typeof(TradeShip));
            // RimWorld 1.6 keeps the faction in a private field of the PassingShip base class,
            // which reflection on TradeShip alone does not return.
            MemberInfo member = null;
            for (Type type = typeof(TradeShip); member == null && type != null; type = type.BaseType)
                member = type.GetMembers(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
                    .FirstOrDefault(candidate =>
                        (candidate is FieldInfo field && field.FieldType == typeof(Faction))
                        || (candidate is PropertyInfo property && property.PropertyType == typeof(Faction) && property.CanWrite));
            if (member == null) throw new MissingMemberException(typeof(TradeShip).FullName, "faction");
            if (member is FieldInfo factionField) factionField.SetValue(ship, faction);
            else ((PropertyInfo)member).SetValue(ship, faction, null);
            return ship;
        }

        public static string Observe(string fixture)
        {
            if (fixture == "FixtureStateRestored")
            {
                RemovePatches();
                if (HasOwnedPatches())
                    throw new InvalidOperationException("Playwright fixture patches remain installed");
                PatchedMethods.Clear();
                return FixtureState.VerifyAndReset("playwright-trade-static-state");
            }

            FixtureState.Require("playwright-trade-static-state");
            var snapshot = new StaticSnapshot();
            try
            {
                switch (fixture)
                {
                case "NonbulkSaleCaptured":
                case "DefinitionPreservedAfterResolve":
                {
                    object state = Capture(TradeAction.PlayerSells, true, false, 3);
                    ThingDef definition = state == null ? null : Read<ThingDef>(state, "Def");
                    int count = state == null ? -1 : Read<int>(state, "Count");
                    return (definition?.defName ?? "null") + ":" + count;
                }
                case "PurchaseNotCounted":
                {
                    object state = Capture(TradeAction.PlayerBuys, true, false, 3);
                    if (state == null) { _scenario = null; InvokePostfix(null); return "null-state"; }
                    return Read<ThingDef>(state, "Def")?.defName ?? "null-def";
                }
                case "ZeroTransferNotCounted":
                {
                    object state = Capture(TradeAction.PlayerSells, true, false, 0);
                    _scenario = ScenarioWith(new WinCondition_SellItems());
                    InvokePostfix(state);
                    return _scenario.AllParts.OfType<WinCondition_SellItems>().First().Notifications.ToString();
                }
                case "EmptyTradeableNotCounted":
                {
                    object state = Capture(TradeAction.PlayerSells, false, false, 2);
                    _scenario = ScenarioWith(new WinCondition_SellItems());
                    InvokePostfix(state);
                    return _scenario.AllParts.OfType<WinCondition_SellItems>().First().Notifications.ToString();
                }
                case "MissingScenarioNotCounted":
                {
                    object state = Capture(TradeAction.PlayerSells, true, false, 2);
                    _scenario = null;
                    InvokePostfix(state);
                    return (_scenario == null).ToString();
                }
                case "NonbulkSaleCounted":
                case "BulkSaleCounted":
                case "SingleNotification":
                {
                    int count = fixture == "BulkSaleCounted" ? 12 : 1;
                    var part = new WinCondition_SellItems();
                    _scenario = ScenarioWith(part);
                    object state = Capture(TradeAction.PlayerSells, true, fixture == "BulkSaleCounted", count);
                    if (fixture != "BulkSaleCounted") { _colony = null; _count = 0; }
                    InvokePostfix(state);
                    if (fixture == "SingleNotification") return part.Notifications.ToString();
                    return part.ObservedCount + ":" + part.Notifications;
                }
                case "MultipleScenpartsNotified":
                {
                    var first = new WinCondition_SellItems();
                    var second = new WinCondition_SellItems();
                    _scenario = ScenarioWith(first, second);
                    object state = Capture(TradeAction.PlayerSells, true, false, 2);
                    _colony = null;
                    _count = 0;
                    InvokePostfix(state);
                    return first.Notifications + ":" + second.Notifications;
                }
                case "FactionPartNotified":
                {
                    var faction = new Faction { def = new FactionDef { defName = "RheniumTradeFaction" } };
                    var part = new WinCondition_SellItemsToFaction();
                    _scenario = ScenarioWith(part);
                    SetTradeSessionTrader(NewTradeShip(faction));
                    object state = Capture(TradeAction.PlayerSells, true, false, 1);
                    _colony = null;
                    _count = 0;
                    InvokePostfix(state);
                    return part.Notifications + ":" + (part.ObservedFaction?.def?.defName ?? "null");
                }
                case "NullFactionSkipped":
                {
                    var part = new WinCondition_SellItemsToFaction();
                    _scenario = ScenarioWith(part);
                    SetTradeSessionTrader(null);
                    InvokePostfix(Capture(TradeAction.PlayerSells, true, false, 1));
                    return part.Notifications.ToString();
                }
                    default:
                        throw new InvalidOperationException("unknown Playwright fixture");
                }
            }
            finally { snapshot.Register(); }
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
            PlaywrightFixtureSeam.InstallBoundary();
        }
    }
}
