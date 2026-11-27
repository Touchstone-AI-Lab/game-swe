# DarkRP: reports about what the server remembers

You are working on **DarkRP**, a Garry's Mod roleplay gamemode written in GLua.
The gamemode source is at `/app/darkrp`.

## Problem

The reports below came in from server owners after this branch went out. They are all
about players — what the server keeps on record for them, and what it makes of the
values and names it is handed. They are observations, not diagnoses: nobody who
filed one knew which part of the gamemode was responsible, and they are not all the same
underlying issue.

> **[#8201]** Everyone joining for the first time since the update starts out the wrong
> way round: they are carrying the amount they were supposed to earn each payday, and
> earning the amount they were supposed to be carrying. Anyone who already had an
> account is completely unaffected.

> **[#8204]** Spend down to exactly nothing and it does not stick. Come back later and
> the old balance is there again, as if the last purchase never happened. Leave so much
> as a single coin and everything behaves.

> **[#8207]** Paying someone who is not currently connected does nothing at all. The
> transfer reports success and the sender is charged, but the moment that player next
> joins they have exactly what they had before. Paying someone who is connected works
> perfectly.

> **[#8210]** Our logging add-on records every name change along with what the person
> was called beforehand. That second value is now always identical to the name they
> changed to, so the log cannot tell us who anyone used to be.

> **[#8213]** People have started setting their name to a single character. Staff cannot
> tell them apart in any list, and the server used to turn these down.

> **[#8216]** Nobody can take a name any more. Whatever is entered, the server insists
> it is already in use — including names that plainly nobody on the server has.

> **[#8219]** One of our add-ons occasionally hands over a nonsense figure — the result
> of a division that went wrong. That used to be turned away. It is now accepted and
> written into somebody's account, and from that point on every sum touching that
> account is nonsense as well.

> **[#8222]** Any staff command aimed at a player whose name contains a bracket now dies
> with a Lua error instead of doing anything. Dashes and percent signs do it too. Plain
> alphabetical names are fine.

> **[#8225]** Typing a staff command and forgetting to say who it is for acts on somebody
> anyway — always whoever happens to be first in the list. It used to do nothing at all.

## What to do

Work in `/app/darkrp`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not paper over a symptom by special-casing the exact scenario in
  a report, and do not change a caller to work around a helper that is behaving
  incorrectly — other callers use the same helper.
- Do not change anything under `/tests`, and do not add test files of your own to the
  gamemode.
- Behaviour that already works must keep working. These routines are used throughout
  the gamemode and by third-party addons, so a change that fixes one report and breaks
  an unrelated caller is not a fix.
