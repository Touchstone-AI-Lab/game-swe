# loot-roll-arbiter — authoring notes

## Design rationale

The task is a need/greed/pass loot roll whose outcome must be reproducible by anybody. That gives the core a
property the other DST tasks do not have: two independent implementations must agree bit for bit, so the
exam publishes the complete generator (Park–Miller MINSTD, multiplier 48271, modulus 2^31−1, seed
normalisation `seed % 2147483646 + 1`, `roll = state % 100 + 1`), the draw order (ascending player id inside
a tier), the re-roll rule (only the tied leaders, continuing state, at most `max_rounds` rounds), one single
ranking rule (lexicographic comparison of per-round roll sequences, then ascending id) that defines both the
winner and every "next-best" candidate, and the fairness boundary (`t − win_time < fairness_window`,
`t = min(now, deadline)`). `state * 48271 < 2^53`, so plain `*` and `%` are exact in Lua 5.1 doubles and in
the sandbox Lua; the exam says so. Three worked examples (seed 1, seed 313 with `max_rounds` 3 and 1, seed
2147483652 ≡ 6) let a solver self-check; none of them is a seed the suites use.

Tricky parts on purpose: side-effect-free rejection (a rejected revision is not recorded, a rejected `open`
does not burn the id), the deadline boundary (`now < deadline` accepts, `now >= deadline` resolves), lazy
greed contest with the *continuing* generator state after the need tier is exhausted (which is why the
generator state must survive save/load), exactly-one-step re-award, demotion evaluated at
`min(now, deadline)` so a late `resolve`/`tick` gives the result of the deadline instant, ledger pruning that
must not change observable results, and clock rebasing in `Arbiter.load` (`options.now`), which is the real
DST problem that `GetTime()` restarts with the process.

On the engine side the component turns one award into one real item: `SpawnPrefab` + `inventory:GiveItem`,
ownership verified with `GetGrandOwner()` (or the item having been merged into a stack), undelivered items
removed, failures reported to the core one at a time. The server suite proves this with real `inventory`
components and the real `goldnugget` prefab, including the two classic traps: a stack merge (the given entity
disappears) and an inventory without free slots (`GiveItem` returns false and drops the item on the ground).

## Evidence that exam.md is self-sufficient

`alternative/` was written by a separate clean-room agent that was allowed to read only a copy of `exam.md`
(`altspace/EXAM.md`); it never saw the suites, the reference, the catalog or the benchmark repository. It
was given structural constraints only (closure objects instead of metatables, one record per player,
on-demand candidate selection instead of a stored ranking, flat ledger, its own roll id scheme
`lr-<generation>-<serial>`). Its first submission passed all 6 hidden cases on both Lua versions and all
4 server cases; the only failed check was my own integration regex, which had hard-coded the literal form
`AddModRPCHandler("rhenium_lootroll", "choose"` while the alternative passes the namespace through a local
constant. The regex was loosened (the real registration is asserted by the server suite anyway). The
alternative was not edited by me at any point, also not after the suites were strengthened later
(pendingtasks accounting, private host entity, `ms_playerleft`). The agent's list of ambiguities was folded
back into exam.md: free layout of the `save` table, `winner`/`tier` of a canceled roll, test-input promises
(monotonic `now`, integer seeds, boolean `ok`, distinct ids/items), free announcement text, ignored RPC return
value, and the master-sim guard snippet.

Expected numbers were produced with the throwaway Python model `tools/gen.py` (generator + contest +
ranking) and then confirmed by the reference and by the alternative under the sandbox Lua and under Lua 5.1
(`tools/hidden.sh`), and by the real server (Lua 5.1) in the server cases.

## What each control shows (see controls.tsv for the observed numbers)

