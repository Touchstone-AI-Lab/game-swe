# Linux acquisition blocker v2 — 2026-10-30

Status: **blocked before licensed source acquisition**. This supersedes the
request to locate an existing provider session; it does not overwrite earlier
receipts. The Linux runtime objective remains active but cannot pass an engine
gate yet.

The operator reports using a password followed by mobile confirmation and cannot
scan QR codes. Do not restart QR login, including a browser QR page. The operator
has not identified a previous successful Rhenium provider session. Read-only
inspection found zero Steam rows in the dedicated WSL state database and no
state database at the checked project defaults. This is not a claim to have
searched every personal directory.

## Confirmed implementation boundary

- `providers/steam/helper/RheniumProtocol.cs`, `Login`: fixes `UseQrCode = true`
  and calls `InitializeSteam3(null, null)`. Its JSONL commands are login,
  validate and acquire. No password/mobile-confirmation login command exists.
- `providers/steam/src/rhenium_steam/provider.py`, `login`: completes helper
  authentication before `_bootstrap_client`. `validate` and `_acquire` require
  the helper session secret. Merely starting or signing in to the official
  client does not replace that requirement.
- `official_client.py` and `assets/steam-client-session.sh`: the current
  bootstrap captures screenshots to extract QR challenges. It is unsuitable
  for a proposed password-entry flow without a separate, reviewed implementation
  that does not capture the authentication screen or user input.
- One prior QR attempt failed with `SteamHelperError`; only its exception type
  was retained. Do not retroactively label that attempt an expired code or an
  account/ownership failure. No successful provider session was saved.

## Rules and excluded shortcuts

[AGENTS.md](../../../../AGENTS.md) says: “Rhenium MUST NEVER request, accept,
log, or store a Steam password.” It also requires automatic game acquisition
through `rhenium runtime prepare` and a pinned Steam `steam-depots` source.

Consequently this work will not add a password field to Rhenium, pass passwords
through a helper or command line, extract credentials from daily Steam, fabricate
a provider session, or substitute local installed files for managed acquisition.
No project rule has been changed. The earlier QR authorization does not authorize
these shortcuts or an unreviewed provider rewrite.

Steam's official documentation confirms password plus phone confirmation is a
supported sign-in method for its client or website. The obstacle is the current
provider integration, not evidence of a problem with the operator's account.
Steam OpenID documents returning a SteamID for website authentication; it does
not document supplying the refresh-token session required by this helper. A
website login alone is therefore not a verified acquisition solution.

Sources:

- [Steam Guard Mobile Authenticator](https://help.steampowered.com/faqs/view/7EFD-3CAE-64D3-1C31)
- [Steamworks authentication and OpenID](https://partner.steamgames.com/doc/features/auth)
- Fixed repository implementation at main
  `e4f8326e388cae4fc4ee5066eff792a6ea7a3a72`, file locations above.

## Preserved results and unexecuted work

WSL2, its Docker daemon and the visible LÖVE 11.5 rendering probe passed. Original
protected directories, dependency pins, 16 controller files and 350 private
assets matched. The preparatory runtime builder and its targeted unit checks
exist; no task is bound to it. Those checks are not Balatro engine evidence.

Not executed: non-QR login, session import, licensed depot acquisition, managed
runtime prepare, Balatro Linux gameplay/save-load, gold/base controls, complete
Linux evaluator integration or final repository-wide validation. No new Steam
client or authentication service has been started during this assessment.

Classification: **provider capability / operator-authentication blocker**, not a
candidate behavior failure or a passing/incomplete engine run. The next decision
is the bounded provider capability proposal in
[AUTHENTICATION-CHANGE-REQUEST-v1.md](AUTHENTICATION-CHANGE-REQUEST-v1.md).
