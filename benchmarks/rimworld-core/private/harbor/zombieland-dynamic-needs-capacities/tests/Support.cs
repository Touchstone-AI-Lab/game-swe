using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RimWorld;
using UnityEngine;
using Verse;

namespace Rhenium.RimWorld.TaskSupport
{
    public sealed class FixtureFailure : Exception
    {
        public FixtureFailure(string message) : base(message) { }
    }

    // Production exceptions are distinguishable from setup, Scribe and cleanup failures.
    public sealed class CandidateFailure : Exception
    {
        public CandidateFailure(Exception inner) : base("candidate operation threw", inner) { }
    }

    public static class CandidateCall
    {
        public static object Invoke(MethodInfo method, object target, object[] args)
        {
            if (method == null) throw new CandidateFailure(new MissingMethodException());
            try { return method.Invoke(target, args); }
            catch (TargetInvocationException error) { throw new CandidateFailure(error.InnerException ?? error); }
        }
        public static bool IsCandidateFailure(Exception error)
        {
            while (error is TargetInvocationException && error.InnerException != null)
                error = error.InnerException;
            return error is CandidateFailure;
        }
    }

    public static class FixtureState
    {
        private sealed class Restoration
        {
            public string Name;
            public Action Restore;
            public Func<bool> Restored;
        }
        private static readonly List<Restoration> Pending = new List<Restoration>();
        private static readonly List<Func<bool>> Audits = new List<Func<bool>>();
        private static readonly HashSet<string> Verified = new HashSet<string>();
        private static readonly List<Func<bool>> Boundaries = new List<Func<bool>>();
        private static readonly Dictionary<string, int> Required = new Dictionary<string, int>();
        private static readonly Dictionary<string, int> Registered = new Dictionary<string, int>();
        private static string CurrentCase;
        private static bool Behavior;
        private static bool Poisoned;
        private static int Completed;
        private static int Registrations;
        private static Game PreviousGame;
        private static Game CaseGame;

        // Install before any task mutation. These checks are independent of the
        // cleanup registration list and remain live until the terminal gate.
        public static void Watch(Func<bool> invariant)
        {
            if (CurrentCase != null || invariant == null || !invariant())
                throw new FixtureFailure("invalid initial fixture boundary");
            Boundaries.Add(invariant);
        }
        private static void CheckBoundaries()
        {
            if (Poisoned || Boundaries.Any(check => !check()) || Audits.Any(check => !check()))
            {
                Poisoned = true;
                throw new FixtureFailure("fixture state differs from its captured boundary");
            }
        }
        public static void BeginCase(string id, bool behavior)
        {
            if (CurrentCase != null || Pending.Count != 0)
                throw new FixtureFailure("unfinished fixture case");
            CheckBoundaries();
            CurrentCase = id;
            Behavior = behavior;
            Registrations = 0;
            PreviousGame = Current.Game;
            if (behavior)
            {
                CaseGame = new Game();
                Current.Game = CaseGame;
                if (ReferenceEquals(Current.Game, PreviousGame)) throw new FixtureFailure("game isolation failed");
            }
        }
        // Required independently at the mutation site. Losing one callback in a
        // multi-object case cannot be hidden by another object's registration.
        public static void Require(string name)
        {
            if (CurrentCase == null) throw new FixtureFailure("restoration obligation outside case");
            Required[name] = Required.TryGetValue(name, out int count) ? count + 1 : 1;
        }
        public static void OnRestore(string name, Action restore, Func<bool> restored, bool mutationObserved)
        {
            if (CurrentCase == null || restore == null || restored == null || string.IsNullOrEmpty(name))
                throw new FixtureFailure("invalid restoration registration");
            // Register first, so a failed mutation precondition still gets cleanup.
            Pending.Add(new Restoration { Name = name, Restore = restore, Restored = restored });
            Registrations++;
            Registered[name] = Registered.TryGetValue(name, out int count) ? count + 1 : 1;
            if (!mutationObserved) { Poisoned = true; throw new FixtureFailure("fixture mutation was not observed"); }
        }
        public static void Restore()
        {
            var failures = new List<string>();
            for (int i = Pending.Count - 1; i >= 0; --i)
            {
                var item = Pending[i];
                try
                {
                    item.Restore();
                    if (!item.Restored()) failures.Add(item.Name);
                    else { Verified.Add(item.Name); Audits.Add(item.Restored); }
                }
                catch { failures.Add(item.Name); }
            }
            foreach (var obligation in Required)
                if (!Registered.TryGetValue(obligation.Key, out int count) || count != obligation.Value)
                    failures.Add("missing or duplicate restoration: " + obligation.Key);
            Required.Clear();
            Registered.Clear();
            Pending.Clear();
            if (Behavior && Registrations == 0) failures.Add("unregistered task mutation");
            if (Behavior)
            {
                if (!ReferenceEquals(Current.Game, CaseGame)) failures.Add("unexpected game replacement");
                Current.Game = PreviousGame;
                if (!ReferenceEquals(Current.Game, PreviousGame)) failures.Add("game restoration failed");
            }
            CurrentCase = null;
            if (failures.Count != 0) Poisoned = true;
            CheckBoundaries();
            if (Behavior) Completed++;
            Behavior = false;
        }
        public static string VerifyAndReset(params string[] required)
        {
            CheckBoundaries();
            if (Pending.Count != 0 || Completed == 0 || required.Any(name => !Verified.Contains(name)))
                throw new FixtureFailure("missing restoration evidence");
            // Do not discard observations: late or repeated contamination remains fatal.
            return "restored";
        }
    }

