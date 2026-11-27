# Stardew Valley core pack

This read-only pack contains eleven real-game SMAPI tasks contributed and
maintained by Jiaxuan Luo: nine repair tasks and two generation tasks. Each
repair task starts from a real mod source tree (Automate, Content Patcher, CJB Cheats
Menu or Tractor Mod) with real or documented engineered defects. Each generation task
(`stardew-summon-horse-anywhere`, `stardew-auto-workshop`) starts from an empty mod
skeleton and a behavioural requirement. A hidden suite judges every task in the
running game. Catalog 1.2.0 removed the two generation tasks and added three
composite repair tasks from Content Patcher, CJB Cheats Menu and Tractor Mod; catalog
1.3.0 restored the generation tasks unchanged. Catalog 1.4.0 retired three Automate
repair tasks that were saturated and no longer discriminated, and catalog 1.5.0 retired
`stardew-cp-i18n-case` for the same reason; their files stay here as history. Public task contracts live in
`exams/`; source snapshots, private assertions, reference solutions, study controls,
and the Harbor validation history live below `private/` and are never copied into
anonymous attempts.

The canonical task namespace is `stardew-valley/core/<task-id>`. The `core`
profile validates the submission layout but is always incomplete. The `full`
profile builds or uses a private Docker image containing an operator-owned
Stardew Valley 1.6.15 Linux installation, disables container networking, boots
SMAPI 4.1.10 headlessly, and requires every real-game assertion to finish.

See `docs/games/stardew-valley.md` for runtime setup and support status.
