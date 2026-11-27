> E0 controls for pack version 1.0.0 (2026-09-24).

# E0 notes: minecraft/construct/blocktrail-block-log-rollback

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: construct task. The workspace holds `plugin/` (the frozen `pom.xml`, a minimal `plugin.yml` and an empty main class). Controls use `root` = `plugin`: patches apply with `patch -p1` from `/app/plugin`, the `alternative` tree is copied over `/app/plugin`. Reference = skeleton + `solution/after/` (`solution/solve.sh`).

## Case roles

27 cases: 2 `static` (`check:submission-shape`, `check:offline-build`), 1 `runtime-sentinel` (`server:BlockTrail is enabled`), 24 `target`, 0 `preserved`. A construct task has no preserved contract: the skeleton does nothing, and every target case fails on it.

## Controls

| control | kind | what it is | observed | admissible |
| --- | --- | --- | --- | --- |
| `starter` | starter | the unchanged skeleton | complete, fails every target case, passes the sentinel and both static checks (10/100) | yes |
| `reference` | reference | skeleton + `solution/after` | 25/25, 100 | yes |
| `target-negative-rollback-oldest-first` | target-negative | reference whose rollback walks the qualifying changes in id order | fails exactly `rollback undoes changes newest first` (replied `1 restored, 1 skipped`, expected `2 restored, 0 skipped`) | yes |
| `alternative` | alternative | independent plugin written from the exam alone | 25/25, 100 | yes |

## The alternative

Written by an isolated agent that read only the public exam and the skeleton (no suite, reference or other task), compiled against the pinned API and never run on a server before the control run: a `TabExecutor` with a subcommand table, a two-pass loader (change lines, then `undo` lines), one timestamp and one append per explosion, BigInteger parsing of page, radius and seconds. It scored 100 on its first run. The agent listed the points it found underspecified: the world name echoed in replies (the loaded world's name), numbers beyond int range, unknown materials in log lines; no case depends on them.

## Runs

Engine: real Paper 1.21.11 build 132 in the prepared verifier image, `--network=none`, through `rhenium run minecraft/construct/blocktrail-block-log-rollback` (runtime `paper-1.21.11-132-construct`).

| control | run | score | complete | failed cases |
| --- | --- | --- | --- | --- |
| reference-1 | `run-b4a1329d416b46e9` | 100.0 | True | none |
| reference-2 | `run-f235c3838bb547c4` | 100.0 | True | none |
| reference-3 | `run-c3be18978b1d4125` | 100.0 | True | none |
| starter | `run-ea54b5b4781f4015` | 10.0 | True | all but the sentinel |
| target-negative | `run-6583382450494afe` | 10.0 | True | `rollback undoes changes newest first` |
| alternative | `run-cad1d4bf486947eb` | 100.0 | True | none |

Authoring runs before the Hub runs (same server image and suite, the trusted javac build instead of Maven) gave the same outcomes for the reference, the target-negative and the alternative.

## Pack 1.3.0 alternative maintenance, 2026-11-04

The historical independent implementation predates the twelve-field log and exact
block-state rollback contract. Current-version `run-8f623072751141bc` completed
but failed the log-format and directional-state cases; that evidence is retained.
The alternative now records full before/after block data for each event, writes
and reads twelve-field lines while preserving legacy ten-field material-only
entries, and compares/restores complete states during rollback. It is a maintained
extension of the original independent implementation, not an untouched first
attempt. Assertions, reference, skeleton and scoring are unchanged. Fresh full real-server run `run-b948b3dc3fab4d0a` completed at 100/100 with every current case passing.
