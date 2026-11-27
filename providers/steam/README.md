# Rhenium Steam provider

`rhenium-steam` is an independent Rhenium auth provider for Steam QR login and
pinned licensed-depot acquisition. Game plugins describe the depots they need;
this package owns the reusable Steam session and downloads those depots without
putting Steam-specific behavior in Rhenium core.

An opt-in [controlled official-client backend](CONTROLLED-CONSOLE.md) can reuse an
already signed-in independent Linux client for exact-depot preparation. It requires
an explicit private profile and approved container-loopback CEF control. The default
helper/QR path is unchanged; this backend does not provide client/login bootstrap.

For the complete runtime lifecycle and game-plugin contract, read
[Managed authentication and runtimes](../../docs/managed-runtimes.md).

## Installation and discovery

The repository development environment installs every workspace distribution:

```sh
devenv shell
rhenium auth list
```

The result must include provider ID `steam`. Outside the workspace, build and
install `rhenium` and `rhenium-steam` into the same Python 3.12 environment:

```sh
uv build --package rhenium --out-dir dist
uv build --package rhenium-steam --out-dir dist
python -m pip install dist/rhenium-0.6.0-py3-none-any.whl \
  dist/rhenium_steam-0.1.0-py3-none-any.whl
```

The provider is intentionally not a dependency of core-only Rhenium.

## Operator use

The provider never accepts a Steam password. Start QR login from the CLI or the
local Web UI:

```sh
rhenium auth list
rhenium auth login steam
rhenium auth status
rhenium runtime prepare <game-id>/<runtime-id>
```

`auth login steam` shows **two QR codes, one after the other**, and each is a
separate Steam sign-in:

1. The helper's QR code authorizes depot downloads. The provider receives a
   persistent Steam refresh token through a private process pipe. CLI and API
   session views expose the account principal and non-secret metadata, not the
   token.
2. The official Steam client's QR code authorizes the client that DRM-protected
   games need in order to start with no network. The second code appears once the
   client has started, which takes a few minutes on first use because the client
   downloads itself.

The two sign-ins cannot be merged: the official client authenticates as its own
Steam device, and its stored credentials are encrypted for the machine that
created them.

Steam rotates a QR code every few seconds and the terminal keeps the old ones on
screen, so scan the **newest** code; the CLI marks each replacement. Scanning an
expired code fails the login with `Steam QR login failed`.

## Official Steam client bootstrap

Games whose runtime keeps Steam DRM, currently only Isaac, declare
`"officialClient": true` in their runtime source. `acquire` then stages the client
state into `.official-client/steam-home` inside the acquired source tree, next to
the depot files, for the game's runtime builder.

The bootstrap runs the client headlessly in a disposable container built from
`assets/steam-client.Dockerfile`: a digest-pinned Ubuntu 24.04 base plus the
32-bit runtime libraries. The client itself is installed into the operator's
client home from the bootstrap archive pinned in
`assets/steam-client-session.sh` and verified against its SHA-256, so the image
contains neither Valve's client nor any account state. Valve updates the client
itself on every start; its version is therefore **not** pinned and must not be
described as such.

The container keeps the client's Chromium sandbox enabled, drops all Linux
capabilities, and enables `no-new-privileges`. It needs `seccomp=unconfined`
because the Steam runtime isolates games with bubblewrap. The container reuses
the named AppArmor profile of the process that starts Rhenium so hosts that
restrict unprivileged user namespaces can still authorize Steam's nested
user/mount namespaces. Set `RHENIUM_STEAM_APPARMOR_PROFILE` to override that
profile when the host requires a dedicated profile; the host-wide user namespace
settings are not changed.

Every native Linux game starts through Steam Linux Runtime 1.0 (scout), and scout
itself runs inside Steam Linux Runtime 2.0 (soldier), which its tool manifest
requires. The client downloads both only while it launches such a game -- something
an offline evaluation cannot do. After the sign-in, the provider therefore acquires
them with the Steam helper from their pinned depots:

