using System.Collections.Generic;
using CJBCheatsMenu.Framework.Components;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Characters;

namespace CJBCheatsMenu.Framework.Cheats.FarmAndFishing;

/// <summary>A cheat which automatically pets pet animals.</summary>
internal class AutoPetPetsCheat : BaseCheat
{
    /*********
    ** Public methods
    *********/
    /// <inheritdoc />
    public override IEnumerable<CheatElement> GetFields(CheatContext context)
    {
        yield return new CheatCheckbox(
            label: I18n.Farm_AutoPetPets(),
            value: context.Config.AutoPetPets,
            setValue: value => context.Config.AutoPetPets = value
        );
    }

    /// <inheritdoc />
    public override void OnConfig(CheatContext context, out bool needsInput, out bool needsUpdate, out bool needsRendering)
    {
        needsInput = false;
        needsUpdate = context.Config.AutoPetPets;
        needsRendering = false;
    }

    /// <inheritdoc />
    public override void OnUpdated(CheatContext context, UpdateTickedEventArgs e)
    {
        if (!e.IsOneSecond || !Context.IsWorldReady)
            return;

        Utility.ForEachCharacter(npc =>
        {
            if (npc is Pet pet && (!pet.lastPetDay.TryGetValue(Game1.player.UniqueMultiplayerID, out int lastPetDay) || lastPetDay != Game1.Date.TotalDays))
                pet.checkAction(Game1.player, pet.currentLocation);

            return true;
        });
    }
}
