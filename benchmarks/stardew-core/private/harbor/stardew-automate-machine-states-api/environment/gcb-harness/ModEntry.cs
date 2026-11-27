using System;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using StardewModdingAPI;
using StardewModdingAPI.Events;

namespace GcbHarness
{
    /// <summary>GameCodeBench verifier harness. Modes (env GCB_MODE):
    ///
    ///   run-suite   pump title-phase cases at the title screen, load the fixture save,
    ///               pump world-phase cases, write the JSON verdict to GCB_RESULT_PATH,
    ///               exit the process.
    ///   gen-save    create the deterministic fixture world, save it, exit. Used once
    ///               at image build time; trials never run this.
    ///
    /// The JSON verdict is the only channel the reward gate trusts: process exit codes
    /// gate nothing (a lesson inherited from the DarkRP suite, where the entrypoint
    /// exits 1 on clean runs).</summary>
    public sealed class ModEntry : Mod
    {
        private string _mode = "run-suite";
        private string _resultPath = "/logs/verifier/result.json";

        private List<IGcbSuite> _suites = new();
        private SuiteRunner? _titleRunner;
        private SuiteRunner? _worldRunner;
        private readonly List<CaseResult> _results = new();

        private bool _titlePhaseStarted;
        private bool _saveLoadRequested;
        private bool _genSaveAdvanced;
        private int _launchGraceTicks;

        public override void Entry(IModHelper helper)
        {
            this._mode = Environment.GetEnvironmentVariable("GCB_MODE") ?? this._mode;
            this._resultPath = Environment.GetEnvironmentVariable("GCB_RESULT_PATH") ?? this._resultPath;

            if (this._mode == "run-suite")
            {
                this._suites = this.DiscoverSuites();
                foreach (IGcbSuite suite in this._suites)
                    suite.OnEntry(helper);
            }

            helper.Events.GameLoop.GameLaunched += this.OnGameLaunched;
            helper.Events.GameLoop.SaveLoaded += this.OnSaveLoaded;
            helper.Events.GameLoop.Saved += this.OnSaved;
            helper.Events.GameLoop.UpdateTicked += this.OnUpdateTicked;

            this.Monitor.Log($"GCB harness up: mode={this._mode}, suites={this._suites.Count}", LogLevel.Info);
        }

        private void OnGameLaunched(object? sender, GameLaunchedEventArgs e)
        {
            if (this._mode == "gen-save")
            {
                try
                {
                    SaveBootstrap.StartNewDeterministicWorld(this.Helper, this.Monitor);
                }
                catch (Exception ex)
                {
                    this.Fatal($"gen-save bootstrap failed: {ex}");
                }
                return;
            }

            if (this._suites.Count == 0)
            {
                this.Fatal("no IGcbSuite compiled into the harness");
                return;
            }

            // Give other mods' GameLaunched handlers a few ticks before title-phase
            // assertions run, then start the title runner (which may be empty).
            this._titlePhaseStarted = true;
            this._launchGraceTicks = 30;
            this._titleRunner = new SuiteRunner(this._suites, GcbPhase.Title);
            this.Monitor.Log($"GCB: title phase starting ({this._titleRunner.CaseCount} case(s))", LogLevel.Info);
        }

        private void OnSaveLoaded(object? sender, SaveLoadedEventArgs e)
        {
            if (this._mode == "gen-save")
                return; // wait for the first on-disk save (OnSaved) before exiting

            this._worldRunner = new SuiteRunner(this._suites, GcbPhase.World);
            this.Monitor.Log($"GCB: world ready, running {this._worldRunner.CaseCount} case(s)", LogLevel.Info);
        }

        private void OnSaved(object? sender, SavedEventArgs e)
        {
            if (this._mode != "gen-save")
                return;
            // The deterministic world now exists on disk (first night processed by
            // Game1.NewDay). Report where it landed and exit.
            this.Monitor.Log($"GCB gen-save: save written for farm '{StardewValley.Game1.player.farmName.Value}' " +
                             $"in folder '{Constants.SaveFolderName}'", LogLevel.Info);
            SaveBootstrap.ExitGame();
        }

        private void OnUpdateTicked(object? sender, UpdateTickedEventArgs e)
        {
            if (this._mode == "gen-save")
            {
                // Once the created world is live, run one day rollover so the game
                // writes the save to disk (vanilla only saves overnight).
                if (Context.IsWorldReady && !this._genSaveAdvanced)
                {
                    this._genSaveAdvanced = true;
                    StardewValley.Game1.NewDay(0f);
                }
                return;
            }

            // Phase 1: title-screen cases, then kick off the fixture-save load.
            if (this._titlePhaseStarted && !this._saveLoadRequested)
            {
                if (this._launchGraceTicks-- > 0)
                    return;

                this._titleRunner!.Tick();
                if (!this._titleRunner.Done)
                    return;

                this._results.AddRange(this._titleRunner.Results);
                this._saveLoadRequested = true;
                try
                {
                    SaveBootstrap.LoadFixtureSave(this.Helper, this.Monitor);
                }
                catch (Exception ex)
                {
                    this.Fatal($"fixture save load failed: {ex}");
                }
                return;
            }

            // Phase 2: world cases once the save is up.
            if (this._worldRunner is null || !Context.IsWorldReady)
                return;

            this._worldRunner.Tick();
            if (!this._worldRunner.Done)
                return;

            this._results.AddRange(this._worldRunner.Results);
            this._worldRunner = null;
            this.WriteVerdictAndExit(fatal: null);
        }

        private List<IGcbSuite> DiscoverSuites()
        {
            // Per-task Suite.cs files are compiled into this assembly by tests/test.sh,
            // so reflection over our own assembly finds exactly the task's suites.
            return typeof(ModEntry).Assembly
                .GetTypes()
                .Where(t => typeof(IGcbSuite).IsAssignableFrom(t) && !t.IsAbstract && t.GetConstructor(Type.EmptyTypes) is not null)
                .Select(t => (IGcbSuite)Activator.CreateInstance(t)!)
                .OrderBy(s => s.GroupName, StringComparer.Ordinal)
                .ToList();
        }

        private void Fatal(string message)
        {
            this.Monitor.Log($"GCB fatal: {message}", LogLevel.Error);
            this.WriteVerdictAndExit(fatal: message);
        }

        private void WriteVerdictAndExit(string? fatal)
        {
            string group = string.Join("+", this._suites.Select(s => s.GroupName).DefaultIfEmpty("(none)"));
            try
            {
                ResultWriter.Write(this._resultPath, group, this._results, fatal);
                this.Monitor.Log($"GCB: verdict written to {this._resultPath} " +
                                 $"(passed={this._results.Count(r => r.Passed)} failed={this._results.Count(r => !r.Passed)} fatal={fatal ?? "none"})",
                                 LogLevel.Info);
            }
            finally
            {
                SaveBootstrap.ExitGame();
            }
        }
    }
}
