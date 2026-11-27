# Garry's Mod addon repair pack

Multi-defect repair tasks built from real open-source Garry's Mod addons. Each task
vendors one upstream addon tree at a fixed commit (the reference) and reverts several
real upstream bug-fix commits (the starter). A hidden [GLuaTest](https://github.com/CFC-Servers/GLuaTest)
suite then boots a real headless Garry's Mod dedicated server with the submitted addon
installed and checks each repaired behaviour, plus neighbouring behaviour that must not
break, through the addon's public surfaces.

```text
benchmarks/gmod-addon-repairs/
├── benchmark.json            schema-v2 plugin and pack selection (pack ID addon-repairs)
├── catalog.json              five tasks, bilingual metadata
├── runtimes.json             the digest-pinned dedicated-server image (own runtime ID)
├── exams/                    the public problem statement for each task
├── validation/               two-way validation and control records
└── private/
    ├── harbor/               the Harbor task packages (environment, tests, solution)
    └── study-controls/       E0 clause maps, control patches and notes
```

The pack is discovered and executed by the Hub through the `rhenium-garrys-mod`
plugin: `rhenium packs` lists `garrys-mod/addon-repairs`, and evaluation runs through
the plugin's GLuaTest evaluator. See [Garry's Mod support](../../docs/games/garrys-mod.md)
for runtime setup.

## Tasks

| Task | Upstream addon | Licence | Base commit | Reverted upstream fixes | Cases (target / preserved / sentinel) |
| --- | --- | --- | --- | ---: | --- |
| `advdupe2-paste-regressions` | [wiremod/advdupe2](https://github.com/wiremod/advdupe2) | Apache-2.0 | `e3ffa3c5` | 5 | 6 / 4 / 1 |
| `cfw-contraption-regressions` | [ACF-Team/CFW](https://github.com/ACF-Team/CFW) | GPL-3.0 | `5bb6f9fe` | 6 (4 reports) | 6 / 3 / 1 |
| `starfallex-library-regressions` | [thegrb93/StarfallEx](https://github.com/thegrb93/StarfallEx) | BSD-3-Clause | `0e8e3d7e` | 6 | 6 / 6 / 1 |
| `wiremod-e2-library-regressions` | [wiremod/wire](https://github.com/wiremod/wire) | Apache-2.0 | `f31ba74e` | 6 | 6 / 4 / 1 |
| `wiremod-gates-chips-regressions` | [wiremod/wire](https://github.com/wiremod/wire) | Apache-2.0 | `f31ba74e` | 6 | 7 / 6 / 1 |

Every defect is an upstream fix reverted; none is hand-injected. Each task's
`task.toml` records the source repository, licence, base commit, the full SHAs of the
reverted fixes (`reverted_fixes`), how each was reverted, and what each hidden case
drives. The reference solution (`solution/after/`, `solution/gold.patch`) is the
upstream code at the base commit.

Public exams describe only player-, builder- or developer-visible observations, as
lettered reports. They omit fix commits, pull requests, file and line hints, defect
counts and diagnoses. Where a hidden case calls a specific public API (for example
`AdvDupe2.SanitizeFilename` or a CFW contraption's `totalMass`), the exam names that
API so the asserted behaviour is derivable from the exam and the addon's own
documentation.

## Hidden suites and the result channel

Each verifier copies the submitted addon to `garrysmod/addons/<name>`, boots the
sandbox gamemode on `gm_construct` without network, and runs the private suite as the
only GLuaTest project. Cases use real entities, bots, constraints, wires, chips and
the addons' own public APIs; no case reads private implementation state to decide an
outcome. Each suite has one load sentinel, one or more target cases per report and at
least two preserved cases that already pass on the starter.

The pack reuses the DarkRP pack's patched-runner collector byte for byte: a nonce-bound
per-case audit, an unchanged-harness hash, clean-exit and crash checks, and an exact
case set. The plugin re-checks the audited verdict and reports name-level
`runtime.caseOutcomes`. Because an addon's `lua/` directory is mounted straight onto
the server's Lua search path, the static preflight additionally rejects addon
submissions that ship `lua/gluatest/` or `lua/tests/` (they could shadow the harness or
add collected cases); none of the vendored upstream trees contains either. The
harness-token scan exempts only lines that occur verbatim in the same file of the
shipped starter, so vendored upstream code such as Wiremod's local `done` counter does
not trip it while every line a submission adds is still scanned.

This is defense in depth, not an isolation boundary: the submission and the private
suite share one Lua state, exactly as in the DarkRP pack.

## Runtime

The pack binds its own runtime key, `garrys-mod/gmod-gluatest-addons`, to the same
digest-pinned GLuaTest source image the DarkRP pack uses (a second pack cannot share
one runtime ID). Preparation builds one evaluator image per task from the task's
`environment/Dockerfile`:

```sh
rhenium runtime prepare garrys-mod/gmod-gluatest-addons
rhenium tasks --game garrys-mod --pack addon-repairs
```

## Licensing

Every vendored tree keeps its upstream licence file (`LICENSE`, `LICENSE.md` or
`License.txt`): Apache-2.0 for Wiremod and Advanced Duplicator 2, BSD-3-Clause for
StarfallEx and GPL-3.0 for Contraption Framework. The Wiremod and StarfallEx trees
include the upstream models, materials and sounds under the same licences, because
the addons' server-side code validates the models it spawns. GLuaTest (GPL-3.0) and the
Garry's Mod dedicated server come from the digest-pinned public image; its availability
is not a grant to redistribute the game files. Do not publish evaluator images.
