# DarkRP: reports about things that will not register properly

You are working on **DarkRP**, a Garry's Mod roleplay gamemode written in GLua.
The gamemode source is at `/app/darkrp`.

## Problem

The reports below came in from server owners and addon authors after this branch went
out. Most of them are about *declaring* something to the gamemode — a vehicle, a
grouping, a shortcut, a value that gets sent to clients — and the declaration not
taking properly. They are observations, not diagnoses. Nobody who filed one knew
which part of the gamemode was responsible, and they are not all the same underlying
issue.

> **[#8401]** A vehicle in our config is refused at load with a complaint that the
> game has never heard of it. It is spelled exactly the way the game's own list
> spells it, just not in the same case, and that never used to matter. Writing it in
> the same case the list uses makes the complaint go away, which is not something we
> should have to care about.

> **[#8404]** We set aside a batch of doors for a group and gave the group a name. The
> doors behave correctly, but nothing that displays the grouping can tell you what it
> is called any more — the name we gave it is simply not on it.

> **[#8407]** Our shortcuts have stopped doing anything. We set up a short word that
> is supposed to stand in for a longer one, and now typing the short one does nothing
> at all while the long one still works. The short word is definitely registered — it
> just seems to be an empty shell with nothing behind it.

> **[#8410]** The list of things you can type comes out backwards. It used to read
> from the start of the alphabet; now it reads from the end. Nothing is missing, the
> order is just inverted.

> **[#8413]** We declare a value that gets sent to clients, and we re-declare it when
> our addon reloads. Since the update, after a reload the writing side is fine but the
> reading side is still the old one, so what arrives on the client is interpreted with
> the wrong routine and comes out as nonsense.

> **[#8416]** We take a grouping of jobs apart at runtime. Afterwards the jobs still
> behave as though they are grouped — whatever we did to remove it clearly did not
> release the jobs that were in it, because acting on one still drags in the others.

> **[#8419]** A value we attach to doors reads back as something else entirely. The
> one we registered immediately after it is what we get, as if the slot we were given
> is not the slot our value went into.

> **[#8422]** Only one of the jobs we list as being able to read a notice can actually
> read it. We list several; the first one on the list is fine and the rest see
> nothing, as though the rest of the list was never taken in.

## What to do

Work in `/app/darkrp`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not paper over a symptom by special-casing the exact scenario in
  a report, and do not change a caller to work around a registration routine that is
  behaving incorrectly — other callers use the same routine.
- Do not change anything under `/tests`, and do not add test files of your own to the
  gamemode.
- Behaviour that already works must keep working. These routines are used throughout
  the gamemode and by third-party addons, so a change that fixes one report and
  breaks an unrelated caller is not a fix.
