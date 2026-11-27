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
using System.Collections;
using ResearchOrganized;
using UnityEngine;
using Verse;

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

        // Startup's finish-actions run before the entry UI exists, and this fixture needs its
        // native WindowStack, so observation starts on the first main-thread frame that has one.
        static VerifierBootstrap() => LongEventHandler.ExecuteWhenFinished(
            () => new GameObject("RheniumVerifierStart").AddComponent<VerifierStart>());

        private sealed class VerifierStart : MonoBehaviour
        {
            private const float WaitSeconds = 120f;
            private float deadline = -1f;

            private void Update()
            {
                if (deadline < 0f) deadline = Time.realtimeSinceStartup + WaitSeconds;
                bool ready = Find.UIRoot != null && Find.WindowStack != null
                    && !LongEventHandler.AnyEventNowOrWaiting;
                // Past the deadline the readiness gate itself fails closed.
                if (!ready && Time.realtimeSinceStartup < deadline) return;
                Destroy(gameObject);
                Run();
            }
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

        private sealed class CandidateFailure : Exception
        { public CandidateFailure(Exception inner) : base("candidate operation failed", inner) { } }

        // Checkpoints restore native objects independently of the submission. No candidate
        // cleanup method is called, and no engine or Mod API is doubled.
        private sealed class Checkpoint : IDisposable
        {
            private readonly List<Action> restore = new List<Action>();
            private readonly List<Func<bool>> verify = new List<Func<bool>>();

            public Checkpoint()
            {
                object randomState = RandomState.GetValue(null, null);
                int randomDepth = ((ICollection)RandomStack.GetValue(null)).Count;
                verify.Add(() => Equals(RandomState.GetValue(null, null), randomState)
                    && ((ICollection)RandomStack.GetValue(null)).Count == randomDepth);
                Game previous = Current.Game;
                restore.Add(() => Current.Game = previous);
                verify.Add(() => ReferenceEquals(Current.Game, previous));
                Capture(typeof(ResearchOrganizedMain), null, true);
                Capture(typeof(ResearchOrganizedLayout), null, true);
                Capture(typeof(DefDatabase<ResearchTabDef>), null, true);
                Capture(typeof(DefDatabase<ResearchProjectDef>), null, true);
                Capture(typeof(DefDatabase<ResearchOrganizedConfig>), null, true);
                foreach (ResearchTabDef tab in KnownTabs()) Capture(tab.GetType(), tab, false);
                foreach (ResearchProjectDef project in DefDatabase<ResearchProjectDef>.AllDefs)
                    Capture(project.GetType(), project, false);
                foreach (ResearchOrganizedConfig config in DefDatabase<ResearchOrganizedConfig>.AllDefs)
                    Capture(config.GetType(), config, false);
                Capture(typeof(ResearchOrganizedSettings), ResearchOrganizedMod.settings, false);
                Capture(typeof(MainTabWindow_Research), window, false);
                WindowStack stack = Find.WindowStack;
                Window[] previousWindows = stack.Windows.ToArray();
                Capture(typeof(WindowStack), stack, false);
                Capture(typeof(WindowStack), null, true);
                // Close through the native lifecycle before restoring the captured fields.
                restore.Add(() =>
                {
                    if (!previousWindows.Contains(window) && stack.IsOpen(window)
                        && !stack.TryRemove(window, false))
                        throw new InvalidOperationException("native window cleanup failed");
                });
                verify.Add(() => stack.Windows.SequenceEqual(previousWindows));
            }

            private static IEnumerable<ResearchTabDef> KnownTabs()
            {
                var tabs = new HashSet<ResearchTabDef>(Tabs);
                foreach (var field in typeof(ResearchOrganizedMain).GetFields(
                    BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
                {
                    object value = field.GetValue(null);
                    if (value is ResearchTabDef tab) tabs.Add(tab);
                    else if (value is IDictionary dictionary)
                    {
                        foreach (object entry in dictionary.Values)
                            if (entry is ResearchTabDef stored) tabs.Add(stored);
                    }
                    else if (value is IEnumerable sequence)
                        foreach (object entry in sequence)
                            if (entry is ResearchTabDef stored) tabs.Add(stored);
                }
                return tabs;
            }

            private void Capture(Type type, object target, bool isStatic)
            {
                BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly
                    | (isStatic ? BindingFlags.Static : BindingFlags.Instance);
                foreach (FieldInfo field in type.GetFields(flags))
                {
                    if (field.IsLiteral) continue;
                    object saved = field.GetValue(target);
                    if (!field.IsInitOnly)
                    {
                        restore.Add(() => field.SetValue(target, saved));
                        verify.Add(() => Equals(field.GetValue(target), saved));
                    }
                    CaptureCollection(saved);
                }
                if (!isStatic && type.BaseType != null) Capture(type.BaseType, target, false);
            }

            private void CaptureCollection(object collection)
            {
                if (collection is IDictionary dictionary)
                {
                    var savedEntries = new List<DictionaryEntry>();
                    IDictionaryEnumerator enumerator = dictionary.GetEnumerator();
                    while (enumerator.MoveNext()) savedEntries.Add(enumerator.Entry);
                    DictionaryEntry[] entries = savedEntries.ToArray();
                    restore.Add(() => { dictionary.Clear(); foreach (var entry in entries) dictionary.Add(entry.Key, entry.Value); });
                    verify.Add(() => dictionary.Count == entries.Length
                        && entries.All(entry => dictionary.Contains(entry.Key) && Equals(dictionary[entry.Key], entry.Value)));
                }
                else if (collection is IList list && !list.IsReadOnly)
                {
                    object[] entries = list.Cast<object>().ToArray();
                    restore.Add(() =>
                    {
                        if (list.IsFixedSize)
                            for (int index = 0; index < entries.Length; index++) list[index] = entries[index];
                        else { list.Clear(); foreach (object entry in entries) list.Add(entry); }
                    });
                    verify.Add(() => list.Cast<object>().SequenceEqual(entries));
                }
                else if (collection is HashSet<ResearchProjectDef> set)
                {
                    ResearchProjectDef[] entries = set.ToArray();
                    restore.Add(() => { set.Clear(); set.UnionWith(entries); });
                    verify.Add(() => set.SetEquals(entries));
                }
            }

            public void Dispose()
            {
                var failures = new List<Exception>();
                for (int index = restore.Count - 1; index >= 0; index--)
                {
                    try { restore[index](); }
                    catch (Exception error) { failures.Add(error); }
                }
                if (failures.Count != 0 || verify.Any(check => !check()))
                    throw new InvalidOperationException("native fixture restoration failed");
            }
        }

        private const int FixtureSeed = 0x5EED;
        private const float ViewExtension = 32f;
        private static readonly PropertyInfo RandomState = typeof(Rand).GetProperty("StateCompressed",
            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
        private static readonly FieldInfo RandomStack = AccessTools.Field(typeof(Rand), "stateStack");
        private static readonly FieldInfo VisibilityField = AccessTools.Field(typeof(ResearchManager), "tabInfoVisibility");
        private static readonly FieldInfo ValuesField = AccessTools.Field(typeof(DefMap<ResearchTabDef, bool>), "values");
        private static readonly FieldInfo WindowTabsField = AccessTools.Field(typeof(MainTabWindow_Research), "tabs");
        private static readonly FieldInfo SelectedProjectField = AccessTools.Field(typeof(MainTabWindow_Research), "selectedProject");
        private static readonly FieldInfo CurrentTabField = AccessTools.Field(typeof(MainTabWindow_Research), "curTabInt");
        private static readonly FieldInfo ViewWidthField = AccessTools.Field(typeof(MainTabWindow_Research), "rightViewWidth");
        private static readonly ConstructorInfo TabRecordConstructor = AccessTools.Constructor(
            AccessTools.Inner(typeof(MainTabWindow_Research), "ResearchTabRecord"),
            new[] { typeof(ResearchTabDef), typeof(string), typeof(Action), typeof(Func<bool>) });
        private static readonly FieldInfo RecordDefField = AccessTools.Field(
            AccessTools.Inner(typeof(MainTabWindow_Research), "ResearchTabRecord"), "def");
        private static MainTabWindow_Research window;
        private static Game originalGame;
        private static ResearchTabDef[] originalTabs;
        private static Window[] originalWindows;
        private static int completedBehavior;
        private static List<ResearchTabDef> Tabs => DefDatabase<ResearchTabDef>.AllDefsListForReading;
        private static IList WindowTabs => (IList)WindowTabsField.GetValue(window);
        private static List<bool> Values => (List<bool>)ValuesField.GetValue(VisibilityField.GetValue(Current.Game.researchManager));

        private static void Run()
        {
            string nonce = Environment.GetEnvironmentVariable("RHENIUM_EVALUATION_NONCE") ?? "";
            var envelope = new ObservationEnvelope
            {
                evaluationId = Environment.GetEnvironmentVariable("RHENIUM_EVALUATION_ID") ?? "",
                nonce = nonce, taskKey = Environment.GetEnvironmentVariable("RHENIUM_TASK_KEY") ?? "",
                fatal = "", gameVersion = VersionControl.CurrentVersionStringWithRev,
                unityVersion = Application.unityVersion,
            };
            try
            {
                foreach (AssertionDispatch assertion in AssertionPlan)
                {
                    try
                    {
                        CaseObservation observation = assertion.Observe();
                        observation.id = assertion.Id;
                        observation.error = "";
                        envelope.cases.Add(observation);
                    }
                    catch (CandidateFailure)
                    {
                        if (assertion.Gate) throw;
                        envelope.cases.Add(new CaseObservation { id = assertion.Id, error = "candidate operation failed" });
                    }
                    if (!assertion.Gate) completedBehavior++;
                }
            }
            catch (Exception error) { envelope.fatal = error.GetType().Name + ": " + error.Message; }
            envelope.terminalMarker = "RIMWORLD_OBSERVATIONS_COMPLETE:" + nonce;
            try
            {
                Directory.CreateDirectory(OutputDirectory);
                File.WriteAllText(Path.Combine(OutputDirectory, "observations.json"), Serialize(envelope) + Environment.NewLine);
                Log.Message("[GCB_RIMWORLD] " + envelope.terminalMarker);
            }
            finally { Application.Quit(string.IsNullOrEmpty(envelope.fatal) ? 0 : 2); }
        }

        private static CaseObservation Observation(string value) => new CaseObservation
        { facts = new List<FactObservation> { new FactObservation { name = "result", value = value } } };

        private static CaseObservation Case(Func<bool> behavior)
        {
            using (var checkpoint = new Checkpoint())
            {
                Rand.PushState(FixtureSeed + completedBehavior);
                try { return Observation(behavior().ToString()); }
                finally { Rand.PopState(); }
            }
        }

        private static void Organize()
        {
            try { ResearchOrganizedMain.OrganizeTabsAndLayout(); }
            catch (Exception error) { throw new CandidateFailure(error); }
        }

        private static void Refresh()
        {
            try { ResearchOrganizedMain.RefreshOpenResearchWindow(); }
            catch (Exception error) { throw new CandidateFailure(error); }
        }

        private static bool Read(ResearchTabDef tab)
        {
            try { return Current.Game.researchManager.TabInfoVisible(tab); }
            catch (Exception error) { throw new CandidateFailure(error); }
        }

        private static void NewGame(bool initializeFlags = true)
        {
            Current.Game = new Game { researchManager = new ResearchManager() };
            if (initializeFlags) Current.Game.researchManager.TabInfoVisible(Tabs[0]);
        }

        private static Dictionary<ResearchTabDef, bool> EditFlags()
        {
            var expected = new Dictionary<ResearchTabDef, bool>();
            for (int index = 0; index < Tabs.Count; index++)
            {
                bool visible = index == 0;
                Values[Tabs[index].index] = visible;
                expected[Tabs[index]] = visible;
            }
            return expected;
        }

        private static void SetOrder(IEnumerable<ResearchTabDef> order)
        {
            ResearchOrganizedConfig[] configs = DefDatabase<ResearchOrganizedConfig>.AllDefs.ToArray();
            foreach (var config in configs) config.tabOrder.Clear();
            configs[0].tabOrder.AddRange(order.Select(tab => tab.defName));
        }

        private static bool Matches(Dictionary<ResearchTabDef, bool> expected) =>
            Tabs.All(tab => expected.ContainsKey(tab) && Read(tab) == expected[tab]);

        private static void PopulateWindow()
        {
            WindowTabs.Clear();
            foreach (ResearchTabDef tab in Tabs)
            {
                Action clicked = () => { };
                Func<bool> selected = () => window.CurTab == tab;
                WindowTabs.Add(TabRecordConstructor.Invoke(new object[] { tab, (string)tab.LabelCap, clicked, selected }));
            }
            window.CurTab = Tabs[0];
        }

        private static bool WindowMatches() => WindowTabs.Cast<object>()
            .Select(record => (ResearchTabDef)RecordDefField.GetValue(record)).SequenceEqual(Tabs);

        private static void OpenWindow()
        {
            // Sounds are outside the contract; native PreOpen/PostOpen still run.
            window.soundAppear = null;
            window.soundClose = null;
            window.soundAmbient = null;
            Find.WindowStack.Add(window);
            if (!IsWindowOpen())
                throw new InvalidOperationException("native research window did not open");
        }

        private static bool IsWindowOpen() => window.IsOpen
            && ReferenceEquals(Find.WindowStack.WindowOfType<MainTabWindow_Research>(), window);

        private static float NativeViewWidth(ResearchTabDef tab)
        {
            CurrentTabField.SetValue(window, null);
            window.CurTab = tab;
            return (float)ViewWidthField.GetValue(window);
        }

        private static bool ViewRecomputed(bool isOpen)
        {
            NewGame(); PopulateWindow();
            if (isOpen) OpenWindow();
            ResearchTabDef tab = Tabs.First(active => DefDatabase<ResearchProjectDef>.AllDefs.Any(project => project.tab == active));
            float originalWidth = NativeViewWidth(tab);
            ResearchProjectDef moved = DefDatabase<ResearchProjectDef>.AllDefs
                .Where(project => project.tab == tab).OrderByDescending(project => project.researchViewX).First();
            moved.researchViewX += ViewExtension;
            // The window sizes its view from ResearchViewX, which only this native routine
            // copies from researchViewX; the checkpoint restores every project's coordinates.
            ResearchProjectDef.GenerateNonOverlappingCoordinates();
            float expandedWidth = NativeViewWidth(tab);
            if (!(expandedWidth > originalWidth))
                throw new InvalidOperationException("native view-width fixture did not expand");
            Organize();
            try
            {
                if (!ReferenceEquals(window.CurTab, tab) || window.IsOpen != isOpen) return false;
                float observedWidth = (float)ViewWidthField.GetValue(window);
                // Obtain the expected width from the real game's setter, after observing
                // the candidate. No candidate helper or copied width formula is used.
                float expectedWidth = NativeViewWidth(tab);
                return expectedWidth != expandedWidth && observedWidth == expectedWidth;
            }
            catch (Exception error) { throw new CandidateFailure(error); }
        }

        private static ResearchTabDef AddTab(bool defaultVisibility)
        {
            var tab = new ResearchTabDef { defName = "RheniumResearchTab", label = "Rhenium research tab",
                visibleByDefault = defaultVisibility, index = (ushort)Tabs.Count };
            DefDatabase<ResearchTabDef>.Add(tab);
            var project = new ResearchProjectDef { defName = "RheniumResearchProject", label = "Rhenium project",
                tab = tab, techLevel = TechLevel.Industrial, baseCost = 100f,
                prerequisites = new List<ResearchProjectDef>() };
            DefDatabase<ResearchProjectDef>.Add(project);
            DefDatabase<ResearchOrganizedConfig>.AllDefs.First().preservedTabs.Add(tab.defName);
            return tab;
        }

        private static CaseObservation RuntimeDefsReady()
        {
            if (VersionControl.CurrentVersionStringWithRev.Split(' ')[0] != "1.6.4871"
                || Application.unityVersion != "2022.3.35f1"
                || ModsConfig.RoyaltyActive || ModsConfig.IdeologyActive || ModsConfig.BiotechActive
                || ModsConfig.AnomalyActive || ModsConfig.OdysseyActive
                || ResearchOrganizedMod.settings == null || Tabs.Count < 2
                || !DefDatabase<ResearchOrganizedConfig>.AllDefs.Any()
                || RandomState == null || RandomStack == null
                || VisibilityField == null || ValuesField == null || WindowTabsField == null
                || SelectedProjectField == null || CurrentTabField == null || ViewWidthField == null
                || TabRecordConstructor == null || RecordDefField == null)
                throw new InvalidOperationException("pinned Core research fixture unavailable");
            if (MainButtonDefOf.Research == null || Find.UIRoot == null || Find.WindowStack == null)
                throw new InvalidOperationException("native entry window stack unavailable");
            window = MainButtonDefOf.Research.TabWindow as MainTabWindow_Research;
            if (window == null || WindowTabs == null || Find.WindowStack.WindowOfType<MainTabWindow_Research>() != null)
                throw new InvalidOperationException("closed native research window unavailable");
            originalGame = Current.Game;
            originalTabs = Tabs.ToArray();
            originalWindows = Find.WindowStack.Windows.ToArray();
            return Observation("ready");
        }

        private static CaseObservation EntryWithoutGame() => Case(() =>
        { Current.Game = null; Organize(); return Tabs.Count > 0; });

        private static CaseObservation UninitializedFlags() => Case(() =>
        { NewGame(false); Organize(); return Tabs.All(tab => Read(tab) == tab.visibleByDefault); });

        private static CaseObservation CollapseDefault() => Case(() =>
        {
            NewGame(); ResearchOrganizedMod.settings.combineAllTabs = true; Organize();
            return Tabs.Count > 0 && Values.Count == Tabs.Count && Tabs.All(tab => tab.index < Values.Count);
        });

        private static CaseObservation FlagsFollowTabs() => Case(() =>
        {
            NewGame(); var expected = EditFlags(); ResearchTabDef first = Tabs[0];
            SetOrder(Tabs.AsEnumerable().Reverse().ToArray()); Organize();
            return Tabs[0] != first && Matches(expected);
        });

        private static bool Expand(bool checkDefaults)
        {
            ResearchOrganizedMod.settings.combineAllTabs = true; Organize();
            NewGame(); int combinedCount = Tabs.Count;
            ResearchOrganizedMod.settings.combineAllTabs = false; Organize();
            if (Tabs.Count <= combinedCount) return false;
            foreach (var tab in Tabs)
            {
                bool visible = Read(tab);
                if (checkDefaults && visible != tab.visibleByDefault) return false;
            }
            return true;
        }

        private static CaseObservation ExpandFromCombined() => Case(() => Expand(false));
        private static CaseObservation RestoredDefaults() => Case(() => Expand(true));

        private static CaseObservation NewTabDefaultTrue() => Case(() =>
        { NewGame(); ResearchTabDef tab = AddTab(true); Organize(); return Tabs.Contains(tab) && Read(tab); });

        private static CaseObservation NewTabDefaultFalse() => Case(() =>
        { NewGame(); ResearchTabDef tab = AddTab(false); Organize(); return Tabs.Contains(tab) && !Read(tab); });

        private static CaseObservation RepeatedRelayout() => Case(() =>
        {
            NewGame(); var expected = EditFlags(); ResearchTabDef[] firstOrder = Tabs.ToArray();
            SetOrder(firstOrder.Reverse()); Organize(); bool first = Matches(expected);
            SetOrder(firstOrder); Organize(); return first && Matches(expected);
        });

        private static CaseObservation ClosedWindowTabs() => Case(() =>
        { NewGame(); PopulateWindow(); ResearchOrganizedMod.settings.combineAllTabs = true; Organize(); return WindowMatches(); });

        private static CaseObservation HiddenCurrentTab() => Case(() =>
        {
            NewGame(); PopulateWindow(); ResearchTabDef remembered = window.CurTab;
            ResearchOrganizedMod.settings.combineAllTabs = true; Organize();
            return !Tabs.Contains(remembered) && window.CurTab != null && Tabs.Contains(window.CurTab);
        });

        private static CaseObservation SelectedProjectPreserved() => Case(() =>
        {
            NewGame(); PopulateWindow(); ResearchProjectDef selected = DefDatabase<ResearchProjectDef>.AllDefs.First();
            SelectedProjectField.SetValue(window, selected);
            ResearchOrganizedMod.settings.combineAllTabs = true; Organize();
            return ReferenceEquals(SelectedProjectField.GetValue(window), selected);
        });

        private static CaseObservation CurrentTabPreserved() => Case(() =>
        {
            NewGame(); PopulateWindow(); ResearchTabDef remembered = window.CurTab;
            SetOrder(Tabs.AsEnumerable().Reverse().ToArray()); Organize();
            return ReferenceEquals(window.CurTab, remembered);
        });

        private static CaseObservation ExplicitClosedRefresh() => Case(() =>
        {
            NewGame(); WindowTabs.Clear();
            Refresh();
            return WindowMatches() && window.CurTab != null && Tabs.Contains(window.CurTab);
        });

        private static CaseObservation SelectedProjectTabPreferred() => Case(() =>
        {
            NewGame(); PopulateWindow();
            ResearchProjectDef project = DefDatabase<ResearchProjectDef>.AllDefs
                .First(candidate => candidate.tab != null && candidate.tab != Tabs[0] && Tabs.Contains(candidate.tab));
            SelectedProjectField.SetValue(window, project);
            CurrentTabField.SetValue(window, new ResearchTabDef { defName = "RheniumRemovedTab", label = "Removed tab" });
            Refresh();
            return ReferenceEquals(window.CurTab, project.tab);
        });

        private static CaseObservation EditedVisibilityPreserved() => Case(() =>
        {
            NewGame(); var expected = new Dictionary<ResearchTabDef, bool>();
            foreach (var tab in Tabs) { Values[tab.index] = !tab.visibleByDefault; expected[tab] = !tab.visibleByDefault; }
            Organize(); return Matches(expected);
        });

        private static CaseObservation ClosedViewRecomputed() => Case(() => ViewRecomputed(false));
        private static CaseObservation OpenViewRecomputed() => Case(() => ViewRecomputed(true));

        private static CaseObservation OpenWindowRelayout() => Case(() =>
        {
            NewGame(); PopulateWindow(); OpenWindow();
            ResearchTabDef remembered = window.CurTab;
            ResearchProjectDef selected = DefDatabase<ResearchProjectDef>.AllDefs.First();
            SelectedProjectField.SetValue(window, selected);
            ResearchOrganizedMod.settings.combineAllTabs = true; Organize();
            return IsWindowOpen() && WindowMatches() && !Tabs.Contains(remembered)
                && window.CurTab != null && Tabs.Contains(window.CurTab)
                && ReferenceEquals(SelectedProjectField.GetValue(window), selected);
        });

        private static CaseObservation ExplicitOpenRefresh() => Case(() =>
        {
            NewGame(); PopulateWindow(); OpenWindow(); WindowTabs.Clear(); Refresh();
            return IsWindowOpen() && WindowMatches() && window.CurTab != null && Tabs.Contains(window.CurTab);
        });

        private static CaseObservation FixtureStateRestored()
        {
            if (completedBehavior != 20 || !ReferenceEquals(Current.Game, originalGame)
                || !Tabs.SequenceEqual(originalTabs)
                || !Find.WindowStack.Windows.SequenceEqual(originalWindows)
                || Find.WindowStack.WindowOfType<MainTabWindow_Research>() != null)
                throw new InvalidOperationException("terminal fixture boundary failed");
            return Observation("restored");
        }
    }
}
