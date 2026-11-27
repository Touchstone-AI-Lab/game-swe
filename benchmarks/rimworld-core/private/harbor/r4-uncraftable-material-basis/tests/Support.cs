using Verse;

namespace RRRR
{
    public sealed class RRRR_Settings : ModSettings
    {
        public float recycleGlobalMult = 1.0f;
        public bool skipIntricateComponents;
        public float repairHpPerCycle = 0.20f;
        public float cleanCostFraction = 0.20f;

        public int RepairCyclesFull =>
            UnityEngine.Mathf.Max(1, UnityEngine.Mathf.CeilToInt(1.0f /
                UnityEngine.Mathf.Clamp(repairHpPerCycle, 0.05f, 1.0f)));

        public int RepairCostDivisor => RepairCyclesFull * 2;

        public int CleanCostDivisor =>
            UnityEngine.Mathf.Max(1, UnityEngine.Mathf.RoundToInt(1.0f /
                UnityEngine.Mathf.Clamp(cleanCostFraction, 0.05f, 1.0f)));
    }

    public static class RRRR_Mod
    {
        public static RRRR_Settings Settings { get; } = new RRRR_Settings();
    }

    public static class R4Log
    {
        public static void Debug(string message) { }
        public static void Warn(string message) => Log.Warning("[R4] " + message);
        public static void Error(string message) => Log.Error("[R4] " + message);
    }
}