| App | Depot | Manifest | Build | Installed as |
| --- | --- | --- | --- | --- |
| `1070560` | `1070561` | `4956520704156364317` | `23825428` | `SteamLinuxRuntime` |
| `1391110` | `1391111` | `2977690073285208032` | `24599738` | `SteamLinuxRuntime_soldier` |

For each one it restores the execute bits a depot download does not carry, writes the
matching `appmanifest` with `StateFlags "4"`, and records the app in
`steamapps/libraryfolders.vdf`, so the client treats the runtime as fully installed and
does not try to download it with no network. The session records the outcome as
`officialClient.steamLinuxRuntime`.

Requirements and behavior:

- Linux x86_64 with Docker. On any other host the helper login still completes and
  the session records `officialClient.state` as `unavailable` with the reason.
- `RHENIUM_STEAM_SKIP_OFFICIAL_CLIENT=1` skips the bootstrap for depot-only use.
- A client home that already holds a sign-in is reused: a later `auth login steam`
  re-authorizes the helper session and shows only its QR code. Delete the client
  home to force a fresh client sign-in.
- The client state lives in
  `$RHENIUM_STATE_DIR/providers/steam/<account-alias>/official-client`. It holds a
  reusable Steam sign-in and is exactly as sensitive as the refresh token: never
  copy, publish, or bake it into a shared image.
- `auth logout` removes only Rhenium's local record. Revoke the device in Steam
  itself if the host may be compromised.

Unit tests cover this flow with a fake container runtime. On a licensed Linux
x86_64 host, a live helper QR sign-in, the reuse of an already signed-in client,
and the staging of both pinned runtime depots have been validated against real
Steam content: the staged trees match the layout the client produces itself, and
their execute bits, app manifests, and library index were verified on disk.
`runtime prepare` for a DRM-protected game and an engine-backed evaluation of it
have **not** yet completed end to end.

Use a named account when necessary:

```sh
rhenium auth login steam --account maintainer
rhenium runtime prepare <game-id>/<runtime-id> --account maintainer
rhenium auth logout steam --account maintainer
```

Logout deletes only Rhenium's local record. It reports `remoteRevoked: false` and
does not revoke the Steam device remotely.

### Private release access

The packaged provider manifest points at versioned helper assets in GitHub
Releases. When the repository is private, use either:

```sh
gh auth login
gh auth status
```

or set `GH_TOKEN`/`GITHUB_TOKEN` for an environment without `gh`. The token must
be able to read `Touchstone-AI-Lab/GameCodeBench` release assets. If `gh` is
installed, Rhenium uses `gh release download`; fix its authentication rather than
expecting a fallback to the environment token path.

## Provider extension point

The package registers one provider through Python entry-point discovery:

```toml
[project.entry-points."rhenium.auth_providers"]
steam = "rhenium_steam.provider:SteamAuthProvider"
```

`SteamAuthProvider` implements the core `AuthProvider` contract:

```python
def login(
    account_alias: str,
    *,
    challenge: ChallengeCallback,
    progress: ProgressCallback,
) -> AuthSession: ...

def validate(session: AuthSession) -> AuthSession: ...

def acquire(
    source: dict[str, Any],
    session: AuthSession,
    destination: Path,
    *,
    progress: ProgressCallback,
) -> AuthSession: ...
```

All three methods may return a refreshed session. Rhenium saves that value only
after validating that its provider ID and account alias match the request.

The provider descriptor is:

```text
id: steam
version: 0.1.0
capabilities: qr-login, persistent-session, licensed-depots
```

## Licensed-source schema

Rhenium core treats `RuntimeSpec.source` as an opaque object. The Steam helper
currently consumes this shape:

```json
{
  "kind": "steam-depots",
  "appId": 413150,
  "os": "linux",
  "depots": [
    {"id": 413153, "manifest": "6005910083361727734"}
  ],
  "expectedFiles": ["Stardew Valley.dll", "Content"],
  "sha256": {
    "optional/file": "optional-pinned-file-sha256"
  }
}
```

Field behavior:

