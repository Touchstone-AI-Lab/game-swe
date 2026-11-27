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

        // ResolveTrade removes a sold non-bulk thing from the tradeable, so what was sold is
        // read before the trade resolves and handed to the postfix as state.
        [HarmonyPrefix]
        static void Prefix(Tradeable __instance, out SoldThing __state)
        {
            bool selling = __instance.ActionToDo == TradeAction.PlayerSells;
            bool hasThing = selling && (__instance.FirstThingColony != null || __instance.FirstThingTrader != null);
            __state = hasThing
                ? new SoldThing { Def = __instance.ThingDef, Count = __instance.CountToTransferToDestination }
                : default;
        }

        [HarmonyPostfix]
        static void Postfix(SoldThing __state)
        {
            if (__state.Def == null || __state.Count < 1)
            {
                return;
            }

            Scenario scenario = Find.Scenario;
            if (scenario == null)
            {
                return;
            }

            Faction traderFaction = TradeSession.trader?.Faction;
            foreach (ScenPart part in scenario.AllParts)
            {
                if (part is WinCondition_SellItems sellItems)
                {
                    sellItems.NotifyThingSoldToTrader(__state.Def, __state.Count);
                }
                else if (traderFaction != null && part is WinCondition_SellItemsToFaction sellToFaction)
                {
                    sellToFaction.NotifyThingSoldToTrader(__state.Def, __state.Count, traderFaction);
                }
            }
        }
    }
}
