using System;
using System.Collections.Generic;
using System.IO;
using Terraria.ModLoader.IO;

namespace Aequus.Common.Carpentry;

internal sealed class BuildChallengeRegistrySnapshot {
    public readonly BuildChallenge[] ById;
    public readonly string[] Names;
    public readonly int[] BuffTypes;
    public readonly Dictionary<string, int> ByName;

    public int Count => ById.Length;

    private BuildChallengeRegistrySnapshot(BuildChallenge[] byId, string[] names, int[] buffTypes, Dictionary<string, int> byName) {
        ById = byId;
        Names = names;
        BuffTypes = buffTypes;
        ByName = byName;
    }

    public static BuildChallengeRegistrySnapshot Capture() {
        int count = BuildChallengeLoader.BuildChallengeCount;
        if (count < 0 || BuildChallengeLoader.registeredBuildChallenges.Count != count) {
            throw new InvalidOperationException("The build-challenge registry is not contiguous.");
        }

        var byId = new BuildChallenge[count];
        var names = new string[count];
        var buffTypes = new int[count];
        var byName = new Dictionary<string, int>(count, StringComparer.Ordinal);
        for (int id = 0; id < count; id++) {
            BuildChallenge challenge = BuildChallengeLoader.registeredBuildChallenges[id];
            if (challenge == null || challenge.Type != id || string.IsNullOrEmpty(challenge.FullName) ||
                !byName.TryAdd(challenge.FullName, id)) {
                throw new InvalidOperationException("The build-challenge registry has an invalid identity.");
            }
            byId[id] = challenge;
            names[id] = challenge.FullName;
            buffTypes[id] = challenge.BuildBuffType;
        }
        return new BuildChallengeRegistrySnapshot(byId, names, buffTypes, byName);
    }

    public static bool TryCapture(out BuildChallengeRegistrySnapshot snapshot) {
        try {
            snapshot = Capture();
            return true;
        }
        catch (InvalidOperationException) {
            snapshot = null;
            return false;
        }
    }

    public bool IsCurrent() {
        if (BuildChallengeLoader.BuildChallengeCount != Count ||
            BuildChallengeLoader.registeredBuildChallenges.Count != Count) {
            return false;
        }
        for (int id = 0; id < Count; id++) {
            BuildChallenge challenge = BuildChallengeLoader.registeredBuildChallenges[id];
            if (!ReferenceEquals(challenge, ById[id]) || challenge.Type != id ||
                !string.Equals(challenge.FullName, Names[id], StringComparison.Ordinal) ||
                challenge.BuildBuffType != BuffTypes[id]) {
                return false;
            }
        }
        return true;
    }

    public void RequireCurrent() {
        if (!IsCurrent()) {
            throw new InvalidOperationException("The build-challenge registry changed during the operation.");
        }
    }
}

public readonly struct BuildChallengeSaveData {
    public readonly List<string> Challenges;
    public readonly string SaveKey;

    public BuildChallengeSaveData(string saveKey) {
        SaveKey = saveKey;
        Challenges = new();
    }

    public void Clear() {
        Challenges?.Clear();
    }

    private static List<string> CanonicalNames(IEnumerable<string> names) {
        var result = new List<string>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        if (names == null) {
            return result;
        }
        foreach (string name in names) {
            if (!string.IsNullOrEmpty(name) && seen.Add(name)) {
                result.Add(name);
            }
        }
        return result;
    }

    public void SaveData(TagCompound tag) {
        List<string> snapshot = CanonicalNames(Challenges);
        if (snapshot.Count > 0) {
            tag[SaveKey] = snapshot;
        }
    }

    internal List<string> ReadSaveData(TagCompound tag) {
        if (!tag.ContainsKey(SaveKey)) {
            return new List<string>();
        }
        if (!tag.TryGet<List<string>>(SaveKey, out var saved) || saved == null) {
            throw new InvalidDataException("The saved completion list has an invalid value.");
        }
        return CanonicalNames(new List<string>(saved));
    }

    internal void Replace(IEnumerable<string> names) {
        var copy = CanonicalNames(names);
        Challenges.Clear();
        Challenges.AddRange(copy);
    }

    public void LoadData(TagCompound tag) {
        Replace(ReadSaveData(tag));
    }

    public void Clone(BuildChallengeSaveData source) {
        if (Challenges == null || source.Challenges == null) {
            return;
        }
        var copy = new List<string>(source.Challenges);
        Challenges.Clear();
        Challenges.AddRange(copy);
    }

    public bool ContainsChallenge(int id) {
        return BuildChallengeRegistrySnapshot.TryCapture(out var registry) && id >= 0 && id < registry.Count &&
            ContainsChallenge(registry.ById[id]);
    }

    public bool ContainsChallenge(BuildChallenge buildChallenge) {
        return buildChallenge != null && ContainsChallenge(buildChallenge.FullName);
    }

    public bool ContainsChallenge(string internalName) {
        return !string.IsNullOrEmpty(internalName) && Challenges.Contains(internalName);
    }

    public bool ContainsAny(Predicate<string> predicate) {
        return predicate != null && Challenges.ContainsAny(predicate);
    }

    public void Add(BuildChallenge challenge) {
        if (challenge != null && !string.IsNullOrEmpty(challenge.FullName) && !ContainsChallenge(challenge.FullName)) {
            Challenges.Add(challenge.FullName);
        }
    }

    public void TrimData() {
        Replace(Challenges);
    }

    internal byte[] PrepareFrame(BuildChallengeRegistrySnapshot registry) {
        var ids = new SortedSet<int>();
        foreach (string name in CanonicalNames(Challenges)) {
            if (registry.ByName.TryGetValue(name, out int id)) {
                ids.Add(id);
            }
        }

        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, leaveOpen: true)) {
            writer.Write(ids.Count);
            foreach (int id in ids) {
                writer.Write(id);
            }
        }
        return stream.ToArray();
    }

    public void SendData(BinaryWriter writer) {
        BuildChallengeRegistrySnapshot registry = BuildChallengeRegistrySnapshot.Capture();
        byte[] frame = PrepareFrame(registry);
        registry.RequireCurrent();
        writer.Write(frame);
    }

    internal List<string> ParseFrame(BinaryReader reader, BuildChallengeRegistrySnapshot registry) {
        try {
            int count = reader.ReadInt32();
            if (count < 0 || count > registry.Count) {
                throw new InvalidDataException("Invalid completed challenge count.");
            }
            var names = new List<string>(count);
            int previousId = -1;
            for (int i = 0; i < count; i++) {
                int id = reader.ReadInt32();
                if (id < 0 || id >= registry.Count || id <= previousId) {
                    throw new InvalidDataException("Invalid, duplicate, or noncanonical challenge identifier.");
                }
                names.Add(registry.Names[id]);
                previousId = id;
            }
            return names;
        }
        catch (EndOfStreamException ex) {
            throw new InvalidDataException("Completed challenge data is truncated.", ex);
        }
    }

    public void RecieveData(BinaryReader reader) {
        BuildChallengeRegistrySnapshot registry;
        try {
            registry = BuildChallengeRegistrySnapshot.Capture();
        }
        catch (InvalidOperationException ex) {
            throw new InvalidDataException("The completion registry is invalid.", ex);
        }

        List<string> names = ParseFrame(reader, registry);
        if (!registry.IsCurrent()) {
            throw new InvalidDataException("The completion registry changed while receiving data.");
        }
        Replace(names);
    }
}