| Field | Required by helper | Meaning |
| --- | --- | --- |
| `appId` | yes | Unsigned Steam application ID. |
| `depots` | yes | List of depot IDs and exact manifest IDs. Manifest IDs are decimal strings. |
| `depots[].id` | yes | Unsigned Steam depot ID. |
| `depots[].manifest` | yes | Exact unsigned 64-bit manifest ID; never use a rolling latest manifest for a reproducible runtime. |
| `os` | no | Steam platform filter passed to DepotDownloader, such as `linux`. |
| `kind` | no | Catalog convention; version 0.1.0 does not branch on it. |
| `expectedFiles` | no | Policy available to the game builder; the Steam helper does not validate it. |
| `sha256` | no | Policy available to the game builder; the Steam helper does not validate it. |

`expectedFiles` and `sha256` are declarative metadata unless the selected game
builder enforces them. Core and Steam provider v0.1.0 do not apply either field
automatically. A developer adding them to a catalog must implement and test the
corresponding builder checks; their mere presence is not verification evidence.

Acquisition always uses Steam's `public` branch, enables DepotDownloader's
file verification, and writes into the destination selected by Rhenium. Beta
branches, passwords, language filters, and file include/exclude expressions are
not part of the v0.1.0 protocol. Add them explicitly to the versioned protocol
before using them in a catalog.

The Steam account must own the requested content. A DLC depot may also require
the account to own the base app. Provider success proves that Steam delivered the
requested manifests; the game `RuntimeBuilder` remains responsible for checking
game-specific files and constructing/verifying the evaluator artifact.

## Helper resolution and integrity

The Python package communicates with a self-contained
`rhenium-steam-helper`. It resolves the executable in this order:

1. `RHENIUM_STEAM_HELPER`, intended only for local development and tests;
2. `rhenium-steam-helper` already on `PATH`;
3. the platform asset pinned by `src/rhenium_steam/helper-manifest.json`.

The first two are explicit local overrides and are not checked against the
packaged manifest. The third is downloaded to
`$RHENIUM_STATE_DIR/tools/steam/<version>/` (or `.rhenium/hub/tools/steam/` by
default), verified against its pinned SHA-256, and made owner-executable.

Supported helper assets are:

- `linux-x64`;
- `osx-arm64`;
- `osx-x64`;
- `win-x64.exe`.

The provider package does **not** embed the released binaries. Linux and Windows
assets are self-contained but are not platform code-signed. macOS builds receive
an ad-hoc signature during the build. Release authenticity relies on repository
access/TLS plus the SHA-256 pinned in the reviewed package manifest; the hash
provides integrity, not an independent publisher signature.

On Windows, the native `win-x64` helper handles QR login. Rhenium has no Windows
execution worker, so Linux runtimes are acquired and prepared on a Linux host.

## JSON Lines protocol

Rhenium starts the helper as:

```sh
rhenium-steam-helper jsonl
```

It writes exactly one request object followed by a newline to stdin. The helper
writes newline-delimited event objects to stdout and diagnostics to stderr. Every
operation ends with one `result` or `error` event.

### Commands

Login request:

```json
{"command":"login","persistent":true}
```

Validate request:

```json
{
  "command": "validate",
  "principal": "steam-account-name",
  "session": {"refreshToken": "...", "guardData": "..."}
}
```

Acquire request:

```json
{
  "command": "acquire",
  "principal": "steam-account-name",
  "session": {"refreshToken": "...", "guardData": "..."},
  "source": {"appId": 413150, "os": "linux", "depots": []},
  "destination": "/absolute/rhenium/cache/path"
}
```

### Events

QR challenge:

```json
{"type":"challenge","uri":"steam://..."}
```

Progress:

```json
{"type":"progress","value":5,"phase":"Steam session validated"}
```

Successful final result:

```json
{
  "type": "result",
  "value": {
    "principal": "steam-account-name",
    "refreshToken": "...",
    "guardData": "..."
  }
}
```

Failure:

```json
{"type":"error","message":"stored Steam session is invalid or revoked"}
```

Unknown events are forwarded to the provider callback layer; malformed JSON,
non-object events, a missing final result, or a non-zero process exit fails the
operation. Login has a 10-minute provider timeout, validation one minute, and
acquisition four hours.

