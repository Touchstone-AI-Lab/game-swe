# Maintainer notes

- Frozen upstream: Fargo's Souls Mod 1.7.3.7 at
  `226fadeadbe3422785a7708ba2cdf53bd8548c00`.
- License: MIT; the frozen `LICENSE` file is retained.
- The evaluator compiles and invokes the four real production toggler files.
  Stubs expose Terraria player, preferences, localization, chat parsing, mod
  content lookup, and representative accessory-effect types only.
- The starter source is byte-for-byte upstream for the retained C# files;
  there is no compatibility delta.
- The oracle diff is regenerated from Harbor-relative paths and contains no
  workstation-specific separators or absolute paths.
- Upstream history includes the toggler reimplementation, ordering fixes,
  guarded lookup fix, custom-preset work, and default-toggle additions cited
  in the provenance receipt.
- Public smoke is compile-only; private cases run in isolated processes.
- Revision 2 snapshots virtual effect metadata at registration and gives live
  registry changes an atomic per-backend rebase transaction, including preset
  rebinding, canonical suppression policy, and generation-change rollback.
  Its oracle passes 82/82 and the frozen starter 25/82.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` loads the submitted toggle registry and uses
  real Terraria chat-tag parsing in a dedicated-server mod.
- Sentinels cover metadata snapshots, fresh registry loads, and duplicate
  identity rejection.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3. Preferences
  files and local-player preset application remain source-projection checks.
