using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using RimWorld;
using RRRR;
using UnityEngine;
using Verse;
using MaterialUtility = RRRR.MaterialUtility;

namespace Rhenium.RimWorld.Verifier
{
    [Serializable]
    public sealed class MaterialObservation
    {
        public string defName;
        public int count;
    }

    [Serializable]
    public sealed class CostObservation
    {
        public string channel;
        public List<MaterialObservation> entries = new List<MaterialObservation>();
    }

    [Serializable]
    public sealed class FactObservation
    {
        public string name;
        public string value;
    }

    [Serializable]
    public sealed class ScalarObservation
    {
        public string name;
        public float value;
        public string bits;
    }

    [Serializable]
    public sealed class CaseObservation
    {
        public string id;
        public string error;
        public List<FactObservation> facts = new List<FactObservation>();
        public List<ScalarObservation> scalars = new List<ScalarObservation>();
        public List<CostObservation> outputs = new List<CostObservation>();
    }

    [Serializable]
    public sealed class ObservationEnvelope
    {
        public int schema = 2;
        public string adapter = "rhenium-rimworld-observer-v2";
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

    public sealed class CandidateObservationException : Exception
    {
        public CandidateObservationException(string message, Exception inner = null)
            : base(message, inner)
        {
        }
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
            {
                Id = id;
                Observe = observe;
                Gate = gate;
            }
        }

        private sealed class FallbackFixture
        {
            public ThingDef Definition;
            public Thing Item;
            public float MarketValue;
            public float BulkMarketValue;
            public float TargetValue;
            public float Quotient;
        }

        static VerifierBootstrap()
        {
            LongEventHandler.ExecuteWhenFinished(Run);
        }

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
            var observations = new ObservationEnvelope
            {
                evaluationId = Environment.GetEnvironmentVariable("RHENIUM_EVALUATION_ID") ?? "",
                nonce = nonce,
                taskKey = Environment.GetEnvironmentVariable("RHENIUM_TASK_KEY") ?? "",
                fatal = "",
                gameVersion = VersionControl.CurrentVersionStringWithRev,
                unityVersion = Application.unityVersion,
            };

            // RimWorld 1.6 CostListAdjusted reads Find.Storyteller.difficulty, which exists only
            // inside a Game; the cases run from the main menu, so they get a temporary one.
            // The fixtures author exact abstract MarketValues, including negative and float32
            // boundary values. Core's MarketValue StatDef clamps at zero and rounds values above
            // 200 to multiples of five, so both are lifted for the case loop and then restored.
            // The fixtures specify float32 quotients, not bulk prices. Over Core Plasteel's price
            // of 9, no float32 MarketValue yields a quotient of exactly 3.5 or 100 once multiplied
            // by 0.15f, so Plasteel is priced at 8 for the case loop, which reaches every one.
            Game previousGame = Current.Game;
            StatDef marketValue = StatDefOf.MarketValue;
            float marketFloor = marketValue.minValue;
            float marketRoundToFiveOver = marketValue.roundToFiveOver;
            float plasteelMarket = ThingDefOf.Plasteel.GetStatValueAbstract(marketValue);
            try
            {
                Current.Game = new Game();
                marketValue.minValue = -9999999f;
                marketValue.roundToFiveOver = float.MaxValue;
                ThingDefOf.Plasteel.SetStatBaseValue(marketValue, 8f);
                foreach (AssertionDispatch assertion in AssertionPlan)
                    AddCase(observations, assertion);
                observations.terminalMarker = "RIMWORLD_OBSERVATIONS_COMPLETE:" + nonce;
            }
            catch (Exception error)
            {
                observations.fatal = error.GetType().Name + ": " + error.Message;
                observations.terminalMarker = "RIMWORLD_OBSERVATIONS_COMPLETE:" + nonce;
            }
            finally
            {
                ThingDefOf.Plasteel.SetStatBaseValue(marketValue, plasteelMarket);
                marketValue.minValue = marketFloor;
                marketValue.roundToFiveOver = marketRoundToFiveOver;
                Current.Game = previousGame;
            }

            try
            {
                Directory.CreateDirectory(OutputDirectory);
                File.WriteAllText(
                    Path.Combine(OutputDirectory, "observations.json"),
                    Serialize(observations) + Environment.NewLine);
                Log.Message("[GCB_RIMWORLD] " + observations.terminalMarker);
            }
            finally
            {
                Application.Quit(string.IsNullOrEmpty(observations.fatal) ? 0 : 2);
            }
        }

