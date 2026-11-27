# Maintainer notes

- Frozen upstream: Terraria Overhaul 5.0.0.38 at
  `55c23fbde42f6fcb9eb266992475a040d14c2b84`.
- License: GPL-3.0; the frozen `LICENSE.md` is retained in the submission.
- The evaluator compiles the five retained production files directly. The two
  copies of projection stubs model engine-owned APIs and are shared harness
  infrastructure, not a replacement entity/chunk implementation.
- Upstream commits `98915aa96d1ff8b4fb0f41bd1332b36fa8c88d52`,
  `1bf023a1b3b5f8ab8f97a9d4f6acfb7bd0c68141`, and the frozen revision
  document changes to this exact lifecycle.
- Public smoke compilation has no behavioral assertions. Private cases use a
  separate stub copy and per-case process isolation.
- Revision 2 extends the same production path with the public component
  operation contract and the frozen `IterateVisibleChunks` bottom-edge typo;
  the latter used `screenPosition.X` where the vertical `Y` origin is required.
- Revision 2 is intentionally left uncalibrated until all ten Terraria tasks
  finish design and implementation, per the authoring plan.
- Revision 5 adds normal load-order component capacity, deterministic ambiguous
  name handling, active query snapshots, single-pass world coordinate
  conversion, transactional creation callbacks, stale mapping repair, and
  stable all-chunk enumeration. The public prompt states each new ordering and
  failure contract explicitly; the revised local controls are oracle 78/78 and
  frozen starter 25/78.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` loads the submitted production entity/chunk
  sources in a real dedicated-server mod against Terraria `1.4.4.9`.
- Sentinels verify active-query snapshots, the world-coordinate entrypoint,
  and transactional creation observers.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3.
