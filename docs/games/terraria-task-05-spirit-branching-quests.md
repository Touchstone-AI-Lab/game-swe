# Terraria task 05 design: Spirit Mod branching quest replication

## Candidate and provenance

- Upstream: `https://github.com/GabeHasWon/SpiritMod`
- Frozen revision: `7ef2993d6f465f44420b2028e8666748ab31fe43`
- Upstream version: Spirit Mod 1.5.0.48
- License: MIT
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: quests advance after stable completion checks, branching
  tasks select one successor, task state is serialized for joins, and the
  quest multiplayer handler relays authoritative progress to other clients.

Upstream commit `68ddb80854088e4350286f9d6db6b3d7bb5d0150` is titled
"tons of bugs, mostly mp quest thing" and changes `Quest.cs`,
`QuestMultiplayer.cs`, and `BranchingTask.cs` to carry a branching task slot
through client, server, and remote completion. `QuestTask.cs` is retained as
the production base class used by those paths.

## Operator reports to preserve in the task contract

1. Quest completion requires three consecutive positive task checks; a false
   check resets the debounce counter, and each transition resets it for the
   next task.
2. A branching task evaluates candidates in stable order, remembers the first
   completed branch as a byte slot, follows that branch's successor, and fully
   clears the choice during reset.
3. Local multiplayer completion sends one progress frame before mutation with
   quest identity, branch slot (or the non-branch sentinel), and player ID.
   Quiet/server-applied completion never echoes a client frame.
4. Remote branch completion validates the slot and current task before any
   mutation, completes/deactivates exactly the selected child, and activates
   its successor or completes the quest. Invalid or stale frames are no-ops.
5. Task save/join buffers preserve the current task ID and its complete
   variable-length payload rather than assuming 16 bytes. Malformed, unknown,
   and truncated buffers are rejected without replacing current state.
6. Quest snapshot flags round-trip all booleans and signed 16-bit countdowns
   without bit carry/sign extension. Optional task buffers use a one-byte
   length consistently, including zero and 255, and oversize buffers are
   rejected before an ambiguous frame is emitted.
7. Server packet handling validates quest, branch slot, and claimed player,
   applies the state once under a scoped `QuestManager.Quiet`, restores quiet
   state even when quest code throws, and only then relays the same canonical
   frame while excluding the claimed sender.

## Expected repair shape

The retained production files are:

- `Mechanics/QuestSystem/Quest.cs`
- `Mechanics/QuestSystem/QuestMultiplayer.cs`
- `Mechanics/QuestSystem/Tasks/QuestTask.cs`
- `Mechanics/QuestSystem/Tasks/BranchingTask.cs`

The expected repair coordinates debounce state, branch identity, transition
ordering, binary framing, and quiet network authority. It keeps existing types
and public method signatures.

## Evaluation boundary

The evaluator directly compiles the four production files in a .NET 8 source
projection. Test doubles provide only engine-owned tModLoader/Terraria types
and unretained Spirit interfaces such as `TaskBuilder` and `QuestManager`.
Private tests use concrete test quests/tasks to execute the real update,
completion, buffer, branching, flag, and packet-handler code. Public smoke
uses an independent stub copy and has no behavioral assertions.

## Difficulty and fairness review

This is hard because a branch slot must retain the same meaning through a lazy
task collection, local transition, serialized packet, server application,
remote relay, and join-state buffer. Debounce and `Quiet` are state machines
whose bugs appear only on later ticks or exceptions. Bit packing adds signed
boundary behavior without being an unrelated algorithm: it is the production
quest snapshot format.

The task remains fair. The prompt states every frame field, sentinel, timing,
validation, and rollback requirement. The visible projection types document
packet and task-builder contracts. No assertion depends on UI, random timing,
undisclosed quest names, or game assets.

## Design and implementation verdict

Accepted and locally audited. The 36 named contracts cover seven independent
behavior groups and match the executable case list one-for-one. The frozen
starter passes 14/36 cases while the oracle passes 36/36; both source
projections compile with zero warnings and zero errors. The feature has
explicit upstream multiplayer bug history, a coherent four-file lifecycle,
and a source-level evaluator that exercises the real state transitions.

## Contract correction (2026-09-22)

Three behavioral cases depended solely on verifier-only exception classes for
malformed task buffers; the public contract promised nonreplacement, not a
specific throw. The verifier now accepts a return or throw while checking
unchanged live state. A successful-switch case expected deactivation of the old
task, which is now stated explicitly in the public exam. A fresh strict attempt
is required.

## Revision 2 design brief: authoritative transition packets (2026-09-22)

