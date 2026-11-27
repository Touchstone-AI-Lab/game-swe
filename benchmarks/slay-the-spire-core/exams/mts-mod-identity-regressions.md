# ModTheSpire: reports about telling mods apart

You are working on **ModTheSpire**, the loader every Slay the Spire mod is loaded
through. It is a Java 8 project built with Maven, and the source is at
`/app/modthespire`.

## Problem

The reports below came from mod authors and server owners after this build went out.
They are observations, not diagnoses, and they are not all the same underlying issue.

> **[#802]** One of our mods shows up in the loader's list with a completely blank label.
> Its descriptor has the identifier field present but left empty — we never filled it in —
> and it used to fall back to the readable title. Now there is nothing to click on.

> **[#805]** Two mods that are definitely different are being treated as the same one.
> Only one of them declares an identifier; the other has none at all and merely happens
> to share a title. Whichever loads second silently replaces the first.

> **[#808]** A mod of ours stopped loading entirely. Its descriptor says its version is
> "1.0", which every mod in our pack has written that way for years. Writing it as
> "1.0.0" instead makes it load again, so nothing else about the mod has changed.

> **[#811]** We keep a spare copy of a library mod later in the load folder as a fallback.
> Something that requires that library is now being ordered against the spare copy
> instead of the real one, and starts before the real one is ready.

## What to do

Work in `/app/modthespire`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not special-case the exact scenario in a report, and do not work
  around a problem in a caller — other callers use the same machinery.
- Do not change anything under `/tests`, and do not add test files of your own.
- Behaviour that already works must keep working.
- The project targets Java 8. `mvn -o -B test-compile` builds it offline.