        private static void AddCase(
            ObservationEnvelope observations,
            AssertionDispatch assertion)
        {
            RRRR_Settings settings = RRRR_Mod.Settings;
            float repair = settings.repairHpPerCycle;
            float clean = settings.cleanCostFraction;
            float recycle = settings.recycleGlobalMult;
            bool skip = settings.skipIntricateComponents;
            try
            {
                settings.repairHpPerCycle = 0.2f;
                settings.cleanCostFraction = 0.2f;
                settings.recycleGlobalMult = 1f;
                settings.skipIntricateComponents = false;
                CaseObservation item;
                try
                {
                    item = assertion.Observe();
                    item.id = assertion.Id;
                    item.error = "";
                }
                catch (CandidateObservationException error)
                {
                    if (assertion.Gate)
                        throw;
                    item = new CaseObservation
                    {
                        id = assertion.Id,
                        error = error.Message,
                    };
                }
                observations.cases.Add(item);
            }
            finally
            {
                settings.repairHpPerCycle = repair;
                settings.cleanCostFraction = clean;
                settings.recycleGlobalMult = recycle;
                settings.skipIntricateComponents = skip;
            }
        }

        private static ThingDef NewDefinition(
            string name,
            TechLevel technology,
            float marketValue,
            List<ThingDefCountClass> costs = null,
            List<DefModExtension> extensions = null)
        {
            return new ThingDef
            {
                defName = name,
                techLevel = technology,
                costList = costs,
                modExtensions = extensions,
                statBases = new List<StatModifier>
                {
                    new StatModifier { stat = StatDefOf.MarketValue, value = marketValue },
                },
            };
        }

        private static Thing NewItem(ThingDef definition, ThingDef stuff = null)
        {
            var item = new ThingWithComps { def = definition };
            if (stuff == null)
                return item;
            FieldInfo field = typeof(Thing).GetField(
                "stuffInt", BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null)
                throw new InvalidOperationException("RimWorld Thing.stuffInt fixture API is missing");
            field.SetValue(item, stuff);
            return item;
        }

        private static List<ThingDefCountClass> CraftCosts()
        {
            return new List<ThingDefCountClass>
            {
                new ThingDefCountClass(ThingDefOf.Steel, 37),
                new ThingDefCountClass(ThingDefOf.WoodLog, 8),
            };
        }

        private static R4MaterialCostExtension Extension(
            List<ThingDefCountClass> materials)
        {
            return new R4MaterialCostExtension { materials = materials };
        }

        private static List<DefModExtension> Extensions(
            R4MaterialCostExtension extension)
        {
            return new List<DefModExtension> { extension };
        }

        private static List<ThingDefCountClass> BasisE()
        {
            return new List<ThingDefCountClass>
            {
                new ThingDefCountClass(ThingDefOf.Steel, 60),
                new ThingDefCountClass(ThingDefOf.ComponentIndustrial, 2),
            };
        }

        private static List<ThingDefCountClass> CandidateCall(
            Func<List<ThingDefCountClass>> action,
            string label)
        {
            try
            {
                return action();
            }
            catch (Exception error)
            {
                throw new CandidateObservationException(label + " raised an exception", error);
            }
        }

        private static List<ThingDefCountClass> ResolveContract(Thing item)
        {
            MethodInfo[] matches = typeof(MaterialUtility).GetMethods(
                    BindingFlags.Public | BindingFlags.Static)
                .Where(method => method.Name == "ResolveMaterialBasis")
                .ToArray();
            if (matches.Length != 1)
                throw new CandidateObservationException("API_MISSING");
            MethodInfo method = matches[0];
            ParameterInfo[] parameters = method.GetParameters();
            if (
                method.ReturnType != typeof(List<ThingDefCountClass>)
                || parameters.Length != 1
                || parameters[0].ParameterType != typeof(Thing))
            {
                throw new CandidateObservationException("API_MISSING");
            }
            try
            {
                var result = method.Invoke(null, new object[] { item })
                    as List<ThingDefCountClass>;
                if (result == null)
                    throw new CandidateObservationException("resolver returned null");
                return result;
            }
            catch (CandidateObservationException)
            {
                throw;
            }
            catch (Exception error)
            {
                throw new CandidateObservationException("resolver raised an exception", error);
            }
        }

