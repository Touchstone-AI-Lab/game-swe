# dst/core/combat-target-arbiter — E0 notes

Construction task from an empty starter (task version 2.0.1). All controls were run
through `rhenium-study e0 run` in the managed container runtime (real dedicated
server, runtime `dst/dst-dedicated-24700372`); the hidden suite was also run
locally with `python -m rhenium_dst.lua_runner`.

## Preserved contracts

None. The starter is an empty workspace: every static, hidden and regex case is
`F` in `starter.execution.json` and the server cases are unobserved because an
empty tree does not load as a mod. No case can be `preserved`, so there is **no
compat-negative**; the task enters general completion only.

## Controls

| control | kind | result | admissible |
| --- | --- | --- | --- |
| `target-negative-taunt-boundary` | target-negative | 95, fails only `hidden:taunt overrides until exact expiry` | yes |
| `alternative-a` | alternative | 100, complete, passed | yes |
| `alternative-strict-reading` | alternative | 95, fails `hidden:ties use first seen then lexical id` ("first-seen tie break failed") | **no — rejected by the private suite** |

### target-negative-taunt-boundary (`reference` + patch)

Two comparisons in the reference core become inclusive (`now > expires_at` for
expiry in `_advance`, `now <= expires_at` in `choose`), so a taunt is still in
force exactly at `expires_at`. This breaks one requested behavior, the second
half of core-5 / accept-3 ("it lapses as soon as the boundary is reached"). Everything else, including the
5.999 check of the same case, the retry and all server cases, still passes.

### alternative-a (`starter` + tree)

Written from the public exam, structurally unlike the reference:

- core: no metatable/class; `Arbiter.new`/`load` return a table of closures over
  a private state table (the reference is a `setmetatable` class with public
  fields that its component reads directly, e.g. `arbiter.clock`, `arbiter.entities`);
- state: one flat list of `source -> target` edges with `amount`/`stamp`, a nested
  `guard[source][target]` replay map and per-source leases (the reference keeps a
  table of per-source threat tables keyed by a joined stream string);
- snapshot is a structured view (`entities`, `threats`, `taunts`), save writes
  already-decayed levels at `now` instead of raw bases;
- time: queries (`choose`, `snapshot`, `save`) never move the clock; only
  mutations advance a horizon;
- integration: an extra module `scripts/combatarbiter/registry.lua` owns the
  entity/id map and the three per-entity listeners; the component numbers
  attacked events with its own persisted per-stream counters (the reference asks
  the core for `last_seq`); the taunt RPC carries only a retry token and the
  server picks the followed fighters within range of the real player (the
  reference lets the client name one creature id).

Decay model of alternative-a: all edges of a source share one decay clock that
restarts at every accepted threat event of that source (zeroed edges are
released first, amounts are not folded). This is the reference's model and is
the only thing that differs from the strict-reading tree.

### alternative-strict-reading (`starter` + tree)

Identical to alternative-a except for one function, `edge_for_event` in
`scripts/combatarbiter/arbiter.lua` (plus the header comment; `diff -ru` of the
two trees shows nothing else). Here each entry decays from **its own** last
update: on an accepted event the edge is first brought to its current level and
then re-stamped, other edges are untouched. This is the plain reading of the
public sentence (Core semantics item 3):

> Threat decays linearly from the last update time at `options.decay_per_second` and is clamped at zero; the result must not depend on how often `tick` is called.

Result: the private suite rejects it. `benchmarks/dst/hidden/combat-target-arbiter.lua:30-31`
adds 10 for `b` at t=0 and 10 for `a` at t=1 (decay 1/s) and expects `b` at t=2
as a first-seen tie. Per entry: b = 10 - 2 = 8, a = 10 - 1 = 9, so `a` leads.
Only a model that does not decay `b` over [0,1] produces the tie (reference:
b = a = 10 - 1 = 9). Folding the whole table at the event also fails (9 vs 10 at
t=1, 8 vs 9 at t=2). The other 15 cases pass, including the three server cases.
The control is kept as-is and shows the expected problem in `e0 run`.

## Assertion findings

- Over-constraint above: the tie case decides the decay model, which the public
  exam does not state. Recommendation: do not admit the case
  `hidden:ties use first seen then lexical id` as clean evidence for core-4
  until the exam sentence is clarified by the task owner; if per-case exclusion
  is not possible, the task's admission is questionable because a valid
  implementation loses 5 points and cannot pass. The second half of the same
  case (lexical order, same timestamp) is sound.
- `benchmarks/dst/server/combat-target-arbiter.lua:37-39` calls
  `service:OnSave()` / `service:OnLoad(data)` with a receiver. There is no
  receiver-less `OnSave` call in this task; ordinary class methods pass
  (both alternatives use plain `function Component:OnSave()`).
- `server/...:29` pushes a bare `death` event while health still reports alive;
  the component must trust the event (both alternatives and the reference do).
- Unasserted public clauses (excluded): core-1a (id/time/amount/duration
  validation), core-6b (`remove`), core-7c (first-seen, leases, request
  history and replay state across save/load), dst-5b (cancel on removal),
  dst-6 (RPC taunt), api-1 (nil attacker), api-2 (check
  `combat.target`). The exam's Acceptance bullet 5 claims the server suite triggers
  attacked/onremove and checks lease expiry and cleanup; it does not.

## Not run

Nothing outstanding for this task. No compat-negative exists by design (see above).

## Catalog 2.1.0 update

The sections above describe catalog 2.0.1 (study snapshot 5929c99). core-3 now states per-entry linear decay with its formula, the tie case adds 9 instead of 10 to the later target so the tie is genuine under that rule, and the reference implements per-entry decay. The former `alternative-strict-reading` (per-entry decay) is kept as `alternative-b` and passes at 100; alternative-a still passes. Re-run on 2026-09-22: reference 100, alternative-a 100, alternative-b 100, target-negative-taunt-boundary fails `taunt overrides until exact expiry` only.
