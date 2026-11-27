# Maintainer notes

This task freezes GPL-3.0-only source from
`SirPlease/L4D2-Competitive-Rework` at `6cb2fcbe092776c8287944ab541244e2b8262662`.
The three broken behaviors are reversions of real upstream repairs, except that
the map-name oracle uses SourceMod `FindMap` instead of the upstream
`GetMapDisplayName` call: the latter does not resolve `c1m2` to an installed map
on the pinned Linux runtime and therefore cannot satisfy the public contract.

The verifier compiles each submitted target and runs six isolated L4D2 server
boots. Isolation matters because a failed forced changelevel can leave Director
transition state dirty. Tests use real player/weapon entities, engine weapon-info
memory, Confogl's named global-forward boundary, SourceMod `ForceChangeLevel`,
Director changelevel arguments, and actual map loads. They do not compare source
text or private helper names.

`tests/deps/left4dhooks` is verifier-only GPL-3.0-or-later source used to provide a
frozen public runtime dependency. It is compiled inside the verifier; no `.smx`
or Valve file is committed. The agent receives the full Competitive Rework source
tree and a compile-only public smoke test, but not tests, dependency fixtures, or
the reference solution.

Publication gate: base, oracle, nop, three single-group predicates, at least two
complete differential alternatives, contract hashes, and any model calibration
must all refer to the same frozen verifier revision.