        private static CostObservation ObserveCosts(
            string channel,
            List<ThingDefCountClass> costs)
        {
            if (costs == null)
                throw new CandidateObservationException(channel + " returned null");
            var observation = new CostObservation { channel = channel };
            try
            {
                foreach (ThingDefCountClass entry in costs)
                {
                    if (entry == null || entry.thingDef == null)
                        throw new CandidateObservationException(channel + " returned a null material");
                    observation.entries.Add(new MaterialObservation
                    {
                        defName = entry.thingDef.defName,
                        count = entry.count,
                    });
                }
            }
            catch (CandidateObservationException)
            {
                throw;
            }
            catch (Exception error)
            {
                throw new CandidateObservationException(
                    channel + " returned invalid materials", error);
            }
            return observation;
        }

        private static FactObservation Fact(string name, string value)
        {
            return new FactObservation { name = name, value = value };
        }

        private static string FloatBits(float value)
        {
            return BitConverter.ToInt32(BitConverter.GetBytes(value), 0).ToString("x8");
        }

        private static ScalarObservation Scalar(string name, float value)
        {
            return new ScalarObservation { name = name, value = value, bits = FloatBits(value) };
        }

        private static float NextFloat(float value, int direction)
        {
            if (float.IsNaN(value) || float.IsInfinity(value) || value <= 0f)
                throw new InvalidOperationException("fixture float must be finite and positive");
            int bits = BitConverter.ToInt32(BitConverter.GetBytes(value), 0);
            return BitConverter.ToSingle(BitConverter.GetBytes(bits + direction), 0);
        }

        private static ThingDef BulkFor(TechLevel technology)
        {
            TechLevel normalized = technology == TechLevel.Undefined
                ? TechLevel.Industrial
                : technology;
            return normalized >= TechLevel.Spacer ? ThingDefOf.Plasteel : ThingDefOf.Steel;
        }

        private static FallbackFixture NewFallbackFixture(
            string name,
            TechLevel technology,
            float desiredQuotient,
            List<ThingDefCountClass> costs = null,
            List<DefModExtension> extensions = null)
        {
            ThingDef bulk = BulkFor(technology);
            float bulkMarketValue = Mathf.Max(
                0.01f, bulk.GetStatValueAbstract(StatDefOf.MarketValue));
            float authoredMarket = desiredQuotient * bulkMarketValue / 0.15f;
            for (int attempt = 0; attempt < 4096; attempt++)
            {
                ThingDef definition = NewDefinition(
                    name, technology, authoredMarket, costs, extensions);
                float marketValue = definition.GetStatValueAbstract(StatDefOf.MarketValue);
                float targetValue = Mathf.Max(0f, marketValue) * 0.15f;
                float quotient = targetValue / bulkMarketValue;
                if (FloatBits(quotient) == FloatBits(desiredQuotient))
                {
                    return new FallbackFixture
                    {
                        Definition = definition,
                        Item = NewItem(definition),
                        MarketValue = marketValue,
                        BulkMarketValue = bulkMarketValue,
                        TargetValue = targetValue,
                        Quotient = quotient,
                    };
                }
                authoredMarket = NextFloat(
                    authoredMarket, quotient < desiredQuotient ? 1 : -1);
            }
            throw new InvalidOperationException("unable to construct exact float32 quotient fixture");
        }

        private static FallbackFixture NewBoundaryFixture(
            string name,
            TechLevel technology,
            float marketValue,
            List<ThingDefCountClass> costs = null,
            List<DefModExtension> extensions = null)
        {
            ThingDef definition = NewDefinition(
                name, technology, marketValue, costs, extensions);
            ThingDef bulk = BulkFor(technology);
            float observedMarket = definition.GetStatValueAbstract(StatDefOf.MarketValue);
            float bulkMarket = Mathf.Max(
                0.01f, bulk.GetStatValueAbstract(StatDefOf.MarketValue));
            float target = Mathf.Max(0f, observedMarket) * 0.15f;
            return new FallbackFixture
            {
                Definition = definition,
                Item = NewItem(definition),
                MarketValue = observedMarket,
                BulkMarketValue = bulkMarket,
                TargetValue = target,
                Quotient = target / bulkMarket,
            };
        }

