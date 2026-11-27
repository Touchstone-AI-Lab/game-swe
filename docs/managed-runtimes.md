# Managed authentication and runtimes

Rhenium separates provider authentication, source acquisition, and game-specific
evaluator construction. Sources may be licensed depots or publicly readable,
digest-pinned images. This keeps provider credentials out of game plugins and lets
one local account session prepare runtimes for several games.

This document is the contract for operators and game-plugin developers. Steam
helper development is documented in
[`providers/steam/README.md`](../providers/steam/README.md).
The public image provider is documented in
[`providers/container/README.md`](../providers/container/README.md), and the
pinned official-download provider in
[`providers/official-download/README.md`](../providers/official-download/README.md).

## System boundary

```text
operator (CLI or local Web UI)
             |
             v
       Rhenium Hub
       |          |
       |          +-- game RuntimeBuilder
       v                    |
  AuthProvider              v
       |              immutable local artifact
       v              (for example Docker image IDs)
provider-owned source
```

The responsibilities are deliberately separate:

- Rhenium core discovers providers and plugins, stores sessions and runtime
  records, coordinates lifecycle operations, and passes ready artifacts to an
  evaluator.
- An `AuthProvider` performs interactive login when needed, validates or refreshes
  a session, and acquires a provider-specific source into a Rhenium cache directory.
  A public provider may mint an empty anonymous session, but public readability is
  not a license grant.
- A game plugin implements `RuntimeBuilder` to turn that source into a local,
  immutable evaluator artifact and to verify or prune it.
- A benchmark pack declares runtime specifications and task bindings in a
  read-only `runtimes.json` file.
- Rhenium has no Windows execution worker. A Linux runtime is prepared and
  evaluated on a Linux (or declared macOS) host; on Windows, the host ID is
  `windows-<arch>`, which no Linux runtime declares, so preparation is rejected.

An evaluation never logs in, downloads a depot, or builds a missing runtime.
Preparation is an explicit operator action.

The independent [local-files provider](../providers/local-files/README.md) can
also snapshot operator-selected local files. Its session contains no credential
and is not proof of licence ownership. Source paths live only in the selected
state-local runtime catalog; selection and copy behavior remain provider-owned.
Stardew's opt-in [macOS maintenance diagnostic](games/stardew-valley.md#macos-native-maintenance-diagnostics)
uses this provider and the existing runtime lifecycle. It is not eligible for a
complete benchmark score and does not replace the normal Linux runtime binding.

## Operator workflow

From the repository root, first check provider and host discovery:

```sh
rhenium auth list
rhenium runtime list
rhenium runtime doctor <game-id>/<runtime-id>
```

For a private GitHub repository, authenticate the GitHub CLI before the first
helper download:

```sh
gh auth login
gh auth status
```

If `gh` is unavailable, set `GH_TOKEN` or `GITHUB_TOKEN` to a token that can read
the repository. Public repositories need neither. Rhenium verifies every
download against the SHA-256 value pinned in source code or a packaged manifest.

Log in by scanning the QR code with the Steam Mobile app, then prepare and verify
the selected runtime. A runtime whose game keeps Steam DRM also needs a signed-in
official Steam client, so `auth login steam` shows a second QR code for it on a
Linux x86_64 host with Docker; see
[the Steam provider](../providers/steam/README.md) for that container and its
credential boundary.

```sh
rhenium auth login steam
rhenium auth status
rhenium runtime prepare <game-id>/<runtime-id>
rhenium runtime verify <game-id>/<runtime-id>
```

For a public, digest-pinned container runtime, login creates only an anonymous
local session and never contacts the registry:

```sh
rhenium auth login container
rhenium runtime prepare <game-id>/<runtime-id>
rhenium runtime verify <game-id>/<runtime-id>
```

The subsequent explicit `prepare` performs the pull. Public readability does not
make the image openly licensed, signed, or safe to redistribute.

