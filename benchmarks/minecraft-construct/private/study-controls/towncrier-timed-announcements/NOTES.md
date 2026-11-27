> E0 controls for pack version 1.0.0 (2026-09-24).

# E0 notes: minecraft/construct/towncrier-timed-announcements

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: construct task. The workspace holds `plugin/` (the frozen `pom.xml`, a minimal `plugin.yml` and an empty main class). Controls use `root` = `plugin`: patches apply with `patch -p1` from `/app/plugin`, the `alternative` tree is copied over `/app/plugin`. Reference = skeleton + `solution/after/` (`solution/solve.sh`).

## Case roles

22 cases: 2 `static` (`check:submission-shape`, `check:offline-build`), 1 `runtime-sentinel` (`server:TownCrier is enabled`), 19 `target`, 0 `preserved`. A construct task has no preserved contract: the skeleton does nothing, and every target case fails on it.

## Controls

| control | kind | what it is | observed | admissible |
| --- | --- | --- | --- | --- |
| `starter` | starter | the unchanged skeleton | complete, fails every target case, passes the sentinel and both static checks (10/100) | yes |
| `reference` | reference | skeleton + `solution/after` | 20/20, 100 | yes |
| `target-negative-interval-keeps-old-timer` | target-negative | reference whose `/crier interval` saves the value but does not restart the timer | fails exactly `interval changes the period and is saved` (no announcement 50 ticks after the change) | yes |
| `alternative` | alternative | independent plugin written from the exam alone | 20/20, 100 | yes |

## The alternative

Written by an isolated agent that read only the public exam and the skeleton (no suite, reference or other task), compiled against the pinned API and never run on a server before the control run: the last-loaded YAML document edited in memory (NUL path separator, wide dump), lazily built cycles, timers created in file order, one regex pass for placeholders. It scored 100 on its first run. The agent listed the points it found underspecified: the order of the `remove` checks (index first, then last message; the reference agrees), placeholders in the prefix (replaced in both), YAML 1.1 boolean group names (avoided by the suite).

## Runs

Engine: real Paper 1.21.11 build 132 in the prepared verifier image, `--network=none`, through `rhenium run minecraft/construct/towncrier-timed-announcements` (runtime `paper-1.21.11-132-construct`).

| control | run | score | complete | failed cases |
| --- | --- | --- | --- | --- |
| reference-1 | `run-11e7d194cda9457e` | 100.0 | True | none |
| reference-2 | `run-16c770c34b3841fc` | 100.0 | True | none |
| reference-3 | `run-ded44f5e900541f3` | 100.0 | True | none |
| starter | `run-eb6378d94e914b14` | 10.0 | True | all but the sentinel |
| target-negative | `run-5cf00fe132114d28` | 10.0 | True | `interval changes the period and is saved` |
| alternative | `run-094d05592dbc4361` | 100.0 | True | none |

Authoring runs before the Hub runs (same server image and suite, the trusted javac build instead of Maven) gave the same outcomes for the reference, the target-negative and the alternative.
