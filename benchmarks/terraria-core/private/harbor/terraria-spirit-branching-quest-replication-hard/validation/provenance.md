# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/GabeHasWon/SpiritMod`
- Commit: `7ef2993d6f465f44420b2028e8666748ab31fe43`
- Mod version: Spirit Mod 1.5.0.48
- License: MIT, Copyright (c) GabeHasWon and contributors
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The retained starter production files preserve the recorded upstream content
with the benchmark repository's required LF normalization; there is no
behavioral starter delta. Original upstream Git blob IDs are recorded
separately. The upstream license is retained. No assets, Git data, binaries,
caches, or build output are packaged.

## Real production path

`Quest.Update` debounces actual completion checks and `RunCompletion` performs
the live task transition. `BranchingTask` selects the successor and carries
the branch slot. `Quest.GetTaskDataBuffer` and `ReadFromDataBuffer` serve
save/join state. `QuestMultiplayer.HandlePacket` is the real client/server
authority and relay path. Private tests compile and execute these methods; the
projection doubles only expose external APIs and record effects.

## Historical grounding

Upstream commit `68ddb80854088e4350286f9d6db6b3d7bb5d0150`, titled "tons of
bugs, mostly mp quest thing", changes the retained `Quest.cs`,
`QuestMultiplayer.cs`, and `BranchingTask.cs` paths and adds the branch slot to
client/server quest completion. `QuestTask.cs` is retained as the production
base class used by those paths. The benchmark follows that same real state
identity through debounce, save buffers, snapshots, remote validation, quiet
application, and canonical relay.

## Fairness and uniqueness

All 97 assertions map to explicit prompt clauses in `case-contracts.tsv`.
The prompt specifies the sentinel, frame order, counter threshold, signed
field widths, payload bound, validation order, and quiet restoration. No
assertion depends on an undisclosed quest, UI rendering, timing, or assets.
The task is distinct from the earlier Terraria tasks because it couples a
branching state machine with two binary formats and bidirectional authority.

## Revision history

The 50-case authoritative-transition revision passed 50/50 oracle and 16/50
frozen-starter local controls.

Revision 3 follows a single identity-and-framing failure chain in the same
production paths. Three positive branch checks must agree on one slot; local
and remote completion now commit the same selected child; task buffers and
nested branch payloads carry explicit lengths and roll back failed reads; and
progress frames carry the current wrapper task ID so delayed packets cannot
advance a later task. Exact packet consumption is applied consistently, and
the previously uncovered quest-book and NPC-loot message branches receive the
same authority and bounds discipline. The oracle passes 77/77 and the frozen
starter passes 16/77.

Revision 4 is grounded in the retained task graph rather than a synthetic
extension. `BranchingTask` derives from `QuestTask`, and frozen
`TaskBuilder.AddBranches` wraps each child builder's `Start`, so a child start
may itself be a branch. The former one-byte slot loses the inner choice and
also lets debounce reuse an outer slot while the inner leaf changes. The new
length-prefixed path is carried through the existing progress message and is
resolved without mutation before either endpoint applies it.

The retained manager and task hooks can throw after mutating state. Restoring
only `QuestManager.Quiet` prevented a relay but did not restore the server's
quest graph. The new transaction snapshots quest flags/countdowns/debounce,
current task, and each registered task's serialized payload, completion bit,
and successor. The contract deliberately limits rollback to owned observable
state and does not promise reversal of arbitrary external callback effects.

Revision 4 controls are oracle 97/97 and frozen starter 16/97.
