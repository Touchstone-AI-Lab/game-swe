# DarkRP: reports against the shared helper libraries

You are working on **DarkRP**, a Garry's Mod roleplay gamemode written in GLua.
The gamemode source is at `/app/darkrp`.

## Problem

DarkRP ships small helper libraries that both the gamemode itself and third-party
addons build on. The reports below came from server staff and from addon authors
after this branch went out. They are observations of what happened, not diagnoses —
nobody who filed one knew which part of the gamemode was responsible, and several of
them assumed the fault was in their own addon until it turned up elsewhere too.

They are not all the same underlying issue, and they are spread across more than one
helper.

> **[#7301]** Our addon keeps its own table of things, filed under ids we chose. We
> ask one of DarkRP's helpers to narrow that table down to the entries we care about,
> and the result comes back renumbered from one — every id we filed them under is
> gone, so the very next lookup finds nothing. It behaves itself when the table is a
> plain ordered list; it's only the ones we file under our own ids that come back
> scrambled.

> **[#7304]** Doors we had shared with specific people quietly stop being shared. A
> player is granted access, it works, and some time later the grant is simply not
> there any more and nobody removed it. It seems to happen when the list of granted
> people is touched for any reason.

> **[#7307]** Anything the gamemode builds up by combining a list together comes out
> back to front. The pieces are all present and none are missing — the order is just
> reversed from what it used to be, and from what the config says.

> **[#7310]** We trim the last thing off a list before handing it on. What we get back
> has lost the *first* thing instead, and still has the one we meant to remove.

> **[#7313]** Same shape of problem at the other end: we drop the leading thing off a
> list, and what comes back has lost the trailing one and kept the leader.

> **[#7316]** Fields that are allowed to be left out are no longer checked when you do
> fill them in. We had a typo in one of ours — a word where a number belongs — and it
> used to be refused at load with a clear complaint. Now it loads without a murmur and
> something downstream misbehaves much later, which took us a day to trace back.

> **[#7319]** A field that is supposed to require at least one entry now accepts a
> completely empty one. The thing then exists with nothing in it and behaves oddly
> everywhere it is used.

> **[#7322]** A numeric floor is behaving like a ceiling. We set a floor and the big
> values are the ones being turned away, while the small values we meant to exclude go
> straight through.

## What to do

Work in `/app/darkrp`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not paper over a symptom by special-casing the exact scenario in
  a report, and do not change a caller to work around a helper that is behaving
  incorrectly — other callers depend on the same helper.
- Do not change anything under `/tests`, and do not add test files of your own to the
  gamemode.
- Behaviour that already works must keep working. Several of these helpers are used
  throughout the gamemode, so a change that fixes one report and breaks an unrelated
  caller is not a fix.
