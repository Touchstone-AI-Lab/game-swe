# DarkRP: bug reports against this release branch

You are working on **DarkRP**, a Garry's Mod roleplay gamemode written in GLua.
The gamemode source is at `/app/darkrp`.

## Problem

This branch missed a batch of fixes. Below is what users reported. Nobody has
diagnosed any of it — these are observations, not causes. They are not all the same
underlying issue, and they are spread across different parts of the gamemode.

> **[#4415]** Random Lua errors on a busy server from things players spawn — dropped
> weapons and ammo crates especially. When it happens the item ends up half set up:
> it exists but never settles properly.

> **[#4418]** Our admins keep asking why nothing happens when they try to unrestrict
> a weapon and forget to type which one. Silent — no error, no confirmation, nothing,
> and sometimes the console spits an error instead.

> **[#4421]** The voting module throws `attempt to index a nil value` sometimes. I
> can't reliably reproduce it; it seems to happen while a vote is being cleaned up.

> **[#4424]** My job pack's installer broke after updating. It does
> `local id = DarkRP.createJob(...)` and then uses `id` to finish setting the job up.
> Now it gets nothing back and the rest of the installer errors out on a nil.

> **[#4431]** Our shop script looks shipments up by name. It works for most of them
> but a few just never resolve. The ones that work all seem to have all-lowercase
> names. A colleague renamed one to lowercase and it started working, but we would
> rather not rename every shipment's display name to dodge a bug.

> **[#4423]** *(feature request, same milestone)* There is no supported way for an
> addon to ask which players the server currently has arrested. We need three
> functions on the `DarkRP` namespace — `DarkRP.iterateArrestedPlayers`,
> `DarkRP.arrestedPlayers` and `DarkRP.arrestedPlayerCount` — giving an iterator
> usable directly in a `for ... do` loop, a plain list, and a count. They have to
> agree with one another and must work when nobody is arrested. Publish them the way
> the rest of the police API is published.

## Task

Diagnose and fix everything above. Behaviour on the paths that already work must not
change.

## Notes

- Server-side code. Files are named `sv_*.lua` (server), `sh_*.lua` (shared) and
  `cl_*.lua` (client); entity code lives under `entities/`.
- Do not modify anything under `/tests`.
- The grading harness boots a real headless Garry's Mod dedicated server with the
  DarkRP gamemode loaded and runs an automated test suite against it.
