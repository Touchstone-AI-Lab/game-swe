# Repair Spirit Mod branching quest replication

The frozen Spirit Mod 1.5.0.48 source contains related failures in quest
debouncing, branch selection, task-state framing, and multiplayer authority.
Repair the existing production code; do not replace it with a parallel quest
implementation.

Work in these files:

- `Mechanics/QuestSystem/Quest.cs`
- `Mechanics/QuestSystem/QuestMultiplayer.cs`
- `Mechanics/QuestSystem/Tasks/QuestTask.cs`
- `Mechanics/QuestSystem/Tasks/BranchingTask.cs`

Keep existing public types and method signatures. Keep the submission
source-only; do not add binaries, archives, build output, or dependencies.

## Required behavior

### Debounce and select branches deterministically

A task advances only after three consecutive positive completion checks. For a
branch, all three checks must identify the same complete path of child slots;
changing an inner or outer slot restarts the count at one. A false check resets
the counter and candidate, and advancing resets both before the next task.

A `BranchingTask` snapshots its constructor array, rejects null children and
more than 255 children, evaluates them in stable order, chooses the first
completed child, remembers its byte slot, and follows that child's successor.
Reset clears both the chosen slot and successor and resets every child. A
normal branch deactivation deactivates every active child even when debounce
has a pending candidate. Branch children may themselves be `BranchingTask`s.
Resolving such a child continues until a non-branch terminal task, rejects
cycles and incomplete or overlong paths, and never accepts slot 255 as a path
segment.

### Preserve local and remote transition semantics

In multiplayer-client mode, local completion sends one progress frame before
mutating quest state. It contains message type, server-bound flag, localized
quest name, the signed 32-bit ID of the current wrapper task, a byte path
length, that many branch-slot bytes, and player ID. A non-branch task has a
zero-length path. Completion applied while `QuestManager.Quiet` is set never
echoes a frame. Nested completion marks every wrapper and the terminal leaf
complete, deactivates the selected top-level child (which owns its nested
subtree), and activates the terminal leaf's successor.

Remote completion must validate the advertised task ID against the current
task and validate the complete branch path before any mutation. A path ending
at another branch, continuing after a terminal task, containing an invalid or
sentinel slot, or applied to a non-branch current task is a no-op on both
server and client. Valid remote completion performs the same wrapper/leaf
commit and follows the terminal leaf's successor.

### Frame task and snapshot state without corruption

Task data buffers contain the current signed 32-bit task ID, an unsigned
16-bit payload length, and exactly that many payload bytes. Do not assume a
16-byte buffer. Reject payloads larger than 65535 before writing. Malformed
headers, unknown task IDs, length mismatches, trailing bytes, incomplete task
consumption, and task `ReadData` failures must not replace the current task or
leave partial state in the target task. Reading the already-current task
updates its payload without replaying lifecycle hooks. After a successful read
of a different task, deactivate the previous task, then switch and activate
the new task. The whole load is a transaction: if either lifecycle hook fails,
restore the current-task selection, quest flags and countdowns, debounce path,
and every registered task's serialized payload, completion bit, and successor.

`BranchingTask` payloads are versioned and self-framing: version byte `1`,
child-count byte, selected-slot byte, then for every child its signed 32-bit
task ID, completed boolean, unsigned 16-bit payload length, and exact payload.
The fixed topology, order, IDs, and selected slot must validate before child
state changes. Wrong versions/topology, truncation, trailing data, incomplete
child reads, or a child exception leave every child payload/completed bit and
the prior branch choice unchanged. Successful reads restore the selected
child's successor.

Quest snapshots pack both signed 16-bit countdowns and the four existing
boolean flags without sign extension or carry between fields. The optional
task payload uses its existing one-byte length consistently: zero and 255 are
valid, while a payload larger than 255 must be rejected before any partial
frame is written.

### Make the server authoritative and exception-safe

Every handled packet must consume exactly its documented payload; trailing as
well as truncated frames are rejected before mutation or relay. For
server-bound progress, parse and validate the quest name, advertised current
task ID, declared path length and complete path, current-task branch semantics,
and claimed player range before mutation or relay. Apply exactly once under a
scoped `QuestManager.Quiet`,
restore its previous value even if quest code throws, and relay only after a
successful apply. The canonical relay is client-bound, retains the validated
quest, task ID, path length, and complete path, omits the player byte, and
excludes the claimed sender.

Apply the same server-authority ordering to server-bound Activate, Deactivate,
Unlock, and SyncNPCQueue messages. Read their entire payload (quest name or
16-bit NPC ID, followed by the claimed player byte) before changing state;
reject a claimed player outside `Main.maxPlayers`. A missing quest or a
transition already in its target state is a no-op: Activate requires an
inactive quest, Deactivate an active quest, and Unlock a locked quest. An NPC
queue removal requires an existing, nonempty queue for that ID. Apply a valid
transition locally before allocating/sending its one canonical client-bound
relay, excluding the claimed player; the relay retains the original message
type and quest name or NPC ID, but omits the player byte. Rejected, duplicate,
trailing, or malformed messages must neither change state nor emit a relay.
Quest-hook exceptions may propagate; in that case the prior `Quiet` value and
all tracked quest/task state must be restored and nothing relayed. This applies
even when a hook throws after mutating the active, unlocked, completed, timer,
payload, completion, or successor state. A queue removal consumes exactly one entry;
missing or empty queues are harmless no-ops on both server and client paths.
Client-bound messages must never echo a relay.

Apply the same apply-before-relay rule to server-bound `ObtainQuestBook`: read
the claimed player, require it to be in range and the book still locked,
unlock once, then send a canonical client-bound header-only relay excluding
that player. Duplicate, malformed, trailing, invalid-player, or throwing book
requests do not relay, and a post-mutation exception restores the prior book
lock. Client book relays are silent and idempotent. A
client-bound `SyncOnNPCLoot` contains exactly one NPC index byte and calls the
loot hook only when that index exists; invalid or trailing frames are no-ops.
Server-bound loot frames and unknown message types are no-ops.

The activate, deactivate, complete, and unlock helpers must all preserve the
prior quiet value and restore it on exceptions. Preserve existing public and
internal method signatures except for private helpers or overloads needed to
carry the task identity and branch path.

## Public check

Run `python3 tools/smoke.py` to compile the four production files in the
offline .NET 8 source projection. It contains no behavioral assertions.
Private evaluation uses separate engine doubles and directly executes the
production quest/update/buffer/packet paths. The full profile also compiles
submitted production sources into a verifier mod and runs task-specific
sentinels inside pinned tModLoader `2026.7.3.0` on a Terraria `1.4.4.9`
dedicated server.
