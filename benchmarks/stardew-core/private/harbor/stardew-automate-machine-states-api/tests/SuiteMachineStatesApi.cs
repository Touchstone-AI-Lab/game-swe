using System.Collections;
using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using StardewValley;

namespace GcbHarness.Suites
{
    /// <summary>The subset of Automate's public mod API this suite consumes, proxied
    /// by SMAPI's mod-API mechanism.</summary>
    public interface IAutomateApi
    {
        IDictionary<Vector2, int> GetMachineStates(GameLocation location, Rectangle tileArea);
    }

    /// <summary>Verifies the GetMachineStates API contract. In Automate's model, a
    /// machine group with no connected chest is a "non-automated" group, and the API
    /// documents that it reports those too (Data Layers renders them).
    ///
    /// Discriminator: the fixture save contains no chests, so the initial scan on save
    /// load finds only non-automated groups — the farm's shipping bin among them. The
    /// probe runs BEFORE anything else is placed: on the base tree that initial scan
    /// never publishes any machine data, so the API reports an empty farm; on the
    /// fixed tree the shipping bin is reported. Ordering matters — once any automated
    /// group is created, both trees publish, so the probe must come first.
    ///
    /// Sentinel: a chest+furnace placed afterwards must be reported on both trees.</summary>
    public sealed class MachineStatesApiSuite : IGcbSuite
    {
        public string GroupName => "automate.machine-states-api";

        private static readonly Rectangle FarmArea = new(8, 20, 4, 3);

        private IModHelper? _helper;
        private IAutomateApi? _api;

        private static Rectangle WholeFarm(Farm farm)
        {
            var layer = farm.Map.Layers[0];
            return new Rectangle(0, 0, layer.LayerWidth, layer.LayerHeight);
        }

        public void OnEntry(IModHelper helper)
        {
            this._helper = helper;
        }

        public IEnumerable<GcbCase> Cases =>
        [
            new GcbCase("non-automated machines are reported after the initial scan", this.NonAutomatedReportedOnLoad, timeoutTicks: 1200),
            new GcbCase("sentinel: an automated machine group is reported", this.SentinelAutomatedMachineReported, timeoutTicks: 1800),
            new GcbCase("automated and non-automated machines are reported together", this.BothReportedTogether, timeoutTicks: 600),
        ];

        private IEnumerator NonAutomatedReportedOnLoad()
        {
            this._api = this._helper!.ModRegistry.GetApi<IAutomateApi>("Pathoschild.Automate");
            GcbAssert.IsNotNull(this._api, "Automate exposes its mod API");

            // Give Automate several automation intervals (default 60 ticks) to run its
            // initial full scan. Nothing is placed before this probe.
            yield return GcbWait.Ticks(360);

            Farm farm = Game1.getFarm();
            IDictionary<Vector2, int> states = this._api!.GetMachineStates(farm, WholeFarm(farm));
            GcbAssert.IsTrue(states.Any(),
                "API reports the farm's non-automated machines (e.g. the shipping bin) after the initial scan");
        }

        private IEnumerator SentinelAutomatedMachineReported()
        {
            // Chest first, then furnace beside it: the chest is tracked as an outdated
            // container, so the machine placement queues a reload on both trees.
            Farm farm = Game1.getFarm();
            GcbWorld.ClearArea(farm, FarmArea);
            GcbWorld.Place(farm, new Vector2(FarmArea.X, FarmArea.Y), "(BC)130");
            GcbWorld.Place(farm, new Vector2(FarmArea.X + 1, FarmArea.Y), "(BC)13");

            int deadline = 1500;
            yield return GcbWait.Until(
                () => this._api!.GetMachineStates(Game1.getFarm(), FarmArea).Any() || --deadline <= 0);

            GcbAssert.IsTrue(this._api!.GetMachineStates(Game1.getFarm(), FarmArea).Any(),
                "API reports machine states for the farm's automated machine group");
        }

        private IEnumerator BothReportedTogether()
        {
            Farm farm = Game1.getFarm();
            IDictionary<Vector2, int> states = this._api!.GetMachineStates(farm, WholeFarm(farm));
            GcbAssert.IsTrue(states.ContainsKey(new Vector2(FarmArea.X + 1, FarmArea.Y)),
                "the automated furnace's tile is present in the farm-wide report");
            GcbAssert.IsTrue(states.Count > 1,
                "the farm-wide report also covers machines outside the automated group");
            yield break;
        }
    }
}
