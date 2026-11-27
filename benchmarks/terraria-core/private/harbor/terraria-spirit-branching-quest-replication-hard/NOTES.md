# Maintainer notes

- Frozen upstream: Spirit Mod 1.5.0.48 at
  `7ef2993d6f465f44420b2028e8666748ab31fe43`.
- License: MIT; frozen `LICENSE.txt` is retained in the workspace.
- The evaluator compiles and invokes the four retained production files.
  Separate projection stubs expose only engine and unretained-mod contracts.
- Upstream commit `68ddb80854088e4350286f9d6db6b3d7bb5d0150`, titled
  "tons of bugs, mostly mp quest thing", changes the retained quest,
  multiplayer, and branching-task paths. `QuestTask.cs` is the retained
  production base class used by those paths.
- Public smoke is compile-only. Private cases run in isolated processes.
- Revision 3 adds stable branch identity debounce, selected-child local
  transitions, versioned transactional child snapshots, length-framed task
  state, replay-resistant progress task IDs, exact packet consumption, and
  authoritative quest-book/NPC-loot handling.
- Revision 4 replaces the single progress slot with a fully validated nested
  branch path and makes completion, task-buffer switching, quest transitions,
  and quest-book unlock transactional across post-mutation hook failures.
- Revision 4 local controls: oracle 97/97 and frozen starter 16/97.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` loads the submitted branching quest production
  source in a real dedicated-server mod.
- Sentinels cover constructor snapshots, null-child rejection, and binary
  branch-frame round trips.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3. HUD rendering
  and client quest application remain source-projection assertions.
