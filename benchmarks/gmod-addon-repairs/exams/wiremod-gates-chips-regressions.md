# Wiremod: reports about gates, chips and holograms

You are working on **Wiremod**, the Garry's Mod addon that adds wiring, logic gates and
the Expression 2 (E2) programmable chip. The addon source is at `/app/wire`.

## Problem

The reports below came in from builders and E2 programmers after this build of the
addon was deployed. They are observations, not diagnoses: nobody who filed one knew
which part of the addon was responsible, and they are not all the same underlying
issue. E2 programs behave the same whether they run on a chip or through the addon's
own script compiler (`E2Lib.compileScript`, which the `e2test` command uses).

> **[A]** The derivative gates misbehave. The number Derivative gate keeps showing the
> last rate of change forever once its input stops changing; it should drop back to 0
> as soon as the input is steady, like the other time-based gates that keep updating on
> their own. The vector and angle Delta (derivative) gates output infinite or NaN
> values when they are evaluated twice at the same instant - for example right after
> they are placed; with no time elapsed the rate must be zero.

> **[B]** When a chip's outputs are redeclared with a new output in front of the
> existing ones (for example `@outputs A B` becomes `@outputs X A B` on the next
> upload), the outputs end up with clashing positions in the port list, and the next
> time the port list is rebuilt one of the outputs disappears altogether. Outputs
> should be numbered in the order they are declared (X, A, B), and all of them must
> survive.

> **[C]** With `wire_expression2_unlimited 1`, `perf()` reports the raised per-tick
> budget, yet loops are still aborted with "tick quota exceeded" at the normal limit,
> so a `while (perf()) { ... }` loop that `perf()` considers fine gets killed. Loops
> should be allowed to use the raised budget. With the normal settings, runaway loops
> must still be stopped.

> **[D]** Inside the callback of a lambda timer's final run, `timerExists("name")` says
> the timer no longer exists, and in `@strict` mode `timerGetReps("name")` kills the
> chip. A timer must still exist while its callback runs; it is gone only after its last
> run has finished.

> **[E]** Hologram functions crash the chip with internal errors when they are asked
> about a hologram that does not exist, or when a hologram cannot be created (for
> example because the chip's owner has left). They should return the neutral value of
> their type instead: `holoCreate` a null entity, `holoScale` a zero vector, the
> count, length and frame functions 0, and the list functions an empty array.
> Holograms that do exist keep reporting their real properties.

> **[F]** Calling a function by its name as a standalone statement - `"myFunction"()`
> for a user function that returns a value, or `"curtime"()` - fails at runtime with
> "Mismatching return types". Using the result, as in `"myFunction"()[number]`, works.

## What to do

Work in `/app/wire`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not special-case the exact scenario in a report; every gate, chip
  and wired entity on the server goes through the same code.
- Do not change anything under `/tests`, and do not add test files of your own to the
  addon.
- Behaviour that already works must keep working: ordinary gates still follow their
  wired inputs at once, chips keep their outputs and timers, and the tick quota still
  protects the server.