| control | broken obligation | score | failed (observed) |
| --- | --- | --- | --- |
| reference | — | 100.0 (complete=true) | nothing, passed |
| alternative | — | 100.0 (complete=true) | nothing, passed |
| nop | empty starter (README only) | 0.0 (complete=false) | everything; no modmain.lua, so the server suite cannot be injected and the run is incomplete |
| choice-accepted-at-deadline | `now >= deadline` closes | 90.0 (complete=true) | hidden 2, 6 |
| deadline-task-leaks | cancel the deadline task on settlement | 70.0 (complete=true) | server 1, 2, 4 |
| delivery-trusts-giveitem | owner verification + removal of undelivered item | 90.0 (complete=true) | server 3 |
| duplicate-revision-accepted | strictly increasing revision | 70.0 (complete=true) | hidden 2, 6, server 2, 4 |
| eligible-not-deduplicated | deduplicated frozen set | 85.0 (complete=true) | hidden 1, server 2 |
| failure-skips-reaward | re-award to next-best | 80.0 (complete=true) | hidden 4, 6, server 3 |
| fairness-boundary-inclusive | `<` boundary | 90.0 (complete=true) | hidden 5, 6 |
| fairness-evaluated-at-call-time | `t = min(now, deadline)` | 95.0 (complete=true) | hidden 5 |
| item-whitelist-ignored | `allowed_items` | 85.0 (complete=true) | hidden 1, server 1 |
| load-ignores-clock-rebase | `options.now` rebasing | 95.0 (complete=true) | hidden 6 |
| net-state-leaks-player | aggregate-only net state | 90.0 (complete=true) | server 2 |
| no-immediate-settlement | settle when the last player chooses | 80.0 (complete=true) | server 2, 4 |
| onload-drops-state | `OnLoad` restores state | 90.0 (complete=true) | server 4 |
| playerleft-keeps-cached-entity | forget the departed player's entity | 90.0 (complete=true) | server 3 |
| playerleft-shrinks-eligible | frozen set does not shrink | 90.0 (complete=true) | server 3 |
| ranking-by-last-roll | lexicographic ranking | 85.0 (complete=true) | hidden 3, 4, 6 |
| removal-leaks-tasks | `OnRemoveFromEntity` cancels tasks | 90.0 (complete=true) | server 4 |
| reroll-includes-everyone | only tied leaders re-roll | 85.0 (complete=true) | hidden 3, 4, 6 |
| resolve-draws-again | idempotent resolve | 85.0 (complete=true) | hidden 4, 5, 6 |
| second-resolve-redelivers | item created at most once | 70.0 (complete=true) | server 2, 3, 4 |
| seed-not-normalised | `state0 = seed % 2147483646 + 1` | 55.0 (complete=true) | hidden 2, 3, 4, 5, 6, server 2, 3 |
| snapshot-leaks-choices | snapshot privacy | 95.0 (complete=true) | hidden 6 |

Together the negatives fail every one of the 6 hidden cases and every one of the 4 server cases at least
once; every negative still loads and produces a complete run.

## Deliberate suite decisions

- All hidden scenarios feed a non-decreasing `now` per arbiter instance and the exam promises that, so an
  implementation that assumes monotonic time is not punished.
- Validation order is published; the suites mostly use single-fault inputs and sample the order with four
  multi-fault calls.
- The save table layout is never inspected; it is validated as plain data, deep-copied and loaded.
- Server player fixtures deliberately have no `player` tag: with the tag, `inventory_replica` creates a
  classified entity and `RemoveComponent("inventory")` crashes inside the base game
  (`inventory_replica.lua:45`), which has nothing to do with the task.
- `ms_playerleft` is never pushed on the live world (base-game listeners expect a real player). It is pushed
  on a private `CreateEntity()` host that carries its own instance of the component; the exam publishes that
  the component must not assume `inst == TheWorld` and must listen on `inst` itself.
- Timer hygiene is observed through `inst.pendingtasks`, the engine's own bookkeeping of unfinished entity
  tasks (`Cancel` removes the entry synchronously). The exam publishes the exact accounting the suite checks.
  This is an engine-internal field; it has had this shape for years, but it is the one place where the suite
  depends on something that is not a documented modding API (listener bookkeeping `inst.event_listeners` is
  the second, same remark).
- Item conservation is measured as the summed stack size of every live `goldnugget` entity in `Ents`, so a
  merged stack, a dropped item and a duplicate are all visible.

## Weak / unasserted

- `TheNet:Announce` is only a regex (`TheNet` is userdata; the call cannot be observed synchronously).
- That the deadline task actually *resolves* the roll when it fires cannot be observed by a synchronous
  suite; only its existence, uniqueness and cancellation are asserted.
- The client branch (`lootrolldirty` listener) cannot run on a dedicated server; only the creation of the
  net variable and the server-side value are asserted.
- The clock rebase in `OnLoad` (`options.now = GetTime()`) is covered by the hidden suite only; on the server
  `OnLoad` runs in the same process, so the shift is ~0.
- Core option defaults `window = 30`, `fairness_window = 600`, `allowed_items = {}` are published but not
  asserted (the suites pass them explicitly); `max_rounds = 3` and `max_wins_per_window = 2` are asserted.
- Of the ten whitelisted prefabs only `goldnugget` is exercised; `log` is the only rejected prefab.
- "The RPC handler must not be able to open rolls / accept seeds" is a code-review property; the suite only
  proves that the registered handler routes identity from `player.userid`.
- Closed rolls are kept forever (ids are final), so state grows without bound on a very long-lived save.
  This is inherent to the published contract and not addressed.

## Not run / limitations

- Everything listed in controls.tsv was run on the real dedicated server through `tools/eval.sh`
  (full profile, no network). Nothing was run against a real client, so replication to clients is unobserved.
- No repository checks (ruff/mypy/pytest) were run because nothing in the benchmark repository was modified;
  the scratch catalog was validated with `DstCatalog.load`.
- Helper scripts under `tools/` (`gen.py`, `hidden.sh`, `mkneg.py`, `mkclauses.py`, `controls.sh`) are
  authoring aids, not deliverables. `altspace/` is the clean-room workspace (exam copy + the agent's output,
  identical to `alternative/`). `runs/` holds raw evaluator output.
