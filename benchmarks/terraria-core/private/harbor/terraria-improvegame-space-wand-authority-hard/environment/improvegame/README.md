# Quality of Terraria Space Wand repair workspace

This source-only projection freezes Quality of Terraria 1.8.3 at commit
`284fa78849f2234e70300f101a92a36db34b256d`. The retained production files
implement Space Wand geometry, world mutation, inventory consumption, and
multiplayer execution. Projection stubs provide engine APIs and small
interfaces from unretained partials; they contain no replacement implementation
of the behavior under repair.

Run `python tools/smoke.py` for a compile-only public check.
