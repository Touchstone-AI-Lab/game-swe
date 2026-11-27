# Maintainer notes

## Rhenium Hub integration

The measurements below describe the frozen Harbor 0.20.0 snapshot before its
Rhenium 0.5 integration. The Hub exposes the same authored prompt from
`benchmarks/isaac-core/exams/isaac-exodus-release-regressions.md`; its only text
change replaces the container path `/app/exodus` with the anonymous workspace path
`exodus/`. The integrated exam SHA-256 is
`5aeee4ec6e4374f5bd17bf5b5915f9d772eaf20c7c4f7a3c440b5ea1a52939da`.

The old Harbor-specific model runner is not retained in the integrated pack. Rhenium
materializes the public source and prompt, while private tests, the gold patch, and
the validation history stay below this private provenance tree.

`environment/exodus/save1.dat` and `save2.dat` are intentionally tracked despite
the upstream `*.dat` ignore rule. They are deterministic empty mod-data fixtures
(`[]` and `{"Register":[]}`) that were present in the validated Harbor snapshot;
without initialized mod data, Exodus unconditionally decodes `LoadData()` during
startup. Rhenium copies both fixtures into every fresh starter.

## Provenance

- Source: `EchoGekko/Exodus`; its root `LICENSE.txt` declares MIT.
- The vendored binary room, art, and audio files match that upstream commit, but
  their individual provenance has not been independently verified. Resolve this
  release-review item before treating the root license as proof for every asset.
- Fixed source commit: `7f88cea2d9549128679017dc1fca438efd044b90`.
- The task tree reverses relevant `main.lua` hunks from twenty upstream fixes:
  `07b50ff1`, `78800008`, `3a8ea05d`, `63161cb4`, `cce19e43`, `50ddc4e`,
  `8996d35`, `210cd57`, `406a853`, `999e32c`, `6da5cbf`, `08ac37c`,
  `61193a7`, `315c253`, `a2de722`, `0d57715`, `f1146fd`, `0dfd838`,
  `0ff59f3`, and `e513560`.
- Both broken and reference trees contain the same startup compatibility guard for a
  zero pre-run seed. It removes two harmless engine assertions and is not part of the
  scored patch.
- Historical source under the upstream `removed/` directory is deliberately absent
  from both trees. It is dead at runtime and exposed several reference fixes directly.

The checked-in gold patch is a thirty-two-hunk diff against `main.lua`. Its input and
output SHA-256 values are, respectively,
`9f307160a7f481b64354b8341a974817bb8bc8cff899b32164627fc6d1ba51c6` and
`ee5753ae7da0c9308f5e76c43674553d06c7200b7a3e891e66e7bd95ae1d93c6`.

## Runtime boundary

The repository contains the fixed upstream mod snapshot and verifier code. It does
not contain or redistribute the installed game runtime, Steam account credentials,
or an offline ticket. The upstream root declares MIT; see the per-asset provenance
review item above.

The verifier uses Harbor's separate-environment mode. Only `/app/exodus` is copied
from the agent container. Rhenium builds the private verifier locally from an isolated,
zero-progression Steam client state and records its immutable image ID. The source
cache and image must never be exported or pushed.

Prepare that host with:

```bash
rhenium auth login steam
rhenium runtime prepare isaac-rebirth/afterbirth-plus-1.06.t1
```

The managed runtime requires a legal App 250900 entitlement and performs the one-time
official-client Offline Mode bootstrap as an explicit action. See `PROVISIONING.md`.

## Verifier design

The v4.1 suite performs thirty-five live-game assertions: twenty-four primary target
behaviors and eleven runtime or regression guards. It starts three independent native
game processes:

| process | cases | purpose |
|---|---:|---|
| main | 30 | broad report coverage, negative James scope, and preservation guards |
| James | 2 | runtime sentinel and positive custom-character mapping behavior |
| secret room | 3 | runtime sentinel, Blue Moon, and The Apocryphon |

