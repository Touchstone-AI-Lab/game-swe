# Controlled official-client preparation (experimental)

The opt-in `official-console-v1` backend reuses an independently prepared,
already signed-in official Steam client. It does not accept passwords, obtain
helper refresh tokens, copy account state into a runtime, or launch a new login
flow. The default helper/QR backend is unchanged. This is a controlled Linux
preparation path, not cross-host bootstrap or an untrusted-code boundary.

An operator-created mode-0600 profile under `RHENIUM_STATE_DIR` binds the existing
private client home, an immutable installed container image, reviewed client
code hashes, a specific source fingerprint, and explicit CEF-control approval.
`RHENIUM_STEAM_OFFICIAL_PROFILE` selects this profile only during explicit
`rhenium auth login steam`. The resulting opaque session contains a profile path
and hash; its principal names a client profile, not a Steam account ID. Steam's
own persistent authentication state remains sensitive in its independent home.

This version requires the reviewed Linux UID/GID 1000 setup. Its visible WSLg
preparation container retains 3 GiB memory, two CPUs, 512 PIDs, 1 GiB `/dev/shm`,
cap-drop ALL, no-new-privileges and the explicitly approved
`seccomp=unconfined`. The only mounts are that private home, the read-only X11
socket directory, and the reviewed read-only launcher. No port is published.
Actual CEF listeners must be loopback-only before HTTP/CDP access. A container
watchdog bounds execution to 1740 seconds plus 15 seconds for termination;
the controller also reserves time for normal shutdown within 30 minutes.

The backend supports one exact depot per source. Each expected file requires a
SHA-256. `rhenium runtime prepare` sends a single `download_depot` command via
the installed client's console API. It requires the command echo, exactly one
matching completion event, the exact manifest string, a depot path confined to
the private home, expected-file hashes, and normal official-client shutdown.
Only then is the provider cache marked complete. An unresolved request is never
resent automatically. A valid cache can be reverified without starting Steam.
The game builder must still independently verify its declared source policy.

`auth login` and `auth validate` explicitly start a bounded preparation client
to verify the existing sign-in. They stop with `RuntimeActionRequired` if it is
not usable; they do not request credentials. Evaluation, runtime doctor and
runtime verify never invoke this backend. Source files and private preparation
receipts remain local and non-redistributable.

The provider-owned probe and the managed entry are separate evidence stages.
The first real fixed-depot probe verified its requested manifest and game hash
after diagnosing an incorrect download-location assumption. The actual core CLI
subsequently completed managed authentication, acquisition and read-only runtime
verification. A further controlled-runtime preparation recorded one command echo,
one exact-manifest completion, zero failure events and normal client exit. Its
game hash matched the fixed builder policy. See the separate
[Linux runtime record](../../plugins/balatro/runtime/linux/LINUX-RUNTIME-REPORT-v2.md)
for real-engine coverage; provider success alone is not engine validation.

## Explicit reuse of a completed provider cache

`python -m rhenium_steam.official_cache` accepts an explicit private profile,
`--prior-cache` and `--destination`. Both caches must be direct fingerprint-named
children of the selected state's `cache/providers/steam`. It starts no client
and sends no command. The prior acquisition must retain its matching request,
single exact completion, successful original issue response, normal exit and
unchanged declared source bytes. Every subsequent use rechecks that proof.

If the destination has a failed request, it must have terminal client-exit
evidence. The request and shutdown record remain unchanged and are hash-bound in
a separate reuse receipt; the failed attempt is not a successful source. No
recovery receipt is created for an unresolved client. Existing source receipts,
changed files, linked paths and altered provenance are rejected. Without this
explicit operator action, the original incomplete-request rejection still applies.

This supports reuse of already licensed, provider-acquired source across runtime
versions. It is not operator-supplied game import, a new login route, or permission
to delete a failure and resend a non-idempotent command. Game bytes stay private.
