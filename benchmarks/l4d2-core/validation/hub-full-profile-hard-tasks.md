# Hub full-profile validation of the hard tasks (2026-09-24)

The five hard tasks added in pack 1.1.0 were previously validated only by direct
maintainer control runs (see each task's `NOTES.md` and
[review revisions](../review-revisions.md)). This record is the first validation of
those tasks through the Hub full profile, `rhenium run left-4-dead-2/core/<task>`,
using the same plugin evaluator as every attempt. It was run on 2026-09-24 on one
Linux x86_64 host (Linux 7.2, Docker Engine 29.8.0 with the containerd overlayfs
snapshotter on btrfs) under heavy load from other jobs. It is not evidence for
macOS, Windows/WSL2 or another filesystem.

## Why the Hub runs differed from the maintainer runs

The reference of `l4d2-competitive-score-lifecycle-hard` completed but failed 0/57
through the Hub, and several other hard-task runs ended incomplete. Four verifier
harness defects in the tasks' `tests/verify.py` were found. The first two explain
those results; the other two appeared during the validation runs. None of the fixes
changes a suite, case name, weight, pass criterion, exam, starter or reference.

1. **Plugin load order (score task).** SourceMod autoloads the plugin directory in
   raw directory-entry order, not by file name. The verifier copied the score plugin
   into the directory before `00_left4dhooks.smx`. This host's overlay upper layer
   enumerates entries in creation order, so SourceMod loaded the score plugin first
   and its `OnMapStart` called `L4D_GetVersusMaxCompletionScore` before Left4DHooks
   had started. Every suite boot logged a SourceMod exception and failed closed,
   reference included. The maintainer runs used a hash-ordered filesystem that
   happened to list Left4DHooks first. The verifier now creates the binaries in their
   numbered load order (Left4DHooks, L4D2Lib, the score plugin, the suite) and returns
   `INVALID_ENVIRONMENT`, an incomplete run and never a verdict, when the directory
   still enumerates them in another order. A hash-ordered filesystem such as ext4 may
   therefore make this task incomplete; that case was not exercised. The other
   SourcePawn hard tasks do not call Left4DHooks natives from `OnMapStart` and keep
   their staging order.
2. **Server reaping (all five hard tasks).** After the suite's FINAL marker the
   verifier stops the server with SIGTERM, then SIGKILL, and waited five seconds for
   each. On this loaded host the multithreaded srcds took 8 to 15 seconds to be reaped
   after SIGKILL, measured with an instrumented copy of the verifier. The
   `subprocess.TimeoutExpired` traceback left no case lines, so the run was
   incomplete. The verifiers now wait up to 120 seconds after SIGKILL and report
   `INVALID_ENVIRONMENT` if the server is still not reaped.
3. **Boot deadline (all five hard tasks).** Each server boot had 55 seconds of wall
   time to reach its FINAL marker. A healthy boot needs 5 to 15 seconds. On
   2026-09-24, one L4D2Lib reference Tank boot stalled during plugin loading for
   longer than that. The SourcePawn verifiers treat a missing FINAL as a failure of
   every case in that boot, so the reference received a complete 23/44 verdict
   (`run-16e3db396d2f494e`, prepare-2 image). The VScript verifiers already ended such
   runs as incomplete. All five hard verifiers now allow 240 seconds. The Harbor
   `timeout_sec` metadata in `task.toml` is unchanged. The L4D2Lib starter's map boot
   still never reaches FINAL: in an instrumented run with a 300-second budget its
   server process exited about four seconds after map load, so that is starter
   behaviour, not host delay.
4. **Failure message (three SourcePawn hard tasks).** When a suite boot fails closed,
   every case is printed as `FAIL <case>: <detail>`. The detail was the last server
   line containing the substring `error`: `Invalid counterterrorist spawnpoint`,
   `dlopen ... with error:` or `END ERRORS FROM AUTOMATIC UPDATER`. It now names the
   SourceMod exception or a missing FINAL marker. The message never affects a verdict.

`plugins/left-4-dead-2/tests/test_l4d2_hard_verifier_harness.py` covers these
helpers. The runtime was re-prepared with
`rhenium runtime prepare left-4-dead-2/l4d2-23990100-sourcemod-1.12.7246`.
The verified artifact identity is `sha256:479174442e5f90851216e7428cfdafa47a86f5281e51299edc43c0c517e86b2b`.

Every prepare assigns new image IDs, even to unchanged tasks: BuildKit stores each
image as an index that carries build attestations, and those differ per build. The
base image's filesystem layers were identical across all four builds on this host.
The images of the five original tasks therefore changed identity but not content.
The results below were produced on the final (fourth) build. Earlier builds were used
only for diagnosis and are cited only where stated.

