# Maintainer notes

- Frozen upstream: Aequus 2.7.3.3 at
  `f823418776e7dd54b0f370e3ff1b4befc2bc857d`.
- License: MIT for code; the retained package contains code and license only.
- The evaluator compiles and invokes the four real carpentry production files.
  Stubs expose Terraria/tModLoader types, challenge registration, scans, and
  packet recording only.
- Upstream commit `d305013bd40786760760b3a51d56b6aab19c61e8` is titled
  "fix carpenter not completing challenges in mp" and touches this path.
- Public smoke is compile-only; private cases run in isolated processes so a
  malformed implementation cannot block the complete suite.
- The strengthened contract also covers canonical receive order,
  coordinate-overflow rectangles, stale persisted groups, and the real
  `CarpentryPlayer.CheckBuffBuildings`/`PostUpdate` gameplay path.
- Revision 3 keeps the same four production files but binds transient IDs to
  stable full names across registry reorder and content unload, enforces one
  canonical registry generation per transaction, adds a global 4,096-location
  frame budget, and makes scans/writer/buff callbacks reentrancy-safe. Its
  oracle passes 87/87 and the frozen starter 12/87.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` loads the submitted carpentry persistence and
  replication source in a real dedicated-server mod.
- Sentinels cover transactional receive failure, registry-ID serialization,
  and detached real `TagCompound` save state.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3. Local-player
  buff application remains a source-projection assertion.
