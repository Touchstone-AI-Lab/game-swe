# Palworld benchmark support

## Ownership and status

The maintainer is Rui Hu. The independent `palworld` plugin lives under
`plugins/palworld/`. Its pack is `benchmarks/palworld/`, stable catalog ID
`rhenium-palworld-v1`, catalog version **2.0.0**. Status remains Experimental.

Plugin **0.7.0** registers a native Linux x86_64 managed runtime for all ten
current construct tasks. `rhenium runtime prepare` acquires the server through
the existing Steam provider from exact depot manifests, validates the pinned
content hashes, then compiles a pinned
native UE4SS revision, patches the shared world helper and seals a local image.
The Hub evaluator uses only the ready artifact that core passes to it.

The native path uses no Windows executable, Windows host, VM or Wine. It remains
Experimental and is limited to the pinned Linux x86_64 configuration. It does
not assert general upstream Linux mod support. The original manual runtime
controls are in [Linux controls](../../benchmarks/palworld/validation/linux-controls.md).
The earlier [SteamCMD prototype controls](../../benchmarks/palworld/validation/managed-runtime-controls.md)
remain historical. Steam-depot preparation and final-source control coverage
are recorded in the [Lab controls](../../benchmarks/palworld/validation/lab-steam-depot-controls.json).

## Catalog history and compatibility

- Catalog 1.0 contained five construct tasks. Their historical real Windows
  controls are in [original controls](../../benchmarks/palworld/validation/rhenium-controls.md).
- Catalog 1.1.0 added five advanced tasks. Their separate real Windows controls
  are in [advanced controls](../../benchmarks/palworld/validation/advanced-controls.md).
- Catalog 1.2.0 translated the public exams and Harbor headers to English.
  Requirements, assertions, references and weights stayed unchanged. The earlier
  Windows evidence carried over; those controls were not rerun for 1.2.0.
- Catalog 2.0.0 retires `palbox-transfer-transaction` and
  `damage-attribution-arbiter`. Their specific native Linux engine hooks crashed
  before any assertion result. Their assets remain historical; no assertion was
  weakened to accept that failure. Two new construct identities replace them:
  `base-containment-mincut` and `guild-draft-canonical-order`.

The two replacements require exact global optimization, history stability,
canonical ties, atomic failure and validated recovery. Both start from empty
workspaces. Their suggested 960 minutes are author estimates. No model pass
rate or calibrated difficulty is claimed. The other eight task entries and all
their authored assets remain unchanged. Their study task versions remain 1.2.0;
the new tasks start at 2.0.0. Prior attempt results never transfer to new IDs.

## Native Linux managed setup

Install the core, Palworld plugin and independent `rhenium-steam` provider in
the same Python 3.12 environment. In a source workspace, `uv sync --locked
--all-packages --all-extras` installs all three. Docker must already run on a
Linux x86_64 host. No host packages or Windows features are installed by Rhenium.

```sh
rhenium auth login steam
rhenium runtime doctor palworld/palworld-linux-25247047-native-2397c7b
rhenium runtime prepare palworld/palworld-linux-25247047-native-2397c7b
rhenium runtime verify palworld/palworld-linux-25247047-native-2397c7b
rhenium run palworld/core/base-containment-mincut /path/to/submission --profile full
```

The dedicated server needs no official Steam client. For depot-only login, set
`RHENIUM_STEAM_SKIP_OFFICIAL_CLIENT=1` when running `rhenium auth login steam`.

`auth login steam` uses the existing QR-authenticated Steam session; Rhenium
never requests or accepts a Steam password. Preparation downloads Steam App
2394010 from depot 1006 manifest `4559160656493359681` and depot 2394012 manifest
`7031055933861146620`. These pins correspond to the measured build 25247047,
v1.0.5.102999, UE 5.1.1. The builder validates required files and both critical
source hashes before building. It consumes the provider's flat depot output,
restores the server executable mode inside the image, and never accepts an
operator-supplied installation or a rolling `app_update` as a substitute.
The existing [Steam provider contract](../../providers/steam/README.md) applies.

On 2026-10-27, Lab completed Steam-depot preparation and immutable-file
verification on Linux x86_64. An earlier recipe passed all thirty maintenance
controls, including 40/40 gold real-server assertions, before the review added
explicit no-pull flags and preparation-error redaction. That predecessor is
separate historical evidence.

