# DarkRP: reports from a live server

You are working on **DarkRP**, a Garry's Mod roleplay gamemode written in GLua.
The gamemode source is at `/app/darkrp`.

## Problem

This branch went out to a live server and the reports below came back over the
following fortnight. They are player and staff observations — nobody has diagnosed any
of them, and the person who filed each one had no idea what part of the gamemode was
responsible. They are not all the same underlying issue, and they are spread across
different subsystems.

> **[#5102]** Our staff-audit addon has been useless since we updated. Whenever one of
> us changes what another player is permitted to do, it records what that player was on
> beforehand and what we moved them to. The "beforehand" is now always identical to the
> "moved them to", so the trail is gone entirely. The change itself applies correctly —
> people end up with exactly the powers we intend. The addon listens the same way it
> always has and we have not touched it.

> **[#5103]** You can register a hitman team against a job that doesn't exist. We had a
> typo in our config (wrong variable name, so it evaluated to a job number nothing
> uses) and the server took it without a word. The hit menu then had a dead entry in
> it. It used to refuse this.

> **[#5104]** One of the lists in the buy menu has gone wrong. Our server addon takes a
> couple of the built-in entries out of that list at load and puts its own in. Since the
> update, the entries we asked it to remove are still sitting there, and different ones
> we never touched have disappeared instead. We haven't changed our addon in months.

> **[#5105]** We get `attempt to index a nil value` in console every so often. From the
> timestamps it lines up with someone answering one of those yes/no popups the server
> puts in front of you — usually when two of us answer the same one, or when whoever
> raised it has already left.

> **[#5106]** A player sent me a screenshot of `/demote` giving them complete gibberish
> instead of a readable message — a string of characters that meant nothing. I couldn't
> reproduce it at first; it only seems to go wrong when the demote doesn't land on
> anybody.

> **[#5107]** Removing a job doesn't fully remove it. We reload our job config
> regularly, and jobs we've deleted leave their vote command behind — players can still
> type the `/vote…` command for a job that isn't in the config any more.

> **[#5108]** Two of the lists in the buy menu are tied together somehow. Put something
> into one of them and it turns up in the other one as well; take it out of one and it
> goes from both. They are supposed to be separate lists with separate contents.

> **[#5109]** If two of our addons declare the same heading in the buy menu, everything
> already filed under that heading disappears. Whichever addon loads second wins and
> the first one's entries are simply gone. We work around it by making sure only one
> addon ever declares each heading, which is not sustainable.

> **[#5110]** Every so often something that comes off a player ends up half set up — it
> is there, you can see it, but it never settles; it just hangs where it appeared.
> There's a Lua error in console at the same moment. It's specifically the stuff that
> comes out of a player, not the things they spawn from a menu.

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
