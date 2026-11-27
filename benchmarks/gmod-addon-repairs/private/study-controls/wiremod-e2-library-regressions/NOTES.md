# E0 notes: garrys-mod/addon-repairs/wiremod-e2-library-regressions

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: the workspace holds `wire/`, so every patch here is written against the
workspace root (paths start with `wire/`) and applied with `patch -p1` from it
(`root` = `.`). Reference = starter + `solution/after/` copied over `wire/` (the task's
own `solve.sh`).

## Baseline

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-0289c8f21dbc45b5` | 2026-09-23 | 10 | True | 5 of 11 | every target case (6) |
| reference #1 | `run-599181ac610749c3` | 2026-09-23 | 100 | True | 11 of 11 | none |
| reference #2 | `run-802eea80a3c74ba7` | 2026-09-23 | 100 | True | 11 of 11 | none |
| reference #3 | `run-630e1c2488c84c18` | 2026-09-23 | 100 | True | 11 of 11 | none |

Reference repeats: 3 runs, identical case outcomes: True.

## Preserved contracts

- `preserved: whole numbers still convert to other bases` ([B]).
- `preserved: complex numbers with both parts print as before` ([C]).
- `preserved: character codes in and out of range behave as before` ([D]; an
  out-of-range code already yields an empty string in non-strict mode).
- `preserved: searching an array for numbers, strings and vectors` ([F]).

## Controls

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-complex-text` | target-negative | reference | Reference with the zero-part comparisons fixed but a real-only complex number still returned as a number rather than text (half of report C). | `run-3d145d114599487b` (2026-09-23) | complete; fails exactly `C: complex numbers with a zero part print cleanly` | admissible |
| `compat-negative-tochar-clamp` | compat-negative | reference | Reference whose toChar clamps a bad code instead of rejecting it: NaN still yields an empty string, but an out-of-range code now yields a character. | `run-65037d99e3e74ebb` (2026-09-23) | complete; fails exactly `preserved: character codes in and out of range behave as before` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all six reports: a clamp helper, truncation in the toString(n, base) wrapper, a rewritten complex formatter, NaN-proof range checks, a per-evaluation copy of the table element types, and element-wise comparison in indexOf. | `run-ee4688452f3940bf` (2026-09-23) | 100, every case passes | admissible |

### `alternative-independent-fix` versus the reference

Written from the public reports and the supplied source only.

- [A] The reference restores the `x`/`z` assignments. The alternative replaces the body
  with a per-component helper over the vector's indices.
- [B] The reference floors both arguments inside `tobase`. The alternative truncates in
  the `toString(n, base)` wrapper and leaves `tobase` unchanged.
- [C] The reference fixes two comparisons and one `tostring`. The alternative rewrites
  the formatter from the exact parts.
- [D] The reference adds `n ~= n` to the guard. The alternative inverts the range test
  so NaN fails it.
- [E] The reference builds a fresh types array alongside the values. The alternative
  copies the compile-time array per evaluation.
- [F] The reference registers a per-type `indexOf` that uses the type's `==` operator.
  The alternative compares table-backed values component by component.

## Known issues

- Every case runs E2 through `E2Lib.compileScript` (world owner, non-strict), the path
  of the addon's own `e2test` command; results are asserted inside the E2 program with
  `assert`.
- [F] uses distinct component values for each typed element: indexOf in both upstream
  and the alternative compares table-backed values by content, so a `vector4` and a
  `quaternion` with equal components are indistinguishable. The upstream test data does
  the same.

## Not run / not done

- All runs used the managed GLuaTest container on this Linux x86_64 host through
  `rhenium run` (the real Hub evaluator path). Nothing was run on Windows or through
  Harbor, and the task is not registered in the `tools/study` inventory, so
  `rhenium-study e0 run` has not been used on it.
