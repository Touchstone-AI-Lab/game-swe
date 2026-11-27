# E0 notes: garrys-mod/addon-repairs/advdupe2-paste-regressions

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `advdupe2/`, so every patch here is written against the
workspace root (paths start with `advdupe2/`) and applied with `patch -p1` from it
(`root` = `.`). Reference = starter + `solution/after/` copied over `advdupe2/` (the
task's own `solve.sh`).

## Baseline

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-51d95c2b0e0b48aa` | 2026-09-23 | 10 | True | 5 of 11 | every target case (6) |
| reference #1 | `run-a18eb581de0547a1` | 2026-09-23 | 100 | True | 11 of 11 | none |
| reference #2 | `run-8b5eccb52d89469e` | 2026-09-23 | 100 | True | 11 of 11 | none |
| reference #3 | `run-374b45594a7a4a98` | 2026-09-23 | 100 | True | 11 of 11 | none |

Reference repeats: 3 runs, identical case outcomes: True.

## Preserved contracts

Stated publicly in `## What to do`, Notes bullet 4 (clause `Task-preserve`), and in
reports [D] and [E] themselves:

- `preserved: a copied prop pastes at the requested place, frozen` - the plain
  Copy/Paste path of the tool.
- `preserved: a pasted weld still counts as a constraint` - report [D] says welds keep
  counting as constraints; the boundary of the rope fix.
- `preserved: file names keep their other characters readable` - report [E] lists the
  existing clean-up (quotes and colons, collapsed spaces).
- `preserved: an encoded dupe decodes to the same contraption` - Encode/Decode round
  trip.

## Controls

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-rope-limit` | target-negative | reference | Reference with the rope-limit check dropped: pasted ropes are counted as ropes but sbox_maxropeconstraints is never enforced (half of report D). | `run-fc9f6b72dcfb4e8e` (2026-09-23) | complete; fails exactly `D: the rope limit is enforced when pasting` | admissible |
| `compat-negative-all-ropes` | compat-negative | reference | Reference that counts every pasted constraint as a rope: every target passes, but a pasted weld no longer counts against the constraint allowance. | `run-d1dde9503c9742f2` (2026-09-23) | complete; fails exactly `preserved: a pasted weld still counts as a constraint` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all five reports: re-activate scaled props in the paste loop, remove the entity where DoGeneric fails, a numeric bone loop from 0, a per-type rope limit, and one-sided separator trimming. | `run-07062039d1d74081` (2026-09-23) | 100, every case passes | admissible |

### `alternative-independent-fix` versus the reference

Written from the public reports and the supplied source only.

- [A] The reference adds `prop:Activate()` to `MakeProp`. The alternative leaves
  `MakeProp` alone and re-activates a scaled `prop_physics` in the paste loop, restoring
  its frozen state afterwards.
- [B] The reference collects every entity created during the generic path through a
  temporary `OnEntityCreated` hook and removes them when creation fails. The alternative
  wraps `duplicator.DoGeneric` in `pcall` inside `GenericDuplicatorFunction`, removes the
  entity it just created and re-raises.
- [C] The reference switches `ipairs` to `pairs`. The alternative walks bones
  numerically from 0 to `GetPhysicsObjectCount() - 1`.
- [D] The reference checks both limits for every constraint and detects ropes by the
  `keyframe_rope` entity the factory returns. The alternative picks one limit name from
  the constraint type (`Rope` -> `ropeconstraints`) and uses it for both the check and
  the count.
- [E] The reference strips `%s*` on both sides in one pattern. The alternative
  collapses whitespace first and then removes one space before and one after each
  separator in two passes.

## Known issues

- [A] is asserted through the physics volume of a pasted crate at scale 2 relative to
  one at scale 1 (a ratio between 6 and 10, 8 expected). The report speaks of the
  collision hull; volume is the engine's public measure of it.
- [B] needs an entry that fails during creation. The case registers a trivial scripted
  entity class (unknown to the duplicator, so the generic path is used) and gives it a
  string `Skin`, which makes `SetSkin` raise inside `duplicator.DoGeneric`. The report
  describes this as corrupted stored entity data.
- [C] is observed through `Player:UnfreezePhysicsObjects()`, the function sandbox's
  double-tap physics-gun reload calls.

## Not run / not done

- All runs used the managed GLuaTest container on this Linux x86_64 host through
  `rhenium run` (the real Hub evaluator path). Nothing was run on Windows or through
  Harbor, and the task is not registered in the `tools/study` inventory, so
  `rhenium-study e0 run` has not been used on it.
