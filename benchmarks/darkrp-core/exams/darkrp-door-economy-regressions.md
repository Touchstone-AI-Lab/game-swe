# DarkRP: reports from a live server

You are working on **DarkRP**, a Garry's Mod roleplay gamemode written in GLua.
The gamemode source is at `/app/darkrp`.

## Problem

The reports below came in from a server running this branch. They are player and staff
observations — nobody has diagnosed any of them, and the person who filed each one had
no idea what part of the gamemode was responsible. They are not all the same underlying
issue, and they are spread across different subsystems.

> **[#6218]** Two accounts went from broke to the top of the richest list inside a day
> and neither of them has been doing anything that earns. No admin gave it to them, the
> logs show no transfer, and the regular income everyone gets is the normal amount. What
> we did work out is that it happens when they *spend*: they come away with more than
> they started with, and the more they buy the richer they get. Nothing is being
> duplicated — no extra props, no extra items, the count of what they own is right. It
> is the balance itself that moves the wrong way.

> **[#6221]** Door owners can't lock their own doors. Buy a door, walk up to it, hit
> lock, nothing happens. Adding yourself as a co-owner of your own door works around it,
> which is obviously not how it is meant to go.

> **[#6224]** Our door-sharing setup has stopped behaving. We hand out access to
> specific people, and now the person we granted it to gets nothing, while every so
> often somebody who was never on the list can get in. It seems to depend on who joined
> when — a rejoin sometimes changes who it lets through.

> **[#6227]** The first job in each of our group-chat lines can't see that group chat.
> Everyone else on the line can. We list several jobs per group chat and it is always
> the first one that is left out.

> **[#6230]** An addon we run adds a handful of things players can type. Since the
> update some of them do nothing whatsoever — no response, no complaint that it isn't
> recognised, nothing. The author swears they changed nothing and the rest of what the
> same addon adds still works fine.

> **[#6233]** The notice our crime boss writes up for their crew hasn't changed in a
> week. I assumed nobody was bothering, but the players whose job it is say they have
> been trying and it just doesn't take. Nothing appears in console. Everyone else can
> still read whatever was put up there before.

> **[#6236]** Cash that ends up loose on the ground doesn't get treated as cash. What
> lands when somebody dies, or what a player deliberately puts down, just sits there
> like scenery — none of the things that are supposed to happen around it happen. What
> you take out of the buy menu behaves correctly.

> **[#6239]** We set aside a few doors for one particular job to use. The people in that
> job can't lock or unlock them. It works if we name each person individually instead,
> which defeats the point of setting them aside for the job in the first place.

> **[#6242]** We took one of our own additions back out of the buy menu and players can
> still type the word for it and get it. The entry is gone from the menu itself — it is
> only the typing that still works. The ones we add as jobs come out cleanly.

## What to do

Work in `/app/darkrp`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not paper over a symptom by catching an error and discarding it,
  and do not special-case the exact scenario in a report.
- Do not change anything under `/tests`, and do not add test files of your own to the
  gamemode.
- Behaviour that already works must keep working — several of these live next to code
  paths that are fine.
