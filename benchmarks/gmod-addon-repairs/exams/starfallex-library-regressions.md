# StarfallEx: reports from a scripting server

You are working on **StarfallEx**, the Garry's Mod addon that lets players write
sandboxed Lua programs ("chips") that run on the server and on clients. The addon source
is at `/app/starfallex`.

## Problem

The reports below came in from players and server staff after this build of the addon
was deployed. They are observations, not diagnoses: nobody who filed one knew which part
of the addon was responsible, and they are not all the same underlying issue.

> **[A]** `loadstring` ignores the environment table we give it. Its documentation says
> the optional third argument is the environment the compiled function runs in, but a
> chunk compiled with its own table still reads and writes the chip's globals: a name it
> should find in the supplied table comes back `nil`, and whatever it assigns leaks into
> the chip. Without a third argument, chunks should keep running in the chip's own
> environment, as they do now.

> **[B]** Turning a reference to an entity that has since been removed into text
> (`tostring`, string concatenation in our log lines) now throws an error and kills the
> chip. It is supposed to give the placeholder text `(null entity)`, which our scripts
> compare against. Live entities still print as usual.

> **[C]** `giveWeapon` on a player is completely broken for chips whose owner is allowed
> to use it: the call dies with a Lua error and nobody receives the weapon. Owners who
> are not allowed to use it are still refused, as they should be.

> **[D]** Skipping forward past the end of a `bit.stringstream` corrupts the stream:
> asking for the position afterwards raises an error, and anything written afterwards
> is lost. Skipping forward should stop at the end of the buffer (the position just
> after the last byte) and leave the stream usable, so that a later write appends.
> Skipping within the buffer works fine.

> **[E]** `math.slerpQuaternion` returns the wrong rotation. Halfway between a 90 degree
> yaw and no rotation it does not give a 45 degree yaw, and interpolating a rotation
> with itself does not even give that rotation back. At `t = 0` it correctly returns
> the first quaternion.

> **[F]** Every chip that uses `--@includedata` fails to compile with an internal
> error, so none of our chips that ship data files load at all. A file included that
> way should be available to the chip as text (for example through `getScripts()`),
> without being run as code. Plain `--@include` still works.

## What to do

Work in `/app/starfallex`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not special-case the exact scenario in a report; every chip on the
  server goes through the same libraries.
- Do not change anything under `/tests`, and do not add test files of your own to the
  addon.
- Behaviour that already works must keep working, including the permission checks that
  decide what a chip's owner may do. A change that fixes one report and breaks an
  unrelated library function is not a fix.
