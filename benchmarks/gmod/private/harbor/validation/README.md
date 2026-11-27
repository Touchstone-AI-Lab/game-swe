# GMod Addons Harbor validation record

All runs below used Linux x86_64 (NixOS host, Docker 29.8.0) on 2026-09-21 and the
verifier base image built by `private/runtime/gmod-harbor-runtime/build-image.sh`
from a retained native Linux Dedicated Server: Steam app 4020, build `23150012`.
Every verifier container ran without network. Every passing run reported
`server_build: 23150012` and a complete result, which the evaluator grants only
when every declared server phase ran with its integrity checks intact. An empty
starter is rejected as an invalid Addon tree, so its result is incomplete as well
as failed.

## Two-way controls

| Task | Harbor `oracle` | Harbor `nop` | First reference | Second reference | Empty starter |
| --- | --- | --- | --- | --- | --- |
| `prop-ownership-quota-registry` | reward 1.0 | reward 0.0 | `array-registry`: reward 1 | `table-registry`: reward 1 | reward 0 |
| `staged-prop-alignment` | reward 1.0 | reward 0.0 | `frame-map`: reward 1 | `frame-rows`: reward 1 | reward 0 |
| `persistent-loadout-profiles` | reward 1.0 | reward 0.0 | `profile-map`: reward 1 | `profile-rows`: reward 1 | reward 0 |
| `hot-object-round-controller` | reward 1.0 | reward 0.0 | `player-map`: reward 1 | `player-rows`: reward 1 | reward 0 |
| `contraption-blueprint-duplicator` | reward 1.0 | reward 0.0 | `graph-map`: reward 1 | `graph-rows`: reward 1 | reward 0 |

- Harbor columns: `harbor run --path <task> --agent oracle|nop -y` with Harbor CLI
  0.23.0, including the agent-environment image build and the separate verifier.
  The oracle installs `solution/reference/`, the generated copy of the first
  reference.
- Reference and empty-starter columns: `scripts/validate-all.sh` plus one direct
  verifier run per second reference, all with plain Docker and the same task
  verifier images.
- Every passing run scored 100/100: required files, Lua and `addon.json` syntax,
  the hidden behavior suite, adapter integration, lifecycle cleanup and all real
  Dedicated Server groups.

These runs confirm the existing catalog on a second Linux host through a new
packaging path. They do not replace the
[Linux validation record](../../../../../docs/games/garrys-mod-linux-validation.md),
whose mutation-matrix controls were not repeated here.

## Catalog 2.2.0 recheck (2026-10-23)

Catalog 2.2.0 changes the exams to English and makes the evaluator compare each exam
heading with `title.en`, so the verifier base image built for 2.1.0 rejects every 2.2.0
task. On 2026-10-23 (UTC+8), on the same NixOS host, the base image was rebuilt with
`build-image.sh` from the 2.2.0 tree and the same retained build `23150012`
installation (`sha256:1fee743578a1…` became `sha256:e685a464c66a…`). Its baked
evaluator copy was compared file by file with
`private/runtime/gmod-harbor-runtime/evaluator/` (34 files, identical).
`scripts/validate-all.sh` then ran every task without network:

| Task | `nop` | `oracle` |
| --- | --- | --- |
| `prop-ownership-quota-registry` | reward 0 | reward 1, 100/100, real server ran |
| `staged-prop-alignment` | reward 0 | reward 1, 100/100, real server ran |
| `persistent-loadout-profiles` | reward 0 | reward 1, 100/100, real server ran |
| `hot-object-round-controller` | reward 0 | reward 1, 100/100, real server ran |
| `contraption-blueprint-duplicator` | reward 0 | reward 1, 100/100, real server ran |

Every oracle result was complete and reported `server_build: 23150012`. As before, the
`nop` starter is rejected as an invalid Addon tree before the engine starts, so it is not
engine-backed NOP evidence. The Harbor CLI, the second references and the empty-starter
column above were not re-run for 2.2.0.

## Not run

- The mutation matrix (`mutations.json`) through the Harbor verifier.
- Windows hosts, and any Linux installation other than the retained build
  `23150012`. On 2026-09-21 the public branch of app 4020 was at build `25375525`,
  so the image cannot be reproduced from an anonymous download.
- Model-under-test trials. Only the `oracle` and `nop` agents were run.
- Disposable-host (`--security-mode untrusted`) scoring.
