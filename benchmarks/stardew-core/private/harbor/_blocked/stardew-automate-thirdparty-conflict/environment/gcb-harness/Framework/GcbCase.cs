using System;
using System.Collections;
using System.Collections.Generic;

namespace GcbHarness.Framework
{
    /// <summary>One behavioral assertion case. The body is a coroutine pumped once per
    /// game update tick, so a case can span in-game time: yield a <see cref="GcbWait"/>
    /// to give the game ticks/days before the next step runs. A case fails by throwing
    /// (use <see cref="GcbAssert"/>) and passes when its enumerator completes.</summary>
    public sealed class GcbCase
    {
        public string Name { get; }
        public Func<IEnumerator> Body { get; }

        /// <summary>Upper bound on real game ticks this case may consume before it is
        /// marked failed as hung. Generous by default; cases that sleep across in-game
        /// days should raise it explicitly.</summary>
        public int TimeoutTicks { get; }

        /// <summary>When the case runs: in the loaded world (default), or at the title
        /// screen before the fixture save is loaded (for load-order/startup behavior).</summary>
        public GcbPhase Phase { get; }

        public GcbCase(string name, Func<IEnumerator> body, int timeoutTicks = 600, GcbPhase phase = GcbPhase.World)
        {
            this.Name = name;
            this.Body = body;
            this.TimeoutTicks = timeoutTicks;
            this.Phase = phase;
        }

        /// <summary>Convenience for single-tick synchronous cases.</summary>
        public static GcbCase Sync(string name, Action body, GcbPhase phase = GcbPhase.World)
        {
            return new GcbCase(name, () => SyncBody(body), phase: phase);
        }

        private static IEnumerator SyncBody(Action body)
        {
            body();
            yield break;
        }
    }

    /// <summary>Yield values understood by the harness pump.</summary>
    public abstract class GcbWait
    {
        /// <summary>Wait n real update ticks (60/s game-time).</summary>
        public static GcbWait Ticks(int n) => new WaitTicks(n);

        /// <summary>Wait until the given predicate holds (checked once per tick).</summary>
        public static GcbWait Until(Func<bool> predicate) => new WaitUntil(predicate);

        internal sealed class WaitTicks : GcbWait
        {
            public int Remaining;
            public WaitTicks(int n) { this.Remaining = n; }
        }

        internal sealed class WaitUntil : GcbWait
        {
            public readonly Func<bool> Predicate;
            public WaitUntil(Func<bool> predicate) { this.Predicate = predicate; }
        }
    }

    /// <summary>Which stage of the boot sequence a case runs in.</summary>
    public enum GcbPhase
    {
        /// <summary>After the fixture save is loaded and the world is ready.</summary>
        World,

        /// <summary>At the title screen, before the harness loads the fixture save.
        /// Use for behavior that must hold immediately on game launch.</summary>
        Title,
    }

    /// <summary>A task's assertion suite: a named group of ordered cases. The per-task
    /// C# file compiled into the harness at verify time implements this.</summary>
    public interface IGcbSuite
    {
        string GroupName { get; }
        IEnumerable<GcbCase> Cases { get; }

        /// <summary>Called from the harness mod's Entry, before the game launches. Use
        /// to register asset edits or other SMAPI hooks that must exist at load time.
        /// World state is NOT available here.</summary>
        void OnEntry(StardewModdingAPI.IModHelper helper) { }
    }
}
