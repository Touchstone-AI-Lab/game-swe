using System.Collections.Generic;
using Terraria.ID;
using Terraria.ModLoader;

namespace ModLiquidLib.ModLoader;

public abstract class ModLiquid : ModType
{
    public ushort Type { get; internal set; }

    public virtual ushort GetMapOption(int i, int j) => 0;

    public override void Register() => ModTypeLookup<ModLiquid>.Register(this);

    public override void SetupContent() => SetStaticDefaults();
}

public static class LiquidLoader
{
    private static readonly Dictionary<int, ModLiquid> Liquids = new();

    public static int LiquidCount { get; set; } = LiquidID.Count;

    public static ModLiquid GetLiquid(int type) => Liquids[type];

    public static ModLiquid GetLiquid(ushort type) => Liquids[type];
}
