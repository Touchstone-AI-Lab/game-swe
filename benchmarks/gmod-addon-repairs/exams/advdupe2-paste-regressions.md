# Advanced Duplicator 2: reports from a building server

You are working on **Advanced Duplicator 2**, the Garry's Mod addon that copies
contraptions ("dupes"), saves them to files and pastes them back. The addon source is at
`/app/advdupe2`.

## Problem

The reports below came in from server operators and builders after this build of the
addon went out. They are observations, not diagnoses: nobody who filed one knew which
part of the addon was responsible, and they are not all the same underlying issue.

> **[A]** Props that were saved at a non-default model scale come back looking right
> after a paste, but they do not behave at that size. A crate saved at double scale is
> drawn at double size, yet physically it is still a normal crate: its collision hull
> and physical volume are those of the unscaled model, so things sink into it. Props
> saved at the normal scale paste exactly as before.

> **[B]** When a dupe contains an entry that cannot be recreated - we see it with files
> whose stored entity data has been corrupted - the paste gives up on that entry as it
> should, but the server keeps a half-made entity of that class for every attempt. The
> leftovers are never spawned, belong to nobody and pile up until the map changes. An
> entry that fails to paste must leave nothing behind.

> **[C]** Props a player pasted can no longer be released with the physics gun's
> "unfreeze everything I froze" (double-tapping reload). The pasted props arrive frozen,
> as they should, but they stay frozen afterwards, while props the same player froze by
> hand are released. Pasted props should count as frozen by the player who pasted them.

> **[D]** Ropes in a pasted dupe are counted against the wrong allowance. They use up
> the player's general constraint allowance instead of the rope allowance
> (`sbox_maxropeconstraints`), and that rope limit is not enforced for pasted ropes at
> all: with the limit set to 0 a player can still paste ropes. Pasted ropes should be
> counted and limited like ropes made with the rope tool; welds and the other
> constraints keep counting as constraints.

> **[E]** Dupe names with spaces around folder separators or the extension dot, such as
> `my dupes / sub dir . txt`, produce oddly named folders and files with stray spaces
> at the edges. The addon's name clean-up routine (`AdvDupe2.SanitizeFilename`)
> should remove the spaces directly around `/`, `\` and
> `.` (`my dupes/sub dir.txt`). Everything it already does must keep working: other
> spaces are kept, runs of spaces still collapse to one, and quotes and colons are
> still replaced with underscores.

## What to do

Work in `/app/advdupe2`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not special-case the exact scenario in a report; the same code
  paths serve every dupe, player and entity class.
- Do not change anything under `/tests`, and do not add test files of your own to the
  addon.
- Behaviour that already works must keep working. Copying, pasting, saving and loading
  dupes are used by every builder on the server, so a change that fixes one report and
  breaks an unrelated paste is not a fix.
