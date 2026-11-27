# Garry's Mod benchmark support

## Ownership and identity

| Field | Value |
| --- | --- |
| Maintainers | Changyi, Yunta Hsieh |
| Status | `Experimental` overall; pack-specific qualifications below |
| Plugin distribution | `plugins/garrys-mod/` (`rhenium-garrys-mod`) |
| Plugin / game ID | `garrys-mod` |
| Addons pack (construct) | `garrys-mod/addons` in `benchmarks/gmod/` |
| DarkRP pack (repair) | `garrys-mod/darkrp` in `benchmarks/darkrp-core/` |
| Addon repair pack (repair) | `garrys-mod/addon-repairs` in `benchmarks/gmod-addon-repairs/` |
| Submission language | Lua (GLua) |
| Evaluator languages | Python 3.12, Bash, Lua |

One plugin owns the game and serves three packs with two task models, chosen by
catalog identity. The Addons pack asks for a clean-room Addon written from an empty
workspace and is judged by plain-Lua suites plus the pinned native App 4020 Dedicated
Server in two processes (Phase A/B). The DarkRP and addon-repair packs hand over a real
source tree with defects, repaired by the model and judged by a private GLuaTest suite
on a real headless dedicated server in a managed container. The packs keep separate
catalogs, evaluators, private assets and runtimes; sharing a plugin does not combine
their scoring contracts.

The repository-maintenance `rhenium-author` tool can also stage anonymous clean-room
GLua gamemode repairs in a separate `garrys-mod/synth` pack with its own runtime key.
No generated synth task is included by default; see
[clean-room authoring](../../tools/authoring/README.md).

## Pack summary

| Pack | Tasks | Task model | Runtime | Evidence |
| --- | ---: | --- | --- | --- |
| `addons` | 5 | Clean-room Addon construction from an empty workspace | Operator-prepared native App 4020 build `23150012` (Windows or Linux x86_64); no managed runtime key | Historical Windows evidence; Linux references on Lab (2026-09-07) and again after the 2026-09-24 restoration; see below |
| `darkrp` | 7 | Multi-defect DarkRP gamemode repair | `garrys-mod/gmod-gluatest-darkrp` | Controlled Linux container evidence; see below |
| `addon-repairs` | 5 | Multi-defect repair of real upstream addons, starters built by reverting upstream fixes | `garrys-mod/gmod-gluatest-addons` | Two-way validation and E0 controls through `rhenium run` on Linux x86_64; see below |

The integration has not completed multi-model calibration and is not Stable.

## Addons pack (construct)

The Addons catalog is `rhenium-gmod-v2` version 2.2.0. Catalog 2.2.0 translates the
five public exams, and the Harbor instruction header, from Chinese to English;
clauses, interfaces, required files and assertions are unchanged. Each exam heading
now equals the catalog's English title, which the evaluator checks, so an evaluator
from before 2.2.0 rejects every 2.2.0 exam. Attempts recorded against 2.1.0 saw the
Chinese exams. Its tasks are:

| Task | Main capability | Functional inspiration |
| --- | --- | --- |
| `prop-ownership-quota-registry` | Prop ownership, quota, lifecycle and persistence | Simple Prop Protection |
| `staged-prop-alignment` | Toolgun geometry, constraints, rollback and Undo | Magic Align |
| `persistent-loadout-profiles` | Weapon/ammo profiles across respawn and restart | Custom Loadout |
| `hot-object-round-controller` | Physical touch ordering and multiplayer lifecycle | You Touched it Last |
| `contraption-blueprint-duplicator` | Entity/constraint graph capture, paste and Undo | Advanced Duplicator 2 |

These are clean-room derivations. Source records under
`benchmarks/gmod/sources/` document feature-existence evidence and licence
handling; the benchmark does not copy or download Workshop code or assets.

Each task has one canonical public exam, isolated private assets, two
structurally different references, a mutation matrix and public/private clause
traceability. The `core` profile validates the Addon tree, syntax, plain-Lua
behavior and adapter contracts, but is deliberately incomplete. A complete
`full` result also requires every real Dedicated Server group and both Phase A
and Phase B where declared.

### Native Windows runtime

