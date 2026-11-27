// MIT: derived from pardeike/Zombieland; see LICENSE and validation/source-derivation.json.
// Reproducible source slice: three production patch classes, unchanged bodies.
// Full Mod startup, assets and optional integrations are intentionally not loaded.
using System.Collections.Generic;
using HarmonyLib;
using RimWorld;
using UnityEngine;
using Verse;
namespace ZombieLand
{
    static partial class Patches
    {
		// patch to make infected colonists have no needs
		//
		[HarmonyPatch(typeof(Need))]
		[HarmonyPatch(nameof(Need.CurLevel), MethodType.Setter)]
		public static class Need_CurLevel_Patch
		{
			// this is set periodically from Alerts.Alert_ZombieInfection
			public static HashSet<Pawn> infectedColonists = new();

			static bool ShouldBeAverageNeed(Need need)
			{
				var pawn = need?.pawn;
				if (pawn == null)
					return false;
				if (infectedColonists.Contains(pawn))
					return true;
				if (need is Need_Mood && ZombieSymbiant.HasMoodFixedBenefit(pawn))
					return true;
				if (ZombieSymbiant.HasNoFoodOrRestBenefit(pawn) && (need.def == NeedDefOf.Food || need.def?.defName == "Rest"))
					return true;
				return false;
			}

			[HarmonyPriority(Priority.Last)]
			static void Prefix(Need __instance, ref float value)
			{
				if (ShouldBeAverageNeed(__instance))
					value = 0.5f;
			}
		}

		// patch to make infected colonists and Symbiants feel no pain
		//
		[HarmonyPatch(typeof(HediffSet))]
		[HarmonyPatch(nameof(HediffSet.PainTotal), MethodType.Getter)]
		static class HediffSet_CalculatePain_Patch
		{
			static bool Prefix(HediffSet __instance, ref float __result)
			{
				var pawn = __instance?.pawn;
				if (pawn is ZombieSymbiant || pawn != null && Need_CurLevel_Patch.infectedColonists.Contains(pawn))
				{
					__result = 0f;
					return false;
				}
				return true;
			}
		}

		// patch to make infected colonists and Symbiants have full capacity
		//
		[HarmonyPatch(typeof(PawnCapacitiesHandler))]
		[HarmonyPatch(nameof(PawnCapacitiesHandler.GetLevel))]
		static class PawnCapacitiesHandler_GetLevel_Patch
		{
			static bool FullLevel(Pawn pawn)
			{
				return pawn?.health?.Dead == false
					&& (pawn is ZombieSymbiant || Need_CurLevel_Patch.infectedColonists.Contains(pawn));
			}

			[HarmonyPriority(Priority.Last)]
			static bool Prefix(Pawn ___pawn, ref float __result)
			{
				if (FullLevel(___pawn))
				{
					__result = 1f;
					return false;
				}
				return true;
			}
		}

    }
}
