using System.Collections;
using System.Collections.Generic;
using GcbHarness.Framework;
using StardewModdingAPI;
using StardewValley.GameData.Objects;

namespace GcbHarness.Suites
{
    /// <summary>Verifies Content Patcher's runtime migration of pre-1.6 Load patches.
    /// The verifier installs a format-1.28 pack that Loads Data/ObjectInformation with
    /// two legacy-format entries. Correct migration merges those entries into the
    /// vanilla Data/Objects (like an edit); the buggy migration replaces the whole
    /// asset, wiping every 1.6-only item and the rest of the catalogue with it.
    /// Assertions are pure data reads, independent of update timing.</summary>
    public sealed class LegacyLoadSuite : IGcbSuite
    {
        public string GroupName => "content-patcher.legacy-load-migration";

        private IModHelper? _helper;

        public void OnEntry(IModHelper helper)
        {
            this._helper = helper;
        }

        public IEnumerable<GcbCase> Cases =>
        [
            GcbCase.Sync("sentinel: the legacy pack's entries are applied to Data/Objects", this.SentinelLegacyEntriesApplied),
            GcbCase.Sync("1.6-only items survive a legacy Load patch", this.NewItemsSurvive),
            GcbCase.Sync("the rest of the object catalogue survives a legacy Load patch", this.CatalogueSurvives),
        ];

        private Dictionary<string, ObjectData> LoadObjects()
        {
            var data = this._helper!.GameContent.Load<Dictionary<string, ObjectData>>("Data/Objects");
            GcbAssert.IsNotNull(data, "Data/Objects loads");
            return data;
        }

        private void SentinelLegacyEntriesApplied()
        {
            Dictionary<string, ObjectData> data = this.LoadObjects();
            GcbAssert.IsTrue(data.TryGetValue("24", out ObjectData? parsnip), "parsnip entry exists");
            GcbAssert.AreEqual(350, parsnip!.Price, "parsnip price from the legacy pack");
            GcbAssert.IsTrue(data.TryGetValue("16", out ObjectData? horseradish), "wild horseradish entry exists");
            GcbAssert.AreEqual(250, horseradish!.Price, "wild horseradish price from the legacy pack");
        }

        private void NewItemsSurvive()
        {
            Dictionary<string, ObjectData> data = this.LoadObjects();
            GcbAssert.IsTrue(data.ContainsKey("Carrot"), "Carrot (added in 1.6) is still in Data/Objects");
            GcbAssert.IsTrue(data.ContainsKey("SummerSquash"), "Summer Squash (added in 1.6) is still in Data/Objects");
        }

        private void CatalogueSurvives()
        {
            Dictionary<string, ObjectData> data = this.LoadObjects();
            GcbAssert.IsTrue(data.Count > 500,
                $"Data/Objects still contains the full catalogue (got {data.Count} entries)");
        }
    }
}