The Addons pack uses Steam Dedicated Server App 4020 stable build
`23150012`, Sandbox and `gm_flatgrass` on Windows x86-64. The operator prepares
the installation separately and sets `RHENIUM_PLUGIN_GMOD_SERVER_ROOT`; see
`plugins/garrys-mod/.env.addons-windows.example`. Evaluation never
logs in, invokes SteamCMD, downloads, updates or rebuilds the server, and fails
closed if the build or installation contract differs.

The state directory and server must be on the same NTFS volume because the
runner creates task-scoped hard-linked server views. Windows Job Objects bound
the process tree, but they are not a security sandbox. The runtime is pack-specific;
the DarkRP and addon-repair packs use their separate managed Linux container runtimes.

### Native Linux runtime

The Addons runtime now also accepts an explicitly prepared native Linux App 4020
installation on an x86_64 host. The optional catalog field `runtime.linux_build_id`
pins this installation independently from the unchanged Windows `build_id` and
`platform` fields. Catalogs without a Linux pin remain Windows-only. This pack
pins both installations to build `23150012`; adding the Linux pin changed no public
exam, reference, assertion or scoring weight.

Preparation is an explicit operator action using an already installed SteamCMD:

```sh
steamcmd +force_install_dir /srv/rhenium/gmod-server \
  +@sSteamCmdForcePlatformType linux +login anonymous +app_update 4020 validate +quit
export RHENIUM_PLUGIN_GMOD_SERVER_ROOT=/srv/rhenium/gmod-server
rhenium tasks --game garrys-mod --pack addons
```

SteamCMD's `app_update` requests the currently published stable build, not a
historical build. Check `steamapps/appmanifest_4020.acf` after acquisition and
retain the exact pinned installation privately. If stable has moved, this command
does not reproduce the pin and evaluation fails closed; do not change the pin
or relabel the manifest to accept a newer download. No personal Steam login is
needed for the anonymous server download, and no game files may be committed.

The stable `srcds_linux` is a 32-bit x86 ELF: the host/container needs its 32-bit
glibc loader and game dependencies. Rhenium does not install host packages.
On a host without those dependencies (including the tested NixOS configuration),
use a separately prepared Linux x86_64 container with the required libraries.
This runs the native Linux binary, not Wine or Windows emulation. Runtime
probing checks executable format, build and same-filesystem placement; only an
actual engine run proves loader/library and engine readiness.

The native runner requires procfs and creates a fresh process group and server
view for each phase, with bounded output and timeout cleanup. Server and state
must share a filesystem because static server files are hard-linked; mutable
game directories are private, and only the task's data symlink is reused across
phases. The original install, submission and suite are checked for changes.
In a container, keep the server and writable state under one common bind mount:
Linux refuses hard links across separate bind mounts even when `st_dev` matches.
Mount the benchmark inputs read-only separately; do not mount the state subtree
as an independent volume over that common mount.
The engine receives a minimal environment and an empty run-local home, never
the operator's Steam session or loader overrides. Evaluation launches
`srcds_linux` directly and never invokes the updating wrapper or SteamCMD.

The pinned Linux engine does not forward Lua console messages to stdout. The
runner enables `-condebug`, collects a fresh per-phase `garrysmod/console.log`
and rejects missing, linked, non-regular or oversized logs. Both stdout and the
console log are bounded to 4 MiB each. The combined transcript still has to
contain exactly one nonce-bound frame; evidence/state hashes, exact case sets,
phase separation, exit status and cleanup checks are unchanged.

This native lifetime-control path is for trusted maintenance/reference runs.
Process groups do not prevent a malicious process from escaping via a new
session, and hard-linked views are not a filesystem security boundary. Network
flags are not network isolation. Use a credential-free `--network=none` container
for controlled Linux checks; formal untrusted scoring still requires the
disposable-host provider and its evidence. No such real provider ships yet.

On 2026-09-07, all ten references (two per task) passed complete `full` evaluations
on Lab Linux x86_64, including both native engine phases and 294 assertion
verdicts. Five frozen defect variants and five empty starters were rejected.
See the [Linux validation record](garrys-mod-linux-validation.md) for exact
controls and limitations. No new Windows validation or multi-model calibration
is claimed by this platform change.

### Harbor packages