The separate James process is required because Afterbirth+ `v1.06.T1` does not expose
`EntityPlayer:ChangePlayerType`. It starts the run as Exodus's custom James character
through the game's real character-selection command instead of simulating the type.
Blue Moon and The Apocryphon remain isolated because the broken Blue Moon behavior can
destroy the secret-room boundary and prevent later room updates.

The verifier requires all three exits, all thirty-five named cases exactly once, three
suite summaries, and no fatal marker. Each process has a PASS_TO_PASS runtime sentinel.
Steam may retain a just-finished run in its in-memory offline cache even after ordinary
game-state files are removed, so each suite explicitly establishes the inventory and
state it observes. `validation/case-contracts.tsv` maps every case to its public report
sentence or runtime role; its case-name set is checked against `tests/test.sh`.

The submission and verifier mods share one game process, and the current reward gate
parses unauthenticated markers from the shared game log. This is adequate only under
the benchmark's honest-code assumption; a deliberately adversarial submission may be
able to forge those markers. An externally authenticated result channel remains a
release blocker before promotion beyond In Development.

## Validation matrix

The v4.1 controls were run on 2026-08-08 against native Linux Afterbirth+
`v1.06.T1`, Steam App 250900 build `22878971`.

| tree / control | real-game result | reward |
|---|---:|---:|
| broken base | 9 pass / 26 fail | 0 |
| complete gold patch | 35 pass / 0 fail | 1 |
| each of 20 single-report candidates | 10-12 pass / 23-25 fail | 0 |

The nine base passes are intentional guards: three runtime sentinels plus Mutant
Clover room reset, mature Beehive wobble, normal Deja Vu return, preserved Grid Worm
turn cadence, Broken Glasses floor reset, and the positive James behavior. The broken
tree fails every report discriminator and the two additional state-preservation guards
that exercise Tragic Mushroom diminishing gains and Anamnesis charge persistence.

Every single-report candidate was generated from the broken hash and run through all
three native game processes with 4 CPUs and 8 GiB. All 20/20 completed with zero fatal
markers and changed only their mapped cases. Overlapping upstream hunks were split so
EX-191 does not fix EX-303, EX-303 does not fix EX-191 or EX-311, and EX-335 does not
fix EX-342. Candidate hashes and observed flips are recorded in
`validation/predicate-matrix.tsv`; `scripts/validate-predicates.sh` rebuilds and checks
the matrix.

Official Harbor `0.20.0` controls used separate-environment artifact transfer, not a
direct bind mount:

| Harbor agent | complete runtime evidence | exceptions | reward |
|---|---|---:|---:|
| `oracle` | 35 pass / 0 fail; 3 processes; 0 fatal | 0 | 1.0 |
| `nop` | 9 pass / 26 fail; 3 processes; 0 fatal | 0 | 0.0 |

The table above was first established on a pre-release v4.1 snapshot. The final
frozen-snapshot checksum and trial IDs are recorded outside this task directory in the
repository root README: Harbor hashes the entire task directory, so writing those
values back here would itself create a different checksum.

Run the direct controls on the licensed runtime host with:

```bash
./scripts/validate-task.sh \
  "$PWD" gcb-isaac-exodus-verifier:abp-v1.06.t1

./scripts/validate-predicates.sh \
  "$PWD" gcb-isaac-exodus-verifier:abp-v1.06.t1 \
  "$PWD/.predicate-validation"
```

## Judging an attempt

Verify a submitted tree with the same private image. A reward of zero counts as an agent
failure only when all three game processes and all thirty-five cases ran, and only after
screening the diff for a correct alternative that the suite accidentally rejects. Do not
treat a game process that failed to start as an agent failure.

The public prompt explicitly states both Grid Worm cadence preservation and normal Deja Vu
return preservation. The cadence sentence was added in v4.1 together with the Grid Worm
cadence guard.