        private static List<ScalarObservation> FallbackScalars(FallbackFixture fixture)
        {
            return new List<ScalarObservation>
            {
                Scalar("marketValue", fixture.MarketValue),
                Scalar("bulkMarketValue", fixture.BulkMarketValue),
                Scalar("targetValue", fixture.TargetValue),
                Scalar("quotient", fixture.Quotient),
            };
        }

        private static CaseObservation ObserveCleanBasis(FallbackFixture fixture)
        {
            RRRR_Mod.Settings.cleanCostFraction = 1f;
            return new CaseObservation
            {
                scalars = FallbackScalars(fixture),
                outputs = new List<CostObservation>
                {
                    ObserveCosts(
                        "clean",
                        CandidateCall(
                            () => MaterialUtility.GetCleanCost(fixture.Item),
                            "clean operation")),
                },
            };
        }

        private static bool CostsMatch(
            List<ThingDefCountClass> actual,
            params ThingDefCountClass[] expected)
        {
            if (actual == null || actual.Count != expected.Length)
                return false;
            var actualMap = actual
                .Where(entry => entry != null && entry.thingDef != null)
                .ToDictionary(entry => entry.thingDef.defName, entry => entry.count);
            return expected.All(
                entry => actualMap.TryGetValue(entry.thingDef.defName, out int count)
                    && count == entry.count);
        }

        private static Thing StuffAdjustedItem()
        {
            var definition = NewDefinition(
                "GCB_StuffAdjusted",
                TechLevel.Industrial,
                500f,
                new List<ThingDefCountClass>
                {
                    new ThingDefCountClass(ThingDefOf.Steel, 7),
                });
            definition.costStuffCount = 20;
            definition.stuffCategories = new List<StuffCategoryDef>(
                ThingDefOf.WoodLog.stuffProps.categories);
            return NewItem(definition, ThingDefOf.WoodLog);
        }

        private static float InstanceMarketValue(Thing item)
        {
            PropertyInfo property = typeof(Thing).GetProperty(
                "MarketValue", BindingFlags.Public | BindingFlags.Instance);
            if (property == null || property.PropertyType != typeof(float))
                throw new InvalidOperationException("RimWorld Thing.MarketValue fixture API is missing");
            return (float)property.GetValue(item, null);
        }

        private static FallbackFixture DefinitionMarketFixture(out float instanceMarket)
        {
            FallbackFixture fixture = NewFallbackFixture(
                "GCB_DefinitionMarket", TechLevel.Industrial, 10f);
            fixture.Definition.useHitPoints = true;
            fixture.Definition.statBases.Add(
                new StatModifier { stat = StatDefOf.MaxHitPoints, value = 100f });
            FieldInfo hitPoints = typeof(Thing).GetField(
                "hitPointsInt", BindingFlags.Instance | BindingFlags.NonPublic);
            if (hitPoints == null)
                throw new InvalidOperationException("RimWorld Thing.hitPointsInt fixture API is missing");
            hitPoints.SetValue(fixture.Item, 1);
            instanceMarket = InstanceMarketValue(fixture.Item);
            if (float.IsNaN(instanceMarket) || float.IsInfinity(instanceMarket)
                || instanceMarket == fixture.MarketValue)
            {
                throw new InvalidOperationException("instance market-value fixture is not distinct");
            }
            return fixture;
        }

        private static CaseObservation RuntimeDefinitionsReady()
        {
            bool modsReady = LoadedModManager.RunningModsListForReading.Any(
                mod => mod.PackageId == "cheatereater.rrrr")
                && LoadedModManager.RunningModsListForReading.Any(
                    mod => mod.PackageId == "rhenium.rimworld.verifier");
            bool defsReady = ThingDefOf.Steel != null
                && ThingDefOf.Plasteel != null
                && ThingDefOf.ComponentIndustrial != null
                && ThingDefOf.ComponentSpacer != null
                && ThingDefOf.Uranium != null
                && ThingDefOf.WoodLog != null;
            bool versionsReady = VersionControl.CurrentVersionStringWithRev.StartsWith(
                    "1.6.4871", StringComparison.Ordinal)
                && Application.unityVersion == "2022.3.35f1";
            if (!modsReady || !defsReady || !versionsReady || RRRR_Mod.Settings == null)
                throw new InvalidOperationException("runtime definitions are not ready");
            return new CaseObservation
            {
                facts = new List<FactObservation> { Fact("ready", "true") },
            };
        }

