# E0 notes: stardew-valley/core/stardew-summon-horse-anywhere

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: construction task. The workspace holds `mod/SummonAnywhere/`; controls use `root` = `mod`
(patches apply with `patch -p1` from `/app/mod`, the `alternative` tree is copied over `/app/mod`).
Reference = starter with `solution/reference/ModEntry.cs` copied in.

## Case roles

4 cases: 1 static, 1 setup, 1 target, 1 preserved.

- target: `the flute summons the horse indoors` (fails in the unchanged starter).
- preserved: `sentinel: the flute still summons the horse outdoors`. It is base-game behaviour, so it
  passes with the empty skeleton mod (`starter.execution.json`: P). I still label it `preserved` rather
  than `runtime-sentinel`: the exam states it as a must-keep ("Using the flute outdoors must behave as
  it always has"), it holds before the change, and a mod that implements the target can break it, which
  `cn-toggles-indoors-flag` demonstrates in the real game. The task therefore has exactly one preserved
  contract and enters the preserved-contract analysis with that single case.

## Controls (all run in the real game, all admissible)

| control | kind | change | observed |
| --- | --- | --- | --- |
| `tn-clears-wrong-restriction` | target-negative | reference whose postfix clears `NoRoom` instead of `Indoors` | fails only the indoor case |
| `cn-toggles-indoors-flag` | compat-negative | reference with `^=` instead of `&= ~` on the `Indoors` flag | indoor case passes, outdoor sentinel fails (outdoors the flag gets set, so the game refuses) |
| `alternative` | alternative | starter + `alternative/SummonAnywhere/ModEntry.cs` | 4/4 |

`alternative` does not touch `Utility.GetHorseWarpRestrictionsForFarmer`, which is the whole of the
reference. It puts a Harmony prefix on `Object.performUseAction`; for the horse flute, when the game's
own restriction check reports `Indoors`, it either shows the game's refusal for the remaining
restrictions or performs the summon itself (flute sound, 1.5 s delay, re-check, horse mutex,
`Game1.warpCharacter`). Outdoors and for every other item the original method runs untouched. Known
limitation: it acts for the main player only; a farmhand indoors falls back to the base game.

## Probe (not in `manifest.tsv`; its row is kept in `probes.tsv`)

`probe-clears-every-restriction`: the reference changed to return `HorseWarpRestrictions.None`
unconditionally, which violates requirement bullet 2 ("the other conditions ... still apply"). Result:
4/4, score 100 (`e0/records/.../probe-clears-every-restriction.json`; run as a compat-negative, verdict
"must violate at least one preserved contract"). Bullet 2 is a preserved contract of the base game with
no assertion.

## Exclusions and weak clauses

- `Keep-2` (other summoning conditions still apply): unasserted, excluded; see the probe.
- `Keep-3` (no summon on its own): weak, a single precondition assertion.
- `Req-1-beside-player`: weak, the indoor case never checks the horse's position.
- `Notes-manifest`, `Notes-tests`: unasserted delivery constraints, excluded.
- No task-level exclusion is recommended. Note that the scored contract is 1 target + 1 preserved case.

## Findings a reader of results needs

- The harness uses the flute by calling `Object.performUseAction` directly. An input-layer
  implementation (a button handler) is valid for a player and fails the suite. I did not build such a
  mod as `alternative-strict-reading` because whether "using the horse flute" must cover a direct
  `performUseAction` call is a judgement about the exam wording rather than a clear over-constraint.
- Only the FarmHouse is exercised indoors.
- The prepared image bakes the harness that predates the wait-predicate fix (commit 276a070); in this
  suite a throwing predicate still ends in a failed case.

## Not run

Nothing. Every control and the probe have real-engine records under
`e0/records/stardew-valley/core/stardew-summon-horse-anywhere/`.
