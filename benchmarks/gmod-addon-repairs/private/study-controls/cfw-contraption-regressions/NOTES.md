# E0 notes: garrys-mod/addon-repairs/cfw-contraption-regressions

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `cfw/`, so every patch here is written against the
workspace root (paths start with `cfw/`) and applied with `patch -p1` from it
(`root` = `.`). Reference = starter + `solution/after/` copied over `cfw/` (the task's
own `solve.sh`). Most of CFW's Lua files use CRLF line endings; the patches keep them
byte-for-byte (see the pack's `.gitattributes` entry).

## Baseline

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-12bdf0e258994a31` | 2026-09-23 | 10 | True | 4 of 10 | every target case (6) |
| reference #1 | `run-2f8bee57ea32419a` | 2026-09-23 | 100 | True | 10 of 10 | none |
| reference #2 | `run-2a8e5ae106474189` | 2026-09-23 | 100 | True | 10 of 10 | none |
| reference #3 | `run-6720c1c0c0684325` | 2026-09-23 | 100 | True | 10 of 10 | none |

Reference repeats: 3 runs, identical case outcomes: True.

## Preserved contracts

- `preserved: a welded contraption's total mass follows a member's new mass` - report
  [A] states the contraption total already follows; it must keep doing so.
- `preserved: a parent with both hooks can refuse or accept children` - report [B]
  states the veto works when both hooks are defined.
- `preserved: welding two props makes one contraption until the weld goes` - ordinary
  links still form and split (Notes bullet 4).

## Controls

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-players-only` | target-negative | reference | Reference with only the player exclusion kept: NPCs and nextbots are still pulled into contraptions (a partial repair of report C). | `run-b8b7032a0e0f4c75` (2026-09-23) | complete; fails exactly `C: something parented to an NPC stays out of contraptions`, `C: something parented to a nextbot stays out of contraptions` | admissible |
| `compat-negative-family-only` | compat-negative | reference | Reference that moves the mass update to the family instead of adding it: every target passes, but a contraption's total no longer follows a member's new mass. | `run-e15cba9bde5841b2` (2026-09-23) | complete; fails exactly `preserved: a welded contraption's total mass follows a member's new mass` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all four reports: recompute the family total from its members, ask any parent that defines the veto hook, one character check before linking, and ignore self-constraints where constraints are tracked. | `run-ad61457d90b2404b` (2026-09-23) | 100, every case passes | admissible |

### `alternative-independent-fix` versus the reference

Written from the public reports and the supplied source only.

- [A] The reference adds the mass delta to the family total. The alternative recomputes
  the family total from its members' physics objects.
- [B] The reference also records a parent that has only `CFW_PreParented`. The
  alternative looks the veto hook up on the new parent when no saved parent exists.
- [C] The reference adds three guards (player, NPC, nextbot). The alternative uses one
  `isCharacter` check before any linking.
- [D] The reference guards `CFW.connect` and `CFW.disconnect`. The alternative ignores
  self-constraints where constraints are tracked (`constraints_sv.lua`), so no link is
  ever created.

## Known issues

- [C] is exercised with a bot player, an `npc_citizen` and a nextbot class the suite
  registers from `base_nextbot` (no nextbot ships with the sandbox gamemode).
- [D] welds bone 0 to bone 1 of a `models/Humans/Group01/male_07.mdl` ragdoll.

## Not run / not done

- All runs used the managed GLuaTest container on this Linux x86_64 host through
  `rhenium run` (the real Hub evaluator path). Nothing was run on Windows or through
  Harbor, and the task is not registered in the `tools/study` inventory, so
  `rhenium-study e0 run` has not been used on it.
