using System.Collections;
using System.Collections.Generic;
using GcbHarness.Framework;
using StardewModdingAPI;

namespace GcbHarness.Suites
{
    /// <summary>Verifies that the {{i18n}} token preserves translation text exactly.
    /// The verifier installs a minimal Content Patcher pack whose i18n file contains
    /// "True", "FALSE", and "Howdy", written into a custom data asset. Sentinel:
    /// ordinary text and literal entries come through unchanged on both trees. The
    /// base tree lowercases translations whose entire text matches a predefined set
    /// like true/false; the fixed tree preserves their case.</summary>
    public sealed class I18nCaseSuite : IGcbSuite
    {
        public string GroupName => "content-patcher.i18n-case";

        private IModHelper? _helper;

        public void OnEntry(IModHelper helper)
        {
            this._helper = helper;
        }

        public IEnumerable<GcbCase> Cases =>
        [
            GcbCase.Sync("sentinel: the pack's patches apply and ordinary text is unchanged", this.SentinelPatchApplies),
            GcbCase.Sync("a translation reading \"True\" keeps its capital T", this.TrueKeepsCase),
            GcbCase.Sync("a translation reading \"FALSE\" keeps its upper case", this.FalseKeepsCase),
        ];

        private Dictionary<string, string> LoadProbe()
        {
            var asset = this._helper!.GameContent.Load<Dictionary<string, string>>("Mods/GameCodeBench/Probe");
            GcbAssert.IsNotNull(asset, "probe asset loads");
            return asset;
        }

        private void SentinelPatchApplies()
        {
            Dictionary<string, string> probe = this.LoadProbe();
            GcbAssert.IsTrue(probe.TryGetValue("static", out string? staticValue), "literal entry was written");
            GcbAssert.AreEqual("constant", staticValue, "literal entry value");
            GcbAssert.IsTrue(probe.TryGetValue("greeting", out string? greeting), "i18n entry was written");
            GcbAssert.AreEqual("Howdy", greeting, "ordinary translation text");
        }

        private void TrueKeepsCase()
        {
            Dictionary<string, string> probe = this.LoadProbe();
            GcbAssert.IsTrue(probe.TryGetValue("flag", out string? flag), "flag entry was written");
            GcbAssert.AreEqual("True", flag, "translation text matching a boolean");
        }

        private void FalseKeepsCase()
        {
            Dictionary<string, string> probe = this.LoadProbe();
            GcbAssert.IsTrue(probe.TryGetValue("negative", out string? negative), "negative entry was written");
            GcbAssert.AreEqual("FALSE", negative, "translation text matching a boolean, upper-cased");
        }
    }
}
