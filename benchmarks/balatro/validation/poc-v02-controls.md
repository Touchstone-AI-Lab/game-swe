# Balatro-10 v0.2 historical controls

These results were recorded on 2026-09-20 in the separate Balatro PoC. They are
imported evidence, **not new game runs or Rhenium pipeline validation on this
branch**. The JSON summary was derived from the completed source qualifications,
not from the existence of task directories.

| Slot | Task | Authored tier | Gold complete/pass | Base complete/reject | Other correct flows | Rejected mutant flows | Native processes |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| E1 | growth-v2 | easy | 3/3 | 3/3 | 1 | 3 | 10 |
| E2 | reversible-hand-limit-v1 | easy | 3/3 | 3/3 | 0 | 3 | 9 |
| E3 | seeded-effect-stream-v1 | easy | 3/3 | 3/3 | 0 | 3 | 36 |
| M1 | bounded-generator-v2 | medium | 3/3 | 3/3 | 0 | 3 | 45 |
| M2 | deck-removal-consistency-v2 | medium | 3/3 | 3/3 | 0 | 3 | 27 |
| M3 | live-joker-adjacency-v2 | medium | 3/3 | 3/3 | 0 | 4 | 20 |
| M4 | isolated-card-wear-v2 | medium | 3/3 | 3/3 | 0 | 4 | 10 |
| H1 | durable-charge-v2 | hard | 3/3 | 3/3 | 1 | 6 | 65 |
| H2 | shop-price-coherence-v2 | hard | 3/3 | 3/3 | 1 | 8 | 45 |
| H3 | pack-choice-commit-v2 | hard | 3/3 | 3/3 | 1 | 7 | 42 |

The final selection contains 108 independently sealed submissions and 309 native
processes. Gold and base ran three interleaved complete flows per task. Each Hard
task also accepted a reviewed alternative implementation with a different state
strategy. Required checks, immutable input identity and normal process cleanup
were verified by the source qualification workflow. Core-protocol assertions and
native-game assertions remain distinct; a core-only discriminator is not claimed
as a native occurrence of that abnormal protocol sequence.

The final recovery retained 88 completed flows / 249 processes and added 20 flows
/ 60 processes. One earlier H2 flow timed out during startup and remains an
excluded incomplete environment failure, with its two processes excluded from
the 309. After the operator reported disconnecting a headset, one bounded smoke
completed; only the failed flow was repeated, followed by the previously unrun
flows. The already complete flows were not rerun. There were no per-process
headset checks, and neither causality nor a permanent startup repair was proven.

The source final freeze recorded 131 passing unit tests. The later additive
recovery orchestration recorded 137 passing tests. These are historical PoC
results, not test counts for this repository change. Native operation was
visible and serial, with gamespeed=1, FAST=0 and HEADLESS=0. Difficulty remains
unmeasured; no model experiment or formal Rhenium integration was performed.

`poc-v02-summary.json` includes content fingerprints and the hashes/names of
source evidence held by the operator. It excludes absolute host paths, run IDs,
nonces, process IDs, save locations, raw traces and private assertion details.
The omitted evidence cannot be independently recomputed from this summary alone.
Another host must establish its own runtime readiness and engine evidence.

For this branch's asset preparation, the public file allowlist and hashes were
checked against the original release, then against the staged Git blobs. No
game was launched. This change adds no Python evaluator, shell script, runtime,
UI, dependencies or core behavior; full repository Python/Web/engine checks were
not rerun and no whole-repository green result is claimed. The local preparation
handoff records the exact staged checks and any unresolved issues.
