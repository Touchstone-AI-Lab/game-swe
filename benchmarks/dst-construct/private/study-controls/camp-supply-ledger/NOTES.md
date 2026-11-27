# dst/core/camp-supply-ledger — E0 notes

Task version 2.0.1. Construction from an empty starter.

## Roles

- 17 cases: 14 `target` (6 hidden, 4 server, 4 regular-expression source gates), 3 `static`
  (`check:required-files`, `check:lua-syntax`, `check:implementation-depth`).
- No `preserved` case. The starter is an empty workspace; it never loads as a mod, the starter
  execution is incomplete and observes no server case. Nothing holds before the change, so there is
  **no compat-negative** and the task can enter general completion only.
- The four `check:supply-*` gates are regular expressions over the submitted source. They are kept
  as `target` but the DST-integration clauses that only they touch are `weak`.

## Controls

| control | kind | what it is | result |
| --- | --- | --- | --- |
| `target-negative-rollback-keeps-quota` | target-negative | reference + 5-line patch: `Ledger:rollback` still marks the token `rolled_back` but no longer releases the reserved quota (core-5b) | 95, fails only `hidden:rollback releases quota exactly once` ("rollback did not restore quota"); admissible |
| `alternative-a` | alternative | full mod written from the public exam, see below | 100, every case passes; admissible |
| `alternative-strict-reading` | alternative | `alternative-a` with `OnSave`/`OnLoad` as plain `Class` methods, exactly as the exam prescribes | 90, **rejected** by `server:component state survives save and load`; shows problems by design |

### alternative-a vs the reference

- Core: the reference is a metatable class with per-day/per-player/per-prefab `reserved`/`committed`
  counters. The alternative returns a table of closures over private state and keeps a single
  append-only reservation journal; quota use is derived by summing journal entries that are not
  rolled back, so there are no counters to reset on `begin_day` or to restore on `load`. Requests are
  indexed `player -> request` instead of a concatenated key. Save format, token format
  (`csl:0000000001`) and snapshot layout differ from the reference.
- Component: the reference spawns and gives stack by stack and measures the inventory delta. The
  alternative stages every stack of the bundle first (a spawn failure never touches the player),
  then hands stacks over while checking the return value, the real grand owner and the running
  inventory count, and on failure removes stray entities before consuming merged surplus. Listeners
  go through one registry that is unwound with the same function objects; it additionally
  deactivates a player on `ms_playerleft`.
- It was written from the exam text, not tuned to the suite, with one exception that is called out
  below (receiver-less `OnSave`). Bundle tables are accepted both as `{ prefab = count }` maps (the
  exam's literal) and as `{ { prefab =, count = } }` lists ("each bundle lists ...").

### The strict-reading variant (decides admission)

`diff -r alternative-strict-reading alternative-a` touches only
`scripts/components/campsupplyledger.lua`: a module-level `attached` instance that `OnSave`/`OnLoad`
fall back to when called without a receiver. The strict tree has the exam's
`function Component:OnSave()` and nothing else.

Result on the real dedicated server: `server:component state survives save and load` fails with
`scripts/components/campsupplyledger.lua:200: attempt to index local 'self' (a nil value)`, caused by
`benchmarks/dst/server/camp-supply-ledger.lua:28` (`component.OnSave()`, dot call). All other 16
cases pass. The engine itself always calls `OnSave` with a receiver, and the exam
(`Base-game API contract` ¶4) prescribes the method form, so this is a valid implementation rejected by an
over-constraining assertion. The assertion was not changed.

## Recommendations

- Task: the private suite rejects a valid implementation on one of 4 server cases. Either exclude
  the task from admission until the task owner fixes line 28 (a benchmark-authoring change), or
  admit it with `server:component state survives save and load` excluded from the target set. It
  must not be used as-is to score "general completion" without that caveat.
- Excluded (unasserted) clauses: background-1, core-1a, 2c, 3b, 6b, 7a, dst-5, dst-7b,
  api-1. Reasons are in each clause's `note`. Notably the failure/rollback delivery path
  (dst-5, api-1) has no evidence although Acceptance bullet 5 says the server suite asserts it.
- Fixture trap (documented, not a control): the hidden fixture configures bundles as lists of
  `{ prefab, count }` while the exam's only literal is the map form. A map-only core fails 5/6 hidden
  cases. This was checked locally with `python -m rhenium_dst.lua_runner` on a temporary variant of
  `alternative-a`, not as an engine run.

## Not run

- Only the Linux x86_64 managed container runtime (real dedicated server) was used.
- The map-only bundle variant above was exercised against the hidden layer only.

## Catalog 2.1.0 update

The sections above describe catalog 2.0.1 (study snapshot 5929c99). The server suite now calls `component:OnSave()` with a receiver and the exam publishes the bundle shapes, result fields and status strings the suites read. The former `alternative-strict-reading` (plain class-method OnSave/OnLoad) is therefore a valid implementation: it is kept as `alternative-b` and passes at 100 on the real server. Re-run on 2026-09-22: reference 100, alternative-a 100, alternative-b 100, target-negative-rollback-keeps-quota fails `rollback releases quota exactly once` only.
