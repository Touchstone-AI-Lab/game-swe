namespace FargowiltasSouls.Core.AccessoryEffectSystem;

public class Header
{
    public string SortCategory { get; set; } = "General";
}

public class AccessoryEffect
{
    public virtual string Name => GetType().Name;
    public virtual string FullName => GetType().FullName ?? Name;
    public virtual Header ToggleHeader { get; set; } = new();
    public virtual string ToggleDescription => Name;
    public virtual bool DefaultToggle => true;
    public virtual bool MutantsPresenceAffects => false;
    public virtual bool MinionEffect => false;
}
