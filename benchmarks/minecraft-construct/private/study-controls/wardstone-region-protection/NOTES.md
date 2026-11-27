> E0 controls for pack version 1.0.0 (2026-09-24).

# E0 notes: minecraft/construct/wardstone-region-protection

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: construct task. The workspace holds `plugin/` (the frozen `pom.xml`, a minimal `plugin.yml` and an empty main class). Controls use `root` = `plugin`: patches apply with `patch -p1` from `/app/plugin`, the `alternative` tree is copied over `/app/plugin`. Reference = skeleton + `solution/after/` (`solution/solve.sh`).

## Case roles

27 cases: 2 `static` (`check:submission-shape`, `check:offline-build`), 1 `runtime-sentinel` (`server:Wardstone is enabled`), 24 `target`, 0 `preserved`. A construct task has no preserved contract: the skeleton does nothing, and every target case fails on it.

## Controls

| control | kind | what it is | observed | admissible |
| --- | --- | --- | --- | --- |
| `starter` | starter | the unchanged skeleton | complete, fails every target case, passes the sentinel and both static checks (10/100) | yes |
| `reference` | reference | skeleton + `solution/after` | 25/25, 100 | yes |
| `target-negative-trust-any-region` | target-negative | reference that exempts owners and members of any region at the block | fails exactly `deny wins between equal priorities and the first name decides` (Hank, an owner of `zeta`, may break although `beta` decides) | yes |
| `alternative` | alternative | independent plugin written from the exam alone | 25/25, 100 | yes |

## The alternative

Written by an isolated agent that read only the public exam and the skeleton (no suite, reference or other task), compiled against the pinned API and never run on a server before the control run: eleven classes: an `EnumMap` of flags, a `RegionRegistry` that resolves flags in name order, a hand-written `regions.yml` with flow maps and quoting, atomic moves. It scored 100 on its first run. The agent listed the points it found underspecified: echoed numbers (parsed values), case-insensitive world matching, what reload does with bad entries; no case depends on them.

## Runs

Engine: real Paper 1.21.11 build 132 in the prepared verifier image, `--network=none`, through `rhenium run minecraft/construct/wardstone-region-protection` (runtime `paper-1.21.11-132-construct`).

| control | run | score | complete | failed cases |
| --- | --- | --- | --- | --- |
| reference-1 | `run-bc0bf4fe61da47a3` | 100.0 | True | none |
| reference-2 | `run-657401905bb84742` | 100.0 | True | none |
| reference-3 | `run-cd2dc8dd935547b3` | 100.0 | True | none |
| starter | `run-a1ecd21817834656` | 10.0 | True | all but the sentinel |
| target-negative | `run-b40314c50c0a48ca` | 10.0 | True | `deny wins between equal priorities and the first name decides` |
| alternative | `run-8898ea1f438a4b6b` | 100.0 | True | none |

Authoring runs before the Hub runs (same server image and suite, the trusted javac build instead of Maven) gave the same outcomes for the reference, the target-negative and the alternative.

## Pack 1.3.0 alternative maintenance, 2026-11-04

The historical independent alternative predates the public fluid-destination
contract. Its current-version run `run-9d8ce804a73d4ed4` completed but failed that
case; the failed record is retained. Maintenance adds a `BlockFromToEvent`
listener using the existing region resolver with the destination block and
`block-place` flag. It leaves allowed destinations and already cancelled events
unchanged. This is an extension of the original independent implementation,
not an untouched first attempt. Assertions, reference, skeleton and scoring are
unchanged. Fresh full real-server run `run-121eb38c1cbc45fc` completed at 100/100 with every current case passing.
