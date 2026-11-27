# Maintainer notes

- Frozen upstream: Calamity Overhaul 0.9209 at
  `91d8ea961644a48d20d051ace9a948dbf9f8298c`.
- License: MIT; the frozen `LICENSE.txt` is retained.
- The evaluator compiles and invokes the two real production replication
  files. Stubs expose Terraria entity arrays, loader counts, ModSystem hooks,
  logging, time-freeze generation, and the four existing snapshot providers.
- The starter C# files are byte-for-byte upstream; there is no compatibility
  delta.
- The exhaustive layer is a source projection; the full profile additionally
  loads selected submitted production files in a pinned real tModLoader server.
  It does not claim rendering or real socket coverage.
- Public smoke is compile-only; private cases run in isolated processes.
- Revision 3 adds one coherent frame-stable pending transaction across both
  entity kinds and world/authority-stable snapshot callback boundaries. These
  are production-path state-machine requirements, not independent trivia.
- The frozen starter passes 35/78 cases and the oracle passes 78/78.
- Both source projections compile with zero warnings and zero errors.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` executes submitted time-control production
  code with real projectile ownership and dedicated-server net mode.
- Sentinels cover owner wire bounds, canonical rejected identities, and
  omission of failed late-join snapshots.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3. Client snapshot
  application remains a source-projection assertion.
