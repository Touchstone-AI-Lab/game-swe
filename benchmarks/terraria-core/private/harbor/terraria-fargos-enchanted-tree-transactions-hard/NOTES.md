# Maintainer notes

- Frozen upstream: Fargo's Mutant Mod 3.4 at
  `85246bb5e4d3b225028b1bf73cd6d99b81674307`.
- License: MIT; the frozen `LICENSE` is retained in the submission tree.
- Evaluation compiles the three affected production files directly. The
  projection stubs model engine-owned APIs and are not part of the repair.
- Upstream commits `97f0e061e46f5f5277f0ece3ba2118e4f107d77a`
  and `85246bb5e4d3b225028b1bf73cd6d99b81674307` document prior fixes in
  this exact feature and motivated the transaction/lifecycle contract.
- Upstream commit `f45bd3f8601391d6785e6d05b549d5d9221ab9b1` introduced the
  coin-backed duplication transaction, while `97f0e061e46f5f5277f0ece3ba2118e4f107d77a`
  also fixed prefix propagation for duplicated fruit. Revision 2 therefore
  exercises the existing branch and purchase state machine instead of adding a
  benchmark-only behavior.
- The public smoke build has no behavioral assertions. Private tests use a
  separate stub copy and per-case process isolation.
- Revision 4 has 78 cases in 15 groups and adds only production-path
  invariants: replacement recipe snapshots, canonical sender/receiver forest
  validation, deletion-time index compaction, ancestry-specific branch
  collapse, and once-per-frame registry processing.
- Revision 4 local controls: oracle 78/78 and starter 30/78.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` runs the real recipe lifecycle and production
  `MiscRecipeSystem` against Terraria `1.4.4.9`.
- Sentinels verify stale graph removal, ingredient deduplication, and
  `NotDupableFromDupable` policy on a real registered recipe.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3. Tree drawing,
  sound, dragging, and local purchase UI remain source-projection assertions.
