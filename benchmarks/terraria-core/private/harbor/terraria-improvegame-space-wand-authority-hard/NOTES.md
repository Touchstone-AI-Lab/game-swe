# Maintainer notes

- Frozen upstream: Quality of Terraria 1.8.3 at
  `284fa78849f2234e70300f101a92a36db34b256d`.
- License: MIT; the frozen `LICENSE` is retained in the workspace.
- The evaluator directly compiles the three production files. Engine and
  unretained-partial definitions in the two independent stub copies provide
  interfaces/state recording only, not replacement feature behavior.
- Upstream commit `0e52de3b0554f9bbc5120e64f83a4aa7338b158c`
  documents a real multiplayer Space Wand tile-sync repair.
- Public smoke compilation has no behavioral assertions. Private cases use
  per-case process isolation.
- Revision 5 local controls are complete at starter 33/82 and oracle 82/82.
  Public starter and oracle smoke builds both complete with zero warnings and
  zero errors.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` executes submitted selection code against the
  real `WorldGen.InWorld` and Terraria world dimensions.
- Sentinels cover out-of-world starts, square clipping, and corner termination.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3. Mouse input,
  preview text, sounds, and client packet emission remain source-projection
  assertions.
