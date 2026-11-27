# Spirit Mod branching quest repair workspace

This source-only projection freezes Spirit Mod 1.5.0.48 at commit
`7ef2993d6f465f44420b2028e8666748ab31fe43`. The retained production files
implement quest debounce, branching, task serialization, and multiplayer
replication. Projection stubs provide engine and unretained-mod interfaces;
they contain no replacement implementation of the behavior under repair.

Run `python tools/smoke.py` for a compile-only public check.
