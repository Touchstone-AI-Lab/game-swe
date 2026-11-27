# Maintainer notes

- Frozen upstream: Starlight River 0.2.9.4 at
  `d367416dcadfe68a541a5821a0c4be86b42db219`.
- License: GPL-3.0 for code; frozen `LICENSE.txt` is retained.
- The evaluator compiles and invokes the seven real production files. Stubs
  expose engine types, fixed built-in abilities, item factories, TagCompound,
  delivery context, and packet recording only.
- The .NET 8 projection replaces two later-language expressions in both
  starter and oracle with behaviorally equivalent backing-field/null-check
  syntax. The exact compatibility delta is retained separately.
- Validation patch paths are repository-independent (`upstream` to `starter`
  for the compatibility delta, and Harbor-relative for the oracle).
- Upstream history includes dedicated ability-sync, fresh-character, stamina,
  and infusion-fix commits cited in the provenance receipt.
- Public smoke is compile-only; private cases run in isolated processes.
- Revision 3 treats lifecycle and tick hooks as untrusted reentrant callbacks.
  It adds exception-safe activation rollback and retirement, one-transition
  deferral, death-time request suppression, and deterministic ownership-checked
  fixed/draw snapshots. Its oracle passes 84/84 and the frozen starter 14/84.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` executes submitted ability packets with real
  server net mode and real `Main.player` state.
- Sentinels reject invalid players and spoofed start/progress senders.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3. VFX, draw
  hooks, hotkeys, and local activation remain source-projection assertions.
