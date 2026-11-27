using System;
using System.Collections.Generic;

namespace Aequus.Common.Carpentry;

public sealed class BuildChallenge
{
    public int Type { get; set; }
    public string FullName { get; set; } = string.Empty;
    public int BuildBuffType { get; set; }
}

public static class BuildChallengeLoader
{
    public static readonly List<BuildChallenge> registeredBuildChallenges = new();
    public static int BuildChallengeCount => registeredBuildChallenges.Count;

    public static bool TryFind(string name, out BuildChallenge challenge)
    {
        challenge = registeredBuildChallenges.Find(value => value.FullName == name)!;
        return challenge is not null;
    }
}

internal static class EngineListExtensions
{
    internal static bool ContainsAny<T>(this List<T> values, Predicate<T> predicate)
        => values.Exists(predicate);
}
