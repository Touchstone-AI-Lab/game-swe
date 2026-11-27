# E0 notes: garrys-mod/addon-repairs/wiremod-gates-chips-regressions

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `wire/`, so every patch here is written against the
workspace root (paths start with `wire/`) and applied with `patch -p1` from it
(`root` = `.`). Reference = starter + `solution/after/` copied over `wire/` (the task's
own `solve.sh`).

## Baseline

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-0deee9dac0014432` | 2026-09-23 | 10 | True | 7 of 14 | every target case (7) |
| reference #1 | `run-bf66d7b72a204b34` | 2026-09-23 | 100 | True | 14 of 14 | none |
| reference #2 | `run-fa50e74433d14a28` | 2026-09-23 | 100 | True | 14 of 14 | none |
| reference #3 | `run-88aa9acb43b14a79` | 2026-09-23 | 100 | True | 14 of 14 | none |

Reference repeats: 3 runs, identical case outcomes: True.

## Preserved contracts

- `preserved: an ordinary gate still follows its inputs at once` (Notes bullet 4; a
  sloppy [A] fix that makes every gate timed or breaks input triggering fails it).
- `preserved: a chip's outputs carry the values it assigns` ([B]).
- `preserved: the normal per-tick budget still stops a runaway loop` ([C]).
- `preserved: a finished timer is gone afterwards` ([D]).
- `preserved: an existing hologram reports its own properties` ([E]).
- `preserved: calling a function by name for its value works` ([F]).

## Controls

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-derive-untimed` | target-negative | reference | Reference with the vector/angle Delta gates fixed but the number Derivative gate left untimed (half of report A). | `run-6ad7e478313c4ebf` (2026-09-23) | complete; fails exactly `A: a derivative gate drops back to zero once its input settles` | admissible |
| `compat-negative-timers-kept` | compat-negative | reference | Reference that never forgets a lambda timer after its last run: every target passes, but a finished timer still reports that it exists. | `run-e9617eb4bc3f4576` (2026-09-23) | complete; fails exactly `preserved: a finished timer is gone afterwards` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all six reports: timed derivative and dT > 0 guards, a renumbering pass over declared outputs, a cached quota that also follows the unlimited switch, deferred timer removal keyed to its callback, early exits of typed hologram functions return the neutral value of the type declared in each e2function signature, and a statement-only return-type check. | `run-9b76625d8ba643e1` (2026-09-23) | 100, every case passes | admissible |

### `alternative-independent-fix` versus the reference

Written from the public reports and the supplied source only.

- [A] Same `timed = true` for the number gate (there is no other way for an untriggered
  gate to update); the Delta gates test `dT > 0` instead of `dT ~= 0`.
- [B] The reference assigns `Num = n` while adjusting. The alternative keeps the old
  numbering loop and renumbers every declared output in a final pass.
- [C] The reference reads the global `e2_tickquota` at run time. The alternative keeps
  the compiler's cached quota and refreshes it when either `wire_expression2_quotatick`
  or `wire_expression2_unlimited` changes.
- [D] The reference runs the callback before forgetting the timer. The alternative does
  too, but only forgets the record if it still belongs to the same callback.
- [E] The reference rewrites the early returns function by function. The alternative
  derives each early exit's value from the return type declared in the e2function
  signature (entity -> NULL, vector -> zero vector, number -> 0, array -> empty array),
  and adds a final `return NULL` where a holoCreate variant could fall off the end. An
  earlier version of this control instead wrapped every typed hologram function at
  `postinit`; it failed report [E]'s case (`holoCreate(1)` without a valid owner still
  did not compare equal to `noentity()`), was recorded as run `run-6beb9aada4694445`
  and replaced. The reason the wrapper did not take effect was not investigated.
- [F] The reference relaxes both return-type checks with `ret_type == nil or r == ""`.
  The alternative only checks the return type when the call's value is used.

## Known issues

- Gates read inputs only through wires, so the gate cases wire a Constant Value entity
  (`gmod_wire_value`) to the gate with `WireLib.Link_Start` / `Link_End`, as the wiring
  tool does.
- [B] asserts the output ports' `Num` fields (the order the wiring tools list ports in)
  and that all ports survive `WireLib.RefreshSpecialOutputs`.
- [C] toggles `wire_expression2_unlimited` and waits for the restored value to apply
  before finishing, so later cases run with the normal budget.
- [E]'s "cannot create" half runs through `E2Lib.compileScript` with the world as owner
  (no valid player), the state a chip is in after its owner leaves.

## Not run / not done

- All runs used the managed GLuaTest container on this Linux x86_64 host through
  `rhenium run` (the real Hub evaluator path). Nothing was run on Windows or through
  Harbor, and the task is not registered in the `tools/study` inventory, so
  `rhenium-study e0 run` has not been used on it.