| task | verifier image |
| --- | --- |
| `l4d2-competitive-release-regressions-easy` | `sha256:e0b6223ee3a62ca509557d55446f1f98268f72af4149abb11203046dc0a7b16b` |
| `l4d2-left4dhooks-api-regressions-medium` | `sha256:514c5321b721f77e1152515c2c62fb570ee4f4bda0374e23e99b792219279327` |
| `l4d2-infected-bots-release-regressions-medium` | `sha256:ae8d05c38ea8a06b3896cfd48fb7bd8d1e7390f1f60c9f6c1b13322418ba0692` |
| `l4d2-linge-release-regressions-hard-v3` | `sha256:b8f237cf2d4e0b9b1756a235a37a1061711a552d2992dcfe952c788453f1567e` |
| `l4d2-mutant-tanks-release-regressions-hard` | `sha256:e979749ccb0a647b47808d22c8fcb0b2d8c46a1b7ac2921f416d0df562b5a151` |
| `l4d2-linge-director-state-hard` | `sha256:4cd34822c13d47752ec70908f1949a9fa3bd4680e00b6c9973a0769442bd9e3f` |
| `l4d2-competitive-score-lifecycle-hard` | `sha256:fa0c3e08df241bbc9402f8bfaa487ae911027e0165197ec32f2c17bb547e97a8` |
| `l4d2-vslib-scheduler-persistence-hard` | `sha256:96293b942d5283a4616f3e0a2685c267aa0fc0ae6df5f5e9e112d61d0f003f2b` |
| `l4d2-confogl-cvar-transactions-hard` | `sha256:ea0f0828734dc40d8f73b054f2083ff9b31d66ee4bf03380ba0f8cda9ee4a1d5` |
| `l4d2-library-map-tank-state-hard` | `sha256:696134f77e37d2225c883fa1a003d1fe503dc98496da087c92c2aa4959620129` |

## Two-way validation

Every result below was complete. Reference case outcomes were identical in all three
runs. Starter failures are exactly the cases mapped `target` in
`private/study-controls/<task>/clause-map.json`, plus the two L4D2Lib `setup` fixtures,
which fail with that starter's fail-closed boots. Every `preserved` case passed on the
starter.

The evaluations were run one at a time. Seven attempts in this final batch produced no
verdict and were repeated; none produced a case line. Three reached the evaluator, but
`docker create` exceeded the plugin's 300-second bookkeeping timeout on the congested
host, so the result was incomplete: `run-a1d0c8bac9914b8e`, `run-205fa4daf83f4e40`
and `run-e752d5b7f03f489d`. Four more stopped on a locked shared Hub database before
the container started. Only completed runs are cited as evidence.

| task | unchanged starter | reference | target / preserved cases |
| --- | --- | --- | --- |
| `l4d2-linge-director-state-hard` | 11/41 (`run-7d142ea9b8494564`) | 41/41 x3 (`run-409c68dbc2194f43`, `run-18fde9775ee74b66`, `run-d1cf05e2cf224e37`) | 30 / 10 / 1 setup |
| `l4d2-competitive-score-lifecycle-hard` | 17/57 (`run-f96d18bd6faf4b3c`) | 57/57 x3 (`run-3c93b754ae484cdd`, `run-d243a61e85854271`, `run-bc3e81354a474863`) | 40 / 17 |
| `l4d2-vslib-scheduler-persistence-hard` | 15/52 (`run-3ab1ea8570e7409b`) | 52/52 x3 (`run-37cde9bbcb384741`, `run-911d9563955f4a86`, `run-5b3990e74ac446e1`) | 37 / 15 |
| `l4d2-confogl-cvar-transactions-hard` | 0/42 (`run-901ae3ef40d74b46`) | 42/42 x3 (`run-5521d56bbb2348ba`, `run-cd3f72e89b784cfb`, `run-d76756ac56174bb8`) | 42 / 0 |
| `l4d2-library-map-tank-state-hard` | 0/44 (`run-a8ecfb858ffd443c`) | 44/44 x3 (`run-8c076b5a048b43a5`, `run-310d4046691f4fe1`, `run-b504d548f92a4f03`) | 42 / 0 / 2 setup |

The Confogl and L4D2Lib starters fail closed. The Confogl starter raises a SourceMod
exception (`Invalid index -1` in `confogl_cvardiff`) during its single boot. The
L4D2Lib starter throws `Client index 0 is invalid` in the Tank boot, and its map
boot's server exits shortly after map load without reporting FINAL. Both starters
reached 0 cases on every run, so these two tasks have no preserved baseline. The
maintainer runs recorded the same fail-closed 0/N outcome for both.

## E0 study controls

Controls are declared in `private/study-controls/<task>/manifest.tsv` and were
evaluated as study-style trees: the base was built by the task's relocated
`solution/solve.sh`, then the patch was applied with `patch -p1` through `rhenium run`.

