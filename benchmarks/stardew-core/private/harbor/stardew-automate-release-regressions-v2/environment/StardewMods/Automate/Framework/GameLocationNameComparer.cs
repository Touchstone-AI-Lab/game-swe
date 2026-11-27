using System.Collections.Generic;
using StardewValley;

namespace Pathoschild.Stardew.Automate.Framework;

/// <summary>A comparer which considers two locations equal if they have the same name.</summary>
internal class GameLocationNameComparer : IEqualityComparer<GameLocation>
{
    /*********
    ** Public methods
    *********/
    /// <inheritdoc />
    public bool Equals(GameLocation? left, GameLocation? right)
    {
        string? leftName = left?.Name;
        string? rightName = right?.Name;

        if (leftName is null)
            return rightName is null;

        if (rightName is null)
            return false;

        return leftName == rightName;
    }

    /// <inheritdoc />
    public int GetHashCode(GameLocation obj)
    {
        return (obj.Name ?? string.Empty).GetHashCode();
    }
}