        private static CaseObservation FixturePreconditions()
        {
            if (!Enum.IsDefined(typeof(TechLevel), TechLevel.Animal)
                || !Enum.IsDefined(typeof(TechLevel), TechLevel.Neolithic)
                || !Enum.IsDefined(typeof(TechLevel), TechLevel.Medieval)
                || !Enum.IsDefined(typeof(TechLevel), TechLevel.Industrial)
                || !Enum.IsDefined(typeof(TechLevel), TechLevel.Spacer)
                || !Enum.IsDefined(typeof(TechLevel), TechLevel.Ultra)
                || !Enum.IsDefined(typeof(TechLevel), TechLevel.Archotech)
                || !Enum.IsDefined(typeof(TechLevel), TechLevel.Undefined))
            {
                throw new InvalidOperationException("TechLevel fixture is unavailable");
            }
            List<ThingDefCountClass> stuffCosts = StuffAdjustedItem().def.CostListAdjusted(
                ThingDefOf.WoodLog, false);
            if (!CostsMatch(
                stuffCosts,
                new ThingDefCountClass(ThingDefOf.WoodLog, 20),
                new ThingDefCountClass(ThingDefOf.Steel, 7)))
            {
                throw new InvalidOperationException("stuff-adjusted fixture is invalid");
            }
            FallbackFixture negative = NewBoundaryFixture(
                "GCB_NegativePrecondition", TechLevel.Industrial, -1f);
            if (!(negative.MarketValue < 0f))
                throw new InvalidOperationException("negative MarketValue fixture is not legal");
            float instanceMarket;
            FallbackFixture definition = DefinitionMarketFixture(out instanceMarket);
            float instanceQuotient = Mathf.Max(0f, instanceMarket) * 0.15f
                / definition.BulkMarketValue;
            if (FloatBits(instanceQuotient) == FloatBits(definition.Quotient))
                throw new InvalidOperationException("definition MarketValue fixture is not distinct");

            float evenBelow = NextFloat(2.5f, -1);
            float evenAbove = NextFloat(2.5f, 1);
            float oddBelow = NextFloat(3.5f, -1);
            float oddAbove = NextFloat(3.5f, 1);
            foreach (float quotient in new[]
            {
                evenBelow, 2.5f, evenAbove, oddBelow, 3.5f, oddAbove,
            })
            {
                FallbackFixture fixture = NewFallbackFixture(
                    "GCB_FloatPrecondition_" + FloatBits(quotient),
                    quotient < 3f ? TechLevel.Industrial : TechLevel.Spacer,
                    quotient);
                if (FloatBits(fixture.Quotient) != FloatBits(quotient))
                    throw new InvalidOperationException("float32 quotient fixture changed");
            }
            return new CaseObservation
            {
                facts = new List<FactObservation>
                {
                    Fact("fixturesValid", "true"),
                    Fact("roundEvenBelowBits", FloatBits(evenBelow)),
                    Fact("roundEvenHalfBits", FloatBits(2.5f)),
                    Fact("roundEvenAboveBits", FloatBits(evenAbove)),
                    Fact("roundOddBelowBits", FloatBits(oddBelow)),
                    Fact("roundOddHalfBits", FloatBits(3.5f)),
                    Fact("roundOddAboveBits", FloatBits(oddAbove)),
                },
            };
        }

        private static CaseObservation PublicResolverContract()
        {
            var craft = NewDefinition(
                "GCB_PublicCraft", TechLevel.Industrial, 500f, CraftCosts());
            var extension = NewDefinition(
                "GCB_PublicExtension",
                TechLevel.Spacer,
                500f,
                null,
                Extensions(Extension(new List<ThingDefCountClass>
                {
                    new ThingDefCountClass(ThingDefOf.Uranium, 9),
                })));
            return new CaseObservation
            {
                facts = new List<FactObservation> { Fact("signature", "true") },
                outputs = new List<CostObservation>
                {
                    ObserveCosts("craft", ResolveContract(NewItem(craft))),
                    ObserveCosts("extension", ResolveContract(NewItem(extension))),
                },
            };
        }

