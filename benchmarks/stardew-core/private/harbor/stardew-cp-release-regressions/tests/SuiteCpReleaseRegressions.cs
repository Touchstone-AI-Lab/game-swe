using System.Collections.Generic;
using System.Linq;
using GcbHarness.Framework;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using xTile;

namespace GcbHarness.Suites
{
    /// <summary>A data model owned by the verifier, standing in for a C# mod that exposes a
    /// custom data asset for content packs to edit (the verifier requests the asset with
    /// this type, so Content Patcher edits it as a data model).</summary>
    public sealed class GcbProbeModel
    {
        public string? Label { get; set; }
        public Vector2 Offset { get; set; }
        public List<string> Tags { get; set; } = new() { "default" };
        public Dictionary<string, string> Extra { get; set; } = new();
    }

    /// <summary>Verifies Content Patcher behaviour through a fixture content pack
    /// (tests/probe-pack) that edits two verifier-owned data assets and a vanilla map
    /// that no location uses outside its festival. Every case reads the edited assets
    /// through the game's content pipeline after the save is loaded, when every token in
    /// the pack is ready.</summary>
    public sealed class CpReleaseRegressionsSuite : IGcbSuite
    {
        private const string ProbeAsset = "Mods/GameCodeBench/Probe";
        private const string ModelsAsset = "Mods/GameCodeBench/Models";
        private const string MapAsset = "Maps/Town-EggFestival";

        public string GroupName => "content-patcher.release-regressions";

        private IModHelper? _helper;

        public void OnEntry(IModHelper helper)
        {
            this._helper = helper;
        }

        public IEnumerable<GcbCase> Cases =>
        [
            GcbCase.Sync("sentinel: the probe pack loads and plain entries apply", this.Sentinel),
            GcbCase.Sync("PathPart: a positive index returns that segment from the left", this.PathPartFromLeft),
            GcbCase.Sync("PathPart: a negative index returns that segment from the right", this.PathPartFromRight),
            GcbCase.Sync("PathPart: fragment names return the file and directory parts", this.PathPartFragments),
            GcbCase.Sync("nested data: a tokenised nested key keeps its tokenised value resolved", this.TokenisedNestedKey),
            GcbCase.Sync("nested data: a plain nested key with a tokenised value resolves", this.PlainNestedKey),
            GcbCase.Sync("positions: the {X, Y} object form is accepted in a new entry", this.ObjectPositionInEntry),
            GcbCase.Sync("positions: the {X, Y} object form is accepted in a field edit", this.ObjectPositionInField),
            GcbCase.Sync("positions: the \"X, Y\" text form is accepted in a new entry", this.StringPositionInEntry),
            GcbCase.Sync("positions: the \"X, Y\" text form is accepted in a field edit", this.StringPositionInField),
            GcbCase.Sync("lists: a new entry's list field holds exactly the listed values", this.ListFieldReplaced),
            GcbCase.Sync("text operations: removing from a missing entry leaves it missing", this.RemoveFromMissingEntry),
            GcbCase.Sync("text operations: removing from a missing map property leaves it missing", this.RemoveFromMissingMapProperty),
            GcbCase.Sync("text operations: removing from an existing entry removes only that value", this.RemoveFromExistingEntry),
            GcbCase.Sync("text operations: appending to a missing entry creates it", this.AppendToMissingEntry),
            GcbCase.Sync("text operations: appending to a missing map property creates it", this.AppendToMissingMapProperty),
        ];

        /*********
        ** Asset access
        *********/
        private Dictionary<string, string> Probe()
        {
            var asset = this._helper!.GameContent.Load<Dictionary<string, string>>(ProbeAsset);
            GcbAssert.IsNotNull(asset, "probe asset loads");
            return asset;
        }

        private Dictionary<string, GcbProbeModel> Models()
        {
            var asset = this._helper!.GameContent.Load<Dictionary<string, GcbProbeModel>>(ModelsAsset);
            GcbAssert.IsNotNull(asset, "model asset loads");
            return asset;
        }

        private Map EggFestivalMap()
        {
            Map map = this._helper!.GameContent.Load<Map>(MapAsset);
            GcbAssert.IsNotNull(map, "festival map loads");
            return map;
        }

        private static string Entry(Dictionary<string, string> data, string key)
        {
            GcbAssert.IsTrue(data.TryGetValue(key, out string? value), $"entry '{key}' was written");
            return value!;
        }

        private static GcbProbeModel Model(Dictionary<string, GcbProbeModel> data, string key)
        {
            GcbAssert.IsTrue(data.TryGetValue(key, out GcbProbeModel? value) && value is not null, $"model entry '{key}' was written");
            return value!;
        }

