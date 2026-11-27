# E0 notes: stardew-valley/core/stardew-auto-workshop

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: construction task. The workspace holds `mod/AutoWorkshop/`; controls use `root` = `mod`
(patches apply with `patch -p1` from `/app/mod`, the `alternative` tree is copied over `/app/mod`).
Reference = starter with `solution/reference/ModEntry.cs` copied in.

## Case roles

12 cases: 1 static, 2 setup, 9 target, 0 preserved.

There is no `sentinel:` case and no preserved contract: the starter is an empty `Entry()`. Besides the
two `setup:` fixtures, one case passes on the unchanged starter, and it is not a preserved contract:
`the far chest and the lone furnace stay untouched` is the boundary of requirement 6 and passes because
an empty mod touches nothing. It stays `target` with `overlap: true`.

So **no compat-negative is written** and the task enters general completion only.

## Controls (all run in the real game)

| control | kind | change | observed | admissible |
| --- | --- | --- | --- | --- |
| `tn-skips-building-interiors` | target-negative | reference walking `Game1.locations` only | fails exactly the two coop cases | yes |
| `tn-ignores-zero-quantity-product` | target-negative | reference that leaves a zero-quantity product in the machine | fails `a zero-quantity product is cleared away`, `the machine carries on ...`, and the two full-chest cases that reuse the now jammed furnace | yes |
| `tn-overreach-feeds-lone-machine` | target-negative | reference that also feeds (never empties) a chestless machine from a chest two tiles away | fails exactly `the far chest and the lone furnace stay untouched` | yes |
| `alternative` | alternative | starter + `alternative/AutoWorkshop/ModEntry.cs` | 12/12 | yes |
| `alternative-strict-reading` | alternative | reference without its 30-tick throttle (services every tick) | fails `a zero-quantity product is cleared away` ("hung: exceeded 3000 ticks"), `a full chest never costs the product` ("expected: the batch finished while the chest was full"), `the product is delivered once space opens` | **no, by design of the control** |

`alternative` is structurally different from the reference: chest-centric (it starts from player chests and
looks at their four neighbours, so a machine can be served by any chest touching it, not only the first one
found), it keeps a per-location station index keyed by `NameOrUniqueName` that is rebuilt on SMAPI world
events (object/building/location list changes, save load, day start, ten-minute safety net) instead of
rescanning every object of every location twice a second, it moves a product only when a capacity
pre-check says the whole stack fits, and it resets the machine the way the game does after a manual
collection (including the `OutputCollected` rule). It relies on public game/SMAPI API only.

### `alternative-strict-reading`

The exam sets no minimum time a finished product must remain in the machine. A mod that services
machines every tick is a valid implementation, and it is the reference with one condition removed. The
suite rejects it because two cases need to observe the ready state before the mod reacts:
`SuiteWorkshop.cs:90` waits, without a deadline, for `readyForHarvest` in order to inject the
zero-quantity glitch, and `:117-119` asserts `readyForHarvest` one tick after advancing the clock. With an
every-tick mod the harness never sees a ready furnace. The third failure is a consequence (the fixture's
ore is exhausted while the second case hangs for 3000 ticks). I kept this control instead of bending it;
`alternative` is the second, passing alternative.

## Probes (not in `manifest.tsv`; rows kept in `probes.tsv`, records kept under `e0/records/...`)

Both were run as target-negatives and both pass 11/11 with score 100 ("must fail at least one target case"):

- `tn-full-chest-destroys-product`: the reference changed to reset the machine even when the chest
  returned a leftover, i.e. it destroys whatever does not fit. It passes because the "full" chest of
  `SuiteWorkshop.cs:107-124` still contains the copper-bar stack collected earlier: the finished bar merges
  into it, the full-chest branch is never reached, and the two assertions after the 360-tick wait are
  satisfied by the next batch. Requirement 3 is therefore `weak`.
- `tn-overreach-two-tiles`: the reference changed to accept a chest two tiles away for feeding and
  collecting. It passes because the guard only reads the lone furnace's end state, and the far chest's
  20 ore are exactly four batches, which are used up by the time the guard runs. Requirement 6 is therefore
  `weak`; only an overreach that leaves evidence in the lone furnace (`tn-overreach-feeds-lone-machine`)
  is caught.

## Exclusions and weak clauses

- `Req-3` (no item lost / full chest): weak, see the first probe.
- `Req-6` (no overreach): weak, see the second probe.
- `Req-0-sides` ("any of the four sides"): weak, every fixture uses the machine's west side.
- `Notes-manifest`, `Notes-tests`: unasserted delivery constraints, excluded.
- Recommendation: keep the task for general completion, but do not read a pass as evidence for
  requirement 3 or for a full no-overreach guarantee, and treat failures on the zero-quantity and
  full-chest cases with care: they can be caused by the observation-window assumption rather than by a
  wrong mod.

## Other findings

- `the product is delivered once space opens` has no `AdvanceClock`; it depends on the in-game clock
  running by itself (it does in the prepared image).
- The prepared image bakes the harness that predates the wait-predicate fix (commit 276a070); in this
  suite a throwing predicate still ends in a failed case.

## Not run

Nothing. Every control and both probes have real-engine records under
`e0/records/stardew-valley/core/stardew-auto-workshop/`.