        private static CaseObservation CleanBasis(
            string name,
            List<ThingDefCountClass> costs,
            List<DefModExtension> extensions = null)
        {
            RRRR_Mod.Settings.cleanCostFraction = 1f;
            Thing item = NewItem(NewDefinition(
                name, TechLevel.Industrial, 500f, costs, extensions));
            return new CaseObservation
            {
                outputs = new List<CostObservation>
                {
                    ObserveCosts("clean", CandidateCall(
                        () => MaterialUtility.GetCleanCost(item), "clean operation")),
                },
            };
        }

        private static CaseObservation CraftableCostPreserved()
        {
            return CleanBasis("GCB_Craftable", CraftCosts());
        }

        private static CaseObservation CraftableBeatsExtension()
        {
            return CleanBasis(
                "GCB_CraftBeatsExtension",
                CraftCosts(),
                Extensions(Extension(new List<ThingDefCountClass>
                {
                    new ThingDefCountClass(ThingDefOf.Uranium, 9),
                })));
        }

        private static CaseObservation StuffAdjustedCostPreserved()
        {
            RRRR_Mod.Settings.cleanCostFraction = 1f;
            Thing item = StuffAdjustedItem();
            return new CaseObservation
            {
                outputs = new List<CostObservation>
                {
                    ObserveCosts("clean", CandidateCall(
                        () => MaterialUtility.GetCleanCost(item), "clean operation")),
                },
            };
        }

        private static CaseObservation AuthoredExtensionUsed()
        {
            return CleanBasis(
                "GCB_AuthoredExtension",
                null,
                Extensions(Extension(new List<ThingDefCountClass>
                {
                    new ThingDefCountClass(ThingDefOf.Uranium, 9),
                })));
        }

