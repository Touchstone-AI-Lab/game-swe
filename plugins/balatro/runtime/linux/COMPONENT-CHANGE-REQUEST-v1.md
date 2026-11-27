# Decision requested: versioned Linux transport repair

Status: **proposal only; not applied to any component or real game**.

The operator authorized fixed acquisition and Linux validation, but explicitly
requires approval before changing fixed BalatroBot/loader/game components. This
request is for a narrowly derived Bot transport copy, not another general login
or host-permission approval. Original `.deps`, pins, game, loaders, operator data,
old artifacts, task semantics and historical evidence will remain unchanged.

## Confirmed evidence

Managed preparation, read-only verification and current-source smoke passed.
Four tasks completed both full gold/base outcomes through `rhenium run`:
growth, reversible hand limit, seeded effect stream and bounded generator.

The next gold, deck-removal-consistency-v2, stopped with
`ProtocolError: Invalid JSON response`. Its single process exited normally with
unchanged inputs; this is **incomplete**, not candidate rejection. The frozen raw
runner uses the broad label `test_gap`; the platform reports environment failure.
The retained operation is `3b8a5fb356624612be39faf8dc92c318` and its halt is intact.

A new independent full-lifecycle diagnosis
`rpc-diagnosis-v1/20261031-055126-743e0a67` reproduced truncation. HTTP status was
200 and Content-Length was **154,032**, but `read` returned **109,458** bytes,
leaving **44,574** missing. JSON failed at byte/character position 109,454 near
the cut. The fixed server again logged `Failed to send response: timeout`.
The process exited normally. No action was resent. The observer recorded only
lengths, counters, hashes and exception metadata; it called original read/parser
functions once, forwarded return values/exceptions and changed no response bytes.
Ten observer/process unit tests passed.

Pinned Bot commit `9052d76f14723293f6c6b2cecaa791a5c4ae68f3`:

- `core/server.lua:160,444` sets the accepted socket non-blocking.
- `core/server.lua:246-257` calls `send` once and discards the partial-write index.
- `send_response`, beginning at line 385, closes the connection after `send_raw`
  regardless of completion. A partial write therefore loses the remaining body.
- Original file SHA-256:
  `668c10439162949e10dbf3f67d85a8d349d32cc0a58a32bb5dbf1e8bde47e928`.

This is a reproduced property of the fixed version on this host. It is not a
claim about an upstream historical bug report or every platform. A larger client
timeout cannot retrieve bytes discarded when the sender closes the connection.

## Reviewable change

[Proposed function](transport-change-v1/send_raw.lua),
[diff](transport-change-v1/send-raw-partial-write.patch) and
[byte manifest](transport-change-v1/proposal.json) are prepared. Only `send_raw`
would change in a **new runtime-owned derived copy**. It continues from the
reported absolute partial-write index, waits for that socket's write readiness,
and returns success only after every original byte was sent. Closed sockets,
invalid indices or an expired **one-second write budget** return failure.
The original HTTP/JSON encoding, request IDs, non-blocking read mode, endpoint
callbacks, game state and 25-second RPC deadline remain unchanged. This handles
partial writes; it does not resend a request or accept truncated JSON.

- Replacement SHA-256:
  `816874dedcd933d44a8854451215f27458294df8f8cf1db3562386f4aa4d5250`.
- Proposed derived file SHA-256, preserving original CRLF:
  `e58590bf9507887be409b083ffe40a5f2ad14671a169f28faddf4cf2113b0e2f`.
- Eight LuaJIT unit cases passed: complete write, partial progress, zero progress,
  closed connection, exhausted budget, readiness timeout, invalid partial index
  and invalid success index. These use doubles and are **not engine evidence**.
- Bot is MIT licensed; the original notice is retained in
  [LICENSE-BalatroBot](transport-change-v1/LICENSE-BalatroBot).

The current controlled-v1 artifact will not be rewritten or relabeled. Approval
would authorize a separate controlled-v2 artifact/manifest binding the original
Bot identity, this explicit patch and the derived byte identity. Old pins and
the existing halt stay intact. A fresh operator binding/state will carry new
smoke and validation evidence. No host setting, network exposure, container
permission, dependency upgrade, task change, commit or push is proposed.

## Validation after approval

1. Verify patch applicability and byte closure; exercise complete/partial/error
   writes with the fixed LuaSocket library in bounded loopback tests.
2. Prepare the new managed artifact using verified licensed source and unchanged
   dependency inputs. Run its visible current-source smoke.
3. Run deck-removal gold/base through the full managed entry, retaining all 56
   cases and all three processes per control. Record complete transport framing.
4. Freeze that implementation, rerun all ten full gold/base pairs and the three
   independent six-case initialized-load probes. Retain any failure separately.
5. Run relevant regressions and applicable repository checks; audit protected
   directories, old pins and artifacts; publish version-specific replay and
   sanitized results. No claim of final-code validation will reuse the current
   four pairs as if they had run against the proposed component.

Until approval, real task scoring is halted. No truncation tolerance, relaxed
assertion, buffer-size workaround or implicit component repair will be used.
