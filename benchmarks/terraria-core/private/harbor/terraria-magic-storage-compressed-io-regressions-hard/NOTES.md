# Maintainer notes: Magic Storage compressed I/O

This task compiles the real upstream `BitBuffer128`, `ValueReader`,
`ValueWriter`, `LengthCompressor`, `StringCompressor`, and
`NetCompression.NetIO` production files. The retained callers show how the
subsystem participates in Magic Storage persistence and multiplayer paths.

The source projection replaces only engine-owned Terraria/tModLoader types and
unrelated mod services. It does not provide alternate framing, bit arithmetic,
string compression, or item metadata implementations. Private tests use a
separate copy of the doubles, so changing the public projection cannot satisfy
behavioral cases.

The frozen revision predates the later upstream debugging rework marked as not
building. It is the `0.7.1` version-bump revision and preserves the MIT license.

Revision 2 adds two defects already present in that frozen production code. The
custom 7-bit integer reader does not validate the high bits of its fifth group,
and `ReadModData` short-circuits before consuming a declared payload when the
receiver lacks a `ModItem`. The latter is part of the same real handler-ordering
failure family documented by upstream commit `334e23a`, which fixed skipped
GlobalItem data after a ModItem failure. The added cases exercise the existing
reader and item codec; no benchmark-only production seam was added.

Revision 3 follows the sender side of the same framed item codec. The frozen
code publishes metadata and list entries before untrusted `NetSend` hooks have
all succeeded, so a propagated hook exception can leave a caller-owned writer
permanently desynchronized. It also lets an outer scope close while a child is
active, publishing the frame through the wrong scope. The new contract requires
whole-call publication atomicity without changing successful bytes or invoking
hooks twice, plus recoverable LIFO scope ownership. Both behaviors are exposed
through existing production APIs; no benchmark-only production seam was added.

For revision 3, the 68-case oracle passes locally and the frozen starter fails
13 of the 14 added cases. The two new predicate controls pass 10/10 and 4/4
cases respectively when combined only with their declared earlier framing/stack
prerequisites.

## Real-engine control

- Pinned tModLoader `2026.7.3.0` loaded the submitted production codecs in a
  real dedicated-server mod against Terraria `1.4.4.9`.
- The engine sentinels cover nested binary frames, full-width long-string
  scalars, and real vanilla `Item` metadata.
- Exact controls on 2026-09-24: frozen starter 0/3; oracle 3/3.
