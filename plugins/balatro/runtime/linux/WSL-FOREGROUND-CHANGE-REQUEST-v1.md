# One additional foreground-supervised client run — approval required

The approved [earlier proposal](AUTHENTICATION-CHANGE-REQUEST-v1.md) says:

> Run at most two bounded acquisition/diagnostic attempts

Those two client attempts are exhausted. The subsequent read-only host
observation identified a controller lifetime defect; no third client was started.
The result and limits are recorded in
[AUTHENTICATION-PROBE-RESULT-v3.md](AUTHENTICATION-PROBE-RESULT-v3.md).

## Concrete prepared change

`providers/steam/probes/interactive_client_v1/control.py` now keeps the original
foreground WSL command alive with `docker wait`, bounded to 900 seconds, then
performs owned-client cleanup if needed. It changes no WSL/system configuration.
Ten offline boundary tests include supervision and deadline behavior.

`resume_foreground_v3.py` and `resume-launch-v3.sh` are prepared review artifacts.
They refuse active previous clients, unexpected account state and repeated use
of their own attempt directory. They reuse the same image and isolated client
home without deleting either prior marker, re-unpacking the bootstrap, changing
pins, relaxing seccomp or adding capabilities. They create new receipts and keep
the foreground caller alive until exit or the deadline.

After approval, the exact Linux entry is:

```sh
/home/psy/balatro-linux-v1/venv/bin/python \
  /mnt/c/Touchstone/Balatro-PoC/staging/swe-game-balatro-linux/providers/steam/probes/interactive_client_v1/resume_foreground_v3.py
```

This command must remain attached to its initiating WSL process; do not launch
it through a detached shell or scheduler. It launches only the independent
official client, not a game or depot acquisition. The operator may enter their
credentials directly in Valve's visible UI only once that UI is available; no
agent input, screenshot or credential logging is enabled.

Approval requested: **one additional client startup/update and, if reachable,
the already intended operator login**, with the default container permissions.
Stop if it fails or needs extra permissions. This is not a request to install
host tools, modify WSL settings, disable sandboxing, extend acquisition attempts
without a verified mechanism, or claim a completed Linux runtime.
