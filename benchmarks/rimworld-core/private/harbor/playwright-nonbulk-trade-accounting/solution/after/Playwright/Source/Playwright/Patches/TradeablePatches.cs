using HarmonyLib;
using RimWorld;
using Rokk.Playwright.PatchCheckers;
using Rokk.Playwright.ScenParts;
using System.Collections.Generic;
using System.Linq;
using Verse;

namespace Rokk.Playwright.Patches
{
    // When an item is sold to a trader, if there are any "Win condition: sell items" parts, notify those scenparts of the trade occurring.
    // TODO: This only handles items, because pawns (prisoners, slaves) have their own implementation of ResolveTrade instead.
    // Do we also have to handle prisoners/slaves? Could be fun tbh
    [HarmonyPatchCategory(WinConditionPatchChecker.TradeCategory)]
    [HarmonyPatch(typeof(Tradeable), nameof(Tradeable.ResolveTrade))]
    public static class Tradeable_ResolveTradePatches
    {
        public struct SoldThing
        {
            public ThingDef Def;
            public int Count;
        }

        // Because ResolveTrade removes the sold Things from Tradeable.thingsColony,
        // we have to store it in a prefix and then read it out again in the postfix when the trade actually happened.
        [HarmonyPrefix]
        static void Prefix(Tradeable __instance, out SoldThing __state)
        {
            __state = default;

            if (__instance.ActionToDo != TradeAction.PlayerSells)
            {
                return;
            }

            // Don't use HasAnyThing here: it calls AnyThing, which is the thing that logs.
            if (__instance.FirstThingColony == null && __instance.FirstThingTrader == null)
            {
                return;
            }

            __state = new SoldThing
            {
                Def = __instance.ThingDef,
                Count = __instance.CountToTransferToDestination
            };
        }

        [HarmonyPostfix]
        static void Postfix(SoldThing __state)
        {
            if (__state.Def == null || __state.Count <= 0)
            {
                return;
            }

            Scenario scenario = Find.Scenario;
            if (scenario == null)
            {
                return;
            }

            foreach (WinCondition_SellItems part in scenario.AllParts.OfType<WinCondition_SellItems>())
            {
                part.NotifyThingSoldToTrader(__state.Def, __state.Count);
            }

            if (TradeSession.trader?.Faction == null)
            {
                return;
            }

            foreach (WinCondition_SellItemsToFaction part in scenario.AllParts.OfType<WinCondition_SellItemsToFaction>())
            {
                part.NotifyThingSoldToTrader(__state.Def, __state.Count, TradeSession.trader.Faction);
            }
        }
    }
}
