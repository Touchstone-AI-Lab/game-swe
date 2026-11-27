# Historical SteamCMD prototype controls

This receipt predates the review change to the existing `steam` provider and
`steam-depots` source. Commands, fingerprints and image identities below describe
the earlier prototype only. They are not evidence that the revised acquisition
path has passed. The later [Lab Steam-depot controls](lab-steam-depot-controls.json)
record the revised path separately.

Date: 2026-10-26. This is repository maintenance, not a model attempt or a
measured model pass rate. Catalog 2.0.0 authored exams, hidden/server assertions,
reference files and scoring weights remain unchanged from the earlier authoring
commit. The game-neutral core and persistent schemas are unchanged.

## Implemented workflow

Plugin 0.7.0 registers all ten current tasks to
`palworld/palworld-linux-25247047-native-2397c7b`. The independent
`rhenium-steamcmd` provider 0.1.0 owns anonymous acquisition and Steam source
schema/manifest checks. The game builder owns required-file/content checks,
native compilation, immutable image verification and prune. Evaluation consumes
only the ready artifact passed by core; it does not fall back to Windows paths,
acquire sources, install packages or rebuild an image.

```sh
rhenium auth login steamcmd
rhenium runtime doctor palworld/palworld-linux-25247047-native-2397c7b
rhenium runtime prepare palworld/palworld-linux-25247047-native-2397c7b
rhenium runtime verify palworld/palworld-linux-25247047-native-2397c7b
rhenium run palworld/core/base-containment-mincut /path/to/submission --profile full
```

The login command creates an empty local anonymous session. No Steam password,
account or QR challenge is used. The controlled driver used Python 3.12 inside
an operator container with access to the existing Docker daemon. It installed
no host packages. The runtime recipe itself starts from public digest-pinned
Ubuntu, not the manual prototype image or the driver image.

## Acquisition and build pins

Anonymous historical `download_depot` was refused for the game depot, although
normal anonymous dedicated-server installation is permitted. The provider uses
`app_update validate` and then rejects any installation that does not match
build **25247047** and the exact depot manifests:

- 1006: `4559160656493359681`.
- 2394012: `7031055933861146620`.

That acceptance policy corresponds to game v1.0.5.102999 and UE 5.1.1. If the
public Steam branch advances, a fresh acquisition fails rather than accepting
the newer build. Cached verified content and ready artifacts can still be used.
The complete accepted installation is hash-bound in the private provider cache.

The builder separately validates `expectedFiles` and the catalog's two critical
SHA-256 pins. It compiles native UE4SS from
`BlackBookOfficial/ue4ss-linux-palworld@2397c7b1ce2841fd6526b8d8110cd008c90a6316`.
The source archive and twelve dependency archives are SHA-256 pinned. The
upstream fmt macro-conflict patch is applied explicitly because supplying fixed
FetchContent directories skips its usual `PATCH_COMMAND`. Rust 1.90.0 and the
`UE4SS` build target are selected. The shared world-helper compatibility patch
selects a real UWorld after game-thread readiness; authority is not simulated.

Runtime code permissions are normalized inside the image so a private operator
installation using umask 077 still works as UID 1001. Game/source files remain
outside the benchmark pack. No game, loader binary, credential or local image
is included in the Python wheels or uploaded to a registry.

## Prepared artifact and real engine evidence

The final prepared local artifact is:

```text
sha256:a57dfeba7e20fb01511ce2ccb80b027ff0d5ba2f55c173e148410840b930dc91
```

Explicit `runtime prepare` and `runtime verify` both returned ready/available.
The current recipe digest matches the artifact. Identity and ownership labels
are checked, and the read-only verification container checks all seven sealed
files and native x86_64 ELF headers. Each server launch rechecks the sealed files.
The exact artifact, fingerprint, runtime file hashes and per-run IDs are in
[the machine-readable record](managed-runtime-controls.json).

Two separate full-profile matrices were run on Red:

- **Ordinary `rhenium run` CLI:** ten gold controls passed at 100, complete, with
  4/4 engine cases each; ten empty NOP controls failed at 0/incomplete; ten
  service-absent controls failed with all four engine cases observed, only the
  world/API sentinel passing. This matrix used the first prepared managed image
  recorded separately in the JSON, not the old manually prepared image.
- **Final image through the public `BenchmarkHub.evaluate_task` method used by
  that CLI:** the same thirty controls passed their expected outcomes, with
  40/40 gold engine cases. One initialized Hub dispatched up to three tasks in
  parallel. The final artifact was built again after keeping provider schema
  interpretation entirely in its owning provider. Native runtime file hashes
  are unchanged; the final-image matrix is separate evidence, not a relabeling
  of the earlier controls.

The trusted CLI/Hub driver and the game containers had network disabled during
these evaluations. Game containers used UID 1001, dropped all capabilities,
no new privileges, CPU/memory/PID limits, and only read-only candidate/suite
mounts. No Hub state, source cache, credential or Docker socket was mounted in
the game container. These are honest-mode maintenance controls, not a formal
hostile-code disposable-host attestation.

A maintenance anonymous `run-attempt --profile full` gold control also passed
at 100 with 4/4 engine cases and no task key in its output. It is not a
model-under-test result or a comparable strict benchmark attempt. The exact
repository `score-exam` shell wrapper could not start its scorer because the
operator container lacks Nix and devenv; wrapper execution is explicitly unrun.

A direct ordinary CLI gold run on the final image also passed at 100 with 4/4
engine cases. A second prepare of that ready artifact was tested with network
disabled and completed in 3.49 seconds. It
reused the same image, left the source record unchanged and created no new
image-build logs. Unit tests cover source/cache mismatches, missing provider
and login, unsupported hosts, fingerprint invalidation, unowned artifact/prune
rejection, idempotent prune, exact worker case coverage, timeout cleanup,
private-code permissions and absence of implicit preparation during evaluation.

## Limits and repository checks

One standalone CLI call in the parallel CLI matrix raised a task lookup
`KeyError` before scoring. Independent Hub startups sharing one state directory
can race existing public-starter materialization. That negative control was
rerun serially and its failure-to-pass outcome was verified; the failed startup
was not counted as a scored result. The final-image matrix used a single
initialized Hub. This change does not add a cross-process core catalog lock.

The configuration remains Experimental: one Linux x86_64 host and fixed
server/loader inputs. Other architectures/builds, player-triggered hook delivery,
long-running stability, the new tasks on Windows, and fresh Harbor scheduler
oracle/NOP jobs remain unvalidated. The ordinary repository exam wrapper remains
untested in this driver, as stated above.

Ruff, Mypy, targeted provider/runtime and Palworld tests, study integration
checks, Bash syntax, ShellCheck, frontend lint/test/build, affected wheel builds
and source-only/data inspection passed. Core-only installation and no-plugin
startup passed. Frontend lint retained eight existing warnings. The exact
`devenv shell` check commands could not run locally because devenv is absent;
the locked Python 3.12 workspace environment and bundled Node 24.19.0 were used.

The final repository-wide pytest run collected 2,118 tests: 2,082 passed,
28 skipped, and eight failed in unchanged code/assets:
two Slay the Spire frozen PNG manifests, three case-sensitive hash-tree fixtures
on this macOS filesystem, and three Mindustry/RimWorld/Terraria tests requiring
the absent local Docker CLI. Other unavailable local-engine/container/JDK checks
were skipped. The separate Red controls above are the Palworld engine evidence.
Neither unrelated assets nor expected hashes were changed to accept a failure.