        /*********
        ** Cases
        *********/
        private void Sentinel()
        {
            Dictionary<string, string> probe = this.Probe();
            GcbAssert.AreEqual("constant", Entry(probe, "static"), "entry loaded from the pack's file");
            GcbAssert.AreEqual("resolved-value", Entry(probe, "sentinel"), "entry set from a dynamic token");
            GcbAssert.AreEqual("base", Model(this.Models(), "base").Label, "model entry loaded from the pack's file");
        }

        private void PathPartFromLeft()
        {
            Dictionary<string, string> probe = this.Probe();
            GcbAssert.AreEqual("assets", Entry(probe, "left0"), "PathPart index 0");
            GcbAssert.AreEqual("portraits", Entry(probe, "left1"), "PathPart index 1");
            GcbAssert.AreEqual("Abigail.png", Entry(probe, "left2"), "PathPart index 2");
        }

        private void PathPartFromRight()
        {
            Dictionary<string, string> probe = this.Probe();
            GcbAssert.AreEqual("Abigail.png", Entry(probe, "right1"), "PathPart index -1");
            GcbAssert.AreEqual("portraits", Entry(probe, "right2"), "PathPart index -2");
        }

        private void PathPartFragments()
        {
            Dictionary<string, string> probe = this.Probe();
            GcbAssert.AreEqual("Abigail.png", Entry(probe, "fileName"), "PathPart FileName");
            GcbAssert.AreEqual("assets/portraits", Entry(probe, "directory").Replace('\\', '/'), "PathPart DirectoryPath");
            GcbAssert.AreEqual("Abigail", Entry(probe, "stem"), "PathPart FileNameWithoutExtension");
            GcbAssert.AreEqual("Abigail", Entry(probe, "docExample"), "PathPart Filename (documented example)");
        }

        private void TokenisedNestedKey()
        {
            GcbProbeModel nested = Model(this.Models(), "nested");
            GcbAssert.IsTrue(nested.Extra.TryGetValue("tokenised_key", out string? value), "nested key built from a token exists");
            GcbAssert.AreEqual("resolved-value", value, "value under the tokenised nested key");
        }

        private void PlainNestedKey()
        {
            GcbProbeModel nested = Model(this.Models(), "nested");
            GcbAssert.IsTrue(nested.Extra.TryGetValue("plain_key", out string? value), "plain nested key exists");
            GcbAssert.AreEqual("resolved-value", value, "value under the plain nested key");
        }

        private static void AssertPosition(GcbProbeModel model, float x, float y, string what)
        {
            GcbAssert.AreEqual($"{x}, {y}", $"{model.Offset.X}, {model.Offset.Y}", what);
        }

        private void StringPositionInEntry()
        {
            GcbProbeModel model = Model(this.Models(), "stringFormat");
            GcbAssert.AreEqual("string", model.Label, "entry label");
            AssertPosition(model, 15, 20, "position written as \"15, 20\"");
        }

        private void StringPositionInField()
        {
            AssertPosition(Model(this.Models(), "fieldString"), 7, 9, "position field edited to \"7, 9\"");
        }

        private void ObjectPositionInField()
        {
            AssertPosition(Model(this.Models(), "fieldObject"), 7, 9, "position field edited to {X: 7, Y: 9}");
        }

        private void ObjectPositionInEntry()
        {
            GcbProbeModel model = Model(this.Models(), "objectFormat");
            GcbAssert.AreEqual("object", model.Label, "entry label");
            AssertPosition(model, 15, 20, "position written as {X, Y}");
        }

        private void ListFieldReplaced()
        {
            GcbProbeModel model = Model(this.Models(), "listed");
            GcbAssert.AreEqual("alpha,beta", string.Join(",", model.Tags), "list field of the new entry");
        }

        private void RemoveFromMissingEntry()
        {
            Dictionary<string, string> probe = this.Probe();
            GcbAssert.IsTrue(!probe.ContainsKey("absent"), "no entry named 'absent' exists after removing a value from it");
        }

        private void RemoveFromMissingMapProperty()
        {
            Map map = this.EggFestivalMap();
            GcbAssert.IsTrue(!map.Properties.ContainsKey("GcbAbsent"), "no map property named 'GcbAbsent' exists after removing a value from it");
        }

        private void RemoveFromExistingEntry()
        {
            GcbAssert.AreEqual("A/C", Entry(this.Probe(), "existing"), "entry after removing B");
        }

        private void AppendToMissingEntry()
        {
            GcbAssert.AreEqual("fresh", Entry(this.Probe(), "appended"), "entry created by appending");
        }

        private void AppendToMissingMapProperty()
        {
            Map map = this.EggFestivalMap();
            GcbAssert.IsTrue(map.Properties.TryGetValue("GcbAppended", out xTile.ObjectModel.PropertyValue? value) && value is not null, "map property created by appending");
            GcbAssert.AreEqual("hello", value!.ToString(), "map property value");
        }
    }
}
