# Prepare the native Slay the Spire task runtime

Run on x86_64 Linux with Python 3.12, Git and Docker (classic or containerd image store).
Keep generated state outside the clone and allow at least 5 GB free memory.
Prepare one runtime at a time; run real-game controls within the host's declared
CPU and memory capacity. Windows execution is not supported.

## Automatic preparation

Use the Steam provider with an account that owns the game:

```sh
rhenium auth login steam
rhenium runtime prepare slay-the-spire/sts-native-646570-build10180494
rhenium runtime verify slay-the-spire/sts-native-646570-build10180494
```

Catalog 1.7.0 prepares exactly the nine admitted real-game tasks. Enum r3
replaces the retired standalone enum r2 JVM probe with fifteen real-game
launches, and load-order r2 and mod-identity r2 run their unchanged r1 JUnit
suites inside the game launched by the submitted loader. Catalog 1.8.0
retires the last original loader task, `mts-loader-internals-regressions`,
without a replacement; the runtime task set and version are unchanged from
catalog 1.7.0. Retired tasks retain their historical source and control
records. Reprepare after upgrading from a catalog before 1.7.0 because the
runtime version/fingerprint changes with that task set.

[game-input.json](game-input.json) pins app 646570, depot 646571, manifest
9072802409324604124 (build 10180494). The builder explicitly verifies
`desktop-1.0.jar` SHA-256
`cfad868ac8d65a88e71a0bf096fb09f78811e553effe0787c5309a655e081673`.
Other game bytes are rejected. Authentication and downloads occur only during
explicit preparation, never during evaluation.

The default recipe pulls the Linux amd64 public tools image from
`ghcr.io/changyiyang/swe-game-sts-tools` using the immutable registry and image
configuration digests in [public-tools-image.json](public-tools-image.json).
It contains Java 8, Maven, Xvfb and pinned Ubuntu graphics/runtime packages,
with no game, compiled mod SDK, task, verifier, solution or model credential.
The tools package is public; game-bearing images are local and non-redistributable.
The pull accepts either image ID Docker can report for the pinned image: the
locked configuration digest (classic image store) or the pinned manifest digest
(Docker 29's containerd image store, whose manifest content-addresses that
configuration). Any other ID fails closed. Later steps build with the classic
builder from local image IDs, which resolves them on both stores. Do not
reconfigure the host daemon for a benchmark.

`recipe-manifest.json` binds preparation code and locks, retaining original
authoring-script hashes separately. Every selected task is checked against its
own frozen manifest before copying. Git LFS image pointers must be materialized;
a pointer in place of a measured image is rejected.

## Public input cache and builds

The recipe downloads pinned public Maven artifacts and Git commits, validates
the Downfall resource archive against all 8,104 recorded file hashes, then
builds the SDK, evaluator images and disposable execution copies locally.
Initial public-input acquisition uses network; SDK builds, task-image builds
and game verification run without network.

Public Maven downloads make at most six attempts for transient transport errors,
HTTP 429 or server errors, with bounded backoff. Permanent HTTP errors and
checksum failures fail closed. A `public-maven-cache` beside the private work
directory is reused across preparations; every hit and download must match both
the locked size and SHA-256. Cache writes are atomic. This cache contains public
build dependencies only, never the game, Steam session state or evaluator results.
Removing it requires downloading those public dependencies again.

Preparation records recipe, game and local image identities in
`preparation.json`. Runtime verification is read-only and checks immutable local
image IDs. Keep source caches, SDKs, execution copies and mode-0600 diagnostics
under private state/cache directories. Never upload a game-bearing image or
licensed source to a registry, release, wheel or CI artifact. Failed preparation
does not produce a ready runtime; preserve private diagnostics when investigating.

## Current controls

Replay NOP and gold through the Hub for each of the nine admitted tasks. Require
all 230 gold assertions and exactly the original NOP failure sets: descriptions
15/46, block 7/27, icons 19/43, Stasis 19/38, event transitions 13/32, socket r3
6/13, enum r3 5/15, load-order r2 5/9 and mod-identity r2 3/7. Both success and failure controls must be complete, with
successful builds, engine exits and exact observation counts. A reward alone is
insufficient.

Socket r3 additionally replays the independently different repair and the two
isolated repairs' original failure sets; see its
[authoring review](../../validation/native-engine/downfall-socket-flow-r3/revision.md).
Enum r3 replays the r2 alternative and its three isolated repairs; see its
[authoring review](../../validation/native-engine/mts-enum-identity-r3/revision.md).
The 214-case historical receipts include the enum r2 JVM probe and socket r2.
They must not be relabeled as current-version game-backed validation.

The enum r3 agent image bounds Maven's heap (`MAVEN_OPTS=-Xmx512m`, as the SDK
build does) while it builds the starter. With the unchanged r2 recipe, that
build exceeded the 1536 MB build-container limit on Lab's 104-CPU host and was
killed, which fails the whole preparation.

The load-order r2 and mod-identity r2 suites and agent images need JUnit Jupiter 5.10.2, JUnit
Platform 1.10.2 and 1.9.3, opentest4j 1.2.0 and 1.3.0, apiguardian 1.1.2 and the
Surefire 3.2.5 JUnit Platform provider. These 31 public artifacts are in
`deps/portable/maven-artifacts.json`, each pinned by path, size and SHA-256 like
every other entry; preparation downloads them from Maven Central and rejects any
other bytes. See the load-order
[authoring review](../../validation/native-engine/mts-load-order-regressions-r2/revision.md).

## Historical reconstruction

The low-level `prepare.py --game-jar ... --output ...` entry point remains for
recipe diagnostics using an exact licensed JAR and a fresh output directory
outside the clone. Operator-supplied game files and manual Harbor preparation
do not meet automatic benchmark acquisition; use the Steam workflow above for
full benchmark runs.

`--build-tools` reconstructs the public tools image from the pinned Maven base
and locked Ubuntu packages at snapshot `20260922T000000Z`. It does not change
source pins or admit additional tasks. Historical seven-task recipes and
nop/oracle records remain in [native validation](../../validation/native-engine/README.md),
including [public tools publication](../../validation/native-engine/ghcr-runtime-publication.json).
Those records describe their recorded versions; no revised task inherits a
historical result. Raw runtime logs remain private.
