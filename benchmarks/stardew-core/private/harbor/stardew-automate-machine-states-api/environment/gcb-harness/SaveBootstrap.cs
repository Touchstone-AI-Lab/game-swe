using System;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Menus;

namespace GcbHarness
{
    /// <summary>Title-screen bypass and process exit. Both paths follow the
    /// production-proven patterns from the MIT-licensed JunimoServer dedicated-server
    /// mod (GameLoaderService / GameCreatorService), not invented ones.</summary>
    internal static class SaveBootstrap
    {
        /// <summary>Load the fixture save directly from the title screen.
        /// <c>GCB_SAVE_NAME</c> is the save folder name under <c>Constants.SavesPath</c>
        /// (e.g. <c>GCB_368157236</c>).</summary>
        public static void LoadFixtureSave(IModHelper helper, IMonitor monitor)
        {
            string saveName = Environment.GetEnvironmentVariable("GCB_SAVE_NAME")
                              ?? throw new InvalidOperationException("GCB_SAVE_NAME not set");

            monitor.Log($"GCB: loading fixture save '{saveName}'", LogLevel.Info);
            Game1.multiplayerMode = 0; // single-player; the suite is the only actor
            SaveGame.Load(saveName);
            if (Game1.activeClickableMenu is IClickableMenu menu)
                menu.exitThisMenu(playSound: false);
        }

        /// <summary>Create the deterministic fixture world (gen-save mode, image build
        /// time only). Fixed name/seed so every image build yields the same farm.</summary>
        public static void StartNewDeterministicWorld(IModHelper helper, IMonitor monitor)
        {
            monitor.Log("GCB: creating deterministic fixture world", LogLevel.Info);

            Game1.player.Name = "GCB";
            Game1.player.favoriteThing.Value = "determinism";
            Game1.player.farmName.Value = "GCB";
            Game1.player.isCustomized.Value = true;
            Game1.whichFarm = 0;          // standard farm layout
            Game1.startingCabins = 0;
            Game1.startingGameSeed = 368157236; // fixed world seed -> stable item RNG streams
            // Level-1 farmhouse (kitchen) so indoor-only placements like mini-fridges
            // are legal in the fixture; persists into the save via the farmer field.
            Game1.player.houseUpgradeLevel.Value = 1;

            Game1.game1.loadForNewGame(loadedGame: false);
            Game1.NewDay(0f);
            Game1.exitActiveMenu();
            Game1.setGameMode(Game1.playingGameMode);
        }

        /// <summary>Quit the process. The JSON verdict is written before this is called;
        /// exit codes deliberately gate nothing in the verifier, so the vanilla quit path
        /// (which can exit non-zero) is fine, with a hard exit as backstop.</summary>
        public static void ExitGame()
        {
            try
            {
                Game1.quit = true;
            }
            finally
            {
                // Backstop for hangs in the vanilla shutdown path: give it a moment via
                // the game loop, then force. Environment.Exit skips SMAPI cleanup, which
                // is acceptable in a disposable verifier container.
                new System.Threading.Timer(_ => Environment.Exit(0), null, 15000, System.Threading.Timeout.Infinite);
            }
        }
    }
}
