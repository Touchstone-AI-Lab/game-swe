# Source provenance

- Upstream repository: `https://github.com/blushiemagic/MagicStorage`
- Frozen revision: `08c76b8911c999908ea8f08b1aa217e8e7e604cd`
- Mod version at the frozen revision: `0.7.1`
- License: MIT; the upstream `LICENSE` file is retained in the candidate tree.
- Game/API family: Terraria `1.4.4.9`, tModLoader `1.4.4` stable API.
- Evaluation toolchain: .NET SDK `8.0.419`, pinned to base-image digest
  `sha256:dd09bcce84d9130e7f3e85c83a8ce9709e1d95e45c48c722a0d7923b38d8024c`.

The retained files were exported from the named Git revision without `.git`,
generated build output, packages, or binaries. `MagicStorage.csproj` includes C#
source by the SDK default glob, so each affected `Common/IO/*.cs` file belongs to
the upstream production build. The source projection compiles the production
compression files directly and supplies doubles only for types owned by Terraria,
tModLoader, or unrelated Magic Storage services.

`upstream-git-blobs.txt` records every retained upstream file and its Git blob ID.
All 28 entries were compared byte-for-byte with the frozen revision after import.

The exhaustive verifier boundary remains an offline source projection. The full
profile additionally compiles these submitted production files into a real
`.tmod` and loads it in pinned tModLoader `2026.7.3.0`; only the three behaviors
listed in `engine-rubric.json` are claimed as real-engine assertions.

## Revision-2 difficulty review

The second revision retains the same frozen source and adds two coupled,
naturally occurring reader defects rather than hiding requirements or adding an
unrelated algorithm:

- `ValueReader.Read7BitEncodedInt` must preserve canonical signed five-group
  values while rejecting only bits that cannot fit the public `int` result.
- `ValueReader.ReadModData`, `ReadGlobalModData`, and
  `NetCompression.ReceiveItem` must cooperate so every declared child frame is
  consumed exactly once and later callbacks still run after an earlier handler
  is missing or throws.

Both requirements are visible in the English prompt and production framing
code. Upstream commit `334e23a3b43ac9ecfacb7f2884981da919eca0cc`
independently documents the real failure class: `ReceiveItem` previously skipped
GlobalItem data after a ModItem failure. The new checks extend that same
maintainer-facing invariant to the current framed format and malformed length
input. The expected patch remains local to `ValueReader.cs` plus the repairs
already required by revision 1.

## Revision-3 difficulty review

The third revision retains the same frozen source and extends the existing
writer/frame invariants at two public ownership boundaries:

- `NetCompression.SendItem` and `SendItems` currently publish metadata, list
  headers, and earlier entries before all third-party `ModItem.NetSend` and
  `GlobalItem.NetSend` hooks have succeeded. A hook exception therefore leaves
  a caught-and-reused `BinaryWriter` or `ValueWriter` with an abandoned partial
  transaction.
- `ValueWriter.CreateScope` returns independently owned `IDisposable` handles,
  but closing a non-active outer handle mutates its lifecycle and routes its
  frame through the still-active child instead of rejecting the ownership
  violation.

The prompt exposes publication atomicity, exact successful wire compatibility,
exactly-once hook execution, nested/misaligned destinations, list rollback, and
recoverable LIFO disposal. Tests observe only public output, exceptions,
callbacks, decoded values, and following sentinels. The oracle stages a logical
send with an exact bit count before appending it and checks scope identity before
changing lifecycle state; it does not add a second wire format.

Local revision-3 controls pass 68/68 for the oracle. The frozen starter rejects
13/14 added cases. Independent predicate controls pass all 10 sender-transaction
cases and all four lifecycle cases with only the earlier framing/stack
prerequisites applied.
