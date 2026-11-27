using System.Collections.Generic;
using CJBCheatsMenu.Framework.Components;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;

namespace CJBCheatsMenu.Framework.Cheats.FarmAndFishing;

/// <summary>A cheat which automatically pets farm animals.</summary>
internal class AutoPetAnimalsCheat : BaseCheat
{
    /*********
    ** Public methods
    *********/
    /// <inheritdoc />
    public override IEnumerable<CheatElement> GetFields(CheatContext context)
    {
        yield return new CheatCheckbox(
            label: I18n.Farm_AutoPetAnimals(),
            value: context.Config.AutoPetAnimals,
            setValue: value => context.Config.AutoPetAnimals = value
        );
    }

    /// <inheritdoc />
    public override void OnConfig(CheatContext context, out bool needsInput, out bool needsUpdate, out bool needsRendering)
    {
        needsInput = false;
        needsUpdate = context.Config.AutoPetAnimals;
        needsRendering = false;
    }

    /// <inheritdoc />
    public override void OnUpdated(CheatContext context, UpdateTickedEventArgs e)
    {
        if (!e.IsOneSecond || !Context.IsWorldReady)
            return;

        Utility.ForEachLocation(
            location =>
            {
                if (location.animals.Length > 0 || location.buildings.Count > 0)
                {
                    List<FarmAnimal> animalsToPet = location.getAllFarmAnimals();
                    animalsToPet.RemoveAll(animal => animal.wasPet.Value);

                    if (animalsToPet.Count > 0)
                    {
                        int wasTime = Game1.timeOfDay;
                        Item wasTemporaryItem = Game1.player.TemporaryItem;

                        try
                        {
                            // avoid feeding hay
                            if (Game1.player.ActiveObject?.QualifiedItemId == "(O)178")
                                Game1.player.TemporaryItem = new Object("0", 1);

                            // avoid 'trying to sleep' dialogue popup
                            if (Game1.timeOfDay >= 1900)
                                Game1.timeOfDay = 1850;

                            // pet animals
                            foreach (FarmAnimal animal in animalsToPet)
                                animal.pet(Game1.player);
                        }
                        finally
                        {
                            // restore previous values
                            Game1.player.TemporaryItem = wasTemporaryItem;
                            Game1.timeOfDay = wasTime;
                        }
                    }
                }

                return true;
            },
            includeInteriors: false
        );
    }
}
