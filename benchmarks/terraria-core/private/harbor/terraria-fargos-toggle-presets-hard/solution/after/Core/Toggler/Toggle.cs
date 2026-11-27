using FargowiltasSouls.Core.AccessoryEffectSystem;
using Microsoft.Xna.Framework;
using System.Collections.Generic;
using Terraria.UI.Chat;

namespace FargowiltasSouls.Core.Toggler
{
    /// <summary>
    /// The toggle's header in the display. <para/>
    /// If the effect shouldn't have a toggle, set this to null.
    /// </summary>
    public class Toggle
    {
        public string Mod;
        public AccessoryEffect Effect;
        public string Identity { get; }
        public Header Header { get; }
        public bool DefaultValue { get; }
        public bool PresenceAffected { get; }
        public bool IsMinionEffect { get; }
        private readonly string registeredMod;

        public string Category => Header.SortCategory;
        public bool ToggleBool;

        public Toggle(AccessoryEffect effect, string mod)
            : this(
                effect,
                mod,
                effect?.FullName,
                effect?.ToggleHeader,
                effect?.DefaultToggle ?? false,
                effect?.MutantsPresenceAffects ?? false,
                effect?.MinionEffect ?? false)
        {
        }

        private Toggle(
            AccessoryEffect effect,
            string mod,
            string identity,
            Header header,
            bool defaultValue,
            bool presenceAffected,
            bool isMinionEffect)
        {
            Effect = effect;
            Mod = mod;
            registeredMod = mod;
            Identity = identity;
            Header = header;
            DefaultValue = defaultValue;
            PresenceAffected = presenceAffected;
            IsMinionEffect = isMinionEffect;
            ToggleBool = defaultValue;
        }

        internal Toggle Materialize(AccessoryEffect registeredEffect) =>
            new Toggle(
                registeredEffect,
                registeredMod,
                Identity,
                Header,
                DefaultValue,
                PresenceAffected,
                IsMinionEffect);

        public override string ToString() => $"Mod: {Mod}, Category: {Category}, Effect: {Effect.Name}, Toggled: {ToggleBool}";

        public string GetRawToggleName()
        {
            string baseText = Effect.ToggleDescription;
            List<TextSnippet> parsedText = ChatManager.ParseMessage(baseText, Color.White);
            string rawText = "";

            foreach (TextSnippet snippet in parsedText)
            {
                if (!snippet.Text.StartsWith("["))
                {
                    rawText += snippet.Text.Trim();
                }
            }

            return rawText;
        }
    }
}
