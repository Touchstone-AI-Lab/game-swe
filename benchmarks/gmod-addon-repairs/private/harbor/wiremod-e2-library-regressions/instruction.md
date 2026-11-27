# Wiremod: reports against the Expression 2 standard library

You are working on **Wiremod**, the Garry's Mod addon that adds wiring, gates and the
Expression 2 (E2) programmable chip. The addon source is at `/app/wire`.

## Problem

The reports below came in from E2 programmers after this build of the addon was
deployed. They are observations, not diagnoses: nobody who filed one knew which part
of the addon was responsible, and they are not all the same underlying issue. E2
programs behave the same whether they run on a chip or through the addon's own script
compiler (`E2Lib.compileScript`, which the `e2test` command uses).

> **[A]** `clamp(vector, vector, vector)` returns nonsense: whatever the inputs, the X
> and Z components of the result are wrong, even when the value is already inside the
> range, while Y is clamped correctly. Each component should be clamped between the
> matching components of the minimum and maximum vectors.

> **[B]** `toString(number, base)` kills the chip with a Lua error when the number or
> the base has a fractional part, e.g. `toString(10.5, 2)` or `toString(10, 2.5)`. The
> fractional parts should simply be dropped: `toString(10.5, 2)` is `"1010"`,
> `toString(-10.5, 2)` is `"-1010"` and `toString(10, 2.5)` is the same as
> `toString(10, 2)`. Whole numbers convert exactly as before.

> **[C]** Complex numbers with a zero part print wrongly. `comp(0, 3)` prints as
> `"0+3i"` instead of `"3i"` (and `comp(0, -3)` as `"0-3i"` instead of `"-3i"`), and a
> complex number without an imaginary part, such as `comp(5, 0)` or `comp(0, 0)`, does
> not turn into the string `"5"` / `"0"`, so comparing its text fails. Numbers with two
> non-zero parts print correctly (`"2-3i"`, `"2+3i"`).

> **[D]** Passing NaN (for example `0 / 0`) to `toChar` or `toUnicodeChar` kills the
> chip with a raw Lua error. Out-of-range codes are already handled as invalid
> arguments (an empty string in non-strict mode); NaN must be handled the same way.

> **[E]** A table created with `table(...)` on a line that runs more than once does not
> start out the same every time. After one instance has had an element removed
> (`T:remove(1)`), later instances created by the same line report the wrong type for
> their entries, so `T[3, number]` returns 0 even though the third value is a number.
> Every evaluation must produce an independent table.

> **[F]** `array:indexOf` never finds values of types such as `vector2`, `vector4`,
> `quaternion`, `complex` or the matrix types, even when an equal value is in the array;
> it returns 0. Numbers, strings, vectors and angles are found as expected. Any value
> whose type supports `==` should be found.

## What to do

Work in `/app/wire`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not special-case the exact values in a report; every chip on the
  server runs through the same compiler and library.
- Do not change anything under `/tests`, and do not add test files of your own to the
  addon.
- Behaviour that already works must keep working. These functions are used by
  thousands of existing E2 programs, so a change that fixes one report and changes an
  unrelated result is not a fix.