        private static CaseObservation NullCostListFallback()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_NullCost", TechLevel.Industrial, 10f));
        }

        private static CaseObservation EmptyCostListFallback()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_EmptyCost", TechLevel.Industrial, 10f,
                new List<ThingDefCountClass>()));
        }

        private static CaseObservation NullExtensionMaterialsFallback()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_NullExtensionMaterials", TechLevel.Industrial, 10f, null,
                Extensions(Extension(null))));
        }

        private static CaseObservation EmptyExtensionMaterialsFallback()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_EmptyExtensionMaterials", TechLevel.Spacer, 10f, null,
                Extensions(Extension(new List<ThingDefCountClass>()))));
        }

        private static CaseObservation ZeroMarketValue()
        {
            return ObserveCleanBasis(NewBoundaryFixture(
                "GCB_ZeroMarket", TechLevel.Industrial, 0f));
        }

        private static CaseObservation NegativeMarketValue()
        {
            return ObserveCleanBasis(NewBoundaryFixture(
                "GCB_NegativeMarket", TechLevel.Industrial, -1f));
        }

        private static CaseObservation PositiveMinimumBulk()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_PositiveMinimum", TechLevel.Industrial, 0.25f));
        }

        private static CaseObservation SpacerBasis()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Spacer", TechLevel.Spacer, 10f));
        }

        private static CaseObservation UltraBasis()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Ultra", TechLevel.Ultra, 10f));
        }

        private static CaseObservation ArchotechBasis()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Archotech", TechLevel.Archotech, 10f));
        }

        private static CaseObservation UndefinedBasis()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Undefined", TechLevel.Undefined, 10f));
        }

        private static CaseObservation MedievalBasis()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Medieval", TechLevel.Medieval, 10f));
        }

        private static CaseObservation NeolithicBasis()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Neolithic", TechLevel.Neolithic, 10f));
        }

        private static CaseObservation AnimalBasis()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Animal", TechLevel.Animal, 10f));
        }

        private static CaseObservation IndustrialComponentsStayTwo()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Industrial100", TechLevel.Industrial, 100f));
        }

        private static CaseObservation SpacerComponentsStayTwo()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_Spacer100", TechLevel.Spacer, 100f));
        }

        private static CaseObservation DefinitionMarketValue()
        {
            float instanceMarket;
            FallbackFixture fixture = DefinitionMarketFixture(out instanceMarket);
            CaseObservation observation = ObserveCleanBasis(fixture);
            observation.scalars = new List<ScalarObservation>
            {
                Scalar("definitionMarketValue", fixture.MarketValue),
                Scalar("instanceMarketValue", instanceMarket),
                Scalar("bulkMarketValue", fixture.BulkMarketValue),
                Scalar("targetValue", fixture.TargetValue),
                Scalar("quotient", fixture.Quotient),
                Scalar("instanceQuotient", Mathf.Max(0f, instanceMarket) * 0.15f
                    / fixture.BulkMarketValue),
            };
            return observation;
        }

        private static CaseObservation RoundEvenBelow()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_RoundEvenBelow", TechLevel.Industrial, NextFloat(2.5f, -1)));
        }

        private static CaseObservation RoundEvenHalf()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_RoundEvenHalf", TechLevel.Industrial, 2.5f));
        }

        private static CaseObservation RoundEvenAbove()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_RoundEvenAbove", TechLevel.Industrial, NextFloat(2.5f, 1)));
        }

        private static CaseObservation RoundOddBelow()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_RoundOddBelow", TechLevel.Spacer, NextFloat(3.5f, -1)));
        }

        private static CaseObservation RoundOddHalf()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_RoundOddHalf", TechLevel.Spacer, 3.5f));
        }

        private static CaseObservation RoundOddAbove()
        {
            return ObserveCleanBasis(NewFallbackFixture(
                "GCB_RoundOddAbove", TechLevel.Spacer, NextFloat(3.5f, 1)));
        }

        private static Thing ExtensionBasisItem()
        {
            return NewItem(NewDefinition(
                "GCB_OperationBasis", TechLevel.Industrial, 500f, null,
                Extensions(Extension(BasisE()))));
        }

        private static CaseObservation RepairDefault()
        {
            return new CaseObservation
            {
                outputs = new List<CostObservation>
                {
                    ObserveCosts("repair", CandidateCall(
                        () => MaterialUtility.GetRepairCycleCost(ExtensionBasisItem()),
                        "repair operation")),
                },
            };
        }

        private static CaseObservation CleanDefault()
        {
            return new CaseObservation
            {
                outputs = new List<CostObservation>
                {
                    ObserveCosts("clean", CandidateCall(
                        () => MaterialUtility.GetCleanCost(ExtensionBasisItem()),
                        "clean operation")),
                },
            };
        }

        private static CaseObservation RepairSettings()
        {
            RRRR_Mod.Settings.repairHpPerCycle = 0.5f;
            return RepairDefault();
        }

        private static CaseObservation CleanSettings()
        {
            RRRR_Mod.Settings.cleanCostFraction = 0.5f;
            return CleanDefault();
        }

        private static CaseObservation RepairIgnoresCleanSettings()
        {
            RRRR_Mod.Settings.repairHpPerCycle = 0.2f;
            RRRR_Mod.Settings.cleanCostFraction = 0.5f;
            return RepairDefault();
        }

        private static CaseObservation CleanIgnoresRepairSettings()
        {
            RRRR_Mod.Settings.repairHpPerCycle = 0.5f;
            RRRR_Mod.Settings.cleanCostFraction = 0.2f;
            return CleanDefault();
        }

        private static CaseObservation RepairStrictThreshold()
        {
            Thing item = NewItem(NewDefinition(
                "GCB_RepairThreshold", TechLevel.Industrial, 500f,
                new List<ThingDefCountClass>
                {
                    new ThingDefCountClass(ThingDefOf.Steel, 5),
                    new ThingDefCountClass(ThingDefOf.Uranium, 6),
                }));
            return new CaseObservation
            {
                outputs = new List<CostObservation>
                {
                    ObserveCosts("repair", CandidateCall(
                        () => MaterialUtility.GetRepairCycleCost(item),
                        "repair operation")),
                },
            };
        }

        private static CaseObservation RepairFallbackHighest()
        {
            Thing item = NewItem(NewDefinition(
                "GCB_RepairFallback", TechLevel.Industrial, 500f,
                new List<ThingDefCountClass>
                {
                    new ThingDefCountClass(ThingDefOf.Steel, 3),
                    new ThingDefCountClass(ThingDefOf.Uranium, 5),
                }));
            return new CaseObservation
            {
                outputs = new List<CostObservation>
                {
                    ObserveCosts("repair", CandidateCall(
                        () => MaterialUtility.GetRepairCycleCost(item),
                        "repair operation")),
                },
            };
        }
    }
}
