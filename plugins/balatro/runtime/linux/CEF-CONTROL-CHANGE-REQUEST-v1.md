# Container-local CEF control — decision requested

The operator has authorized reuse of the independent Steam sign-in, automatic
acquisition of the fixed Balatro depot, and subsequent real Linux validation.
Those actions do not need another general approval. The additional decision
here concerns **a new control endpoint for the authenticated Steam client**.

This is our security assessment under the operator's instruction to retain the
current isolation boundaries and request additional permissions. AGENTS.md does
not specifically prohibit CEF; it does require explicit preparation, secret
protection and truthful capability claims. The previous experiments did not
enable this endpoint.

## Reviewed findings

The current helper-backed `SteamAuthProvider` requires a helper refresh token.
The existing official-client state cannot be represented as that token. Neither
credential extraction nor a fabricated helper session is proposed.

The installed client's public code contains `SteamClient.Console.ExecCommand`,
`GetAutocompleteSuggestions`, `RegisterForSpewOutput` and
`SteamClient.User.RegisterForLoginStateChange`. Its installed `steamclient.so`
contains `-cef-enable-debugging` and the literal
`--remote-debugging-address=127.0.0.1`. These are static observations, not a
successful live API test.

Valve documents executing Steam console commands through CEF for Deck/Machine
development. Desktop compatibility still needs the proposed real probe.
[Steamworks client-console documentation](https://partner.steamgames.com/doc/steamhardware/loadgames#client_console).
Valve also documents `find <string>` for command discovery.
[Steamworks debugging documentation](https://partner.steamgames.com/doc/sdk/api/debugging).

## Exact requested scope

Permit a temporary CEF debugging endpoint **inside the existing independent
task's preparation containers**, for this authorized acquisition/runtime work.
The prepared launch adds only `-cef-enable-debugging` to Steam's arguments.
Retain the tested image, private home, visible WSLg display, UID/GID 1000,
cap-drop ALL, no-new-privileges, container-local seccomp=unconfined, 3 GiB memory,
2 CPU, 512 PIDs and 1 GiB shared memory. No new device, mount, host package,
system setting, host networking or published Docker port is included.

The expected endpoint is container-local `127.0.0.1:8080`. Before any HTTP/API
access, inspect the actual IPv4 and IPv6 listeners inside that owned container.
If the endpoint listens outside loopback, stop the container without connecting.
The listener does not exist until Steam starts, so this is an early runtime
guard, not proof before execution that a transient bind cannot occur. No port
is mapped to Windows/WSL or a public interface.

This endpoint can control the signed-in client; it is more powerful than a
status check. Controls must remain source-reviewed and provider-owned. Do not
capture the sign-in screen, read password/token/account files, enable global
network/authentication logging, change Cloud/licenses/settings, or execute
arbitrary operator-supplied JavaScript/console commands. If the cached login
is no longer usable, stop for operator action; do not launch another QR/password
flow. Each preparation client is bounded to at most 30 minutes with owned
shutdown and foreground WSL supervision.

## Prepared code and staged verification

1. `providers/steam/probes/interactive_client_v1/console_probe_v7.py` and
   `console-launch-v7.sh` are prepared, **unexecuted**. They require a new approval
   receipt, verify that all five older clients are stopped, verify sampled client
   bytes and require the existing state marker without treating it as login proof.
   An exclusive attempt directory and launch marker preserve earlier evidence.
2. The initial probe is read-only: actual listener validation and bounded
   `/json/list` metadata classification. It exports counts/booleans only, not
   raw titles, URLs, target IDs, page content or credentials. This does not yet
   validate authentication or execute a depot command. A detected login target,
   failure or timeout is incomplete and triggers owned cleanup.
3. Only after the endpoint is demonstrated, implement the narrow console bridge
   and an actual authentication check using the installed API's observed
   callback contract. Discover the depot command's syntax with a read-only
   query. Emit a single fixed acquisition request and observe its completion;
   no ambiguous non-idempotent command is resent.
4. The requested source remains app **2379780**, depot **2379781**, manifest
   **3512319404653808464**, build **17459173**, with Balatro.exe SHA-256
   `0d75fe164accf3312734d4b37ac98788dd15f0b8e4f9bb8b7f90c4e59de93f47`.
   Successful acquisition requires manifest/file verification and that game
   hash. No latest-build substitution or manual game copy is allowed.
5. Proven behavior belongs in a distinct official-client session path within
   the Steam provider, preserving the helper path and generic core. Make
   `rhenium runtime prepare` acquire/validate the provider-owned source before
   building the game artifact. A bare console download is not managed-runtime
   completion. Only then execute real Balatro controls using the frozen tasks.

Prepared initial command, runnable **only after this approval**:

```sh
/home/psy/balatro-linux-v1/venv/bin/python \
  /mnt/c/Touchstone/Balatro-PoC/staging/swe-game-balatro-linux/providers/steam/probes/interactive_client_v1/console_probe_v7.py
```

Forty offline probe tests, targeted Ruff/Mypy (eight Python files) and syntax
checks for six shell scripts passed. Tests cover permission gating, actual
loopback listener enforcement, endpoint/metadata boundaries and rejection
before HTTP access. ShellCheck remains unavailable. No new Steam process,
CEF endpoint, game acquisition or real game test has run for this proposal.

Stop on an unusable interface, missing entitlement/manifest, unexpected source
bytes, protection drift or a need for further permissions. Two diagnostic rounds
without new evidence do not justify repeating the same path. Preserve failure
classification and evidence; do not weaken the managed-runtime rules.
