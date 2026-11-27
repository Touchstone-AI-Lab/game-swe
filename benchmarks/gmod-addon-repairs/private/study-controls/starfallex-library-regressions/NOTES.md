# E0 notes: garrys-mod/addon-repairs/starfallex-library-regressions

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `starfallex/`, so every patch here is written against the
workspace root (paths start with `starfallex/`) and applied with `patch -p1` from it
(`root` = `.`). Reference = starter + `solution/after/` copied over `starfallex/` (the
task's own `solve.sh`).

## Baseline

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-554f1402f72440e2` | 2026-09-23 | 10 | True | 7 of 13 | every target case (6) |
| reference #1 | `run-f387869239854711` | 2026-09-23 | 100 | True | 13 of 13 | none |
| reference #2 | `run-ec473bea95d14bec` | 2026-09-23 | 100 | True | 13 of 13 | none |
| reference #3 | `run-dfbd45215ffb40d0` | 2026-09-23 | 100 | True | 13 of 13 | none |

Reference repeats: 3 runs, identical case outcomes: True.

## Preserved contracts

Each report states the neighbouring behaviour that already works, and Notes bullet 4
(clause `Task-preserve`) requires it to keep working. One preserved case per report:

- `preserved: loadstring without an environment runs in the chip` ([A]).
- `preserved: a live entity turns into its usual text` ([B]).
- `preserved: an unpermitted chip still cannot hand out weapons` ([C]; the
  `player.giveweapon` privilege refuses a non-admin owner).
- `preserved: skipping inside a string stream still works` ([D]).
- `preserved: quaternion slerp at zero returns its start` ([E]).
- `preserved: a chip that includes a script can require it` ([F]).

## Controls

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-tell-guard` | target-negative | reference | Reference with the skip() clamp reverted and tell() made tolerant of the gap instead: the position query stops erroring, but a later write still leaves a hole (report D). | `run-80ceb6cd4d4c4f25` (2026-09-23) | complete; fails exactly `D: skipping past the end of a string stream leaves it usable` | admissible |
| `compat-negative-no-permission` | compat-negative | reference | Reference whose giveWeapon also drops its permission check: every target passes, but owners without the privilege can hand out weapons. | `run-d9b0d065f4c04ad3` (2026-09-23) | complete; fails exactly `preserved: an unpermitted chip still cannot hand out weapons` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all six reports: an env local in loadstring, pcall-guarded __tostring, PLY_META.Give at the call site, a post-skip clamp, a textbook sin-weighted slerp, and includedata registering the include directly. | `run-4c05680959bc44c4` (2026-09-23) | 100, every case passes | admissible |

### `alternative-independent-fix` versus the reference

Written from the public reports and the supplied source only.

- [A] Same observable contract; the alternative resolves the target environment up
  front into a local instead of choosing it at `setfenv` time.
- [B] The reference reads the raw entity from the wrapper's sensitive table. The
  alternative keeps the throwing accessor and wraps it in `pcall`.
- [C] The reference adds `Ply_Give` to the cached-method locals. The alternative calls
  `PLY_META.Give` at the call site.
- [D] The reference sets the index to `#self + 1` inside the skip loop. The alternative
  keeps the loop and clamps the position after it.
- [E] The reference removes a spurious conjugation from its log/exp formulation. The
  alternative replaces the body with the textbook sin-weighted slerp (shortest path,
  linear fallback for nearly equal rotations).
- [F] The reference calls the include directive function. The alternative appends the
  file to `self.includes` directly.

## Known issues

- Cases read the values a chip script leaves in its own global environment
  (`chip.instance.env`), i.e. the script's variables, not the addon's internals. The
  chip is compiled through the processor entity's own `ENT:Compile`, the path the tool
  uses.
- [C] needs an owner holding the `player.giveweapon` privilege; the case makes the bot a
  `superadmin` for the call and resets it afterwards.

## Not run / not done

- All runs used the managed GLuaTest container on this Linux x86_64 host through
  `rhenium run` (the real Hub evaluator path). Nothing was run on Windows or through
  Harbor, and the task is not registered in the `tools/study` inventory, so
  `rhenium-study e0 run` has not been used on it.
