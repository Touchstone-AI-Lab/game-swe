# Approved controlled-v2 transport implementation

The operator approved COMPONENT-CHANGE-REQUEST-v1 in the conversation. The exact
replacement is now packaged under `linux_transport_v1` and applied only while
constructing `balatro-linux-17459173-controlled-v2`. Original dependencies, the
probe/controlled-v1 artifacts, old halt, frozen tasks and historical records are
unchanged. No host setting, permission, component version or RPC deadline changed.

The builder first verifies the original input artifact and provider-acquired
game. It copies the complete tree to its own new cache and changes only
`mods/bot/src/lua/core/server.lua`. Both the original and derived whole-file hashes
must equal the approved proposal. It compares the two complete trees, including
executable bits, and rejects every other change. Read-only verify checks the
new immutable record, recipe, runtime specification and actual tree.

Self-authored interpreter resources use byte/closure identity in the new recipe,
so their filesystem executable flags do not make editable and wheel recipes
different. Actual runtime file modes remain verified. The v1 recipe is untouched.
The new operator binding, review records and operations use `linux-controlled-v2`
under the pack's state directory. The old halt is not removed or reinterpreted.

The unchanged fixed LÖVE library's exported LuaSocket implementation passed
bounded loopback checks: a small response, a 1 MiB response with 64 partial writes
and byte-identical delivery, and a nonreading peer causing a bounded failure at
about one second. No game was loaded for these transport checks. The earlier
eight double-based tests remain separate. Builder/state/process/smoke unit tests
also passed; these do not substitute for the engine controls.

## Preparation incident and provenance

The first controlled-v2 preparation downloaded the exact depot once and received
its full completion response, but the official client did not exit after its
shutdown IPC. Owned cleanup forced termination, exit 143. This attempt
`55055c09720f46158020446026f3621d` remains incomplete. The reason that the client
did not exit is not established; no timeout or normal-exit requirement was relaxed.

The same source already had a complete, normally exited acquisition:
`19ba5da56c0647f4819e5e47e15faef6`. Its original provider receipts and actual bytes
were reverified. A new explicit provider cache-reuse command recorded that
provenance, copied only declared game source files into the new provider cache,
and retained hashes of the failed request and terminal shutdown record. It issued
no command and launched no client. The default unresolved-request path still
rejects incomplete proof; reuse is a separate, explicit operator action.

The subsequent real core `runtime prepare` consumed this verified provider cache
and created the new artifact. Preparation took 10.718 seconds; read-only verify
and the new six-case smoke passed. No failed acquisition was promoted to success.
Receipts are under `.test-state/linux-runtime-v2`, separate from v1.

Real engine task validation follows this smoke. Its current outcomes must be read
from the versioned validation summary, not inferred from this implementation note.

## Owned visible-window profile

The first controlled-v2 deck attempt uncovered a separate animation timing
limitation. The fixed Bot's 1/60 simulation step coupled to a roughly 30 FPS
fullscreen software renderer delayed completion beyond the unchanged RPC bound.
[Read-only diagnosis and visible-window controls](RENDER-DIAGNOSIS-v1.md) preserve
those failures, including the unsuccessful 1280×720 pilot and one diagnostic
driver cleanup error.

The 800×600 visible-window diagnostic completed all three deck gold processes.
The adopted `linux_window_v2` control configures only fresh process video settings
through the original game callback. It preserves simulation timing and all
response/acceptance conditions. Its assets and actual dimensions are checked,
and its source is included in the new environment/harness identity. This is
self-authored initialization, not an additional Bot/game component patch.

Final execution uses `linux-controlled-v2-window-v2`, preserving both previous
halts. A fresh normal smoke passed in 37.516 seconds. Implementation was frozen
before the unified ten-pair managed batch. The separate pre-freeze deck pilot
was diagnostic gold only; the managed deck gold/base pair is included in that
same frozen batch rather than claimed as an earlier separate pilot. No earlier
partial pair is counted as final evidence, and this ordering does not reduce
the required 56 deck cases, three processes per control or final twenty controls.
