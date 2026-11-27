# Terraria task 01 design: Magic Storage compressed I/O

Status: revision 3 local controls accepted.

## Candidate and provenance

| Field | Value |
| --- | --- |
| Upstream | `blushiemagic/MagicStorage` |
| Repository | `https://github.com/blushiemagic/MagicStorage` |
| Frozen revision | `08c76b8911c999908ea8f08b1aa217e8e7e604cd` |
| Upstream release state | Magic Storage `0.7.1` version-bump revision |
| License | MIT, copyright Kaylee Minsuh Kim |
| Game/API family | Terraria `1.4.4.9`; tModLoader `1.4.4` stable API |
| Historical stable build used for context | tModLoader `2025.11.3.1` |
| Proposed task ID | `terraria-magic-storage-compressed-io-regressions-hard` |

The task freezes a real Magic Storage source tree. The affected files are
ordinary production files included by `MagicStorage.csproj`; they implement the
bit-packed persistence and multiplayer item formats used by the mod. The task
will not add a parallel implementation for the solver to repair.

The private verifier will compile the affected production files directly in a
.NET 8 source projection with minimal Terraria/tModLoader type doubles. Those
doubles supply engine-owned types only; all framing, bit arithmetic, string
compression, and item metadata behavior under test remains the upstream Magic
Storage implementation. This boundary is source-level and does not claim a
full tModLoader or dedicated-server run.

## Operator reports and contract map

The proposed prompt describes symptoms rather than naming faulty methods. Every
scored behavior maps to a visible code path:

| Group | Observable report | Production files to inspect | Prompt-visible requirement | Planned assertions | Expected repair shape |
| --- | --- | --- | --- | --- | --- |
| nested-scope-accounting | Saving a list whose item contains nested or empty payload sections truncates later metadata or moves it outside the item frame. | `Common/IO/ValueWriter.cs`, `Common/IO/ValueReader.cs`, `Common/IO/LengthCompressor.cs` | Nested non-empty and empty frames must round-trip, remain inside their parent, and leave the writer ready for following fields. | empty inner frame followed by parent data; non-empty bit-count frame; byte-count frame; two nested siblings; sentinel after parent | Restore the enclosing active scope on every successful close and include the nested frame flag, encoded length, and payload in the parent bit count. |
| unsigned-64 | Full-width `ulong` and double bit patterns become zero or consume the wrong following bits. | `Common/IO/BitBuffer128.cs`, `Common/IO/ValueReader.cs`, `Common/IO/ValueWriter.cs` | Aligned and misaligned 64-bit values must round-trip exactly without consuming a following sentinel. | `0`, `ulong.MaxValue`, high-bit patterns, double bit patterns, one-to-seven-bit prefixes, trailing sentinels | Handle the 64-bit mask/shift boundary explicitly when removing bits from the 128-bit buffer. |
| misaligned-64-write | A 64-bit payload written after a non-byte-aligned prefix loses its high bits. | `Common/IO/BitBuffer128.cs`, `Common/IO/ValueWriter.cs` | Full-width payloads must survive every bit alignment supported by the writer. | prefixes of one through seven bits with high and low bits set; adjacent payloads | Split a full-width write across the two 64-bit words when the write head is non-zero instead of truncating the overflow. |
| signed-full-width | Negative 32-bit values collapse to `-1`, and negative 64-bit values are sign-extended from the wrong position. | `Common/IO/ValueReader.cs`, `Common/IO/BitBuffer128.cs` | Full-width and partial-width signed integers must preserve their exact two's-complement value. | `int.MinValue`, representative negative ints, `long.MinValue`, negative longs above 32 bits, partial 12/31/40/63-bit values, positive guards | Sign-extend only when the encoded width is narrower than the destination width, using a mask of the destination type. |
| long-strings | Compressed ASCII and Unicode keys longer than 2,048 characters fail or return a truncated/padded value. | `Common/IO/StringCompressor.cs`, `Common/IO/LengthCompressor.cs` | Every representable string length through 65,535 UTF-16 code units must round-trip exactly and preserve the following value. | boundary lengths 2,047/2,048/2,049; large ASCII; large Unicode; 65,535; trailing sentinels | Allocate/read the declared character count while retaining bounded stack allocation only for genuinely small strings. |
| oversized-string-atomicity | A key longer than the 16-bit format can wrap its length and poison all subsequent fields. | `Common/IO/StringCompressor.cs`, `Common/IO/ValueWriter.cs` | Values above 65,535 code units must throw before changing writer state; a caller may catch the error and write a valid value next. | 65,536 and 70,000 code units; caught rejection followed by a valid string and sentinel | Validate the length before emitting the ASCII flag, tier prefix, or payload. |
| network-stack-restore | A received item keeps the default stack even though the decoder records the transmitted normal, full, or overfull stack. | `Common/IO/NetCompression.NetIO.cs` and its real `SendItem`/`ReceiveItem` path | Standalone and list item round trips must restore stack, prefix, favorite state, and following items; overflow stacks remain supported. | partial stack; exact max stack; multiple full stacks plus remainder; mixed list; `readStack=false` preservation guard | Assign the checked decoded stack to both the item and diagnostic metadata. Reject invalid/overflowing quotient arithmetic through the existing isolated failure path. |
| seven-bit-validation | A malformed fifth 7-bit payload group silently aliases a valid signed 32-bit length. | `Common/IO/ValueReader.cs`, `Common/IO/ValueWriter.cs` | Preserve canonical positive and negative five-group values; reject a fifth payload above `0x0F` or a continuation beyond five groups without consuming the following field. | `int.MaxValue`, `int.MinValue`, `-1`; two high fifth-group patterns; fifth continuation with following sentinel | Decode four ordinary groups and validate the fifth group's payload and continuation bit explicitly. |
| item-handler-isolation | A declared ModItem payload is not consumed when the receiving item has no ModItem instance, so later GlobalItem metadata is reinterpreted. | `Common/IO/ValueReader.cs`, `Common/IO/NetCompression.NetIO.cs` | Always consume a declared ModItem child frame before reporting a missing receiver, preserve callback-failure isolation, attempt every later GlobalItem frame, and leave the outer stream aligned. | missing ModItem with sentinel; missing ModItem followed by GlobalItem; throwing ModItem; one throwing GlobalItem followed by another | Read the complete framed bytes before checking for a receiver, then use the existing per-item aggregation path without weakening the established GlobalItem loop. |
| send-transaction-atomicity | A throwing ModItem or GlobalItem send hook leaves metadata, list headers, or earlier entries in the destination, so a caught exception poisons later sends. | `Common/IO/ValueWriter.cs`, `Common/IO/NetCompression.NetIO.cs` | Each SendItem/SendItems call publishes all of its existing wire-format bits or none; exceptions propagate, hooks run once, and BinaryWriter/ValueWriter destinations remain reusable. | long metadata reaching the backing stream; ModItem and GlobalItem failures; misaligned prefixes; enclosing scopes; middle-list failures; successful byte compatibility; exactly-once hooks | Stage the complete logical call away from the destination, preserve its exact bit count, and append it only after every nested frame and untrusted callback succeeds. |
| scope-lifecycle-ordering | Disposing an outer scope while a child is active emits it into the wrong writer and corrupts the active-scope chain. | `Common/IO/ValueWriter.cs` | Reject out-of-order closes before state or output changes, then permit normal inner-to-outer recovery; retain double-close behavior. | non-empty child; empty byte-count child; three-level wrong-order attempts; double-close guard | Validate the active scope identity before marking or publishing a scope, without changing successful frame encoding. |

