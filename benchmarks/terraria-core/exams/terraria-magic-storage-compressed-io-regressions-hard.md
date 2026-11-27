# Magic Storage compressed I/O regressions

You are working on the MIT-licensed Magic Storage `0.7.1` source tree at
`/workspace/magic-storage`. The snapshot is pinned to upstream revision
`08c76b8911c999908ea8f08b1aa217e8e7e604cd`.

Server operators and mod developers supplied the reports below after exercising
the new compressed save and multiplayer item formats. They are observations,
not diagnoses. Several reports share lower-level code, so a local fix for one
example may still corrupt another caller.

## Reports

### 1. Nested payload frames corrupt their parent

Saving a list of items can truncate later item metadata when an item contains a
nested payload frame. Empty mod/global payloads are especially disruptive: data
written after an empty child sometimes appears outside the parent item frame.
Non-empty child frames also make the parent's declared bit count smaller than
the bytes actually emitted.

Nested empty and non-empty frames must remain inside their parent. Closing any
child must leave the parent active, and the parent's declared length must cover
the child's empty flag, encoded length when present, payload, and later parent
fields. Bit-count and byte-count scopes must both work. Preserve the existing
reader's empty/non-empty flag convention and the established scalar and payload
encodings.

### 2. Full-width 64-bit payloads do not round-trip

Long values and double bit patterns written through `ValueWriter` can read back
as zero or consume bits belonging to the next field. This occurs even when the
payload is aligned. All 64 bits, including the high bit, must round-trip exactly,
and a following sentinel must remain readable.

### 3. Misaligned 64-bit writes lose their high bits

The same payload is corrupted when it follows a one-to-seven-bit prefix. Every
bit alignment supported by `ValueWriter` must preserve a full-width value and
the adjacent fields. Do not change the least-significant-bit-first format used
by existing values.

### 4. Signed full-width values collapse

Negative 32-bit values can return as `-1`, and negative 64-bit values are
sign-extended from the wrong position. Preserve exact two's-complement values
for full-width `int`/`long` payloads and for narrower signed fields. Positive
values and zero-width behavior must not regress.

### 5. Long compressed strings fail during load

ASCII and Unicode tag keys above roughly 2,048 UTF-16 code units are truncated
or fail while loading. Every length representable by the existing 16-bit string
format, through 65,535 code units, must round-trip exactly. The field following
the string must remain intact.

### 6. Oversized strings poison later fields

A string longer than 65,535 UTF-16 code units wraps the encoded length and emits
payload that the reader cannot frame. Reject such a value with
`ArgumentOutOfRangeException` before changing the writer state. A caller that
catches the exception must still be able to write and read a valid string and
following field with that writer.

### 7. Received item stacks stay at their defaults

`NetCompression.SendItem` transmits partial, exact-maximum, and deliberately
overfull stacks, but the corresponding item returned by `ReceiveItem` can keep
its default stack even though diagnostic metadata saw the transmitted value.
Standalone and list round trips must restore stack, prefix, favorite state, and
following items. `readStack=false` retains its existing meaning.

The overflow-stack quotient and remainder are untrusted network input. Reject a
non-positive quotient or checked arithmetic overflow through the existing
isolated failure-item path; do not let it wrap into an ordinary item or desync a
following list entry. Valid overfull stacks remain supported.

### 8. Malformed 7-bit integers alias valid lengths

The custom `ValueReader.Read7BitEncodedInt` accepts a fifth payload group whose
upper three bits do not fit in a signed 32-bit result. Those bits are silently
discarded, so malformed array lengths can alias ordinary values. Preserve the
existing little-endian 7-bit encoding, including the canonical five-group
representations of negative `int` values. Reject a continuation beyond the
fifth group or a fifth payload group above `0x0F` with `FormatException`. Do not
consume a field following the five encoded groups when rejecting them.

### 9. Missing ModItem receivers skip their declared child frame

A current-format item may carry a framed ModItem payload even when the receiving
side cannot materialize a `ModItem` instance. The current reader short-circuits
before consuming that child frame. Consume the complete frame, then report the
mismatch through the existing per-item failure path; do not reinterpret its
length or bytes as GlobalItem metadata.

Preserve the surrounding isolation behavior: whether a ModItem instance is
missing or its callback throws, continue decoding every declared GlobalItem
frame in order. Likewise, one throwing GlobalItem callback must not prevent
later GlobalItem frames from being consumed and attempted. Aggregate the
item-local failure through the existing failure-item behavior, preserve the
decoded item metadata, and leave the following item or field aligned.

### 10. Failed send hooks publish partial item transactions

A `ModItem.NetSend` or `GlobalItem.NetSend` hook can write part of its payload
and then throw. The exception reaches the caller, but item metadata, list
headers, or earlier entries may already have reached the destination. Catching
the exception and sending another item with the same writer then produces a
stream that starts with an abandoned partial transaction.

Treat each `SendItem` and `SendItems` call as one publication transaction. If
any serialization step or send hook throws, propagate that exception without
publishing any bits from that call to the supplied `BinaryWriter` or
`ValueWriter`. The same writer must remain usable after the caller catches the
exception. This applies when the destination already has a non-byte-aligned
prefix, when the call is inside an enclosing scope, and when a later entry in a
list fails after earlier entries were serialized.

Successful calls must retain the established wire format; do not add a new
outer frame. Invoke each successful or failing send hook only once per call.
The rollback requirement covers failures while encoding the item/list and
running its hooks; it does not redefine what happens if the destination stream
itself rejects a write after publication begins.

### 11. Out-of-order scope closes corrupt the scope stack

Code that manually owns nested scope handles can accidentally dispose an outer
scope while a child is still active. The outer frame is currently emitted into
the wrong writer and the active-scope chain becomes unusable.

Scopes must close in reverse creation order. An out-of-order close must throw
`InvalidOperationException` before publishing or changing either scope's
lifecycle state. The caller must then be able to close the active child and
retry the parent successfully, including for empty byte-count children and
three-level nesting. Preserve the existing `ObjectDisposedException` behavior
for closing the same successfully closed scope twice.

## Task

Diagnose and repair all reports in the existing Magic Storage production files.
Preserve the established format for values that were already representable,
the current public method signatures, legacy version dispatch, and per-item
failure isolation. Avoid unrelated changes.

Do not replace the compression system with a second implementation or add a
special path for the verifier. Keep the submission source-only: do not add
binaries, archives, symbolic links, Git metadata, credentials, or build output.
Do not modify anything under `/tests`.

Run the public source-projection build after editing:

```bash
python3 tools/smoke.py
```

The public check compiles the affected production files against minimal
engine-owned type doubles. It contains no behavioral assertions. The private
offline verifier compiles those same submitted production files with its own
type doubles, then checks externally observable values, exceptions, frame
boundaries, following sentinels, and item state. It does not compare your patch
with a reference diff or require private helper names. The full profile also
compiles submitted production sources into a verifier mod and runs
task-specific sentinels inside pinned tModLoader `2026.7.3.0` on a Terraria
`1.4.4.9` dedicated server.
