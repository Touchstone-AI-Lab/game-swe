# dst/core/world-rule-ballot: E0 notes

Construction task from an empty starter (`TASK.md`, `TASK.zh-CN.md`, `task.json` only).
The unchanged starter fails every case, so there is **no `preserved` case and no
`compat-negative`**; the task can enter general completion only.

Cases: 13 `target` (6 hidden plain-Lua, 3 dedicated-server, 4 source-pattern gates) and
3 `static`. The four `check:ballot-*` gates are regular expressions over the source and are
mapped as weak evidence for the DST-integration clauses.

## Controls

| control | kind | what it is |
| --- | --- | --- |
| `target-negative-stale-revision` | target-negative | Reference plus `target-negative-stale-revision.patch`: `cast` no longer compares the revision with the voter's previous one (core-2/3). One behavior; expected to fail only `hidden:newer vote revision replaces old vote`. |
| `alternative-a` | alternative | Full mod written from the public exam. |
| `alternative-strict-reading` | alternative (expected to be rejected) | `alternative-a` with result names the public text leaves open. |
| `alternative-strict-reading-whitelist` | alternative (expected to be rejected) | `alternative-a` whose `Open` enforces the fixed proposal list of dst-1. |
| `alternative-strict-reading-early-close` | alternative (expected to be rejected) | `alternative-a` whose `close` is refused before the deadline. |

### alternative-a versus the reference

- Core: no metatable class. `Ballot.new/load` return an object of closures over private state,
  so votes are unreachable from outside. The reference keeps `votes` and `revisions` maps and
  recounts at close; this core keeps a sorted voter roll with parallel `rev`/`pick` columns and
  running tallies that move one unit when a vote changes. Choices are sorted once at `open`.
- One proposal can be open at a time (`another_proposal_open`); finished proposals stay in the
  book for id reuse and replay. The reference allows any number of concurrent proposals.
- Reload: the reference adds a `rebase(offset)` method that the component calls; here
  `Ballot.load(data, { now = <new clock> })` shifts open deadlines by `now - saved_at`.
- Optional `options.abstain`: a listed abstain option counts toward turnout but cannot win.
- Save format is a different, flat row format (`format = 2`, `rows[].ballots`).
- Integration: `modmain.lua` creates `inst._ballot_state` before the master guard exactly as the
  exam shows and the replica adopts it (the reference creates the net variable inside the
  replica). The public state is a small hand-encoded JSON document (the reference uses a
  `|`-separated string). Rules are data (`flag`/`values`) stored on the component and saved, not
  functions writing world fields. A server-console helper opens a configured proposal by name.
- Forced by the private suite, not by the public text: the result fields `ok`, `status`,
  `choice_id`, the literal `canceled`, top-level `snapshot().counts[i].count`, `Open` accepting an
  unlisted proposal id, and `Close` settling before the deadline. See below.

### The three strict-reading controls

Each is `alternative-a` with one deviation (`diff -ru alternative-a <control>` shows it), so a
rejection is attributable:

1. `alternative-strict-reading`: status literal `cancelled`, winner under `result.winner`,
   snapshot aggregates under `snapshot.tally[i].votes`. The exam names `no_quorum`, `tie` and
   `passed` but no field names and no cancel literal. This is the clearest over-constraint:
   semantics are identical, only unpublished names differ.
2. `alternative-strict-reading-whitelist`: `Open` refuses an id whose name part is not in the
   mod's configured proposal list ("proposals come from a fixed server-side whitelist"). The server suite opens
   `server-rule`, which no public text lists. This reading is defensible but not the only one:
   `Open(proposal, player_entities)` receives full proposal contents, which also supports the
   reference's reading that only the applied rule is whitelisted.
3. `alternative-strict-reading-early-close`: `close` before the deadline returns
   `before_deadline`; `cancel` remains the way to end early. The exam specifies close only at and
   after the deadline. The server suite closes 20 s before the deadline and expects `passed`.
   Also defensible rather than compelled.

## Recommendations

- Task-level: admissible for general completion only if the unpublished result shape
  (known issue 1) is accepted as a risk or the exam is clarified by the task owner; as written a
  correct implementation can lose 3 hidden cases and 1 server case on naming alone.
- Exclude the unasserted clauses listed in `excluded_clauses`: proposal validation
  (deliver-proposal), electorate de-duplication and quorum base (core-1b), abstention
  (core-3b), proposal whitelist (dst-1b), rule application (dst-4), net-variable
  ordering and vote privacy on the wire (api-4, accept-footnote), RPC cannot reach Open
  (api-5b), client cannot decide electorate/deadline/quorum/rule (accept-4).
- accept-5 promises engine verification of timers, net state and announcements; the server
  suite does none of these (it closes by hand and never reads the net variable).

## Not run / limits

- No client process exists in the evaluator, so replication was not observed for any control.
- The alternatives were iterated against the hidden suite locally with
  `python -m rhenium_dst.lua_runner`; engine results come only from `rhenium-study e0 run`.

## Catalog 2.1.0 update

The sections above describe catalog 2.0.1 (study snapshot 5929c99). The exam publishes the result fields and the four status strings, says `Open` accepts any well-formed server proposal, that deadlines use the `GetTime()` clock and that a server-side `Close` settles at once. Two hidden assertions were tightened (the deadline case requires passed/on; the snapshot case checks the mutated ballot). The three former strict-reading alternatives now violate published rules and are kept as target-negatives. Re-run on 2026-09-22: reference 100, alternative-a 100, all four negatives fail.
