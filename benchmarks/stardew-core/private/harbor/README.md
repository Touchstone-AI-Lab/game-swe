# GameCodeBench — Stardew Valley task suite

SWE-style benchmark tasks built from real, open-source [SMAPI](https://smapi.io/)
mods for Stardew Valley, in [Harbor](https://github.com/harbor-framework/harbor)
format. Each task boots **the real game** headless (SMAPI + Xvfb/llvmpipe) inside a
container, loads a deterministic fixture save, and asserts on live game state — not
on compilation, not on unit tests.

This directory is retained as private task provenance for the Rhenium 0.5
`stardew-valley/core` pack. The supported execution path is the
`rhenium-stardew-valley` plugin; these assets must not be copied into an anonymous
attempt or used as a standalone agent workspace.

Sibling of the `darkrp-harbor-tasks` suite, with the same validation discipline:
two-way validation (base tree fails, reference solution passes), oracle and `nop`
controls, and network isolation at trial time.

## Scope note — both proposal categories are represented

GameCodeBench's proposal defines two task categories: **mod generation** (an agent
writes a new mod from a natural-language requirement) and **mod debugging** (diagnose
and repair). Thirteen tasks are repair (debugging) tasks: the agent receives a real
mod source tree with one or more defects and must fix them from symptom reports.
`stardew-summon-horse-anywhere` and `stardew-auto-workshop` are generation tasks: the
agent starts from an empty `ModEntry` and a user-level requirement, the reference
implementation never enters the environment, and the behavioural suite names no
technique or patch target. A hidden suite running in the real game judges both
kinds. Catalog 1.2.0 removed the two generation tasks; catalog 1.3.0 restored them
unchanged.

## Status

**15 tasks: 13 repair, 2 generation.** The ten Automate and Content Patcher repair
tasks predate catalog 1.2.0; the two Automate tasks added in catalog 1.1.0 completed
real-game starter/reference controls on 2026-09-23 (see `docs/games/stardew-valley.md`).
Catalog 1.2.0 added three composite repair tasks built from other real mods (Content
Patcher 2.6.1, CJB Cheats Menu 1.42.0, Tractor Mod 4.24.4), each two-way validated
through `rhenium run` with study controls; see each task's `validation/NOTES.md`.
Catalog 1.3.0 restored the two generation tasks, which were two-way validated in the
real game before the Rhenium integration and again through `rhenium run` on
catalog 1.0.0 and 1.3.0 images (see `docs/games/stardew-valley.md`). Three further tasks are parked in `_blocked/` with their
evidence and the work needed to unblock them — they are deliberately outside the
shippable set so a blocked task can never be mistaken for a validated one.
`NOTES.md` records the suite's design history and the difficulty levers that were
tried.

### Tasks

| task | mod | defect | difficulty |
|---|---|---|---|
| `stardew-automate-minifridge-storage` | Automate 2.4.0 | release regression: mini-fridges no longer treated as storage | easy |
| `stardew-automate-junimohut-seed-config` | Automate 2.5.0 | seeds option silently follows the fertilizer option | easy |
| `stardew-automate-machine-states-api` | Automate 2.4.5 | mod API publishes nothing from the initial save-load scan | medium |
| `stardew-automate-zero-stack-output` | Automate 2.3.1 | zero-size output wedges a machine forever | medium |
| `stardew-cp-i18n-case` | Content Patcher 2.4.3 | `{{i18n}}` lowercases text matching a predefined value | medium |
| `stardew-automate-release-regressions` | Automate 2.6.1 | 4 reverted fixes, symptom-only reports | hard |
| `stardew-automate-release-regressions-v2` | Automate 2.6.1 | 6 groups, no defect count given, engineered mutually-masking pair, unscored decoy | hard |
| `stardew-automate-release-regressions-v3` | Automate 2.6.1 | 3 groups, every one at edge-case-branch difficulty | hard |
| `stardew-automate-output-count-drift` | Automate 2.6.1 | engineered: stored outputs are duplicated or lost depending on free chest space | easy |
| `stardew-automate-setup-extension` | Automate 2.6.1 | engineered: extending a running setup through its chest has no effect until reload | medium |
| `stardew-summon-horse-anywhere` | new mod (generation) | write a mod from a requirement: the horse flute must summon indoors | medium |
| `stardew-auto-workshop` | new mod (generation) | write a chest-runs-adjacent-machines automation mod: six interacting behaviours incl. no-item-loss on a full chest and duplicate building interiors | hard |
| `stardew-cp-release-regressions` | Content Patcher 2.6.1 | 5 later upstream fixes absent from the release: numeric `PathPart`, tokenised nested keys, data-model conversion (positions, lists), text operations on missing targets | hard |
| `stardew-cjb-cheats-regressions` | CJB Cheats Menu 1.42.0 | 5 upstream fixes reverted: one-hit-kill grubs, auto-feed with empty silos, auto-pet animals/pets outside the farm, golden treasure | hard |
| `stardew-tractor-attachment-regressions` | Tractor Mod 4.24.4 | 4 upstream fixes reverted: axe vs grown fruit trees, seeds into garden pots with bushes, unplaceable custom attachments, break-objects vs stones | hard |

Source mods are MIT ([Pathoschild/StardewMods](https://github.com/Pathoschild/StardewMods)
and [CJBok/SDV-Mods](https://github.com/CJBok/SDV-Mods)).
Where a task reverts upstream fixes, the reference solution is upstream's own work,
so pretraining contamination cannot be excluded — except for the engineered defects
(v2/v3's location-key pair, the third-party conflict), which exist in no commit
history.

## Layout

```
<task>/
  task.toml            metadata, provenance, network policy, scoring, fairness notes
  environment/         Dockerfile + trimmed mod monorepo at the base commit
                       (generation tasks: mod/ with an empty ModEntry skeleton)
                       + gcb-harness/ (committed copy of the verifier harness)
  tests/               test.sh (reward gate) + the C# suite (+ fixtures)
  solution/            gold.patch + solve.sh (Harbor oracle)
                       (generation tasks: reference/ModEntry.cs + solve.sh)
harness/               canonical harness source (copied into each task)
scripts/               historical acquisition and two-way validation helpers
_blocked/              authored but non-discriminating tasks, with evidence
```

Public instructions now live in the pack-level `exams/` directory.

The harness is a SMAPI mod: it loads a fixture save generated at image build time,
pumps the task's assertion cases as tick-driven coroutines against live game state,
writes a JSON verdict, and exits. The reward gate parses only that verdict — exit
codes gate nothing.

## Running it through Rhenium

```sh
rhenium auth login steam
rhenium runtime prepare stardew-valley/stardew-1.6.15-smapi-4.1.10
rhenium run stardew-valley/core/stardew-automate-zero-stack-output \
  /path/to/submission --profile full
```

The independent Steam provider pins the exact Linux depot manifest in the runtime
catalog (game 1.6.15, app 413150, depot 413153; SMAPI 4.1.10). Prepared task images
are self-contained and evaluation containers run with `--network=none`. Model
credentials are handled by the game-neutral Hub and are never injected into the
game image.

## Game acquisition (ownership required)

Stardew Valley is a paid, proprietary game. This repository carries task metadata,
patches, tests, harness code, and acquisition scripts only — no game files, ever.
Per the GameCodeBench responsible-release policy, images built from these tasks must
remain private.