The helper clears DepotDownloader's on-disk token and guard-data store in its
`finally` block. Secrets still cross the helper's stdin/stdout pipes and are
stored by Rhenium after the process exits.

## Session security

Steam passwords never enter Rhenium. Persistent refresh tokens and optional
Steam Guard data do: Rhenium 0.6 stores them as **plaintext JSON** in the local
`state.sqlite`. There is no encryption or OS-keychain integration.

Do not share or publish the Rhenium state directory. Use a trusted single-user
host, protect backups, and revoke the device in Steam if the host is lost. Avoid
passing real tokens in command arguments, environment variables, logs, fixtures,
or bug reports; the normal implementation uses process pipes.

## Local development

The helper is a small reviewed patch over the pinned upstream
DepotDownloader `DepotDownloader_3.4.0` tag. Source inputs are:

```text
helper/build-helper.sh
helper/depotdownloader-3.4.0.patch
helper/RheniumProtocol.cs
```

The patched program remains subject to DepotDownloader's GPL-2.0 license. The
normal DepotDownloader CLI is unchanged; the patch adds the `jsonl` command.

Prerequisites for a local helper build are Git, the .NET 9 SDK, and the target
platform toolchain. Build one runtime identifier into a temporary output
directory:

```sh
providers/steam/helper/build-helper.sh osx-arm64 dist
RHENIUM_STEAM_HELPER="$PWD/dist/osx-arm64/rhenium-steam-helper-osx-arm64" \
  rhenium auth login steam --account development
```

Valid runtime identifiers are `linux-x64`, `win-x64`, `osx-arm64`, and
`osx-x64`. macOS targets must be built on macOS because the script applies an
ad-hoc signature. The build script clones the exact upstream tag, applies the
patch with fuzz disabled, performs a self-contained single-file publish, and
writes a SHA256SUMS file.

### Tests

Provider unit tests use a fake executable and must not contact Steam:

```sh
uv run pytest -q providers/steam/tests
uv run ruff check providers/steam
uv run mypy providers/steam
shellcheck providers/steam/helper/build-helper.sh
```

Before changing the protocol, add tests for both the Python event parser and the
patched helper behavior. Never record a real QR URI or session token in a test
fixture.

## Release procedure

The `Steam helper` GitHub Actions workflow builds all four assets on explicit
`workflow_dispatch` and uploads workflow artifacts. It does not create a GitHub
Release or update the Python manifest automatically.

For a new helper version:

1. Review and update the pinned DepotDownloader tag/patch and provider protocol.
2. Bump the provider/helper versions as required and run all provider tests.
3. Dispatch `.github/workflows/steam-helper.yml` from the intended commit.
4. Download the four workflow artifacts and verify their generated checksums.
5. Create the immutable tag/release `steam-helper-v<version>` and upload binaries.
6. Update every URL and SHA-256 in `helper-manifest.json`.
7. Test a clean download without `RHENIUM_STEAM_HELPER` or a PATH override on
   each claimed platform.

Do not replace assets in an existing release after publishing their hashes. Cut
a new version instead.

## Troubleshooting

- `Steam helper does not support <platform>`: there is no manifest entry for the
  detected OS/architecture. Use one of the supported IDs or build a reviewed new
  target.
- `configured Steam helper is missing`: fix or unset `RHENIUM_STEAM_HELPER`.
- GitHub release download fails or returns 404: authenticate `gh`, or remove it
  and provide a repository-readable `GH_TOKEN`/`GITHUB_TOKEN`.
- `SHA-256 mismatch`: do not bypass the check. Confirm release version, asset,
  and manifest, then remove the `.partial` file if one remains.
- stored session invalid/revoked: run `rhenium auth login steam` again for the
  same account alias.
- depot access denied: verify ownership, DLC/base-app entitlement, exact depot
  and manifest IDs, and the `os` filter.
- login emits no scannable QR in the terminal: use `rhenium web`, or verify that
  the terminal renders block characters and is wide enough.
- `Steam QR login failed` right after a scan: the code had already been replaced.
  Run the command again and scan the last code printed.
