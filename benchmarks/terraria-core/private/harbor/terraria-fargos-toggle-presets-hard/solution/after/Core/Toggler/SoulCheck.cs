using FargowiltasSouls.Core.AccessoryEffectSystem;
using Terraria;
using Terraria.ModLoader;

namespace FargowiltasSouls.Core.Toggler
{
    public static class SoulCheck
    {
        public static Toggle GetToggle<T>(this Player player) where T : AccessoryEffect => player.GetToggle(ModContent.GetInstance<T>());
        public static Toggle GetToggle(this Player player, AccessoryEffect effect)
        {
            if (player == null || effect == null)
                return null;

            ToggleBackend backend = player.FargoSouls()?.Toggler;
            if (backend?.Toggles == null)
                return null;
            backend.RefreshRegistry();

            if (backend.Toggles.TryGetValue(effect, out Toggle value))
                return value;

            string identity;
            try
            {
                identity = effect.FullName;
            }
            catch
            {
                return null;
            }
            foreach (Toggle candidate in backend.Toggles.Values)
                if (string.Equals(candidate.Identity, identity, System.StringComparison.Ordinal))
                    return candidate;

            return null;
        }
        public static bool GetToggleValue<T>(this Player player) where T : AccessoryEffect => player.GetToggleValue(ModContent.GetInstance<T>());
        public static bool GetToggleValue(this Player player, AccessoryEffect effect, bool skipChecks = false)
        {
            if (player == null || effect == null)
                return false;

            Toggle toggle = player.GetToggle(effect);
            if (toggle == null)
                return false;
            if (!skipChecks)
            {
                /*
                if (effect.MinionEffect)
                {
                    FargoSoulsPlayer modPlayer = player.FargoSouls();
                    AccessoryEffectPlayer effectPlayer = player.AccessoryEffects();
                    if (modPlayer.GalacticMinionsDeactivated && !effectPlayer.DeactivatedEffects[effect.Index])
                    {
                        effectPlayer.DeactivatedEffects[effect.Index] = true;
                        modPlayer.DeactivatedMinionEffectCount++;
                        return false;
                    }
                }
                */
                if (player.FargoSouls().MutantPresence)
                    if (toggle.PresenceAffected || toggle.IsMinionEffect)
                        return false;
            }
            return toggle.ToggleBool;
        }

        public static bool GetPlayerBoolValue(this Player player, AccessoryEffect effect)
        {
            Toggle toggle = player.GetToggle(effect);
            return toggle?.ToggleBool ?? false;
        }

        public static void SetToggleValue<T>(this Player player, bool value) where T : AccessoryEffect => player.SetToggleValue(ModContent.GetInstance<T>(), value);

        public static void SetToggleValue(this Player player, AccessoryEffect effect, bool value)
        {
            Toggle toggle = player.GetToggle(effect);
            if (toggle != null)
                toggle.ToggleBool = value;
            else if (effect != null)
            {
                try
                {
                    FargowiltasSouls.Instance.Logger.Warn($"Expected toggle not found: {effect.FullName}");
                }
                catch
                {
                    // A malformed foreign effect cannot break runtime lookup.
                }
            }
        }

    }
}