## Why this is one coherent task

All groups belong to the same compressed I/O subsystem and interact in real
call paths. `SaveCompression` and `NetCompression` compose nested scopes, fixed
width values, compressed strings, and item metadata. A local repair to only one
layer can make a simple unit case pass while still corrupting a following field
or a containing item frame.

The task is not a collection of unrelated algorithms. It asks the solver to
recover the invariants of one binary format across its buffer, framing, scalar,
string, and item-consumer layers.

## Difficulty and fairness review

The design is expected to be hard because:

- the 64-bit failure has separate read and misaligned-write causes;
- nested framing contains both state restoration and exact accounting defects;
- item list isolation composes an outer item scope with inner metadata and
  mod/global-data scopes;
- valid boundary behavior must be preserved while malformed stack arithmetic
  fails through an existing recovery path; and
- 7-bit signed compatibility must be preserved while rejecting only the three
  fifth-group bits that cannot fit an `int`; and
- item failure recovery must consume nested payload frames in the right order
  even when a receiver is missing or a callback throws; and
- sender-side rollback must preserve an exact bit stream across untrusted hook
  failures without adding a compatibility-breaking wrapper frame; and
- one transaction primitive must compose with both root writers and nested,
  non-byte-aligned scopes while invoking third-party hooks only once; and
- scope lifecycle validation must reject wrong-order ownership without making
  either handle unrecoverable; and
- a plausible patch spans five production files but must keep the established
  wire format for all already-representable values.

The task remains fair because the prompt will state every affected observable
boundary, the full production files are visible, and no assertion depends on a
private helper name or a reference diff. Tests will call public production APIs
where available and will inspect only returned values, thrown exception type,
stream position through following sentinels, and item state.

This is comparable in shape to accepted hard repository-debugging tasks: it has
multiple independently repairable reports, cross-file interactions, negative
controls, and preservation cases. It is narrower than a nine-feature gameplay
release batch, but its bit-level composition and compatibility constraints make
blind local patches risky. Empirical hardness remains unclaimed.

## Implementation and validation gates

Before this task can be marked complete:

1. import the exact frozen source without `.git`, binaries, build output, or
   unrelated generated assets;
2. create a source projection that compiles the real affected files and only
   stubs engine-owned dependencies;
3. implement private cases listed above and a case-to-prompt table;
4. build a minimal oracle that edits only production Magic Storage files;
5. demonstrate broken-base failures, a complete oracle pass, an empty/no-op
   failure, and at least one target-only predicate per group;
6. verify that every oracle edit is exercised and every test is justified by
   the English prompt;
7. verify task structure, provenance, license retention, source-only packaging,
   and uniqueness against existing tasks; and
8. finish this task's audit and commit before selecting task 02.

Revision 2 added two grounded receive-side groups. Revision 3 adds sender
transactionality and scope lifecycle ordering based on the same production
framing path. Its 68-case oracle passes locally while 13/14 new cases reject the
frozen starter.
