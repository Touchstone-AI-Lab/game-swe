using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using RimWorld;
using RimWorld.Utility;
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
            // Exercise disk transport even when every candidate lifecycle case fails.
            ScribeFixture.ProbeTransport();
            return Observe();
        }

        private static CaseObservation FixtureStateRestored() => Observe();

        private static CaseObservation MissingTrackerCreated() => Observe();

        private static CaseObservation EmptyManagementNoTracker() => Observe();

        private static CaseObservation NoHolderNoTracker() => Observe();

        private static CaseObservation ManagedAbilityAdded() => Observe();

        private static CaseObservation DuplicatePropsDeduplicated() => Observe();

        private static CaseObservation UnrelatedAbilityPreserved() => Observe();

        private static CaseObservation RemovedManagedAbilityPruned() => Observe();

        private static CaseObservation UnequipCapturesState() => Observe();

        private static CaseObservation ReequipRestoresCharges() => Observe();

        private static CaseObservation ReequipRestoresCooldown() => Observe();

        private static CaseObservation PostloadRestoresState() => Observe();

        private static CaseObservation PostloadManagedCleared() => Observe();

        private static CaseObservation HolderUpdateAddsAbility() => Observe();

        private static CaseObservation StaleStatePruned() => Observe();

        private static CaseObservation NullPropertiesTolerated() => Observe();

        private static CaseObservation ReloadPathPreserved() => Observe();
    }

    public static class CWFFixtureSeam
    {
        public static void InstallBoundary()
        {
            // Object/grid/holder snapshots are retained by FixtureState until the final gate.
        }

        private static readonly Assembly Candidate = AppDomain.CurrentDomain.GetAssemblies()
            .Single(assembly => assembly.GetName().Name == "CWF");
        private static readonly Type ProviderType = Candidate.GetType("CWF.CompAbilityProvider", true);
        private static readonly FieldInfo Managed = ProviderType.GetField(
            "_managedAbilityDefs", BindingFlags.Instance | BindingFlags.NonPublic);
        private static readonly FieldInfo States = ProviderType.GetField(
            "_abilityStates", BindingFlags.Instance | BindingFlags.NonPublic);

        // Equipment dispatch still reaches the actual candidate overrides. The
        // wrapper marks only exceptions crossing those production boundaries;
        // errors elsewhere in the game's equipment setup remain fixture-fatal.
        public sealed class ObservedProvider : CWF.CompAbilityProvider
        {
            public override void Notify_Equipped(Pawn pawn)
                => CandidateCall.Invoke(() => base.Notify_Equipped(pawn));
            public override void Notify_Unequipped(Pawn pawn)
                => CandidateCall.Invoke(() => base.Notify_Unequipped(pawn));
        }

        public sealed class Context
        {
            public readonly Pawn Pawn;
            public readonly ThingWithComps Weapon;
            public readonly CWF.CompAbilityProvider Provider;
            public readonly AbilityDef ManagedDef;
            public readonly AbilityDef OtherDef;
            public readonly CompProperties_EquippableAbilityReloadable Props;

            public Context(bool tracker, bool registerDefs = true)
            {
                FixtureState.Require("cwf-holder-state");
                Pawn = new Pawn { def = ThingDefOf.Human, kindDef = PawnKindDefOf.Colonist };
                Pawn.health = new Pawn_HealthTracker(Pawn);
                Pawn.equipment = new Pawn_EquipmentTracker(Pawn);
                // RimWorld 1.6 AddEquipment clears the holder's mindState.droppedWeapon.
                Pawn.mindState = new Verse.AI.Pawn_MindState(Pawn);
                Pawn.abilities = tracker ? new Pawn_AbilityTracker(Pawn) : null;
                ManagedDef = registerDefs ? NewAbilityDef("RheniumManagedAbility")
                    : DefDatabase<AbilityDef>.GetNamed("RheniumManagedAbility");
                OtherDef = registerDefs ? NewAbilityDef("RheniumOtherAbility")
                    : DefDatabase<AbilityDef>.GetNamed("RheniumOtherAbility");
                Props = new CompProperties_EquippableAbilityReloadable
                {
                    abilityDef = ManagedDef, maxCharges = 5, ammoCountPerCharge = 1,
                    ammoDef = ThingDefOf.Steel,
                };
                var definition = new ThingDef
                {
                    defName = "RheniumFixtureWeapon", category = ThingCategory.Item,
                    thingClass = typeof(ThingWithComps), equipmentType = EquipmentType.Primary,
                    comps = new List<CompProperties>
                    {
                        new CompProperties(typeof(CompEquippable)),
                        new CompProperties(typeof(ObservedProvider)),
                    },
                };
                // RimWorld 1.6 keeps ThingDef.verbs private behind the read-only Verbs property.
                typeof(ThingDef).GetField("verbs", BindingFlags.Instance | BindingFlags.NonPublic)
                    .SetValue(definition, new List<VerbProperties>());
                Weapon = (ThingWithComps)ThingMaker.MakeThing(definition);
                Provider = (CWF.CompAbilityProvider)Weapon.AllComps.Single(comp => comp.GetType() == typeof(ObservedProvider));
                var originalTracker = Pawn.abilities;
                var originalManaged = (HashSet<AbilityDef>)Managed.GetValue(Provider);
                FieldInfo propsField = ProviderType.GetField("_abilityPropsToManage",
                    BindingFlags.Instance | BindingFlags.NonPublic);
                var originalProps = (System.Collections.IList)propsField.GetValue(Provider);
                var originalStates = (System.Collections.IList)States.GetValue(Provider);
                FixtureState.OnRestore("cwf-holder-state", () =>
                {
                    // Fixture cleanup is independent of candidate unequip correctness.
                    Pawn.equipment.GetDirectlyHeldThings().Remove(Weapon);
                    Pawn.abilities = originalTracker;
                    originalManaged.Clear();
                    if (!ReferenceEquals(Managed.GetValue(Provider), originalManaged))
                        Managed.SetValue(Provider, originalManaged);
                    originalProps.Clear();
                    originalStates.Clear();
                    propsField.SetValue(Provider, originalProps);
                    States.SetValue(Provider, originalStates);
                    if (originalTracker != null)
                    {
                        originalTracker.RemoveAbility(ManagedDef);
                        originalTracker.RemoveAbility(OtherDef);
                    }
                }, () => Weapon.ParentHolder == null
                    && Pawn.equipment.AllEquipmentListForReading.Count == 0
                    && ReferenceEquals(Pawn.abilities, originalTracker)
                    && ReferenceEquals(Managed.GetValue(Provider), originalManaged)
                    && ManagedCount == 0 && StateCount == 0
                    && ReferenceEquals(propsField.GetValue(Provider), originalProps) && originalProps.Count == 0
                    && (originalTracker == null || originalTracker.abilities.Count == 0),
                    ReferenceEquals(Provider.parent, Weapon) && Weapon.AllComps.Contains(Provider));
            }

            public void Equip()
            {
                if (Weapon.ParentHolder != null) throw new FixtureFailure("weapon already held");
                try { Pawn.equipment.AddEquipment(Weapon); }
                catch (CandidateFailure) { throw; }
                catch { throw new FixtureFailure("equipment setup API failed outside candidate notification"); }
                if (!ReferenceEquals(Weapon.ParentHolder, Pawn.equipment))
                    throw new FixtureFailure("equipment holder was not established");
            }
            public void Unequip()
            {
                try { Pawn.equipment.Remove(Weapon); }
                catch (CandidateFailure) { throw; }
                catch { throw new FixtureFailure("equipment removal API failed outside candidate notification"); }
                if (Weapon.ParentHolder != null) throw new FixtureFailure("equipment removal failed");
            }
            public void Sync(bool postLoad, params CompProperties_EquippableAbilityReloadable[] props)
            {
                var values = props.ToList();
                CandidateCall.Invoke(() => Provider.SetOrUpdateAbilities(values, postLoad));
            }
            public void Start(params CompProperties_EquippableAbilityReloadable[] props)
            {
                Sync(false, props);
                Equip(); // exercises Notify_Equipped after holder assignment
            }
            public Ability Ability => Pawn.abilities?.GetAbility(ManagedDef);
            public Ability RequireAbility()
                => Ability ?? throw new CandidateFailure(new InvalidOperationException("managed ability absent"));
            public FieldInfo CooldownField(string name)
                => AccessTools.Field(typeof(Ability), name)
                    ?? throw new FixtureFailure("Ability cooldown observation API unavailable");
            public int ManagedCount => Managed.GetValue(Provider) is HashSet<AbilityDef> managed
                ? managed.Count : -1;
            public int StateCount => States.GetValue(Provider) is System.Collections.ICollection states
                ? states.Count : -1;
        }

        public sealed class ProviderEnvelope : IExposable
        {
            // The load constructor creates a different pawn, holder and provider.
            // A live managed entry is seeded to observe PostLoadInit clearing it.
            private readonly Context context;
            public bool SawPostLoad;
            public ProviderEnvelope()
            {
                context = new Context(true, false);
                ScribeFixture.ExposeCandidate(() => context.Start(context.Props));
            }
            private ProviderEnvelope(Context source) { context = source; }
            public void ExposeData()
            {
                ScribeFixture.ExposeCandidate(() => context.Provider.PostExposeData());
                if (Scribe.mode == LoadSaveMode.PostLoadInit) SawPostLoad = true;
            }
            public static string Load(Context source, bool checkClear)
            {
                ProviderEnvelope loaded = ScribeFixture.Roundtrip(new ProviderEnvelope(source));
                if (!loaded.SawPostLoad || ReferenceEquals(source.Provider, loaded.context.Provider))
                    throw new FixtureFailure("provider PostLoadInit was not executed on a fresh instance");
                if (checkClear) return loaded.context.ManagedCount.ToString();
                loaded.context.Sync(true, loaded.context.Props);
                return (loaded.context.Ability != null) + ":" + (loaded.context.Ability?.RemainingCharges ?? -1);
            }
        }

        private static AbilityDef NewAbilityDef(string name)
        {
            if (DefDatabase<AbilityDef>.GetNamedSilentFail(name) != null)
                throw new FixtureFailure("fixture AbilityDef name collision");
            var definition = new AbilityDef
            {
                defName = name, label = name, abilityClass = typeof(Ability),
                comps = new List<AbilityCompProperties>(),
                verbProperties = new VerbProperties { verbClass = typeof(Verb_CastAbility) },
            };
            FixtureState.Require("cwf-definitions");
            DefDatabase<AbilityDef>.Add(definition);
            FixtureState.OnRestore("cwf-definitions", () =>
            {
                var remove = typeof(DefDatabase<AbilityDef>).GetMethod("Remove",
                    BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic,
                    null, new[] { typeof(AbilityDef) }, null);
                if (remove == null) throw new FixtureFailure("Def removal API unavailable");
                remove.Invoke(null, new object[] { definition });
            }, () => !DefDatabase<AbilityDef>.AllDefsListForReading.Contains(definition)
                && DefDatabase<AbilityDef>.GetNamedSilentFail(name) == null,
                ReferenceEquals(DefDatabase<AbilityDef>.GetNamedSilentFail(name), definition));
            return definition;
        }

        private static bool Try(Action action)
        {
            try { action(); return true; }
            catch (CandidateFailure) { return false; }
        }

        public static string Observe(string fixture)
        {
            switch (fixture)
            {
                case "MissingTrackerCreated":
                {
                    var context = new Context(false);
                    context.Start(context.Props);
                    return (context.Pawn.abilities != null).ToString();
                }
                case "EmptyManagementNoTracker":
                {
                    var context = new Context(false);
                    context.Start();
                    return (context.Pawn.abilities == null).ToString();
                }
                case "NoHolderNoTracker":
                {
                    var context = new Context(false);
                    context.Sync(false, context.Props);
                    return (context.Pawn.abilities == null && context.Weapon.ParentHolder == null).ToString();
                }
                case "ManagedAbilityAdded":
                case "DuplicatePropsDeduplicated":
                {
                    var context = new Context(false);
                    context.Start(context.Props, context.Props);
                    return (context.Ability != null) + ":" + context.ManagedCount;
                }
                case "UnrelatedAbilityPreserved":
                {
                    var context = new Context(true);
                    context.Pawn.abilities.GainAbility(context.OtherDef);
                    context.Start(context.Props);
                    return (context.Pawn.abilities?.GetAbility(context.OtherDef) != null).ToString();
                }
                case "RemovedManagedAbilityPruned":
                {
                    var context = new Context(true);
                    context.Start(context.Props);
                    context.RequireAbility(); // pruning must start from a candidate-created ability
                    context.Sync(false);
                    return (context.Ability == null) + ":" + context.ManagedCount;
                }
                case "UnequipCapturesState":
                {
                    var context = new Context(true);
                    context.Start(context.Props);
                    context.RequireAbility().RemainingCharges = 2;
                    context.Unequip();
                    return context.StateCount.ToString();
                }
                case "ReequipRestoresCharges":
                {
                    var context = new Context(true);
                    context.Start(context.Props);
                    context.RequireAbility().RemainingCharges = 2;
                    context.Unequip();
                    context.Equip();
                    return (context.Ability != null) + ":" + (context.Ability?.RemainingCharges ?? -1);
                }
                case "ReequipRestoresCooldown":
                {
                    var context = new Context(true);
                    context.Start(context.Props);
                    context.CooldownField("inCooldown").SetValue(context.RequireAbility(), true);
                    context.CooldownField("cooldownEndTick").SetValue(context.RequireAbility(), GenTicks.TicksGame + 120);
                    context.CooldownField("cooldownDuration").SetValue(context.RequireAbility(), 180);
                    context.Unequip();
                    context.Start(context.Props);
                    return context.CooldownField("inCooldown").GetValue(context.RequireAbility()).ToString();
                }
                case "StaleStatePruned":
                {
                    var context = new Context(true);
                    context.Start(context.Props);
                    context.RequireAbility().RemainingCharges = 2;
                    context.Unequip();
                    context.Sync(false);
                    return context.StateCount.ToString();
                }
                case "NullPropertiesTolerated":
                {
                    var context = new Context(true);
                    var invalid = new CompProperties_EquippableAbilityReloadable();
                    return Try(() => context.Sync(false, invalid)).ToString();
                }
                case "PostloadRestoresState":
                case "PostloadManagedCleared":
                {
                    var context = new Context(true);
                    context.Start(context.Props);
                    if (context.Ability == null) return "missing";
                    context.RequireAbility().RemainingCharges = 2;
                    return ProviderEnvelope.Load(context, fixture == "PostloadManagedCleared");
                }
                case "HolderUpdateAddsAbility":
                {
                    var context = new Context(false);
                    context.Start();
                    context.Sync(false, context.Props);
                    return (context.Ability != null).ToString();
                }
                case "FixtureStateRestored":
                    return FixtureState.VerifyAndReset("cwf-holder-state", "cwf-definitions", "scribe-temp");
                case "ReloadPathPreserved":
                {
                    var context = new Context(true);
                    context.Start(context.Props);
                    if (context.Ability == null) return "missing";
                    context.RequireAbility().RemainingCharges = 2;
                    bool found = false;
                    CWF.ReloadableAbility reloadable = null;
                    CandidateCall.Invoke(() => found = context.Provider.TryGetReloadable(context.ManagedDef, out reloadable));
                    if (!found || reloadable == null) return "False:False";
                    Thing ammo = ThingMaker.MakeThing(ThingDefOf.Steel);
                    ammo.stackCount = 2;
                    CandidateCall.Invoke(() => reloadable.ReloadFrom(ammo));
                    return found + ":" + (context.RequireAbility().RemainingCharges == 4 && ammo.Destroyed);
                }
                default:
                    throw new InvalidOperationException("unknown Customize Weapon fixture");
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
            CWFFixtureSeam.InstallBoundary();
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
