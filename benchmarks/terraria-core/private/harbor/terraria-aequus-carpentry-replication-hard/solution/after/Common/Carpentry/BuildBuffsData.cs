using Aequus.Common.Carpentry.Results;
using Microsoft.Xna.Framework;
using System;
using System.Collections.Generic;
using System.IO;
using Terraria.ModLoader.IO;

namespace Aequus.Common.Carpentry;

public readonly struct BuildBuffsData {
    private const int MaxNetworkLocations = 4096;

    public readonly string SaveKeyFormat;
    public readonly Dictionary<int, List<Rectangle>> WorldData;
    private readonly Dictionary<int, string> _worldNames;
    private readonly Dictionary<string, List<Rectangle>> _unloadedData;

    public BuildBuffsData(string saveKeyFormat) {
        SaveKeyFormat = saveKeyFormat;
        WorldData = new();
        _worldNames = new();
        _unloadedData = new(StringComparer.Ordinal);
    }

    public void Clear() {
        WorldData?.Clear();
        _worldNames?.Clear();
        _unloadedData?.Clear();
    }

    private string SaveKey(string fullName) {
        return string.Format(SaveKeyFormat, fullName);
    }

    private bool TryReadSaveKey(string key, out string fullName) {
        int marker = SaveKeyFormat.IndexOf("{0}", StringComparison.Ordinal);
        if (marker < 0) {
            fullName = null;
            return false;
        }
        string prefix = SaveKeyFormat.Substring(0, marker);
        string suffix = SaveKeyFormat.Substring(marker + 3);
        if (!key.StartsWith(prefix, StringComparison.Ordinal) || !key.EndsWith(suffix, StringComparison.Ordinal) ||
            key.Length <= prefix.Length + suffix.Length) {
            fullName = null;
            return false;
        }
        fullName = key.Substring(prefix.Length, key.Length - prefix.Length - suffix.Length);
        return !string.IsNullOrEmpty(fullName);
    }

    internal static bool IsValidRectangle(Rectangle rectangle) {
        if (rectangle.Width <= 0 || rectangle.Height <= 0) {
            return false;
        }
        long right = (long)rectangle.X + rectangle.Width;
        long bottom = (long)rectangle.Y + rectangle.Height;
        return right >= int.MinValue && right <= int.MaxValue && bottom >= int.MinValue && bottom <= int.MaxValue;
    }

    private static bool Intersects(Rectangle left, Rectangle right) {
        return (long)right.X < (long)left.X + left.Width && (long)left.X < (long)right.X + right.Width &&
            (long)right.Y < (long)left.Y + left.Height && (long)left.Y < (long)right.Y + right.Height;
    }

    private static bool Equal(Rectangle left, Rectangle right) {
        return left.X == right.X && left.Y == right.Y && left.Width == right.Width && left.Height == right.Height;
    }

    private static bool SameRectangles(List<Rectangle> current, List<Rectangle> snapshot) {
        if (current == null || current.Count != snapshot.Count) {
            return false;
        }
        for (int i = 0; i < current.Count; i++) {
            if (!Equal(current[i], snapshot[i])) {
                return false;
            }
        }
        return true;
    }

    private static List<Rectangle> FilterRectangles(IEnumerable<Rectangle> source) {
        var filtered = new List<Rectangle>();
        if (source == null) {
            return filtered;
        }
        foreach (Rectangle rectangle in source) {
            if (!IsValidRectangle(rectangle)) {
                continue;
            }
            bool overlaps = false;
            foreach (Rectangle existing in filtered) {
                if (Intersects(existing, rectangle)) {
                    overlaps = true;
                    break;
                }
            }
            if (!overlaps) {
                filtered.Add(rectangle);
            }
        }
        return filtered;
    }

    private static void Merge(Dictionary<string, List<Rectangle>> destination, string name, IEnumerable<Rectangle> rectangles) {
        if (string.IsNullOrEmpty(name)) {
            return;
        }
        if (!destination.TryGetValue(name, out var list)) {
            list = new List<Rectangle>();
            destination.Add(name, list);
        }
        foreach (Rectangle rectangle in rectangles ?? Array.Empty<Rectangle>()) {
            if (!IsValidRectangle(rectangle)) {
                continue;
            }
            bool overlaps = false;
            foreach (Rectangle existing in list) {
                if (Intersects(existing, rectangle)) {
                    overlaps = true;
                    break;
                }
            }
            if (!overlaps) {
                list.Add(rectangle);
            }
        }
    }

    internal Dictionary<string, List<Rectangle>> SnapshotByName(BuildChallengeRegistrySnapshot registry) {
        var stable = new Dictionary<string, List<Rectangle>>(StringComparer.Ordinal);
        foreach (var pair in WorldData) {
            string name = null;
            if (!_worldNames.TryGetValue(pair.Key, out name) && pair.Key >= 0 && pair.Key < registry.Count) {
                name = registry.Names[pair.Key];
            }
            if (name != null) {
                Merge(stable, name, pair.Value);
            }
        }
        foreach (var pair in _unloadedData) {
            Merge(stable, pair.Key, pair.Value);
        }
        return stable;
    }

    internal void ReplaceFromStable(BuildChallengeRegistrySnapshot registry, Dictionary<string, List<Rectangle>> stable) {
        Clear();
        foreach (var pair in stable) {
            List<Rectangle> copy = FilterRectangles(pair.Value);
            if (copy.Count == 0) {
                continue;
            }
            if (registry.ByName.TryGetValue(pair.Key, out int id)) {
                WorldData[id] = copy;
                _worldNames[id] = pair.Key;
            }
            else {
                _unloadedData[pair.Key] = copy;
            }
        }
    }

    private bool Reconcile(BuildChallengeRegistrySnapshot registry) {
        if (!registry.IsCurrent()) {
            return false;
        }
        Dictionary<string, List<Rectangle>> stable = SnapshotByName(registry);
        if (!registry.IsCurrent()) {
            return false;
        }
        ReplaceFromStable(registry, stable);
        return true;
    }

    private bool Evaluate(BuildChallenge challenge, Rectangle rectangle, bool logFailures) {
        if (challenge.Steps == null) {
            return false;
        }
        try {
            var results = new IScanResults[challenge.Steps.Length];
            ScanInfo scanInfo = new(rectangle);
            HighlightInfo highlightInfo = new(scanInfo.Area);
            challenge.PopulateScanResults(results, ref highlightInfo, in scanInfo);
            foreach (IScanResults result in results) {
                if (result == null || result.ResultType == StepResultType.Fail) {
                    return false;
                }
            }
            return true;
        }
        catch (Exception ex) {
            if (logFailures) {
                Aequus.Instance.Logger.Error($"Error from {challenge.FullName} when evaluating.\n{ex}");
            }
            return false;
        }
    }

    internal Dictionary<string, List<Rectangle>> PrepareSaveData(BuildChallengeRegistrySnapshot registry) {
        Dictionary<string, List<Rectangle>> stable = SnapshotByName(registry);
        var prepared = new Dictionary<string, List<Rectangle>>(StringComparer.Ordinal);
        foreach (var pair in stable) {
            List<Rectangle> rectangles = FilterRectangles(pair.Value);
            if (registry.ByName.TryGetValue(pair.Key, out int id)) {
                var validated = new List<Rectangle>();
                foreach (Rectangle rectangle in rectangles) {
                    if (Evaluate(registry.ById[id], rectangle, logFailures: true)) {
                        validated.Add(rectangle);
                    }
                }
                rectangles = validated;
            }
            if (rectangles.Count > 0) {
                prepared[pair.Key] = rectangles;
            }
        }
        return prepared;
    }

    internal void WriteSaveData(TagCompound tag, Dictionary<string, List<Rectangle>> prepared) {
        var names = new List<string>(prepared.Keys);
        names.Sort(StringComparer.Ordinal);
        foreach (string name in names) {
            tag[SaveKey(name)] = new List<Rectangle>(prepared[name]);
        }
    }

    public void SaveData(TagCompound tag) {
        BuildChallengeRegistrySnapshot registry = BuildChallengeRegistrySnapshot.Capture();
        Dictionary<string, List<Rectangle>> prepared = PrepareSaveData(registry);
        registry.RequireCurrent();
        WriteSaveData(tag, prepared);
    }

    internal Dictionary<string, List<Rectangle>> ParseSaveData(TagCompound tag) {
        var parsed = new Dictionary<string, List<Rectangle>>(StringComparer.Ordinal);
        foreach (var pair in tag) {
            if (!TryReadSaveKey(pair.Key, out string fullName)) {
                continue;
            }
            if (pair.Value is not List<Rectangle> rectangles || rectangles == null) {
                throw new InvalidDataException("A saved building group has an invalid value.");
            }
            List<Rectangle> copy = FilterRectangles(new List<Rectangle>(rectangles));
            if (copy.Count > 0) {
                parsed[fullName] = copy;
            }
        }
        return parsed;
    }

    public void LoadData(TagCompound tag) {
        BuildChallengeRegistrySnapshot registry;
        try {
            registry = BuildChallengeRegistrySnapshot.Capture();
        }
        catch (InvalidOperationException ex) {
            throw new InvalidDataException("The building registry is invalid.", ex);
        }
        Dictionary<string, List<Rectangle>> parsed = ParseSaveData(tag);
        if (!registry.IsCurrent()) {
            throw new InvalidDataException("The building registry changed while loading data.");
        }
        ReplaceFromStable(registry, parsed);
    }

    public bool AnyBuild(int id) {
        if (!BuildChallengeRegistrySnapshot.TryCapture(out var registry) || id < 0 || id >= registry.Count || !Reconcile(registry)) {
            return false;
        }
        return WorldData.TryGetValue(id, out var list) && list != null && list.Count > 0;
    }

    public bool AddBuild(int buildChallengeId, Rectangle rectangle) {
        if (!BuildChallengeRegistrySnapshot.TryCapture(out var registry) || buildChallengeId < 0 ||
            buildChallengeId >= registry.Count || !IsValidRectangle(rectangle) || !Reconcile(registry)) {
            return false;
        }
        if (!WorldData.TryGetValue(buildChallengeId, out var list) || list == null) {
            WorldData[buildChallengeId] = new List<Rectangle> { rectangle };
            _worldNames[buildChallengeId] = registry.Names[buildChallengeId];
            _unloadedData.Remove(registry.Names[buildChallengeId]);
            return true;
        }
        foreach (Rectangle existing in list) {
            if (IsValidRectangle(existing) && Intersects(existing, rectangle)) {
                return false;
            }
        }
        list.Add(rectangle);
        _worldNames[buildChallengeId] = registry.Names[buildChallengeId];
        return true;
    }

    public bool RemoveBuild(int buildChallengeId, int x, int y) {
        if (!BuildChallengeRegistrySnapshot.TryCapture(out var registry) || buildChallengeId < 0 ||
            buildChallengeId >= registry.Count || !Reconcile(registry) ||
            !WorldData.TryGetValue(buildChallengeId, out var list) || list == null) {
            return false;
        }
        for (int i = 0; i < list.Count; i++) {
            Rectangle rectangle = list[i];
            if (IsValidRectangle(rectangle) && x >= rectangle.X && (long)x < (long)rectangle.X + rectangle.Width &&
                y >= rectangle.Y && (long)y < (long)rectangle.Y + rectangle.Height) {
                list.RemoveAt(i);
                if (list.Count == 0) {
                    WorldData.Remove(buildChallengeId);
                    _worldNames.Remove(buildChallengeId);
                }
                return true;
            }
        }
        return false;
    }

    public void TrimBuildingBuffsInWorld(int id) {
        if (!BuildChallengeRegistrySnapshot.TryCapture(out var registry) || id < 0 || id >= registry.Count ||
            !Reconcile(registry) || !WorldData.TryGetValue(id, out var list) || list == null || list.Count == 0) {
            return;
        }

        string name = registry.Names[id];
        var original = new List<Rectangle>(list);
        var accepted = new List<Rectangle>();
        foreach (Rectangle rectangle in original) {
            if (!IsValidRectangle(rectangle)) {
                continue;
            }
            bool overlaps = false;
            foreach (Rectangle existing in accepted) {
                if (Intersects(existing, rectangle)) {
                    overlaps = true;
                    break;
                }
            }
            if (!overlaps && Evaluate(registry.ById[id], rectangle, logFailures: true)) {
                accepted.Add(rectangle);
            }
        }

        if (!registry.IsCurrent() || !WorldData.TryGetValue(id, out var current) || !ReferenceEquals(current, list) ||
            !_worldNames.TryGetValue(id, out string currentName) || currentName != name || !SameRectangles(current, original)) {
            return;
        }
        if (accepted.Count == 0) {
            WorldData.Remove(id);
            _worldNames.Remove(id);
        }
        else {
            list.Clear();
            list.AddRange(accepted);
        }
    }

    internal byte[] PrepareFrame(BuildChallengeRegistrySnapshot registry) {
        Dictionary<string, List<Rectangle>> stable = SnapshotByName(registry);
        var groups = new SortedDictionary<int, List<Rectangle>>();
        int total = 0;
        foreach (var pair in stable) {
            if (!registry.ByName.TryGetValue(pair.Key, out int id)) {
                continue;
            }
            List<Rectangle> rectangles = FilterRectangles(pair.Value);
            if (rectangles.Count == 0) {
                continue;
            }
            if (rectangles.Count > MaxNetworkLocations - total) {
                throw new InvalidOperationException("The building frame exceeds its global location budget.");
            }
            total += rectangles.Count;
            groups[id] = rectangles;
        }

        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, leaveOpen: true)) {
            writer.Write(groups.Count);
            foreach (var pair in groups) {
                writer.Write(pair.Key);
                writer.Write(pair.Value.Count);
                foreach (Rectangle rectangle in pair.Value) {
                    writer.Write(rectangle.X);
                    writer.Write(rectangle.Y);
                    writer.Write(rectangle.Width);
                    writer.Write(rectangle.Height);
                }
            }
        }
        return stream.ToArray();
    }

    public void NetSend(BinaryWriter writer) {
        BuildChallengeRegistrySnapshot registry = BuildChallengeRegistrySnapshot.Capture();
        byte[] frame = PrepareFrame(registry);
        registry.RequireCurrent();
        writer.Write(frame);
    }

    internal Dictionary<string, List<Rectangle>> ParseFrame(BinaryReader reader, BuildChallengeRegistrySnapshot registry) {
        try {
            int groupCount = reader.ReadInt32();
            if (groupCount < 0 || groupCount > registry.Count) {
                throw new InvalidDataException("Invalid building group count.");
            }
            var received = new Dictionary<string, List<Rectangle>>(StringComparer.Ordinal);
            int previousId = -1;
            int total = 0;
            for (int i = 0; i < groupCount; i++) {
                int id = reader.ReadInt32();
                int locationCount = reader.ReadInt32();
                if (id < 0 || id >= registry.Count || id <= previousId || locationCount <= 0 ||
                    locationCount > MaxNetworkLocations || locationCount > MaxNetworkLocations - total) {
                    throw new InvalidDataException("Invalid building group.");
                }
                total += locationCount;
                previousId = id;
                var rectangles = new List<Rectangle>(locationCount);
                for (int j = 0; j < locationCount; j++) {
                    var rectangle = new Rectangle(reader.ReadInt32(), reader.ReadInt32(), reader.ReadInt32(), reader.ReadInt32());
                    if (!IsValidRectangle(rectangle)) {
                        throw new InvalidDataException("Invalid building rectangle.");
                    }
                    foreach (Rectangle existing in rectangles) {
                        if (Intersects(existing, rectangle)) {
                            throw new InvalidDataException("Overlapping building rectangles.");
                        }
                    }
                    rectangles.Add(rectangle);
                }
                received.Add(registry.Names[id], rectangles);
            }
            return received;
        }
        catch (EndOfStreamException ex) {
            throw new InvalidDataException("Building data is truncated.", ex);
        }
    }

    public void NetReceive(BinaryReader reader) {
        BuildChallengeRegistrySnapshot registry;
        try {
            registry = BuildChallengeRegistrySnapshot.Capture();
        }
        catch (InvalidOperationException ex) {
            throw new InvalidDataException("The building registry is invalid.", ex);
        }
        Dictionary<string, List<Rectangle>> received = ParseFrame(reader, registry);
        if (!registry.IsCurrent()) {
            throw new InvalidDataException("The building registry changed while receiving data.");
        }
        ReplaceFromStable(registry, received);
    }

    internal SortedDictionary<int, List<Rectangle>> SnapshotActive(BuildChallengeRegistrySnapshot registry) {
        Dictionary<string, List<Rectangle>> stable = SnapshotByName(registry);
        var active = new SortedDictionary<int, List<Rectangle>>();
        foreach (var pair in stable) {
            if (registry.ByName.TryGetValue(pair.Key, out int id)) {
                List<Rectangle> rectangles = FilterRectangles(pair.Value);
                if (rectangles.Count > 0) {
                    active[id] = rectangles;
                }
            }
        }
        return active;
    }
}
