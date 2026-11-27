# Garry's Mod Addons Linux controls

These maintenance controls ran on Lab (`biuh-lab`, Linux x86_64, Docker 29.7.2)
on 2026-09-07, using the PR #5 worktree with main `cca3be1` integrated and the
native Linux runner changes. SteamCMD anonymous acquisition successfully
installed App 4020 stable build `23150012`; no personal Steam session was used.

The native 32-bit Linux ELF ran with its required libraries in a Python 3.12
Linux container, not Wine or Windows emulation. The tooling image was
`sha256:52e30a6aa68474f518f1daefaf63703a0f3e2f23ab3a4cbce27f30da130807fb`;
the game installation was a separate, local, non-redistributed input. The
container used network `none`, no capabilities, no-new-privileges, a non-root
UID, a read-only repository mount and task-local writable state. No real
disposable-host provider or hostile-code isolation claim is made.

## Reference controls

Every result below came through `BenchmarkHub.evaluate_task(..., profile="full")`.
All ten scored 100, were complete, and passed. Each ran distinct Phase A/B
processes; exact case sets, nonce/evidence/state hashes, source preservation
and cleanup all passed. The two references per task yielded 294 successful
real-engine assertion verdicts in total (in addition to the plain-Lua checks).

| Task | Reference | Run ID | Phase A/B assertions |
| --- | --- | --- | --- |
| Prop ownership/quota | array-registry | `run-4dc06d61087b42d2` | 6 / 33 |
| Prop ownership/quota | table-registry | `run-824c3bd321f349c4` | 6 / 33 |
| Staged prop alignment | frame-map | `run-4ab39144c2374e91` | 26 / 10 |
| Staged prop alignment | frame-rows | `run-1e1f55bc73c04742` | 26 / 10 |
| Persistent loadout | profile-map | `run-d6948b0c83f1455b` | 11 / 8 |
| Persistent loadout | profile-rows | `run-e852771678974fbb` | 11 / 8 |
| Hot-object round | player-map | `run-a12e0a837e5c4565` | 18 / 15 |
| Hot-object round | player-rows | `run-42a09ec0b3f647e0` | 18 / 15 |
| Contraption blueprint | graph-map | `run-c43acf3adca24637` | 12 / 8 |
| Contraption blueprint | graph-rows | `run-f91736abecd94318` | 12 / 8 |

## Negative controls

All five frozen defect variants failed in the real engine for the injected
behavior, not an unavailable engine. The prop-registry variant completed both
phases; the other four failed Phase A and the existing contract correctly did
not start Phase B, so their full results are incomplete failures.

| Task | Frozen mutation | Run ID | Score | Complete |
| --- | --- | --- | ---: | --- |
| Prop ownership/quota | shutdown-leaks-timer | `run-6bcf28cc2fb14375` | 87 | true |
| Staged prop alignment | shutdown-leaks-timer | `run-0df5cdfbd04248d1` | 55 | false |
| Persistent loadout | ammo-reset-skipped | `run-cbb7d4c3ac9143c0` | 54.38 | false |
| Hot-object round | shutdown-leaks-timer | `run-b29d3c8ffb1e4f6a` | 55 | false |
| Contraption blueprint | shutdown-leaks-timer | `run-be63c22f311746b9` | 55 | false |

All five plugin-materialized empty starters scored zero and were incomplete
failures. They lack an Addon implementation, so the engine did not start for
those five controls; they are not represented as engine-backed NOP evidence.

No authored exam, private assertion, reference, mutation matrix, task version
or scoring weight was changed. This run did not repeat Windows validation,
multi-model calibration, or a real disposable-provider E2E.

## Root cause corrected

An early Linux probe exited normally but scored incomplete because its stdout
contained no framed verdict. A diagnostic run with `-condebug` showed that the
unchanged private suite had actually passed Phase A and written its verdict to
`garrysmod/console.log`. The Linux collector now bounds and reads that fresh
regular file as well as stdout, without relaxing the shared exact-frame or
evidence checks. The production-run controls above use this corrected path;
they do not use the temporary diagnostic wrapper.

## Existing DarkRP pack regression

The consolidated plugin's separate DarkRP runtime was also explicitly prepared
through the Hub on Lab. Its first build failed on a PyPI fetch timeout; an
unchanged-input retry succeeded without changing its source digest, dependency
pins or frozen Dockerfiles. These six fresh `garrys-mod/darkrp` full evaluations
all completed in the real GLuaTest server; bases failed and references passed.
The DarkRP runtime is independent of the native Addons App 4020 installation.

| Task | Base run (score 10, failed) | Reference run (score 100, passed) |
| --- | --- | --- |
| Release regressions | `run-ec6866cc7bce45bc` | `run-9b3a7c2aa6664ea0` |
| Live-server regressions | `run-feed24ac5a404f69` | `run-a698b7ebec7048d9` |
| Door/economy regressions | `run-956fd704cede4325` | `run-596ece5561374131` |