| task | control | kind | cases passed | failing cases |
| --- | --- | --- | --- | --- |
| `l4d2-linge-director-state-hard` | `tn-dispatch-snapshot-unfixed` | target-negative | 38/41 (`run-654ea76414ec4043`) | `event-nested-sees-current-registration`, `event-prepend-next-dispatch`, `event-remove-current-snapshot` |
| `l4d2-linge-director-state-hard` | `tn-quantity-ceiling-unfixed` | target-negative | 40/41 (`run-a54fdf2810224261`) | `director-minimum-obeys-ceiling` |
| `l4d2-linge-director-state-hard` | `cn-duplicate-registrations-collapsed` | compat-negative | 40/41 (`run-acc5787a8ee34409`) | `event-duplicates-binding-index` |
| `l4d2-linge-director-state-hard` | `alternative-sorted-index-snapshot` | alternative | 41/41 (`run-629014149cfa49f2`) | none |
| `l4d2-competitive-score-lifecycle-hard` | `tn-unload-baseline-unfixed` | target-negative | 55/57 (`run-d432f0ffcebd4255`) | `unload_new_instance_snapshot`, `unload_restores_startup_values` |
| `l4d2-competitive-score-lifecycle-hard` | `cn-dead-survivor-frees-roster-slot` | compat-negative | 56/57 (`run-2d963a8fcf7f4399`) | `score_roster_limit` |
| `l4d2-competitive-score-lifecycle-hard` | `cn-finalized-damage-guards-removed` | compat-negative | 55/57 (`run-1bf073f21c164232`) | `round_finalized_plasma_event`, `round_finalized_sdk_damage` |
| `l4d2-competitive-score-lifecycle-hard` | `alternative-userid-bounded-refund` | alternative | 57/57 (`run-d8510fe3f3f44bf8`) | none |
| `l4d2-vslib-scheduler-persistence-hard` | `tn-legacy-key-substring` | target-negative | 51/52 (`run-6e3608ced565479e`) | `legacy-prefix-not-substring` |
| `l4d2-vslib-scheduler-persistence-hard` | `cn-removed-peer-still-runs` | compat-negative | 51/52 (`run-e28fa2d626414c20`) | `timer-remove-due-peer` |
| `l4d2-vslib-scheduler-persistence-hard` | `cn-copy-array-payloads` | compat-negative | 51/52 (`run-f16d432e6b9248c8`) | `timer-array-payload-identity` |
| `l4d2-vslib-scheduler-persistence-hard` | `alternative-reversed-exponent` | alternative | 52/52 (`run-4754ec191d3949d8`) | none |
| `l4d2-confogl-cvar-transactions-hard` | `tn-bounded-string-numeric` | target-negative | 41/42 (`run-8a2f74a3e7e240c6`) | `bounded-string-finite-writeback` |
| `l4d2-confogl-cvar-transactions-hard` | `tn-finite-writeback-single-pass` | target-negative | 40/42 (`run-e5b8bfa6cda24aee`) | `bounded-string-finite-writeback`, `finite-cross-callback-return` |
| `l4d2-confogl-cvar-transactions-hard` | `alternative-reverse-apply` | alternative | 42/42 (`run-228dc4b54be54be3`) | none |
| `l4d2-library-map-tank-state-hard` | `tn-syntax-validation-missing` | target-negative | 43/44 (`run-159331ec3ae449f2`) | `failed-reload-keeps-image` |
| `l4d2-library-map-tank-state-hard` | `tn-death-timer-postponed` | target-negative | 40/44 (`run-0b45fdbfe1b74bec`) | `duplicate-death-once`, `handoff-cancels-death`, `new-encounter-after-death`, `new-encounter-count-reset` |
| `l4d2-library-map-tank-state-hard` | `alternative-squared-geometry` | alternative | 44/44 (`run-c52679c991594a0b`) | none |

The alternatives come from the pack's existing `validation/candidates.py`. They are
reference-derived variants, not independent implementations. The compat-negatives
`cn-dead-survivor-frees-roster-slot`, `cn-duplicate-registrations-collapsed` and
`cn-copy-array-payloads` were written for this record. Confogl and L4D2Lib have no
compat-negative because no case passes on their starters.

## Original five tasks after the re-prepare

Two of the original tasks were re-run through the Hub on the final images. The
other three were not re-run on them. On the intermediate prepare-2 images, the
Infected Bots starter ended incomplete in all three attempts. Its unchanged verifier
has the same five-second reap wait (`subprocess.TimeoutExpired` in `stop_process`),
and the reference passed 18/18 (`run-e694fcdac90f48b1`). The original verifiers
share the reap wait and the short FINAL budgets (35 to 55 seconds). They were not
changed here and remain exposed to incomplete runs on a loaded host.

| task | recorded starter / reference | starter now | reference now |
| --- | --- | --- | --- |
| `l4d2-competitive-release-regressions-easy` | 13/20 / 20/20 | 13/20 (`run-a85cc0f6e06a4a18`) | 20/20 (`run-7879c768a7d9423a`) |
| `l4d2-linge-release-regressions-hard-v3` | 28/42 / 42/42 | 28/42 (`run-118492a8fb734bfd`) | 42/42 (`run-76eccdec5e964787`) |

## Limits

- One host, one filesystem and one Docker configuration. Load order on hash-ordered
  filesystems and the Windows/WSL2 or macOS runners were not exercised.
- The receipts in each task's `validation/` directory are historical. They are
  bound to the previous `tests` hash and were not rewritten.
- These are operator-Hub runs, not `rhenium-study` records. The study Hub must copy
  the new runtime artifact from the operator database (`rhenium-study seed`) before
  its E0 records can refer to these images.