    public static class FixtureRand
    {
        private sealed class Snapshot
        {
            public object Compressed;
            public int Depth;
        }
        private static readonly PropertyInfo State = typeof(Rand).GetProperty("StateCompressed",
            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
        private static readonly FieldInfo Stack = typeof(Rand).GetField("stateStack",
            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
        public static object Capture()
        {
            if (State == null || State.GetMethod == null || Stack == null
                || !(Stack.GetValue(null) is System.Collections.ICollection stack))
                throw new FixtureFailure("Rand state/stack observation API unavailable");
            return new Snapshot { Compressed = State.GetValue(null, null), Depth = stack.Count };
        }
        public static void Check(object expected)
        {
            var before = (Snapshot)expected;
            var after = (Snapshot)Capture();
            if (!Equals(before.Compressed, after.Compressed) || before.Depth != after.Depth)
                throw new FixtureFailure("Rand state or nesting was not restored");
        }
    }

    public static class BehaviorProbe
    {
        // This dispatcher contains fixture implementations, not grading expectations.
        // Every returned value must come from live RimWorld state after invoking the
        // candidate production surface (Need_CurLevel_Patch); assertions.json remains external.
        public static string Observe(string fixture)
        {
            switch (fixture)
            {
                case "RuntimeDefsReady":
                    bool core = LoadedModManager.RunningModsListForReading.Any(m => m.PackageId == "ludeon.rimworld");
                    bool candidate = LoadedModManager.RunningModsListForReading.Any(m => m.PackageId == "brrainz.zombieland");
                    return core && candidate ? "ready" : "missing";
                case "FixtureStateRestored":
                    return ProductionFixtureDriver.Observe(fixture);
                default:
                    return ProductionFixtureDriver.Observe(fixture);
            }
        }
    }

    internal static class ProductionFixtureDriver
    {
        // The adapter invokes a task-owned runtime seam registered by the verifier's
        // Def fixtures. A missing or duplicate seam fails the case; it never guesses.
        internal static string Observe(string fixture)
        {
            Type seam = GenTypes.AllTypes.FirstOrDefault(t =>
                t.FullName == "Rhenium.RimWorld.Verifier.ZombielandFixtureSeam");
            if (seam == null) throw new InvalidOperationException("fixture seam is unavailable");
            MethodInfo method = seam.GetMethod("Observe", BindingFlags.Public | BindingFlags.Static);
            if (method == null || method.ReturnType != typeof(string))
                throw new InvalidOperationException("fixture seam contract is invalid");
            return (string)method.Invoke(null, new object[] { fixture });
        }
    }
}

namespace ZombieLand
{
    // Rhenium-authored fixture boundary for the unrelated symbiosis service.
    // Never calculates needs, capacities, pain or infected membership.
    public class ZombieSymbiant : Pawn
    {
        public static readonly HashSet<Pawn> MoodBenefit = new HashSet<Pawn>();
        public static readonly HashSet<Pawn> FoodRestBenefit = new HashSet<Pawn>();
        public static bool HasMoodFixedBenefit(Pawn pawn) => MoodBenefit.Contains(pawn);
        public static bool HasNoFoodOrRestBenefit(Pawn pawn) => FoodRestBenefit.Contains(pawn);
    }
}