`benchmarks/gmod/private/harbor/` exports the five Addons tasks as Harbor 1.4
packages. Their separate, networkless verifier image wraps an operator-retained
pinned Linux installation and a byte-for-byte copy of this plugin's Addons
evaluator, so a Harbor reward is the `full` verdict described above, including
both native engine phases. Build the image with
`benchmarks/gmod/private/runtime/gmod-harbor-runtime/build-image.sh <server-root>`;
it performs no Steam login, download or update and refuses any build other than
`23150012`. The image is local, non-redistributable and not a managed runtime: the
Hub path is unchanged and still uses `RHENIUM_PLUGIN_GMOD_SERVER_ROOT`. Layout,
boundary and evidence are in the
[Harbor suite README](../../benchmarks/gmod/private/harbor/README.md).

| Pack | Verifier image | Server | How the image is obtained |
| --- | --- | --- | --- |
| [`garrys-mod/addons`](../../benchmarks/gmod/private/harbor/README.md) | `gcb-gmod-addons-verifier:23150012` | Steam app 4020, Linux build 23150012 | `build-image.sh <server-root>` from an operator-retained installation; the pinned build is no longer the public one |

On Linux x86_64 every task's `oracle` control scored reward 1.0 with the real
server running and every `nop` control scored 0.0; the
[validation record](../../benchmarks/gmod/private/harbor/validation/README.md) lists the
exact runs and what was not run. The image serves Harbor only; the Hub still uses the
plugin-owned native runner for that pack. It is local and must never be pushed to a
registry.

### Restoration check

The pack was withdrawn on 2026-09-23 and restored unchanged on 2026-09-24: catalog,
exams, source records, private suites, references, mutation matrices, Harbor task trees
and study controls are byte-identical to the last published version; only the
vendored evaluator copy in `private/runtime/gmod-harbor-runtime/evaluator/` was
regenerated, because the shared `plugin.py` and `darkrp/` modules changed when the
GLuaTest path was generalised. The plugin dispatches catalog `rhenium-gmod-v2` to the
Addons subsystem and every GLuaTest catalog to the GLuaTest path.

On 2026-09-24 (UTC+8) every reference and every empty starter was re-run through
`rhenium run garrys-mod/addons/<task> <tree> --profile full`, using the current
repository code inside the local `gcb-gmod-addons-verifier:23150012` image (the
retained Linux build `23150012` with its 32-bit loader) with `--network=none`, the
repository and submission mounted read-only and Hub state inside the image
filesystem, because this NixOS host has no 32-bit loader. Run IDs come from that
container's own Hub database.

| Task | Reference | Run ID | Score | Server groups (Phase A and B) |
| --- | --- | --- | ---: | --- |
| `prop-ownership-quota-registry` | `array-registry` | `run-2d1cf0783fdd4ada` | 100 | 5/5 |
| `prop-ownership-quota-registry` | `table-registry` | `run-58acab1095754234` | 100 | 5/5 |
| `staged-prop-alignment` | `frame-map` | `run-08ea26b195b9465f` | 100 | 8/8 |
| `staged-prop-alignment` | `frame-rows` | `run-657f09f4780d4241` | 100 | 8/8 |
| `persistent-loadout-profiles` | `profile-map` | `run-014f9dd136354c77` | 100 | 7/7 |
| `persistent-loadout-profiles` | `profile-rows` | `run-1066ee486d7a4062` | 100 | 7/7 |
| `hot-object-round-controller` | `player-map` | `run-a372518dc3344ffc` | 100 | 8/8 |
| `hot-object-round-controller` | `player-rows` | `run-f82b892a325c43a2` | 100 | 8/8 |
| `contraption-blueprint-duplicator` | `graph-map` | `run-1b99ca4a849b4b97` | 100 | 7/7 |
| `contraption-blueprint-duplicator` | `graph-rows` | `run-b2579d28f6044963` | 100 | 7/7 |

Every reference result was complete, reported server build `23150012`, and ran two
distinct server processes that both exited cleanly.

The five plugin-materialized empty starters (`task.json` and `TASK.md` only) all
scored 0 and failed as incomplete results, by design: the evaluator rejects a tree
without `addon.json` before starting the engine, so they are not engine-backed NOP
evidence. Runs: `run-6b07e648f3d741fb` (prop ownership), `run-6c50cc1928aa4474`
(staged alignment), `run-95c43cda24c846ca` (loadout), `run-135a97cff3a94e78`
(hot object), `run-2b823b4abb834613` (blueprint).

