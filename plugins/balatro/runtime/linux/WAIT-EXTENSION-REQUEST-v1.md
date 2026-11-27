# Extend the same running update to 45 minutes total — approval required

The operator approved one foreground-supervised attempt capped at 15 minutes.
The new container has remained running beyond five minutes, with a visible
updater confirmed by the operator. At 2026-10-30 16:41:35 UTC the updater reported
93,726 / 487,789 KB, about 300 KB/s. At that rate it needs about 22 further minutes.
The prior WSL lifetime problem has not recurred during this foreground attempt.
Increasing the deadline is proposed only to allow this observed update transfer
to finish; it is not evidence that authentication or acquisition works.

Prepared action: `continue_foreground_v3.py` hands off supervision of the same
container to a new foreground WSL controller. It validates the exact owned
container, original supervisor and its `docker wait` child, then terminates only
that old observer. The client is neither signaled nor restarted. There is no gap
in the foreground WSL lifetime. The old controller's resulting error is recorded
as an intentional control handoff, not a client failure.

The replacement wait ends at **45 minutes from the original container start**,
not 45 additional minutes. It requires a new explicit approval receipt, refuses
an exited client, cannot restart a container, preserves all old evidence and
uses the existing bounded cleanup on expiry. Default waits remain 15 minutes.
No host setting, container permission, account action or acquisition scope changes.

This extra confirmation is needed because 15 minutes was the concrete limit we
proposed and the operator approved; it is not a general repository requirement.
If approval is not given, the original 15-minute supervisor remains authoritative.
