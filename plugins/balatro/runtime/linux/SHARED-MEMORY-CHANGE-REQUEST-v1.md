# One shared-memory comparison — separate approval required

The namespace experiment was authorized for **one attempt**, now completed.
It did not establish a stable login UI. No additional start is covered by that
approval. This proposal is prepared but unexecuted.

## Evidence and proposed delta

The login window repeatedly appeared and closed. In eight of twelve bounded
samples the container's 64 MiB `/dev/shm` had only 88 KiB free. There was no
recorded OOM kill or PID-limit hit. The repository's existing official-client
bootstrap explicitly allocates 1 GiB shared memory. These facts justify a
single-variable experiment; they do not establish the failure's root cause.

Permit **one new task-owned container, for at most 900 seconds**, with
`--shm-size 1g`. Reuse the reviewed image and the same independent client home;
do not reinstall or discard updates. Retain UID/GID 1000, cap-drop ALL,
no-new-privileges, container-local seccomp=unconfined, memory=3g, cpus=2,
pids-limit=512 and the original private-home/read-only X11/script mounts.

This enlarges only the container's shared-memory tmpfs ceiling; it does not
reserve 1 GiB immediately or raise the 3 GiB aggregate memory cap. No host
settings, packages, capabilities, devices, additional mounts or graphics flags
change. Do not increase other resources during this attempt.

The operator alone may sign in through a stable official client using password
and phone confirmation. No QR capture, credential collection, account-file
read, game acquisition, restart or automatic retry is included. Startup failure
or expiry leads to bounded owned cleanup. A usable login and a normal shutdown
must be reported separately; an account marker alone is insufficient.

## Prepared implementation and verification

`providers/steam/probes/interactive_client_v1/shm_probe_v5.py` reuses the existing
controller and namespace launch argument construction, adding only the shared
memory option. The new `shm-launch-v5.sh` has its own exclusive marker. Existing
markers and old evidence are preserved. An explicit new approval receipt is
required, all four previous containers must be stopped, and sampled client
bytes must still match the completed experiment's metadata before launch.

The offline tests compare the complete old/new launch argument lists, reject
reuse of the old approval and reject expanded attempt/time/capacity allowances.
No proposal test starts a real client. Actual new-client behavior is untested.

After approval, the sole prepared entry is:

```sh
/home/psy/balatro-linux-v1/venv/bin/python \
  /mnt/c/Touchstone/Balatro-PoC/staging/swe-game-balatro-linux/providers/steam/probes/interactive_client_v1/shm_probe_v5.py
```

Record actual resource limits, bounded shared-memory observations, UI outcome
from the operator, post-run client hashes, cleanup status and elapsed time.
An official self-update during the run is a potential confounder, not silently
treated as the same environment. If this yields no new evidence, stop this
path; do not repeatedly adjust limits or bypass the managed-acquisition rules.