On the final recipe, all ten references passed at 100 with 40/40 real-server
assertions. Ten empty starters failed as incomplete. Two service-absent controls
timed out during the initial matrix; one standard recheck of each completed with
the expected failed assertions. All ten service-absent outcomes were therefore
observed, with four engine cases each, across 32 maintenance control runs. The
original matrix's two incomplete results remain recorded separately. An
ordinary CLI gold control also passed at 100 with 4/4 real-server cases.

These final controls used an isolated Docker 28 classic-store daemon. Docker
execution/cleanup timeouts also occurred on the host's Docker 29 containerd
store. Daemon and kernel captures showed prolonged overlay2 unmount and Btrfs
metadata-reservation waits; they do not establish the cause of every timeout.
Sporadic lifecycle stalls on this shared host remain a limitation, and affected
runs fail as incomplete. No authored task, assertion, reference or scoring
weight changed during review.

Lab's NixOS host used a local `RHENIUM_STEAM_HELPER` container wrapper around
the unchanged version-0.1.0 helper, whose SHA-256 matched the packaged manifest.
This is local override evidence; direct execution of the generic Linux helper
on stock NixOS is not validated. No host package or Docker configuration was
changed to prepare or evaluate Palworld.

The loader source is
[BlackBookOfficial/ue4ss-linux-palworld](https://github.com/BlackBookOfficial/ue4ss-linux-palworld)
at commit `2397c7b1ce2841fd6526b8d8110cd008c90a6316`. Its archive and all twelve
compiler dependency archives have pinned SHA-256 values. Rust is 1.90.0. The
source-only recipe ships in the plugin wheel. Docker build installs compiler
packages inside images; `doctor` and `verify` never install anything.

The shared `UEHelpers.GetWorld()` compatibility patch waits for game-thread
readiness and returns a real reflected UWorld. The real Kismet authority check
remains in use. Submission code and authored assertions are unchanged.

Preparation records the concrete Docker image ID and source/recipe identity.
`verify` checks ownership labels, architecture and sealed runtime files without
network access or rebuilding. A verified ready artifact is reused; a changed
fingerprint requires explicit preparation. Ordinary full evaluation does not
fall back to `RHENIUM_PLUGIN_PALWORLD_ROOT` or `SERVER_BIN`, pull an image,
download content or compile anything. Missing/stale runtime state fails closed
with the exact prepare command.

Every engine evaluation uses a fresh network-disabled container, UID 1001, no
capabilities, no new privileges, and CPU/memory/PID limits. Only a snapshot of
the candidate and the selected assertion suite are mounted, read-only. Hub
state, source caches, credentials and the Docker socket are not mounted in the
game container. The container and temporary snapshot are removed on completion
or failure. Ownership labels protect cleanup. A complete result requires every
named engine assertion; partial/duplicate worker output cannot pass.

Source, image-build and runtime diagnostics stay in private Rhenium cache paths.
Runtime images and acquired game content stay local and non-redistributable.
Prune removes only the selected owned artifact and core's selected caches:

```sh
rhenium runtime prune palworld/palworld-linux-25247047-native-2397c7b
```

Docker's shared build-layer cache can remain. No broad Docker prune is run.
Verification and evaluation explicitly reject a missing local image without
pulling a replacement, including when a concurrent prune removes the image.
Preparation reports file-access failures without exposing local source or artifact paths.
Parallel independent CLI startups sharing one Hub state can race the existing public-starter materialization. Use serial CLI
startup or separate state directories; this change does not add a cross-process
Hub catalog lock.
The manual prototype under `plugins/palworld/runtime/linux/` remains a historical
maintenance path, not the managed runtime's preparation input or fallback.

## Historical Windows setup

The original Windows controls used Windows 11, Steam build 24575149 and RE-UE4SS
3.0.1-1111. Those results do not validate the two new tasks on Windows.

For historical maintenance, an operator can install a disposable Windows server
with anonymous SteamCMD App 2394010 and place the reviewed RE-UE4SS files in
`Pal/Binaries/Win64/`. A directly constructed manual `PalworldRuntimeConfig`
can select that installation. These paths do not select the managed Hub
evaluator in plugin 0.7.0.
Discovery prefers `PalServer-Win64-Shipping.exe` over the launcher
`PalServer.exe`, which spawns a child. Windows discovery remains rolling and
checks file availability, not an exact game/loader version. Do not infer the
Linux launcher's hash guarantees for this older path. Rhenium has no Windows
execution worker; this plugin owns its existing native Windows runner.

## Evaluation and isolation

Submissions contain Lua as embedded by UE4SS and a JSON `Info.json` package
manifest. Core Rhenium remains game-neutral. The plugin owns runtime paths,
server execution, catalog models, Lua analysis and sandboxing.

The evaluation levels are:

1. Lua parsing, required files, package-manifest checks and structure diagnostics.
2. Sandboxed plain-Lua behavioral assertions without `io`, `os`, `require`,
   `package`, `debug`, `load`, or UE4SS globals.
3. Hidden assertions inside the real dedicated server under UE4SS.

A full pass requires all three levels and every required server assertion.
An unavailable engine is incomplete. The reduced `core` profile is always
incomplete. Portable Harbor simulation is distinct from real-engine evidence.

Plugin 0.6.1 executes submitted `scripts/main.lua` unchanged through `loadfile`
from a generated wrapper. This avoids the old parser failure when a submitted
entry point ends in a top-level `return`. Five retained public exams still
forbid that return; their frozen text has not changed. The wrapper has now run
through native Linux full-profile controls. It has not been revalidated on a
Windows server since that change.

The runner copies the submission into a random `rhenium_<hex>` mod directory,
adds one `Mods/mods.txt` line, runs a nonce-bound assertion loader, then removes
the temporary mod and restores the registry. The original submission is not
modified. Generated wrapper names and result files are reserved. The server's
own save tree is writable and is not isolated by the runner itself. Use a
throwaway installation or a separate container overlay, never a live server.
Only one evaluator process may use an installation at a time; in-process
serialization is not a cross-process lock. Server processes are terminated
when results arrive or the timeout expires.

## Harbor export

The active ten Harbor 1.4 packages are selected by the current catalog and
materializer map. Retired directories remain for history. The separate verifier
runs Lua behavior and a restricted UE4SS simulation; it does not start a game
server and records `real_palworld_server_ran=false`. A portable pass cannot
replace a Rhenium full pass. Historical Harbor oracle/nop Docker results apply
to catalog 1.x. The two new packages have local direct-verifier controls; fresh
Harbor scheduler/Docker jobs were not part of this authoring run.

The public repository contains test and reference assets. During an attempt,
the agent receives only the exam and empty starter. Tests and references remain
outside the agent workspace. See the
[Harbor README](../../benchmarks/palworld/private/harbor/README.md).

## Engine API boundary

Use `UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world)`;
`UGameplayStatics::IsDedicatedServer` is absent from the shipping build.
Wait for a valid `UWorld` before authority checks or callback registration.
`NotifyOnNewObject` requires a full class path. UE4SS logs and the nonce-bound
result file carry assertion evidence; stdout alone is insufficient.

The two new tasks register the native
`/Script/Engine.PlayerController:ServerAcknowledgePossession` hook and release
its exact pair on unmount. Controls exercise registration, release, dedicated
world authority and the trusted service protocol. They do not connect a player
to exercise possession delivery. Their graph/order inputs are trusted server
snapshots; they do not claim to manipulate actual inventories or save files.
Source-pattern gates are diagnostics, not execution evidence. The assertion
payload is authoritative; the loader's truncated textual error lines are not.

Other Linux architectures, game builds and loader commits, long-duration
stability, interactive player events, and the new tasks on Windows remain
unvalidated. A separate Wine smoke probe passed, but no full Wine task result
is claimed or needed for the native Linux path.

## References

- [Pocketpair server mod documentation](https://docs.palworldgame.com/settings-and-operation/mod/).
- [Pocketpair mod package specification](https://github.com/pocketpairjp/PalworldModUploader/blob/main/PalworldModUploader/docs/en/04-Tech.md).
- [UE4SS Lua API](https://docs.ue4ss.com/lua-api.html).
- [Native Linux port source](https://github.com/BlackBookOfficial/ue4ss-linux-palworld).