The same five frozen defect variants that the 2026-09-07 Lab controls used were
re-run the same way and failed in the real engine for the injected behavior, with the
Lab scores reproduced exactly. The prop-registry variant completed both phases; the
other four failed Phase A, so the contract did not start Phase B and their results are
incomplete failures.

| Task | Frozen mutation | Run ID | Score | Complete |
| --- | --- | --- | ---: | --- |
| `prop-ownership-quota-registry` | `shutdown-leaks-timer` | `run-2201aeee6dc341d4` | 87 | true |
| `staged-prop-alignment` | `shutdown-leaks-timer` | `run-cacb8280b9374016` | 55 | false |
| `persistent-loadout-profiles` | `ammo-reset-skipped` | `run-d3fc98e25c834e7b` | 54.38 | false |
| `hot-object-round-controller` | `shutdown-leaks-timer` | `run-c68492776d9e4f9d` | 55 | false |
| `contraption-blueprint-duplicator` | `shutdown-leaks-timer` | `run-b38f6eeee1834028` | 55 | false |

Not re-run for the restoration: Windows hosts, Harbor `oracle`/`nop` trials, the rest
of each mutation matrix, the `tools/study` E0 controls and model attempts. The local
`gcb-gmod-addons-verifier:23150012` image was not rebuilt: its baked evaluator copy
still carries the pre-restoration `plugin.py` and `darkrp/` modules, while its
`addons/` subsystem and `rhenium.core` files are byte-identical to the repository's.
Rebuild it with `build-image.sh <server-root>` before claiming a byte-for-byte Harbor
verifier.

### Catalog 2.2.0 check

Catalog 2.2.0 changes the evaluator's exam-heading check from `title.zh` to `title.en`.
That check runs inside the local verifier image, which Harbor trials and `tools/study`
use, so on 2026-10-23 (UTC+8) the image was rebuilt from the 2.2.0 tree with the same
retained installation. Its baked evaluator copy now matches the repository file by
file. `private/harbor/scripts/validate-all.sh`, which mirrors Harbor's separate-verifier
flow with plain Docker, then gave the `nop` and `oracle` sides of all five tasks reward 0
and reward 1; every oracle scored 100 with a complete real Dedicated Server run. The
[Harbor validation record](../../benchmarks/gmod/private/harbor/validation/README.md)
has the details. The `nop` starters are rejected before the engine starts, so they are
not engine-backed NOP evidence. Not re-run for 2.2.0: the second references, the
mutation matrices and frozen defect variants, the `tools/study` E0 controls, Windows
hosts and model attempts.

## GLuaTest runtime (DarkRP and addon-repair packs)

The two repair packs pull the same digest-pinned public GLuaTest dedicated-server image
(`ghcr.io/cfc-servers/gluatest/x86-64@sha256:23cd97d4...`, Garry's Mod patch
2026.04.29, GLuaTest 0.35.2) and build one evaluator image per task. Each pack binds
its own runtime key, because the runtime manager keys runtimes by game and runtime ID:

```sh
rhenium auth login container
rhenium runtime prepare garrys-mod/gmod-gluatest-darkrp
rhenium runtime prepare garrys-mod/gmod-gluatest-addons
rhenium runtime verify garrys-mod/gmod-gluatest-addons
rhenium tasks --game garrys-mod --pack addon-repairs
```

The provider re-checks the manifest digest reported after the pull. The builder
validates its `image.json` source record and declared files, rebuilds rather than
trusting predictable tags, and verifies immutable image IDs plus source, task, runtime
ID, fingerprint and build-context labels. The runtime-ID label is the pack's own
runtime ID. `prune` refuses images without the expected ownership labels. Changing a
task's `environment/` requires preparing that pack's runtime again; changing only its
`tests/` does not, because tests are mounted at run time.