For an official game or dedicated-server distribution that is not on Steam, the
independent [official-download provider](../providers/official-download/README.md)
also creates only an empty, credential-free local session at login:

```sh
rhenium auth login official-download
rhenium runtime prepare <game-id>/<runtime-id>
rhenium runtime verify <game-id>/<runtime-id>
```

`prepare` downloads the exact HTTPS files the catalog names and keeps them only
when each matches its pinned size and SHA-256. Minecraft (the Paper server jar
from PaperMC's download service) and Mindustry (its official server release) use
it. Minecraft's builder additionally stops at `action_required` (`accept-eula`)
until the operator has recorded their own acceptance of the Minecraft EULA in
local state; see [Minecraft runtime setup](games/minecraft.md#runtime-setup).

Palworld uses the existing [Steam provider](../providers/steam/README.md) and a
`steam-depots` source with exact depot manifests. Its builder validates the
required files and critical SHA-256 values, compiles the pinned native loader,
and seals a local Linux image. Evaluation consumes that prepared artifact by
immutable identity and performs no acquisition or construction.

Use `--account <alias>` on `auth login`, `auth logout`, and `runtime prepare` to
keep more than one account. The default alias is `default`; aliases contain 1–64
letters, digits, dots, dashes, or underscores.

Run the full evaluation only after the runtime reports `ready`:

```sh
rhenium run <game-id>/<pack-id>/<task-id> /path/to/submission --profile full
```

To remove the acquired source, local artifact, and runtime database record:

```sh
rhenium runtime prune <game-id>/<runtime-id>
```

Pruning is destructive. It invokes the game builder's `prune` hook before
deleting Rhenium's provider and runtime caches. It does not revoke the Steam
session. `rhenium auth logout steam` removes only the local session and does not
remotely revoke a Steam device.

### Web UI

Run `rhenium web` and open <http://127.0.0.1:4317>. The Auth page displays the QR
challenge, Runtimes exposes doctor/prepare/verify/prune, and Operations shows long-running progress and action-required states.

A pack's readiness uses the runtimes bound to its current tasks. Unbound historical
or capability-probe definitions remain listed for operators and do not block a
pack whose required runtimes are ready. A catalog without task bindings still
requires all its declared runtimes. A missing required runtime stays unavailable.

The management server accepts only `localhost`, `127.0.0.1`, or `::1`. Mutating
auth and runtime API requests are additionally rejected unless the
request originates from loopback. Do not place this management UI behind a
public reverse proxy.

### Native Windows engines

Linux engine runtimes have no Windows path: run them on a Linux host. The managed
runtime path also does not apply to a separately prepared native dedicated
server that needs no account entitlement. Such a plugin may own a native runner and read-only runtime
probe, but evaluation must fail closed on an unexpected version and must never
log in, acquire, install, update, or rebuild that server. GMod Addons App 4020 uses
this narrower boundary; its operator and containment requirements are in the
[Garry's Mod support guide](games/garrys-mod.md). The Garry's Mod DarkRP and
addon-repair packs do not: both use managed container runtimes.

The GMod Addons native path has separate Windows and Linux build pins; its
Linux environment setting is not a managed-runtime artifact. Neither an anonymous download nor a native process group grants
redistribution rights or proves an untrusted-code isolation boundary.

Runtime preparation and disposable evaluation hosting are separate boundaries. A prepared
runtime proves content identity and readiness; it does not make the evaluator safe for hostile
code. Formal untrusted scoring additionally requires the provider-neutral disposable-host
contract in [Disposable evaluation hosts](disposable-evaluation-hosts.md). Evaluation must not
prepare or update a runtime inside the disposable guest.

## Lifecycle and state

A runtime key is `<game-id>/<runtime-id>`. Its fingerprint is the SHA-256 of the
complete runtime specification plus the game plugin ID and version. Changing a
depot manifest, builder plugin version, supported platform, or other spec field
therefore invalidates the previous record.

`runtime prepare` performs these steps under a per-runtime process lock:

1. Reject an unsupported host or a missing provider.
2. Verify and reuse a ready artifact with the current fingerprint when possible.
3. Mark the runtime `preparing` in the database.
4. Load the named local provider session.
5. Ask the provider to acquire the pinned source and save any refreshed session.
6. Ask the game builder to prepare an immutable artifact.
7. Reject an artifact whose runtime key or fingerprint does not match.
8. Run the builder's `verify` hook and record the artifact only when it is available.

The default state layout is:

```text
.rhenium/hub/
├── state.sqlite
├── tools/steam/<helper-version>/
└── cache/
    ├── providers/<provider>/<runtime-fingerprint>/
    └── runtimes/<game>/<runtime>/
```

Set `RHENIUM_STATE_DIR` or `RHENIUM_CACHE_DIR` to relocate these directories.
The state and cache directories are created with owner-only permissions where
the operating system supports them.

### Credential and redistribution policy

Rhenium currently stores provider session secrets as **plaintext JSON in the
local SQLite database**. The database is not encrypted and does not use an OS
keychain. Steam passwords are never requested or stored, and the helper clears
its temporary DepotDownloader token store before it exits, but the reusable
Steam refresh token held by Rhenium is still sensitive.

Therefore:

- use only a trusted, single-user machine or account;
- do not commit, back up, publish, or share `.rhenium/hub`;
- do not print `AuthSession.secret` or include it in operation/public API results;
- log out and revoke the device in Steam itself if a host may be compromised;
- never push restricted runtime images or licensed source caches to a registry;
- review every upstream license before redistributing a public-source evaluator
  image; registry readability alone grants no redistribution right.

## Real-game requirement

Every task is evaluated against the real game: the game itself, or its official
dedicated server, running the submitted code. A source projection, stubbed or
doubled engine types, or a mod loader run without the game does not count as an
evaluation, and a result that depends on one is not a full result.

The game or dedicated server is acquired automatically by `rhenium runtime prepare`
through the Steam provider (a `steam-depots` source), pinned to an exact app, depot
and build. A public, digest-pinned image may supply the evaluator's toolchain or base
system, but not the game. Only when the game is not distributed on Steam, or its
official dedicated server is distributed only outside Steam, may the runtime instead
download that official distribution automatically, pinned to an exact version and
checked by SHA-256. Operator-supplied game files, hand-prepared installations and
manual Harbor workflows do not satisfy this requirement. The official-download
provider implements that exception: Minecraft's Paper server jar and Mindustry's
official server release are acquired this way.

New game integrations and runtime changes must meet it; a pack that does not yet
meet it is not described as meeting it (AGENTS.md, "Real game and automatic
acquisition").

## Adding a managed runtime to a game

### 1. Select the runtime catalog

Add `runtime_catalog` to the pack's schema-v2 `benchmark.json`:

```json
{
  "schema_version": 2,
  "pack_id": "core",
  "plugin": "example-game",
  "catalog": "catalog.json",
  "runtime_catalog": "runtimes.json"
}
```

The path is a normalized relative POSIX path below the read-only pack root.

### 2. Declare specifications and task bindings

Create `runtimes.json`:

```json
{
  "schema_version": 1,
  "runtimes": [
    {
      "id": "example-1.2.3",
      "name": "Example Game 1.2.3",
      "version": "Steam build 123456",
      "provider": "steam",
      "restricted": true,
      "host_platforms": ["linux-x64", "darwin-arm64"],
      "source": {
        "kind": "steam-depots",
        "appId": 1234,
        "os": "linux",
        "depots": [
          {"id": 1235, "manifest": "1234567890123456789"}
        ]
      }
    }
  ],
  "task_bindings": {
    "local-task-id": ["example-1.2.3"]
  }
}
```

Runtime IDs are unique within the catalog. Every task binding is non-empty and
references declared runtime IDs. `source` is opaque to core and is interpreted
by the selected provider; the Steam schema is documented in the
[Steam provider guide](../providers/steam/README.md#licensed-source-schema).

For a public image, use the independent `container` provider and pin the complete
OCI/Docker manifest digest:

```json
{
  "id": "example-server",
  "name": "Example headless server",
  "version": "reviewed image manifest",
  "provider": "container",
  "restricted": false,
  "host_platforms": ["linux-x64"],
  "source": {
    "kind": "container-image",
    "image": "ghcr.io/example/server@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "expectedFiles": ["opt/example/entrypoint.sh"]
  }
}
```

The provider rejects tags and malformed digests, pulls the exact reference,
checks the daemon's `RepoDigests`, and records a non-secret `image.json`. It does
not interpret `expectedFiles`: the game builder that declares that field must bind
the record back to the exact source reference and validate every expected path
before building. The artifact must then record derived image IDs, not local tags.
See the [container provider contract](../providers/container/README.md) for the
record schema, local Docker trust boundary, and test requirements.

For an official distribution outside Steam, use the independent `official-download`
provider and pin every file by exact HTTPS URL, size, and SHA-256:

```json
{
  "id": "example-server-1.2.3",
  "name": "Example dedicated server 1.2.3",
  "version": "1.2.3",
  "provider": "official-download",
  "restricted": false,
  "host_platforms": ["linux-x64"],
  "source": {
    "kind": "official-download",
    "files": [
      {
        "name": "server.jar",
        "url": "https://downloads.example.org/releases/1.2.3/server.jar",
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "size": 12345678
      }
    ],
    "redirectHosts": ["objects.example-cdn.net"],
    "expectedFiles": ["server.jar"],
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }
}
```

The provider follows redirects only to the URL's own host and the declared
`redirectHosts`, and only over HTTPS. It keeps a file only when its size and digest
match, and it reuses an unchanged complete cache. It never overwrites a partial or
changed cache. It passes `expectedFiles` and `sha256` through without interpreting
them, so a builder that declares them must still validate the acquired files. See
the [official-download provider contract](../providers/official-download/README.md).

Host IDs are `<system>-<arch>`, for example `linux-x64`, `darwin-x64`,
`darwin-arm64`, or `windows-x64`. An empty `host_platforms` tuple means that
core performs no host restriction; it is not a portability claim.

### 3. Implement `RuntimeBuilder`

Return a builder for every runtime ID owned by the plugin:

```python
from rhenium.core.plugin import BenchmarkContext, BenchmarkPlugin
from rhenium.core.runtime import RuntimeBuilder, RuntimeSpec

class ExamplePlugin(BenchmarkPlugin):
    # descriptor, catalog, and evaluator hooks omitted

    def create_runtime_builder(
        self,
        context: BenchmarkContext,
        spec: RuntimeSpec,
    ) -> RuntimeBuilder | None:
        if spec.id != "example-1.2.3":
            return None
        return ExampleRuntimeBuilder(context)
```

The builder implements four hooks:

```python
class RuntimeBuilder(ABC):
    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]: ...
    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: RuntimeProgress,
    ) -> RuntimeArtifact: ...
    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]: ...
    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None: ...
```

Follow these rules:

- `doctor` is read-only. It reports prerequisites and never runs package managers,
  `sudo`, or system installers.
- `prepare` consumes provider-owned inputs only from `source`, writes generated state only
  under `destination` or external resources it owns, and calls `progress(0..100,
  phase)` during slow work.
- Return the exact runtime key and fingerprint expected by core. The artifact
  `identity` must identify immutable local content, such as a Docker image ID,
  rather than only a mutable tag.
- `verify` is read-only and returns at least `{"available": true}` or
  `{"available": false, "reason": "..."}`.
- `prune` removes only resources represented by the artifact and is idempotent
  where practical. Core removes its two cache directories afterward.
- Never include credentials, licensed file contents, or private test data in
  artifact metadata or progress messages.
- When a source declares `expectedFiles` or `sha256`, the builder validates those
  fields explicitly and tests both success and mismatch paths; core does not do it
  automatically.

If preparation requires a legitimate interactive step that Rhenium cannot
automate, raise `RuntimeActionRequired(kind, message, details)`. The CLI exits
with status 2 and the Web UI records an `action_required` operation. Put only
non-secret instructions and paths in `details`. The operator completes the step
and reruns the same `runtime prepare` command.

### 4. Consume artifacts in the evaluator

For a complete profile, core resolves the task's ready runtime bindings before
evaluation and passes them as `dict[str, RuntimeArtifact]`. Treat that mapping as
the only authority for the prepared runtime; do not discover mutable image tags,
download files, or rebuild from the evaluator.

### 5. Test the integration

At minimum, cover:

- runtime catalog validation and task bindings;
- provider missing, session missing, and unsupported-host failures;
- `doctor` without mutation;
- prepare progress, immutable artifact identity, and post-build verification;
- reuse of a verified artifact and invalidation after fingerprint changes;
- `RuntimeActionRequired` when the game needs an interactive bootstrap;
- prune behavior without touching unrelated images or directories;
- a missing runtime failing `full` with the exact prepare command;
- a known-good `full` evaluation against every claimed engine platform.

Use `RHENIUM_STEAM_HELPER` with a fake JSONL helper for Steam tests. Public-image
provider tests use a fake local Docker CLI and cover pull failure, digest mismatch,
record contents, and malformed source references. Official-download provider tests
use `httpx.MockTransport` as a fake HTTPS origin and cover success, hash and size
mismatches, undeclared or insecure redirects, partial and changed caches, and reuse
of an unchanged cache. Unit tests must not require a
Steam account, real depot, Docker daemon, or network access.

## Management API

The Web UI uses these routes:

```text
GET    /api/auth/providers
GET    /api/auth/sessions
POST   /api/auth/providers/{provider_id}/login
DELETE /api/auth/providers/{provider_id}/sessions/{account_alias}

GET    /api/runtimes?game={game_id}
GET    /api/runtimes/{game_id}/{runtime_id}/doctor
POST   /api/runtimes/{game_id}/{runtime_id}/prepare
POST   /api/runtimes/{game_id}/{runtime_id}/verify
DELETE /api/runtimes/{game_id}/{runtime_id}

GET    /api/operations?limit=100
GET    /api/operations/{operation_id}
POST   /api/operations/{operation_id}/cancel
```

Login and prepare return an operation immediately. Poll the operation resource;
Steam QR data appears at `publicState.challenge`, and an interactive runtime step
appears at `publicState.action`. Operation responses and session views omit
provider secrets. A cancel request is recorded for observability; providers and
builders must not currently rely on it as an immediate process interruption.

Mutating management routes require a loopback client. Applications embedding
`create_app()` for read-only or remote use should set `management_enabled=False`.

## Troubleshooting

Start with these non-mutating checks:

```sh
rhenium auth list
rhenium auth status
rhenium runtime list
rhenium runtime doctor <game-id>/<runtime-id>
```

Common failures:

- `auth provider is not installed`: install the independent provider distribution
  in the same Python environment as `rhenium` and verify its entry point.
- helper download returns 404: the repository is private and `gh`
  is not authenticated, or the token cannot read release assets.
- SHA-256 mismatch: discard the partial download and verify that the release and
  pinned manifest belong to the same version; do not bypass the check.
- `official-download cache is partial or does not match the pinned files`: an
  interrupted or changed download is in the provider cache. Inspect it, then run
  `rhenium runtime prune <game-id>/<runtime-id>` and prepare again; the provider
  never overwrites it.
- `requires login again`: rerun `rhenium auth login steam --account <alias>`.
- `hostSupported` is false: run on a declared platform; do not edit the catalog merely to suppress the check.
- runtime is `failed`: inspect its `error`, fix the prerequisite, and rerun
  `prepare`. The same runtime record may be retried.
- runtime becomes unavailable after Docker cleanup: run `verify`, then prepare
  again. Mutable Docker tags are not sufficient evidence of artifact availability.