This revision extends the same upstream multiplayer lifecycle rather than
adding unrelated algorithms. In the frozen production `QuestMultiplayer.HandlePacket`,
server-bound Activate, Deactivate, Unlock, and SyncNPCQueue messages allocate
and send client relays before verifying the claimed player and before applying
the local transition. Thus a missing quest, duplicate transition, invalid
player, exhausted queue, truncated frame, or throwing quest hook can produce
an unsupported relay or exception. `RemoveFromNPCQueue` also indexes and
dequeues unconditionally.

The intended patch stays in the retained production `QuestMultiplayer.cs`.
For these four message types, read the full payload first, require a claimed
player below `Main.maxPlayers`, and check whether the named quest has the
required prior state (active for deactivation, inactive for activation, locked
for unlock) or the NPC queue has an entry. Apply the existing quiet-scoped
helper before constructing the canonical client-bound relay, excluding the
claiming player. A rejected/no-op message creates no packet. An application
hook may throw; in that case `Quiet` must be restored and no relay sent. Queue
dequeue consumes exactly one element; missing or empty queues are harmless on
both server and client paths. Keep the existing wire fields, message type and
helper signatures. The handler has no authenticated sender parameter, so this
is range validation and state authority, not an anti-spoofing claim.

The expanded contract will be stated explicitly in the English exam and
checked in the offline source projection using the real handler, manager
callbacks, packet encoder, and queue state. It is a cohesive four-branch
version of the same server-apply/client-relay rule already required for
ProgressOrComplete, not a hidden parser challenge. It remains distinct from
the accepted L4D2 hard tasks (42 and 57 cases, live server), whose difficulty
is server lifecycle behavior; this task relies on quest state, packet framing,
failure atomicity, and client/server separation. Before calibration, verify
each new assertion against the prompt, oracle and starter controls, then run
one fresh strict attempt for this exact revision.

The frozen starter passed 16/50 and the oracle passed 50/50.

## Revision 3 design brief: task identity and transactional framing (2026-09-23)

The 50-case revision was still vulnerable to delayed progress frames: branch
slot 255 says only “non-branch”, so a duplicate completion for task A could
advance a later non-branch task B. Progress frames now retain the current
wrapper's signed task ID on the local, server, and canonical client paths, and
both receivers reject stale identities and non-exact frames before mutation.

The same identity issue existed during the three-tick debounce. A branch could
report child 0 once and child 1 twice and still advance after three positive
checks. Revision 3 requires one stable slot, makes constructor topology
immutable and representable, and makes local completion match the existing
remote rule: mark the wrapper and selected child, deactivate only that child,
then follow its successor. Ordinary quest deactivation still covers every
activated child, including while a choice is merely pending.

Join-state framing is now transactional rather than inferred. The outer task
buffer is `int32 task ID + uint16 payload length + payload`. A branch payload
has version, child count, selected slot, then ordered child ID, completed bit,
uint16 length, and payload. Reads validate topology and complete consumption,
stage all child frames, restore target data after exceptions, avoid lifecycle
replay for the current task, and switch different tasks only after a successful
read. This also makes the 255-byte quest snapshot cap independently auditable.

Finally, every retained packet branch rejects trailing frames. The existing
quest-book request now validates player/state and applies before a header-only
relay, while client NPC-loot sync validates its byte index before accessing
`Main.npc`. These are existing `HandlePacket` branches, not synthetic APIs.

The exact revision has 77 named cases in eleven groups. The oracle passes
77/77 and the frozen starter passes 16/77. A fresh strict calibration is
required before claiming the requested difficulty target.

## Revision 4 design brief: nested paths and state transactions (2026-09-24)

Revision 4 follows two remaining production failures rather than adding an
unrelated algorithm. `BranchingTask` is itself a `QuestTask`, its constructor
accepts arbitrary `QuestTask` children, and frozen `TaskBuilder.AddBranches`
wraps each supplied builder's `Start`; therefore a branch builder may legally
start with another branch. A single slot cannot identify that topology. The
wire format now carries `byte path length + path slots`, with length zero for
a non-branch task. Debounce compares the complete path, recursive resolution
must end at a non-branch leaf, and local/server/client transitions commit the
same wrapper chain and terminal successor. Incomplete, overlong, sentinel,
cyclic, truncated, or trailing paths reject before mutation or relay.

The second failure is exception atomicity. Revision 3 restored `Quiet` and
suppressed relay when a hook threw, but a hook could already have changed the
active/completed flags, current selection, task payload, completion bit, or
successor. Completion, cross-task buffer loads, and authoritative quest
transitions now snapshot every registered task plus quest-owned state and
restore it after a failure. Quest-book unlock similarly restores its global
lock when a post-mutation hook throws. This scope is observable production
state; it does not claim to reverse arbitrary external effects performed by a
third-party callback.

The exact revision has 97 named cases in sixteen groups. The oracle passes
97/97 and the frozen starter passes 16/97.
