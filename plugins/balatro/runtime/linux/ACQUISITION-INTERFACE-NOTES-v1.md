# Official-client acquisition interface research — unverified

This is a source-grounded investigation note, not implemented provider support.
No client console command, remote debugging endpoint or acquisition was executed
for this note. Authentication remains a separate prerequisite.

Valve documents the Steam client's `-console` option, the
`steam://open/console` route and a `find <string>` command for discovering console
commands. This supports the current launch option and a possible later,
read-only capability-discovery step. It does not by itself prove exact historical
manifest acquisition or reliable automation.
[Steamworks API debugging](https://partner.steamgames.com/doc/sdk/api/debugging).

Valve also documents CEF-console access and
`SteamClient.Console.ExecCommand()` for Steam Deck/Machine development. That
documentation is evidence for that development environment, not proof that the
same interface is available in this ordinary Linux desktop client/container.
No developer mode, debug port, device pairing or extra tool has been enabled.
[Steam client console on Deck/Machine](https://partner.steamgames.com/doc/steamhardware/loadgames#client_console).

Any future acquisition probe must first establish a usable authenticated client
and an actual command interface for this installed version. It must discover and
confirm the command's arguments before sending one acquisition request. A title,
account marker or console tab alone is not proof of authentication/acquisition.
An interface which requires credential extraction is unsuitable.

The required source remains app 2379780 / depot 2379781 /
manifest 3512319404653808464 / build 17459173, including the frozen Balatro.exe
SHA-256. Valve describes manifests as file inventories with size, SHA-1 and
flags, so a future successful probe also needs manifest/file verification and
the independent frozen SHA-256 check, not just a download-complete message.
[Steamworks builds and manifests](https://partner.steamgames.com/doc/store/application/builds?l=english).

Only demonstrated capabilities may be designed into an explicit Steam-provider
session backend and `rhenium runtime prepare` flow. The current helper's refresh
token must not be fabricated from ordinary client sign-in. The core and existing
QR backend remain unchanged; no managed-runtime or game validation is claimed.
