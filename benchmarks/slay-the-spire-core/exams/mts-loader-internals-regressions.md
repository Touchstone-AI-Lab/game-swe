# ModTheSpire: reports from the modding community

You are working on **ModTheSpire**, the loader and bytecode patching engine that every
Slay the Spire mod is loaded through. It is a Java 8 project built with Maven, and the
source is at `/app/modthespire`.

## Problem

The reports below came in from people who make mods after this build went out. They are
observations, not diagnoses: none of them knew which part of the loader was responsible,
and they are not all the same underlying issue.

> **[#1013]** The people we credit for making the mod stop being listed once the launcher
> has been run a single time. They are right there in our descriptor and show up on a
> fresh install, then never appear again.

> **[#1016]** We renamed our mod for its new edition — same mod, same identifier, new
> title. The launcher now treats it as an entirely new mod: every per-mod setting our
> users had is gone, and the old entry lingers alongside the new one.

> **[#1010]** One of our mods loads perfectly the first time it is installed and then
> never again. Every launch after the first fails to load it. Deleting the launcher's
> cached data buys us exactly one more successful launch. Our descriptor states which
> release it is as two numbers rather than three, which it always has.

> **[#1019]** We ship a small pack of helper mods that deliberately carry no identifier
> of their own — they are told apart by their titles. Since this build only one of them
> survives in the launcher's list; the rest vanish as though they were all the same thing.

> **[#1102]** We attach something to a routine that hands nothing back, and in one
> specific situation we want to take the job over completely so the game skips its own
> work. The game does its work anyway, every time. In situations where we deliberately
> leave it alone the behaviour is correct, so only the taking-over part is lost.

> **[#909]** The number handed to our addition is the one the caller supplied, not the one
> the method worked out. For anything that transforms its input those are two completely
> different values, and we are reading the wrong one.

> **[#912]** A patch of ours that takes a whole number, changes it and hands it back now
> brings the game down at start-up — the class verifier complains the types on the stack
> do not line up. Doing the same with an object rather than a number is fine.

## What to do

Work in `/app/modthespire`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not special-case the exact scenario in a report, and do not work
  around a problem in a caller — every mod on the platform goes through this machinery.
- Do not change anything under `/tests`, and do not add test files of your own.
- Behaviour that already works must keep working.
- The project targets Java 8. `mvn -o -B test-compile` builds it offline.
