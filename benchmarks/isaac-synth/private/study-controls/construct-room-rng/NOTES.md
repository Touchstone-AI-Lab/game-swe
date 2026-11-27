# isaac-rebirth/synth/construct-room-rng — E0 notes

Construct task "Build deterministic per-room random streams", written from an empty `mod/` starter (only `main.lua` and `metadata.xml`);
the reference is `solution/reference.lua` copied over `mod/main.lua`.
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 36 cases: 35 `target`, 1 `static`.
- Roles come from the 2026-11-02 E0 baseline of catalog 0.1.1 on the real game: the empty starter fails every case, so every case is a target and none is preserved. Clauses are not yet split per exam paragraph: each case cites the whole requested behavior.

## Controls (real Afterbirth+ game through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | the empty starter | `run-fdd0f6816dbd4f1a` | score 10; fails all 35 cases (target); admissible |
| `reference` | reference | `solution/reference.lua` over `mod/main.lua` | `run-6722a5382e474c2c` | score 100; every case passes; admissible |

Recorded on 2026-11-02 (catalog 0.1.1) with `rhenium-study e0 baseline` and checked with `e0 check-maps` and `e0 run`,
in a study directory of its own on the Lab host. The pack's own acceptance controls (empty starter,
reference and unrelated change on two hosts) are in `private/harbor/validation/README.md`.
