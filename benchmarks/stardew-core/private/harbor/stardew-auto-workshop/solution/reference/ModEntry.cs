using System;
using System.Linq;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Objects;
using SObject = StardewValley.Object;

namespace AutoWorkshop
{
    /// <summary>Reference solution. Twice a second, walk every location INCLUDING
    /// building interiors (Utility.ForEachLocation with interiors — Game1.locations
    /// alone misses coops and sheds), and for each machine with a directly adjacent
    /// chest: collect finished output into the chest, then feed it from the chest via
    /// the game's own hopper mechanism (AttemptAutoLoad).
    ///
    /// Invariants held: a zero-quantity output is discarded so the machine never
    /// jams; when the chest is full the output stays in the machine (never dropped)
    /// and is delivered once space opens; only directly adjacent chests participate.</summary>
    public sealed class ModEntry : Mod
    {
        public override void Entry(IModHelper helper)
        {
            helper.Events.GameLoop.UpdateTicked += this.OnUpdateTicked;
        }

        private void OnUpdateTicked(object? sender, UpdateTickedEventArgs e)
        {
            if (!Context.IsWorldReady || !e.IsMultipleOf(30))
                return;
            Utility.ForEachLocation(loc => { this.Process(loc); return true; });
        }

        private void Process(GameLocation loc)
        {
            foreach (var pair in loc.objects.Pairs.ToArray())
            {
                SObject machine = pair.Value;
                if (machine is Chest || machine.GetMachineData() is null)
                    continue;
                Chest? chest = FindAdjacentChest(loc, pair.Key);
                if (chest is null)
                    continue;
                CollectOutput(machine, chest);
                FeedInput(machine, chest);
            }
        }

        private static Chest? FindAdjacentChest(GameLocation loc, Vector2 tile)
        {
            foreach (Vector2 offset in new[] { new Vector2(-1, 0), new Vector2(1, 0), new Vector2(0, -1), new Vector2(0, 1) })
            {
                if (loc.objects.TryGetValue(tile + offset, out SObject obj) && obj is Chest chest)
                    return chest;
            }
            return null;
        }

        private static void CollectOutput(SObject machine, Chest chest)
        {
            if (!machine.readyForHarvest.Value)
                return;
            SObject? held = machine.heldObject.Value;
            if (held is null || held.Stack <= 0)
            {
                machine.heldObject.Value = null;
                machine.readyForHarvest.Value = false;
                return;
            }
            Item? leftover = chest.addItem(held);
            if (leftover is null)
            {
                machine.heldObject.Value = null;
                machine.readyForHarvest.Value = false;
            }
        }

        private static void FeedInput(SObject machine, Chest chest)
        {
            if (machine.heldObject.Value is not null || machine.readyForHarvest.Value)
                return;
            machine.AttemptAutoLoad(chest.GetItemsForPlayer(), Game1.player);
        }
    }
}
