using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using FactionLoadout;
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

        private static CaseObservation ApparelExplicitQuality() => Observe();

        private static CaseObservation WeaponExplicitQuality() => Observe();

        private static CaseObservation ApparelVanillaQuality() => Observe();

        private static CaseObservation WeaponVanillaQuality() => Observe();

        private static CaseObservation ApparelLowHealth() => Observe();

        private static CaseObservation WeaponLowHealth() => Observe();

        private static CaseObservation ApparelMinOneHp() => Observe();

        private static CaseObservation WeaponMinOneHp() => Observe();

        private static CaseObservation ApparelFullHealth() => Observe();

        private static CaseObservation WeaponFullHealth() => Observe();

        private static CaseObservation NonHitpointApparel() => Observe();

        private static CaseObservation NonHitpointWeapon() => Observe();

        private static CaseObservation StylePreserved() => Observe();

        private static CaseObservation ColorPreserved() => Observe();

        private static CaseObservation MaterialPreserved() => Observe();

        private static CaseObservation RandStateRestored() => Observe();
    }

    public static class FactionLoadoutFixtureSeam
    {
        public static void InstallBoundary()
        {
            // Object/grid/holder snapshots are retained by FixtureState until the final gate.
        }

        private static readonly Assembly Candidate = AppDomain.CurrentDomain.GetAssemblies()
            .Single(assembly => assembly.GetName().Name == "FactionLoadout");

        private static MethodInfo Generator(bool apparel) => Candidate.GetType(
                apparel ? "FactionLoadout.Patches.ApparelGenPatch" : "FactionLoadout.Patches.WeaponGenPatch", true)
            .GetMethod(apparel ? "GenerateNewApparel" : "GenerateNewWeapon",
                BindingFlags.Static | BindingFlags.NonPublic);

        private static ThingDef Definition(bool apparel)
        {
            ThingDef result = DefDatabase<ThingDef>.AllDefsListForReading.FirstOrDefault(definition =>
                (apparel ? definition.IsApparel : definition.IsWeapon)
                && definition.thingClass != null
                && definition.comps != null
                && definition.comps.Any(comp => comp.compClass == typeof(CompQuality)));
            return result ?? throw new InvalidOperationException("no Core quality gear definition is available");
        }

        private static Pawn Pawn(float healthFactor)
        {
            FixtureState.Require("total-control-kind");
            var pawn = new Pawn { def = ThingDefOf.Human, kindDef = PawnKindDefOf.Colonist };
            PawnKindDef original = pawn.kindDef;
            var clone = (PawnKindDef)typeof(object).GetMethod("MemberwiseClone",
                BindingFlags.Instance | BindingFlags.NonPublic).Invoke(original, null);
            FloatRange previous = clone.gearHealthRange;
            pawn.kindDef = clone;
            clone.gearHealthRange = new FloatRange(healthFactor, healthFactor);
            FixtureState.OnRestore("total-control-kind", () =>
            {
                clone.gearHealthRange = previous;
                pawn.kindDef = original;
            }, () => ReferenceEquals(pawn.kindDef, original) && clone.gearHealthRange.Equals(previous),
                !ReferenceEquals(pawn.kindDef, original));
            return pawn;
        }

        private static Thing Generate(bool apparel, Pawn pawn, QualityCategory? quality,
            ThingStyleDef style = null, Color color = default(Color), ThingDef material = null)
        {
            var spec = new SpecRequirementEdit
            {
                Thing = Definition(apparel), Material = material, Quality = quality,
                Style = style, Color = color,
            };
            object generated = CandidateCall.Invoke(Generator(apparel), null, new object[] { pawn, spec });
            return generated as Thing
                ?? throw new CandidateFailure(new InvalidOperationException("candidate returned no gear"));
        }

        private static CompQuality Quality(Thing thing) => thing.TryGetComp<CompQuality>();

        private static string Explicit(bool apparel)
        {
            Thing thing = Generate(apparel, Pawn(1f), QualityCategory.Masterwork);
            return Quality(thing)?.Quality.ToString() ?? "null";
        }

        private static string VanillaQuality(bool apparel)
        {
            Pawn pawn = Pawn(1f);
            QualityCategory expected;
            Rand.PushState(7411);
            try { expected = QualityUtility.GenerateQualityGeneratingPawn(pawn.kindDef, Definition(apparel)); }
            finally { Rand.PopState(); }
            Thing thing;
            Rand.PushState(7411);
            try { thing = Generate(apparel, pawn, null); }
            finally { Rand.PopState(); }
            return (Quality(thing)?.Quality == expected).ToString();
        }

        private static string Health(bool apparel, float factor)
        {
            Thing thing = Generate(apparel, Pawn(factor), QualityCategory.Normal);
            int expected = Mathf.Max(1, Mathf.RoundToInt(factor * thing.MaxHitPoints));
            return (thing.HitPoints == expected).ToString();
        }

        private static string NonHitPoint(bool apparel)
        {
            ThingDef definition = Definition(apparel);
            bool previous = definition.useHitPoints;
            FixtureState.Require("total-control-hitpoints");
            definition.useHitPoints = false;
            FixtureState.OnRestore("total-control-hitpoints", () => definition.useHitPoints = previous,
                () => definition.useHitPoints == previous, previous != definition.useHitPoints);
            Thing thing = Generate(apparel, Pawn(0.1f), QualityCategory.Normal);
            // RimWorld 1.6 leaves HitPoints unset (-1) on a thing whose def does not use hit
            // points, so the value the game gives an identical new thing is the unmodified one.
            int unmodified = ThingMaker.MakeThing(thing.def, thing.Stuff).HitPoints;
            return (thing.HitPoints == unmodified).ToString();
        }

        public static string Observe(string fixture)
        {
            switch (fixture)
            {
                case "FixtureStateRestored":
                    return FixtureState.VerifyAndReset("total-control-kind", "total-control-hitpoints");
                case "ApparelExplicitQuality": return Explicit(true);
                case "WeaponExplicitQuality": return Explicit(false);
                case "ApparelVanillaQuality": return VanillaQuality(true);
                case "WeaponVanillaQuality": return VanillaQuality(false);
                case "ApparelLowHealth": return Health(true, 0.4f);
                case "WeaponLowHealth": return Health(false, 0.4f);
                case "ApparelMinOneHp": return Health(true, 0.001f);
                case "WeaponMinOneHp": return Health(false, 0.001f);
                case "ApparelFullHealth": return Health(true, 1f);
                case "WeaponFullHealth": return Health(false, 1f);
                case "NonHitpointApparel": return NonHitPoint(true);
                case "NonHitpointWeapon": return NonHitPoint(false);
                case "StylePreserved":
                {
                    // Core ships no ThingStyleDef (styles come with Ideology), so the fixture authors one.
                    ThingStyleDef style = DefDatabase<ThingStyleDef>.AllDefsListForReading.FirstOrDefault()
                        ?? new ThingStyleDef { defName = "RheniumFixtureStyle" };
                    Thing thing = Generate(false, Pawn(1f), QualityCategory.Normal, style);
                    return (thing.StyleDef == style).ToString();
                }
                case "ColorPreserved":
                {
                    // Core weapons carry no CompColorable, so SetColor has nothing to set. The fixture
                    // gives its weapon definition one for this case and restores the comp list after.
                    ThingDef gear = Definition(false);
                    List<CompProperties> previousComps = gear.comps;
                    FixtureState.Require("total-control-colorable");
                    gear.comps = new List<CompProperties>(previousComps) { new CompProperties(typeof(CompColorable)) };
                    FixtureState.OnRestore("total-control-colorable", () => gear.comps = previousComps,
                        () => ReferenceEquals(gear.comps, previousComps), !ReferenceEquals(gear.comps, previousComps));
                    Color color = new Color(0.17f, 0.43f, 0.71f, 1f);
                    Thing thing = Generate(false, Pawn(1f), QualityCategory.Normal, null, color);
                    return thing.DrawColor.IndistinguishableFrom(color).ToString();
                }
                case "MaterialPreserved":
                {
                    ThingDef gear = Definition(false);
                    ThingDef material = gear.MadeFromStuff
                        ? GenStuff.DefaultStuffFor(gear)
                        : null;
                    Thing thing = Generate(false, Pawn(1f), QualityCategory.Normal, null, default(Color), material);
                    return (thing.Stuff == material).ToString();
                }
                case "RandStateRestored":
                {
                    Rand.PushState(9137);
                    float before;
                    float after;
                    try
                    {
                        before = Rand.Value;
                        Rand.PushState(42);
                        try { Generate(false, Pawn(1f), null); }
                        finally { Rand.PopState(); }
                        after = Rand.Value;
                    }
                    finally { Rand.PopState(); }
                    Rand.PushState(9137);
                    try
                    {
                        float expectedBefore = Rand.Value;
                        float expectedAfter = Rand.Value;
                        return (before == expectedBefore && after == expectedAfter).ToString();
                    }
                    finally { Rand.PopState(); }
                }
                default:
                    throw new InvalidOperationException("unknown Total Control fixture");
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
            FactionLoadoutFixtureSeam.InstallBoundary();
        }
    }
}
