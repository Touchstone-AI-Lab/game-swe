using Microsoft.Xna.Framework;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using Terraria;
using Terraria.ModLoader;
using Terraria.ModLoader.IO;

namespace Aequus.Common.Carpentry {
    [LegacyName("CarpenterBountyPlayer")]
    public partial class CarpentryPlayer : ModPlayer {
        public bool CanClaimFreeShutterstockerGift { get; internal set; }
        private int _selectedBounty = -1;
        private string _selectedBountyName;
        public int SelectedBounty {
            get {
                if (_selectedBountyName != null) {
                    _selectedBounty = BuildChallengeRegistrySnapshot.TryCapture(out var registry) &&
                        registry.ByName.TryGetValue(_selectedBountyName, out int id) ? id : -1;
                }
                return _selectedBounty;
            }
            set {
                _selectedBounty = value;
                _selectedBountyName = BuildChallengeRegistrySnapshot.TryCapture(out var registry) && value >= 0 && value < registry.Count
                    ? registry.Names[value]
                    : null;
            }
        }

        public BuildChallengeSaveData CollectedBounties = new("CollectedBounties");

        public override void Initialize() {
            CollectedBounties.Clear();
            CanClaimFreeShutterstockerGift = false;
            SelectedBounty = -1;
        }

        public override void SaveData(TagCompound tag) {
            tag["FreeCamera"] = CanClaimFreeShutterstockerGift;
            if (!string.IsNullOrEmpty(_selectedBountyName)) {
                tag["SelectedBounty"] = _selectedBountyName;
            }
            CollectedBounties.SaveData(tag);
        }

        public override void LoadData(TagCompound tag) {
            BuildChallengeRegistrySnapshot registry;
            try {
                registry = BuildChallengeRegistrySnapshot.Capture();
            }
            catch (InvalidOperationException ex) {
                throw new System.IO.InvalidDataException("The player challenge registry is invalid.", ex);
            }

            bool canClaimGift = tag.Get("FreeCamera", defaultValue: false);
            string selectedName = tag.TryGet("SelectedBounty", out string savedName) && !string.IsNullOrEmpty(savedName)
                ? savedName
                : null;
            List<string> collected = CollectedBounties.ReadSaveData(tag);
            if (!registry.IsCurrent()) {
                throw new System.IO.InvalidDataException("The player challenge registry changed while loading data.");
            }

            CanClaimFreeShutterstockerGift = canClaimGift;
            _selectedBountyName = selectedName;
            _selectedBounty = selectedName != null && registry.ByName.TryGetValue(selectedName, out int selectedId)
                ? selectedId
                : -1;
            CollectedBounties.Replace(collected);
        }

        public override ModPlayer Clone(Player newEntity) {
            var clone = (CarpentryPlayer)base.Clone(newEntity);
            clone.CollectedBounties = new BuildChallengeSaveData(CollectedBounties.SaveKey);
            clone.CollectedBounties.Clone(CollectedBounties);
            clone._selectedBounty = _selectedBounty;
            clone._selectedBountyName = _selectedBountyName;
            return clone;
        }

        public override void CopyClientState(ModPlayer clientClone) {
            var clone = (CarpentryPlayer)clientClone;
            clone.CollectedBounties = new BuildChallengeSaveData(CollectedBounties.SaveKey);
            clone.CollectedBounties.Clone(CollectedBounties);
            clone._selectedBounty = _selectedBounty;
            clone._selectedBountyName = _selectedBountyName;
        }

        public override void SendClientChanges(ModPlayer clientPlayer) {
        }

        public override void PostUpdate() {
            if (Main.myPlayer != Player.whoAmI || Main.GameUpdateCount % 10 != 0 ||
                NPC.AnyDanger(quickBossNPCCheck: true, ignorePillarsAndMoonlordCountdown: true)) {
                return;
            }
            CheckBuffBuildings();
        }

        public void CheckBuffBuildings() {
#if DEBUG
            var stopwatch = new Stopwatch();
            stopwatch.Start();
#endif
            if (!BuildChallengeRegistrySnapshot.TryCapture(out var registry)) {
                return;
            }
            SortedDictionary<int, List<Rectangle>> buildings = CarpentrySystem.BuildingBuffs.SnapshotActive(registry);
            if (!registry.IsCurrent()) {
                return;
            }

            int range = Player.Aequus().buildingBuffRange;
            if (range <= 0) {
                return;
            }
            long centerX = (int)Player.Center.X / 16L;
            long centerY = (int)Player.Center.Y / 16L;
            long left = centerX - range;
            long top = centerY - range;
            long right = centerX + range;
            long bottom = centerY + range;

            foreach (var pair in buildings) {
                int buffId = registry.BuffTypes[pair.Key];
                if (buffId <= 0) {
                    continue;
                }
                foreach (Rectangle rectangle in pair.Value) {
                    if ((long)rectangle.X < right && left < (long)rectangle.X + rectangle.Width &&
                        (long)rectangle.Y < bottom && top < (long)rectangle.Y + rectangle.Height) {
                        Player.AddBuff(buffId, 60);
                        break;
                    }
                }
            }
#if DEBUG
            stopwatch.Stop();
#endif
        }

        public bool HasUnclaimedBounty() {
            return CarpentrySystem.CompletedBounties.ContainsAny(name => !CollectedBounties.ContainsChallenge(name));
        }
    }
}
