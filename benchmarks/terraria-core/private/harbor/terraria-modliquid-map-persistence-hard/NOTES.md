# Maintainer notes

- Frozen upstream: ModLiquid Library 2025.12.0.0 at
  `282498893150b53d2e52efe26be0813aa8c8e193`.
- License: MIT; frozen `LICENSE.md` is retained.
- The evaluator compiles and invokes the real `ModLoader/MapEntry.cs`,
  `ModLoader/MapLiquidLoader.cs`, `IO/MapLiquidIO.cs`,
  `Hooks/MapLoaderHooks.cs`, `Hooks/MapHelperHooks.cs`, and
  `Hooks/WorldMapHooks.cs`. Independent stubs expose map storage, content
  registries, byte I/O, and MonoMod IL APIs only.
- Upstream commit `59ac922fd286e9348345c489ae8670ca97a3a5f8`
  introduced this complete `.tlmap` production path.
- Public smoke is compile-only; private cases run in isolated processes.
- The strengthened contract also validates canonical header order and
  discriminator bytes, zero-entry framing, malformed string normalization,
  missing type tables, and all RLE width-flag combinations.
- Revision 2 adds coherent save snapshots, atomic writer preparation, strict
  registry identity, destination-generation guards, commit rollback, and
  fail-closed save/load IL anchors. Its oracle passes 74/74 and starter 33/74.
- Revision 3 follows the same real map path into custom-liquid registry
  publication and teardown, transactional runtime option callbacks,
  registry-generation-bound sidecar operations, and fail-closed preflight for
  the six additional production IL anchors. Its oracle passes 103/103 and the
  starter passes 38/103 in local isolated-process controls.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` compiles the submitted loader and sidecar
  production files against the real `MapLoader`, `WorldMap`, and dedicated
  server lifecycle.
- Sentinels cover dedicated-server teardown, atomic registry collision
  handling, and transactional malformed-map decoding.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3. Client map
  rendering and MonoMod IL-anchor execution remain source-projection checks.
