# One container-local seccomp experiment — approval required

The approved authentication proposal explicitly excluded `seccomp=unconfined`
and required stopping for additional permissions. No such relaxation has run.

Evidence after the foreground lifetime fix and completed client update:

- WSL `unshare --user --map-root-user true`: exit 0.
- The same WSL test with `setpriv --no-new-privs`: exit 0.
- Inside the current uid-1000, cap-drop-ALL, no-new-privileges container: exit 1,
  `Operation not permitted`; seccomp mode 2 is active.
- Valve's installed `steam-runtime-check-requirements`: exit 71 and a bubblewrap
  namespace-permission diagnostic. The operator's error dialog matches it.
- The inspected `steam.sh` calls that checker and exits 71 after displaying the
  error. Closing the single owned error dialog produced exit 71 without forced
  container termination. No login, game acquisition or game execution occurred.

These observations identify the current container restriction; they do not
prove that removing seccomp will be sufficient for every subsequent component.
The host supports user namespaces, so no host sysctl/WSL setting change is proposed.

## Exact proposed delta

Permit **one 900-second attempt** adding `--security-opt seccomp=unconfined` to a
new task-owned container using the same verified image and isolated client home.
This removes Docker's syscall filtering for that container. Retain uid/gid 1000,
`--cap-drop ALL`, `--security-opt no-new-privileges`, current resource limits,
bridge networking and only the private home plus read-only X11/script mounts.
Do not use `--privileged`, add capabilities, mount devices or the Docker socket,
change host settings, access daily Steam state or enable input/screen capture.

The repository's existing `official_client.py` already uses this seccomp option
for its bootstrap, with a comment explaining bubblewrap's namespace needs. That
is compatibility context, not implicit permission for this experiment or a
claim of an untrusted-code sandbox.

Prepared, unexecuted entry:

```sh
/home/psy/balatro-linux-v1/venv/bin/python \
  /mnt/c/Touchstone/Balatro-PoC/staging/swe-game-balatro-linux/providers/steam/probes/interactive_client_v1/namespace_probe_v4.py
```

It requires an explicit approval receipt, verifies that all earlier clients have
exited, creates exclusive new attempt records and preserves every old marker.
Its shell first tests user-namespace creation, then starts the official client
with foreground supervision. The operator alone performs sign-in if reachable.
Stop on another unmet permission requirement; no automatic retry, host change,
game acquisition or sandbox-support claim is authorized by this request.
