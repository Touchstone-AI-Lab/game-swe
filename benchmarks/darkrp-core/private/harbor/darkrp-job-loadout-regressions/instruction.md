# DarkRP: reports about what a job hands its players

You are working on **DarkRP**, a Garry's Mod roleplay gamemode written in GLua.
The gamemode source is at `/app/darkrp`.

## Problem

The reports below came in from server owners after this branch went out. They are all
about the things a server owner writes down in configuration — jobs, categories — and
what the players of those jobs actually end up with. They are observations, not
diagnoses: nobody who filed one knew which part of the gamemode was responsible, and
they are not all the same underlying issue.

> **[#9101]** One of our jobs had its list of player models emptied by accident. The
> server took it without a murmur, and every single person who picks that job now walks
> around as a giant red ERROR sign. It used to tell us at load that the job was wrong.

> **[#9104]** A job we wrote with no description at all is accepted these days. The menu
> then shows an empty panel where the text should be, and nobody can tell what the job
> is. We would much rather be told about it up front.

> **[#9107]** We added a category and forgot to say whether it starts open or closed. It
> is taken anyway, and the menu then draws it differently depending on who is looking.

> **[#9110]** One of our jobs is meant to be rooted to the spot — we set its walking
> speed to zero deliberately. Players of that job walk around at the ordinary server
> speed as if we had never set it. Every other number we try is respected.

> **[#9113]** Our jobs that are supposed to start you on low health now start you on
> full. The ceiling is applied correctly — it is the value they are supposed to begin
> the round on that gets ignored.

> **[#9116]** Our police are sprinting at the civilian speed and the civilians are
> sprinting at the police speed. We never set a running speed on either job — we rely on
> the two server settings — and the two have swapped over.

> **[#9119]** A job of ours declares a health ceiling of zero on purpose. Players of that
> job get the ordinary default of a hundred instead, as though we had never said it.

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
