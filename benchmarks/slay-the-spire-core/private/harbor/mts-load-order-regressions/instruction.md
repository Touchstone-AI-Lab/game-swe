# ModTheSpire: reports about loading mods and patching the game

You are working on **ModTheSpire**, the loader and bytecode patching engine that every
Slay the Spire mod is loaded through. It is a Java 8 project built with Maven, and the
source is at `/app/modthespire`.

## Problem

The reports below came from mod authors after this build went out. They are
observations, not diagnoses: none of them knew which part of the loader was responsible,
and they are not all the same underlying issue.

> **[#731]** Our mod lists another mod as a requirement, and since this build it is being
> started **before** the thing it requires. Everything it looks up during start-up is
> still empty, so it falls over immediately. Swapping the order in the folder makes no
> difference.

> **[#734]** Two of our mods name each other in their requirements — deliberately, they
> co-operate. The game now freezes on the loading screen and eventually dies without
> printing anything useful. Removing either one of the two declarations makes the freeze
> go away.

> **[#737]** A mod that requires nothing at all is being moved around in the start-up
> order as though it did. We only declared the requirement in one direction, and the
> loader appears to be acting on the opposite one.

> **[#740]** Patches that take a value, change it, and hand the changed value on into the
> original method bring the game down at start-up. The log says the class verifier
> refused the generated method because the types on the stack do not line up. It only
> happens when the value is one of the plain number kinds, never when it is an object.

## What to do

Work in `/app/modthespire`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not special-case the exact scenario in a report, and do not work
  around a problem in a caller — other callers use the same machinery.
- Do not change anything under `/tests`, and do not add test files of your own.
- Behaviour that already works must keep working. This engine loads and patches every
  mod on the platform.
- The project targets Java 8. `mvn -o -B test-compile` builds it offline.
