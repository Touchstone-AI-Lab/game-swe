# Per-defect validation matrix

Two trees cannot detect a masking pair, so base-versus-reference is not sufficient
evidence. Every defect group additionally gets a tree where **only that group is
fixed**, and must flip exactly its own group and nothing else. All numbers below were
produced on a real headless Garry's Mod server against the revision in this pack.

The sentinel case passes everywhere by design — it only asserts that the gamemode
loaded. `darkrp-live-server-regressions` additionally has one always-passing control
(a real job can still be made a hitman team) and `darkrp-door-economy-regressions`
has one (ordinary prices are unaffected); those are positive controls that exist so
that "reject everything" cannot score.

## darkrp-release-regressions-v3 — 10 cases

| tree | PASS | groups passing |
|---|---|---|
| base | 1 | sentinel only |
| reference | 10 | all |
| fix A only | 3 | sentinel + A (2 cases) |
| fix B only | 3 | sentinel + B (2 cases) |
| fix D only | 2 | sentinel + D |
| fix E only | 2 | sentinel + E |
| fix F only (both halves) | 3 | sentinel + F (2 cases) |
| fix G only | 2 | sentinel + G |

### Masking-pair controls

Group F is a strongly-subsuming higher-order mutant: the shipment name is stored
un-normalised **and** looked up un-normalised, so same-case use keeps working and the
system looks healthy. Repairing either half alone must not make the group pass.

| tree | PASS | F group |
|---|---|---|
| neither half fixed (base) | 1 | 0 of 2 |
| getter half only | 2 | **1 of 2** |
| store half only | 2 | **1 of 2** |
| both halves | 3 | 2 of 2 |

## darkrp-live-server-regressions — 11 cases

| tree | PASS | groups passing |
|---|---|---|
| base | 2 | sentinel + the always-passing control |
| reference | 11 | all |
| fix S / T / U / V / X / Z / AA / BB / CC, each alone | 3 | sentinel + control + that group |

## darkrp-door-economy-regressions — 11 cases

| tree | PASS | groups passing |
|---|---|---|
| base | 2 | sentinel + the always-passing control |
| reference | 11 | all |
| fix P / Q / R / S / T / U / V / W / X, each alone | 3 | sentinel + control + that group |

### Over-permissive control

Group R must fail an implementation that is too permissive, not merely one that is
too strict. With the door allow-list predicate returning `true` for everyone:

| tree | PASS | FAIL |
|---|---|---|
| reference + always-allow mutant | 10 | 1 — exactly R |

## darkrp-core-library-regressions — 10 cases

| tree | PASS | groups passing |
|---|---|---|
| base | 2 | sentinel + control |
| reference | 10 | all |
| fix A / B / C / D / E / F / G / H, each alone | 3 | sentinel + control + that group |

The control is "selecting entries from a plain list still works": it holds on both
trees, so a submission that breaks the helper outright cannot score.

## darkrp-registration-regressions — 10 cases

| tree | PASS | groups passing |
|---|---|---|
| base | 2 | sentinel + control |
| reference | 10 | all |
| fix A / B / C / D / E / F / G / H, each alone | 3 | sentinel + control + that group |

## darkrp-money-regressions — 9 cases

| tree | PASS | groups passing |
|---|---|---|
| base | 2 | sentinel + control |
| reference | 9 | all |
| fix A / B / C / D / E / F / G, each alone | 3 | sentinel + control + that group |

The control ("a whole amount larger than the wallet is not affordable") exercises the
same predicate group A breaks, but with whole numbers, where the rounding cannot
differ — so a submission that simply refuses every purchase cannot score.

A harness trap worth recording: a bot's player data never finishes loading in a
headless container, so it keeps the flag that makes the affordability check refuse
every amount outright. Left alone, the control failed on every tree and case A passed
on every tree — neither for the reason its name claims — and the matrix still looked
plausible. The two cases that touch that predicate now clear the flag explicitly.

## darkrp-persistence-regressions — 12 cases

| tree | PASS | groups passing |
|---|---|---|
| base | 3 | sentinel + both controls |
| reference | 12 | all |
| fix A / B / C / D / E / F / G / H / I, each alone | 4 | sentinel + controls + that group |

The controls drive the same two routines B and E change, at an ordinary balance and an
ordinary name where neither defect can differ, so a submission that refuses every write
— or writes everything through unchecked — cannot score.

### Two bad assertions the matrix caught, which base-versus-reference would have shipped

**A case that passed with its own defect present.** Group H replaces `string.find`'s
`plain` flag so a name is used as a Lua pattern. The first assertion searched for a
fixed string containing an unclosed bracket and expected no error. Lua's matcher is
lazy: the literal prefix never matched the connected player's name, so the matcher
never reached the malformed capture and never raised — on either tree. H now derives
its needles from the name it is searching for.

**A case that failed on its own fix tree.** After that change, H failed everywhere
except the full reference. The failure log printed `nick = x`: DarkRP overrides
`Player:Nick()` to return the roleplay name, and group E's case deliberately sets a
one-character name, which succeeds on every tree where E is unfixed. One case had
renamed the subject out from under another. H now establishes the name it searches for
instead of inheriting it — the same "every case owns its fixture" rule that the spawn
cases in this pack follow, in a form where the shared mutable state is the player
rather than a table.

## darkrp-job-loadout-regressions — 10 cases

Retired in catalog 1.1.0; this matrix is kept as history.

| tree | PASS | groups passing |
|---|---|---|
| base | 3 | sentinel + both controls |
| reference | 10 | all |
| fix A / B / C / D / E / F / G, each alone | 4 | sentinel + controls + that group |

The controls accept a well-formed job and refuse one whose name is not text, so neither
a checker that refuses everything nor one that accepts everything can score.

### A defect that was removed because it could not fail

A sixth defect flipped the value filled in for `allowPurchaseWhileDead` from false to
true. The matrix showed it passing on the base tree. Reading `tablecheck` explains why:
`addHint` collects its wrapped function's results with `local res = {f(...)}` and
returns `unpack(res)`, so when a field declares no hints the table has a hole, `#res`
truncates, and the `replace` / `replaceWith` values `tc.default` depends on are dropped
before `checkTable` can act on them. That default can never apply, on any tree, so an
assertion about it can never fail. It was removed rather than papered over.

## Adversarial controls

See `reward-hack-probe.md` (append-only transcript forgery) and
`result-mutation-probe.md` (in-process rewriting of failing results). Both score 0.
