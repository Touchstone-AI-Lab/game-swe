using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;

namespace GcbHarness.Framework
{
    /// <summary>Pumps a suite's cases one at a time, one enumerator step per game tick
    /// (plus waits). Cases run strictly in order; a failure records and moves on, so a
    /// suite always yields a full per-case verdict rather than stopping at the first
    /// failure.</summary>
    public sealed class SuiteRunner
    {
        private readonly Queue<GcbCase> _pending;
        private readonly List<CaseResult> _results = new();

        private GcbCase? _current;
        private IEnumerator? _body;
        private GcbWait? _wait;
        private int _ticksInCase;

        public bool Done { get; private set; }
        public IReadOnlyList<CaseResult> Results => this._results;
        public int CaseCount { get; }

        /// <summary>Collect every case of the given phase across all suites, keeping
        /// suite order then declaration order.</summary>
        public SuiteRunner(IEnumerable<IGcbSuite> suites, GcbPhase phase)
        {
            this._pending = new Queue<GcbCase>(suites.SelectMany(s => s.Cases).Where(c => c.Phase == phase));
            this.CaseCount = this._pending.Count;
            this.Done = this.CaseCount == 0;
        }

        /// <summary>Advance the runner by one game tick.</summary>
        public void Tick()
        {
            if (this.Done)
                return;

            if (this._current is null && !this.StartNextCase())
                return;

            this._ticksInCase++;
            if (this._ticksInCase > this._current!.TimeoutTicks)
            {
                this.FinishCase(passed: false, error: $"hung: exceeded {this._current.TimeoutTicks} ticks");
                return;
            }

            // Honor an active wait before stepping the coroutine again.
            switch (this._wait)
            {
                case GcbWait.WaitTicks wt when --wt.Remaining > 0:
                    return;
                case GcbWait.WaitUntil wu when !SafePredicate(wu, out string? predError):
                    if (predError is not null)
                        this.FinishCase(passed: false, error: predError);
                    return;
            }
            this._wait = null;

            try
            {
                if (!this._body!.MoveNext())
                {
                    this.FinishCase(passed: true, error: null);
                    return;
                }
            }
            catch (Exception ex)
            {
                this.FinishCase(passed: false, error: ex is GcbAssertException ? ex.Message : $"{ex.GetType().Name}: {ex.Message}");
                return;
            }

            this._wait = this._body.Current as GcbWait;
        }

        private static bool SafePredicate(GcbWait.WaitUntil wait, out string? error)
        {
            try
            {
                error = null;
                return wait.Predicate();
            }
            catch (Exception ex)
            {
                error = $"wait-until predicate threw {ex.GetType().Name}: {ex.Message}";
                // Report "not satisfied" so the caller's guard matches and fails the
                // case with this error. Returning true here skipped that branch and
                // resumed the case as if the awaited condition had been met.
                return false;
            }
        }

        private bool StartNextCase()
        {
            if (this._pending.Count == 0)
            {
                this.Done = true;
                return false;
            }

            this._current = this._pending.Dequeue();
            this._ticksInCase = 0;
            this._wait = null;
            try
            {
                this._body = this._current.Body();
            }
            catch (Exception ex)
            {
                this.FinishCase(passed: false, error: $"case setup threw {ex.GetType().Name}: {ex.Message}");
                return false;
            }
            return true;
        }

        private void FinishCase(bool passed, string? error)
        {
            this._results.Add(new CaseResult
            {
                Name = this._current!.Name,
                Passed = passed,
                Error = error,
                Ticks = this._ticksInCase,
            });
            this._current = null;
            this._body = null;
            this._wait = null;
            if (this._pending.Count == 0)
                this.Done = true;
        }
    }
}
