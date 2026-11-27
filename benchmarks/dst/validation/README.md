# DST repair pack validation record

A result is complete only when every case of the task's frozen `server_cases`
list was observed. Scores are 10 for the submission-shape check plus 90 when every
server case passes.

## Catalog 4.0.0

Catalog 4.0.0 hardened four tasks to task version 2.0.0 (see
[DST benchmark support](../../../docs/games/dst.md#migration-from-catalog-3x)).
All evidence in this section comes from the real Don't Starve Together dedicated
server (Steam app 343050, build 24700372) running offline, in each task's
Harbor verifier image. `private/harbor/scripts/validate-task.sh` built the image
from the task's regenerated `tests/` on `gcb-dst-dedicated-verifier:24700372`
and graded the starter (`nop`) and the upstream reference (`oracle`). Every E0
control was graded in the same image, with the control tree mounted read-only
and no network. The image contains the repository's evaluator, so its reward is
the `full` verdict. Host: Linux 7.2.8 x86_64, Docker 29.8.1. Runs were made on
2026-10-28.

These runs have no Hub run ids. `rhenium run` through the Hub was not repeated
for 4.0.0, and `rhenium runtime prepare dst/dst-dedicated-24700372` was not run
again, so a runtime prepared earlier still holds the 3.0.0 suites.

| Task | Version | Starter (`nop`) | Reference (`oracle`) |
| --- | --- | --- | --- |
| `dst-fixed-bundle-regressions` | 2.0.0 | 10; complete; fails exactly the 6 target cases | 100; all 14 server cases pass |
| `dst-fixed-module-regressions` | 2.0.0 | 10; complete; fails exactly the 8 target cases | 100; all 19 server cases pass |
| `composting-together-regressions` | 1.0.0 | 10; complete; fails exactly the 8 target cases | 100; all 13 server cases pass |
| `dsmmo-release-regressions` | 2.0.0 | 10; complete; fails exactly the 7 target cases | 100; all 15 server cases pass |
| `glassic-api-regressions` | 2.0.0 | 10; complete; fails exactly the 8 target cases | 100; all 15 server cases pass |

Each reference ran once on the final suites. The controls and their results are
listed in each hardened task's `private/study-controls/<task>/NOTES.md`: every
target-negative failed only its own target cases, every compat-negative passed
every target and failed only the preserved case it was built to break, and every
`alternative-a` scored 100. `composting-together-regressions` gained no defect and
its controls were not rerun.

A first version of the module task also reverted `b94f96f` (Mourning Glory into
Dug Grave). Its starter run was incomplete: the reverted code raised in
`PopulateWorld` while the world loaded its graves, before the suite started. The
defect was replaced by `c4c2875`, so a missed fix fails cases instead of leaving
the result incomplete.

## Catalog 3.0.0

The evidence in the following sections comes from the real dedicated server
(Steam app 343050, build 24700372) running offline in the managed
`dst/dst-dedicated-24700372` container runtime, reached through
`rhenium run dst/core/<task> <workspace> --profile full` in the default `honest`
security mode. Host: Linux 7.2.5 x86_64, Docker 29.8.0, shared with other
workloads (load average about 30). Runs were made on 2026-09-24 (UTC+8). They
graded the task version 1.0.0 suites; for the four hardened tasks they are
superseded by the section above.

### Two-way validation

| Task | Starter | Reference run 1 | Reference run 2 | Reference run 3 | Identical reference outcomes |
| --- | --- | --- | --- | --- | --- |
| `dst-fixed-bundle-regressions` | `run-4d375079026944d9`: 10; fails exactly the 5 target cases | `run-42730937bfbe4003`: 100; admissible | `run-ae843d265d8e4059`: 100; admissible | `run-595aa45485a2415e`: 100; admissible | yes |
| `dst-fixed-module-regressions` | `run-d7405ab36f5b4d17`: 10; fails exactly the 6 target cases | `run-9f78d9a1cc1f427a`: 100; admissible | `run-16270aa81f4145e2`: 100; admissible | `run-a5e12765b4bf456b`: 100; admissible | yes |
| `composting-together-regressions` | `run-16e59c5e700b47f1`: 10; fails exactly the 8 target cases | `run-0522285ebb6c438a`: 100; admissible | `run-7bd28fd35a194667`: 100; admissible | `run-ef1f956bd0534884`: 100; admissible | yes |
| `dsmmo-release-regressions` | `run-55a6a259dc114bd4`: 10; fails exactly the 5 target cases | `run-013bd4d7a2ca4964`: 100; admissible | `run-42b1cb1e5d0246ae`: 100; admissible | `run-ac62b8437a834714`: 100; admissible | yes |
| `glassic-api-regressions` | `run-6a26d61f176240ac`: 10; fails exactly the 4 target cases | `run-695af0a2274046d2`: 100; admissible | `run-8c0e64555ac84482`: 100; admissible | `run-ae75498cf25e4f68`: 100; admissible | yes |

Every starter was complete (all cases observed) and failed exactly its target
cases; see each task's `private/study-controls/<task>/clause-map.json` for the
roles. Every reference scored 100 three times.

### E0 controls

| Task | Control | Kind | Run id | Result |
| --- | --- | --- | --- | --- |
| `dst-fixed-bundle-regressions` | `target-negative-preview-left-broken` | target-negative | `run-446dfa8671174b94` | 10; fails only `a saved bundle with a blank preview shows its items after loading`; `the preview of a bundle the game wraps from prefab names lists every item`; admissible |
| `dst-fixed-bundle-regressions` | `target-negative-surprises-still-held` | target-negative | `run-559e3041ee2a4526` | 10; fails only `a surprise gift opened from the inventory releases its creature`; admissible |
| `dst-fixed-bundle-regressions` | `compat-negative-drops-unpickable-items` | compat-negative | `run-1248bf4d0b634786` | 10; every target passes; fails only `moongleam from a held bundle goes into the player's inventory`; admissible |
| `dst-fixed-bundle-regressions` | `alternative-a` | alternative | `run-c6a5fd45491349dd` | 100; admissible |
| `dst-fixed-module-regressions` | `target-negative-extra-moon-glass-kept` | target-negative | `run-2f8c9d5e9c404c92` | 10; fails only `the celestial portal receives exactly one moon glass per dial`; admissible |
| `dst-fixed-module-regressions` | `target-negative-watch-hooks-still-skipped` | target-negative | `run-5237f5a08bd84cfd` | 10; fails only `a Backtrek Watch can be given a name that shows in its display name`; `a named Rift Watch keeps its name across a save and reload`; admissible |
| `dst-fixed-module-regressions` | `compat-negative-temporary-portal-never-registered` | compat-negative | `run-bdd5cf7e30b04672` | 10; every target passes; fails only `using a Desert Stone opens a temporary Lazy Deserter that other portals lead to`; admissible |
| `dst-fixed-module-regressions` | `alternative-a` | alternative | `run-7bcf6bab8fcd4ea7` | 100; admissible |
| `composting-together-regressions` | `target-negative-debug-durations-kept` | target-negative | `run-5147e80b32574cf4` | 10; fails only `a small batch takes three days to become compost`; admissible |
| `composting-together-regressions` | `target-negative-old-load-restoration` | target-negative | `run-d518192913524618` | 10; fails only `a finished pile still offers its harvest after a save and reload`; `an empty pile stays empty and usable after a save and reload`; admissible |
| `composting-together-regressions` | `compat-negative-composting-lost-on-load` | compat-negative | `run-f4b3ed7fab8849c4` | 10; every target passes; fails only `a composting pile that is saved and reloaded finishes on time`; admissible |
| `composting-together-regressions` | `alternative-a` | alternative | `run-207b58c0ba234ca4` | 100; admissible |
| `dsmmo-release-regressions` | `target-negative-self-attack-still-retaliated` | target-negative | `run-58560bff13444f7d` | 10; fails only `a player who hurts themselves is not chased by their own bee`; admissible |
| `dsmmo-release-regressions` | `compat-negative-haunt-branch-removed` | compat-negative | `run-cc93b6fdde01488d` | 10; every target passes; fails only `Ghosty fireflies turn a haunted evil flower into fireflies`; admissible |
| `dsmmo-release-regressions` | `alternative-a` | alternative | `run-663722ae965149ef` | 100; admissible |
| `glassic-api-regressions` | `target-negative-sort-leaves-hole` | target-negative | `run-6b10590d00d240a4` | 10; fails only `sorting a recipe after a later one keeps every recipe of the filter listed`; `sorting a recipe before an earlier one keeps every recipe of the filter listed`; `sorting a recipe to the end of a filter keeps every recipe listed`; admissible |
| `glassic-api-regressions` | `target-negative-vanilla-character-still-removed` | target-negative | `run-7aba8e13d30045eb` | 10; fails only `a vanilla character that receives mod skins stays selectable`; admissible |
| `glassic-api-regressions` | `compat-negative-borrowed-characters-kept` | compat-negative | `run-d518d0ec48744b5e` | 10; every target passes; fails only `a mod character that receives mod skins is only borrowed into the base character list`; admissible |
| `glassic-api-regressions` | `alternative-a` | alternative | `run-9eda921044bd49b3` | 100; admissible |

### Final images

Except for `dst-fixed-module-regressions`, the runs above used verifier images
built before two plugin changes that do not
change how a submission is graded: a typing-only change in
`rhenium_dst/evaluator.py`, and a 300 s timeout (was 60 s) for the host-side Docker
daemon probe and image inspections in `rhenium_dst/container.py`. Both files are
part of the evaluator copy inside the images. After the changes the copy was
regenerated, the runtime was prepared again, and each starter and reference was
run once more on the final images:

| Task | Starter | Reference |
| --- | --- | --- |
| `dst-fixed-bundle-regressions` | `run-1cdb53fc25e847c4`: 10; fails exactly the 5 target cases | `run-a458374cc2ef4d86`: 100; admissible |
| `dst-fixed-module-regressions` (old suite) | `run-dbb814fde57d43b0`: 10; fails exactly the 6 target cases | `run-c7dc48041b564f71`: 10; failed `the celestial portal receives exactly one moon glass per dial`; see below |
| `composting-together-regressions` | `run-43aece7ed81e4408`: 10; fails exactly the 8 target cases | `run-b4d5224e62824f32`: 100; admissible |
| `dsmmo-release-regressions` | `run-9089da9519944a98`: 10; fails exactly the 5 target cases | `run-b0d60551b7c148d1`: 100; admissible |
| `glassic-api-regressions` | `run-6cc084ef7f4540c5`: 10; fails exactly the 4 target cases | `run-7d664f1cc1514522`: 100; admissible |

### Revision of the DST Fixed module suite

The final-image reference run `run-c7dc48041b564f71` of `dst-fixed-module-regressions`
failed `the celestial portal receives exactly one moon glass per dial`: no moon glass was
found near the celestial portal. Each run generates a new world, and the portal and one
moon dial stood at fixed offsets from the spawn portal. Moon glass flung onto an ocean
tile sinks, so the most likely cause is a coastline at that spot; the server log does not
confirm it. The suite now places each check that looks for dropped items at the nearest
offset where all ground within its search radius is land, and keeps the old offset when
it qualifies. Case names, roles and the exam are unchanged. The task's two-way
validation and all of its controls were then rerun on the revised suite and final images;
those are the runs in the tables above. The superseded runs on the old suite are
`run-1739c3d4e0044f24`, `run-429ebb943de74a0f`, `run-e6cd1e3feeba4f73`, `run-3d9ca22957344661`, `run-b9d855edfb5e4844`, `run-1bbd37738b1142a4`, `run-a4e63920a95f4011`, `run-7c89bf51a4ad4a25`.

### Current runtime artifact

After the sixth task was dropped, `rhenium runtime prepare dst/dst-dedicated-24700372`
ran again. The resulting artifact holds five task images, with identity
`sha256:13725ee2a95c475d7a0b701488469c119281d062a323fe11142d48f56d0fad3f` and base
image `sha256:86a368666fc88cae1cc3ff32a398b4e8dfc69f97671e60c2464d4c74198b73eb`. The
build cache of the layers from `COPY evaluator` on had been evicted on this shared
host, so those layers and the task images were rebuilt and their IDs differ from the
images used for the runs above. Suites and harness files did not change, and the
evaluator files in the new base image hash-compare identical to the repository copy.
A smoke run of the Glassic API reference on the new images (`run-14859260ef0c4976`)
scored 100 with all 8 cases observed. The other tasks were not rerun on these images.

### Dropped task

A sixth task, `wolly-logger-regressions` (Wolly Logger from `Crestwave/dst-misc`), passed
the same two-way validation and controls but was removed from the pack for licence
provenance: the mod was published on the Steam Workshop by its author without a
licence and only later imported into an MIT-licensed repository by someone else. Its
runs are not part of this record.

### Method notes

- Before the Hub runs, every suite, starter, reference and control was also run
  against the same server build with the plugin's dedicated-server runner in a
  scratch container. Those runs are development evidence only and are not recorded
  here.
- Some `rhenium run` invocations ended before evaluation with `KeyError: 'dst/core/<task>'`
  or `database is locked`. Every Hub process re-materializes the starter
  workspaces of all packs and writes the shared `.rhenium/hub` database at start-up, and
  concurrent Hub processes on this shared host raced on that. Such invocations
  produced no result and were rerun.
- Some evaluations came back incomplete because the congested Docker daemon did not
  create the verifier container within the 300 s timeout. An incomplete result is
  not evidence either way; each was rerun and the complete rerun is the one
  recorded above: `run-649e33b15fe94b49` (dst-fixed-module-regressions--reference-r1), `run-39d86458d7414ff2` (dst-fixed-module-regressions--reference-r1), `run-a95599b10a3f4365` (dst-fixed-module-regressions--reference-r1), `run-8a3bd403d0384201` (dst-fixed-module-regressions--reference-r2), `run-e0a11590fd36400e` (dst-fixed-module-regressions--starter), `run-c96d5ef809d14206` (dst-fixed-module-regressions--starter), `run-3c45c936fc3247d1` (dst-fixed-module-regressions--starter), `run-28c2916970dc4755` (glassic-api-regressions--starter).
- After repeated create timeouts on the revised module image, one `docker create` of
  that image without a timeout was run by hand (it took 231 s, while the daemon
  prepared the new image's snapshot) and the container was removed at once. It ran no
  evaluation.
- No complete result was discarded or rerun.

### Images rebuilt for the combined plugin (2026-09-24)

The plugin was then extended to serve the restored construct pack
(`dst/construct`) as well; repair tasks keep the evaluator above, and construct
tasks are dispatched to a separate construct evaluator. Because the images embed
the whole plugin, the runtime was prepared again (artifact identity
`sha256:8bb9455f87acc8e690da605f4dd86bc13ba16c3cacd5c29d53b466ce2cad465d`; the
server layers came from the Docker build cache). Two tasks were checked on the
rebuilt images:

| Task | Starter | Reference |
| --- | --- | --- |
| `dsmmo-release-regressions` | `run-27dc050a534749eb`: 10; fails exactly the 5 target cases | `run-99a9aacad5bf4e2e`: 100; complete, passed |
| `glassic-api-regressions` | `run-d2087b82611d4be8`: 10; fails exactly the 4 target cases | `run-c556b9db741b4219`: 100; complete, passed |

The other three tasks were not rerun on the rebuilt images.

## Not validated

- The Harbor CLI `oracle`/`nop` trials and `private/harbor/scripts/validate-all.sh`
  were not run for the repair tasks. The catalog 3.0.0 Hub runs and the catalog
  4.0.0 `validate-task.sh` runs use the same verifier images and evaluator code.
- Catalog 4.0.0 through the Hub: `rhenium runtime prepare` and `rhenium run` were
  not repeated, and each 2.0.0 reference ran once, not three times.
- macOS and Windows/WSL2 hosts: no engine evidence.
- The `untrusted` security mode: no disposable-host provider exists.
- Model attempts: no model has been run on the task version 2.0.0 tasks.
