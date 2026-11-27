using FargowiltasSouls.Core.AccessoryEffectSystem;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace FargowiltasSouls.Core.Toggler
{
    public static class ToggleLoader
    {
        public static Dictionary<AccessoryEffect, Toggle> LoadedToggles
        {
            get;
            set;
        }
        public static HashSet<Header> LoadedHeaders
        {
            get;
            set;
        }
        public static ulong Generation { get; private set; }


        public static void Load()
        {
            LoadedToggles = [];
            LoadedHeaders = [];
            Generation++;
            //LoadTogglesFromAssembly(FargowiltasSouls.Instance.Code);
        }

        public static void Unload()
        {
            LoadedToggles = null;
            LoadedHeaders = null;
            Generation++;
        }


        public static void LoadTogglesFromAssembly(Assembly assembly)
        {
            // Toggles are now registered from the AccessoryEffect system. Headers are now registered from each derived class of the Header baseclass.

            #region Collection Loading (outdated)
            /*
            Type[] types = assembly.GetTypes();
            List<ToggleCollection> collections = new();

            for (int i = 0; i < types.Length; i++)
            {
                Type type = types[i];
                if (typeof(ToggleCollection).IsAssignableFrom(type) && !type.IsAbstract)
                {
                    ToggleCollection toggles = (ToggleCollection)Activator.CreateInstance(type);

                    if (toggles.Active)
                    {
                        collections.Add(toggles);
                    }

                }
            }

            var orderedCollections = collections.OrderBy((collection) => collection.Priority);
            FargowiltasSouls.Instance.Logger.Info($"ToggleCollections found: {orderedCollections.Count()}");

            foreach (ToggleCollection collection in orderedCollections)
            {
                List<Toggle> toggleCollectionChildren = collection.Load();

                foreach (Toggle toggle in toggleCollectionChildren)
                {
                    RegisterToggle(toggle);
                }
            }
            */
            #endregion
        }

        public static void RegisterToggle(Toggle toggle)
        {
            if (toggle?.Effect == null)
                throw new ArgumentNullException(nameof(toggle));
            if (toggle.Header == null)
                throw new ArgumentException("A registered toggle must have a header", nameof(toggle));
            if (string.IsNullOrEmpty(toggle.Identity))
                throw new ArgumentException("A registered toggle must have a stable full identity", nameof(toggle));

            LoadedToggles ??= [];
            if (LoadedToggles.ContainsKey(toggle.Effect) ||
                LoadedToggles.Values.Any(existing => string.Equals(existing.Identity, toggle.Identity, StringComparison.Ordinal)))
                throw new InvalidOperationException("Toggle of effect " + toggle.Identity + " is already registered");

            LoadedToggles.Add(toggle.Effect, toggle);
            Generation++;

        }
        public static void RegisterHeader(Header header)
        {
            if (header == null)
                throw new ArgumentNullException(nameof(header));

            LoadedHeaders ??= [];
            //if (LoadedHeaders.Contains(header)) throw new Exception("Header with internal name " + header.Name + " is already registered");

            LoadedHeaders.Add(header);
        }
    }
}
