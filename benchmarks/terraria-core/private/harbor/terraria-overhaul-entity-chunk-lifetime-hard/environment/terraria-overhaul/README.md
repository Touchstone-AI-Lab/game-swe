# Terraria Overhaul entity/chunk repair workspace

This is a source-only projection of Terraria Overhaul 5.0.0.38 at commit
`55c23fbde42f6fcb9eb266992475a040d14c2b84`. The five retained production
files implement the data store and the entity-backed chunk lifecycle used by
the real mod. `GameCodeBench/ProjectionStubs.cs` contains only deterministic
stand-ins for engine-owned types that are outside the redistributable slice.

Run `python tools/smoke.py` to compile the public projection. It intentionally
contains no behavioral assertions.