Each evaluation runs on a real headless server with `--network=none`, separate
read-only submission and test mounts, dropped capabilities (six file/identity
capabilities are restored for the entrypoint's own staging), CPU, memory and process
limits, and a two-minute inner engine timeout. The patched GLuaTest runner captures a
nonce-bound exact case set and completion record; the collector also checks the
harness hash, clean-exit state, crash log and terminal verdict, and writes
`result.json`, which the plugin re-checks. A complete result reports name-level
`runtime.caseOutcomes` from the private audit, only when the audited case set equals
the task's expected cases exactly. `core` is always incomplete; only `full` runs the
server.

## DarkRP pack

The DarkRP catalog is `darkrp-core` version 1.1.0 with seven multi-defect debugging
tasks built from [DarkRP](https://github.com/FPtje/DarkRP) (MIT). Version 1.1.0 retires
`darkrp-job-loadout-regressions` (SG-028) without a replacement: it was saturated and
no longer discriminated. Its exam, Harbor package and matrix stay in the pack as
history. The prepared `garrys-mod/gmod-gluatest-darkrp` artifact records one image per
catalog task, so an artifact prepared before 1.1.0 fails `runtime verify`; prepare the
runtime again. The submission is the
`darkrp/` gamemode tree. Controlled Linux evidence for the pack's first three
references, broken bases and result or authorization mutations is recorded in
[`rhenium-controls.md`](../../benchmarks/darkrp-core/validation/rhenium-controls.md);
per-defect matrices for every task are in
[`per-defect-matrix.md`](../../benchmarks/darkrp-core/validation/per-defect-matrix.md).

On 2026-09-23 (UTC), after the plugin was generalised for the addon pack, two DarkRP tasks
were re-run through `rhenium run` against the unchanged prepared DarkRP runtime:

| Task | Tree | Run ID | Score | Cases |
| --- | --- | --- | ---: | --- |
| `darkrp-money-regressions` | starter | `run-3c5a8661aa7b456c` | 10 | complete, 2 of 9 pass (sentinel and control) |
| `darkrp-money-regressions` | reference | `run-75092ba666fe41fe` | 100 | 9 of 9 |
| `darkrp-door-economy-regressions` | starter | `run-a25ddd567b534ddd` | 10 | complete, 2 of 11 pass |
| `darkrp-door-economy-regressions` | reference | `run-d68494a446644f34` | 100 | 11 of 11 |

On 2026-09-24 (UTC+8), after the Addons pack was restored next to this pack, one task
was re-run through `rhenium run` against the unchanged prepared DarkRP runtime:

| Task | Tree | Run ID | Score | Cases |
| --- | --- | --- | ---: | --- |
| `darkrp-money-regressions` | starter | `run-3226ca332bff4432` | 10 | complete, 2 of 9 pass (sentinel and control) |
| `darkrp-money-regressions` | reference | `run-ab107cf5339d4c13` | 100 | 9 of 9 |

## Addon repair pack

The addon-repair catalog is `gmod-addon-repairs` version 1.0.0. Every task vendors one
real open-source addon at an upstream commit (the reference) and reverts several real
upstream bug-fix commits (the starter); none of the defects is hand-injected. The
workspace holds the addon directory (for example `wire/`); the verifier installs it as
`garrysmod/addons/<name>` next to GLuaTest and boots the sandbox gamemode on
`gm_construct`.

| Task | Addon (licence) | Base commit | Reverted upstream fixes | Target / preserved / sentinel cases |
| --- | --- | --- | --- | --- |
| `advdupe2-paste-regressions` | Advanced Duplicator 2 (Apache-2.0) | `e3ffa3c5` | `3c6dda8d` `6c9a4b58` `ded84cec` `b10d6d69` `2f735956` | 6 / 4 / 1 |
| `cfw-contraption-regressions` | Contraption Framework (GPL-3.0) | `5bb6f9fe` | `5bb6f9fe` `14d289bd` `7331e604` `4ef05dc2` `839af481` `cea75d5f` | 6 / 3 / 1 |
| `starfallex-library-regressions` | StarfallEx (BSD-3-Clause) | `0e8e3d7e` | `c06b8744` `e7c57fd0` `2eda19da` `b53506de` `07a9665f` `1b7d91a2` | 6 / 6 / 1 |
| `wiremod-e2-library-regressions` | Wiremod (Apache-2.0) | `f31ba74e` | `3ad16644` `21c1991d` `074ff60e` `e87fea31` `4dff1ee1` `e4a29515` | 6 / 4 / 1 |
| `wiremod-gates-chips-regressions` | Wiremod (Apache-2.0) | `f31ba74e` | `d1f46905` `0caed1c8` `a201ecb6` `808b8555` `af74e4fa` `8197779c` | 7 / 6 / 1 |

Each task's `task.toml` records the full commit SHAs, how every fix was reverted and
what each hidden case drives. Public exams list lettered, symptom-only reports; they
omit fix commits, pull requests, file hints and defect counts, and name a public API
only where a hidden case calls it.

Addon submissions go through the same static preflight as DarkRP plus two addon rules:
the tree must contain `lua/`, and it may not ship `lua/gluatest/` or `lua/tests/`,
which would shadow the harness or add GLuaTest cases. The harness-token scan exempts
only lines that occur verbatim in the same file of the shipped starter, because
vendored upstream code can contain a harness-like name (Wiremod has a local `done`).

### Validation

All five tasks were validated on 2026-09-23 (UTC) on a shared Linux x86_64 host with
Docker, through `rhenium run` against the prepared `garrys-mod/gmod-gluatest-addons`
runtime. Run IDs and per-case outcomes are in
[`validation/README.md`](../../benchmarks/gmod-addon-repairs/validation/README.md).

| Task | Starter (score, cases passed) | Reference x3 | E0 controls (target-negative, compat-negative, alternative) |
| --- | --- | --- | --- |
| `advdupe2-paste-regressions` | 10, 5/11; only targets fail | 100 three times, identical outcomes | all admissible |
| `cfw-contraption-regressions` | 10, 4/10; only targets fail | 100 three times, identical outcomes | all admissible |
| `starfallex-library-regressions` | 10, 7/13; only targets fail | 100 three times, identical outcomes | all admissible |
| `wiremod-e2-library-regressions` | 10, 5/11; only targets fail | 100 three times, identical outcomes | all admissible |
| `wiremod-gates-chips-regressions` | 10, 7/14; only targets fail | 100 three times, identical outcomes | all admissible |

Not validated: Windows hosts, Harbor runs of these packages, model attempts, and the
`tools/study` E0 pipeline (the tasks are not in its inventory; the controls were run
directly through `rhenium run` with the same evaluator).

On 2026-09-24 (UTC+8), after the Addons pack was restored next to this pack, one task
was re-run through `rhenium run` against the unchanged prepared addon-repair runtime:

| Task | Tree | Run ID | Score | Cases |
| --- | --- | --- | ---: | --- |
| `cfw-contraption-regressions` | starter | `run-c80a243ef4ee4117` | 10 | complete, 4 of 10 pass; exactly the six target cases fail |
| `cfw-contraption-regressions` | reference | `run-16d4443727d447c3` | 100 | 10 of 10 |

## Security and licence boundary

All three packs remain honest benchmarks. Submission code and private tests execute
inside the same Garry's Mod Lua state. Read-only mounts, containers, nonce binding and
verifier hardening do not guarantee private-suite secrecy against an actively
malicious or obfuscated submission. Formal untrusted scoring still requires a
disposable credential-free host boundary.

Local reference and development runs use `security.mode=honest`; Windows Job Objects,
Linux process groups and the GLuaTest containers are defense in depth. Formal
model-generated or external submissions must select `--security-mode untrusted`, an
approved `rhenium.evaluation_hosts` provider and an immutable image or snapshot
identity. Missing network, credential, input, result or destruction evidence fails
closed without invoking either local GMod evaluator. No real disposable provider ships
with Rhenium yet; follow the [provisioning runbook](../disposable-host-runbook.md)
before making a formal-untrusted claim. The per-surface comparison is in the
[DST and Garry's Mod security matrix](../dst-gmod-security-matrix.md).

The Addons tasks are clean-room derivations: the pack contains no Workshop code or
assets. The vendored DarkRP trees keep their MIT licence; the addon-repair trees keep
their upstream Apache-2.0, BSD-3-Clause or GPL-3.0 licence files, and the Wiremod and
StarfallEx trees include their upstream models, materials and sounds. GLuaTest is
GPL-3.0. The pinned GLuaTest image and the Addons verifier image both contain the
Garry's Mod dedicated server, whose public availability is not a grant to redistribute
it. Neither this repository nor the plugin wheel contains a Dedicated Server
installation, a built evaluator image, personal Steam state, credentials or API keys.
Do not publish evaluator images.

Benchmark packs are read-only. Attempts, logs, runtime records, server views and
generated results belong only under Rhenium state and cache directories.