Both packs and every control submission remained unchanged by evaluation.

## 2026-09-24 restoration controls

The Addons pack was withdrawn on 2026-09-23 and restored unchanged on 2026-09-24,
next to the DarkRP and addon-repair GLuaTest packs. Its task content is byte-identical
to the version above; the plugin's `plugin.py` and GLuaTest modules had changed in the
meantime, so every reference and empty starter and the same five frozen defect
variants were re-run.

These controls ran on a shared NixOS Linux x86_64 host (Docker), not on Lab. Each ran
`rhenium run garrys-mod/addons/<task> <tree> --profile full`, that is
`BenchmarkHub.evaluate_task(..., profile="full")`, with the current repository code
inside the local `gcb-gmod-addons-verifier:23150012` image, which carries the retained
Linux App 4020 build `23150012` and its 32-bit loader and libraries. The container used
network `none`, no-new-privileges, CPU, memory and process limits, a read-only
repository mount (the host virtualenv and `/nix/store` supplied the Hub's Python), a
read-only submission mount, and Hub state inside the image filesystem next to the
server so that per-phase views could hard-link it. It ran as the image's root user, not
a non-root UID as on Lab. Run IDs come from each container's own Hub database.

| Task | Control | Run ID | Score | Complete | Server groups |
| --- | --- | --- | ---: | --- | --- |
| Prop ownership/quota | array-registry | `run-2d1cf0783fdd4ada` | 100 | true | 5/5 |
| Prop ownership/quota | table-registry | `run-58acab1095754234` | 100 | true | 5/5 |
| Prop ownership/quota | shutdown-leaks-timer | `run-2201aeee6dc341d4` | 87 | true | |
| Prop ownership/quota | empty starter | `run-6b07e648f3d741fb` | 0 | false | not started |
| Staged prop alignment | frame-map | `run-08ea26b195b9465f` | 100 | true | 8/8 |
| Staged prop alignment | frame-rows | `run-657f09f4780d4241` | 100 | true | 8/8 |
| Staged prop alignment | shutdown-leaks-timer | `run-cacb8280b9374016` | 55 | false | Phase A failed |
| Staged prop alignment | empty starter | `run-6c50cc1928aa4474` | 0 | false | not started |
| Persistent loadout | profile-map | `run-014f9dd136354c77` | 100 | true | 7/7 |
| Persistent loadout | profile-rows | `run-1066ee486d7a4062` | 100 | true | 7/7 |
| Persistent loadout | ammo-reset-skipped | `run-d3fc98e25c834e7b` | 54.38 | false | Phase A failed |
| Persistent loadout | empty starter | `run-95c43cda24c846ca` | 0 | false | not started |
| Hot-object round | player-map | `run-a372518dc3344ffc` | 100 | true | 8/8 |
| Hot-object round | player-rows | `run-f82b892a325c43a2` | 100 | true | 8/8 |
| Hot-object round | shutdown-leaks-timer | `run-c68492776d9e4f9d` | 55 | false | Phase A failed |
| Hot-object round | empty starter | `run-135a97cff3a94e78` | 0 | false | not started |
| Contraption blueprint | graph-map | `run-1b99ca4a849b4b97` | 100 | true | 7/7 |
| Contraption blueprint | graph-rows | `run-b2579d28f6044963` | 100 | true | 7/7 |
| Contraption blueprint | shutdown-leaks-timer | `run-b38f6eeee1834028` | 55 | false | Phase A failed |
| Contraption blueprint | empty starter | `run-2b823b4abb834613` | 0 | false | not started |

Every reference passed with two distinct server processes that exited cleanly, valid
state and evidence hashes, and unchanged submission, suite and server installation.
The five defect variants reproduced the Lab scores exactly. The empty starters were
rejected before the engine started (`required file is missing: addon.json`), as
before; they are not engine-backed NOP evidence.

The GLuaTest path was checked after the restoration through `rhenium run` on the host
against the unchanged prepared runtimes: `garrys-mod/darkrp/darkrp-money-regressions`
starter `run-3226ca332bff4432` scored 10 (complete, 2 of 9 cases) and reference
`run-ab107cf5339d4c13` scored 100 (9 of 9);
`garrys-mod/addon-repairs/cfw-contraption-regressions` starter `run-c80a243ef4ee4117`
scored 10 (complete, 4 of 10, exactly the six target cases failing) and reference
`run-16d4443727d447c3` scored 100 (10 of 10).

Not run for the restoration: Windows validation, Harbor `oracle`/`nop` trials, the
remaining mutation-matrix entries, `tools/study` E0 controls, model attempts, and a
real disposable-provider run.
