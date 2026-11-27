# Portable verifier controls

This historical table covers the original five tasks. The five catalog 1.1.0
additions, their portable/mutation controls, and separate real Windows server
results are recorded in [advanced controls](../../../validation/advanced-controls.md).

These rows come from direct local invocations of the checked-in Lua 5.4
verifier and simulated UE4SS contract. They are not Docker/Harbor job results or
Windows Palworld dedicated-server runs.

Measured on 2026-09-08 with Python 3.13, Lupa 2.8's explicitly selected
`lua54` backend, and the checked-in verifier:

| Task | Portable reference fixture | Empty/nop | Reward pair |
| --- | --- | --- | --- |
| `guild-storage-ledger` | 19 pass / 0 fail | 0 pass / 16 fail | 1 / 0 |
| `palbox-transfer-transaction` | 20 pass / 0 fail | 0 pass / 17 fail | 1 / 0 |
| `raid-dispatch-queue` | 20 pass / 0 fail | 0 pass / 17 fail | 1 / 0 |
| `server-rule-ballot` | 20 pass / 0 fail | 0 pass / 17 fail | 1 / 0 |
| `damage-attribution-arbiter` | 20 pass / 0 fail | 0 pass / 17 fail | 1 / 0 |

The repository test `test_palworld_harbor_tasks.py` reruns both directions for
all five tasks. The fixtures and tests are open benchmark assets in this public
repository; a real Harbor run keeps them out of the agent container and runs
the tests later in a separate verifier. A fixture pass requires every static,
behavior, and simulated integration case to pass. The empty starter must
receive reward 0 because it is missing the required mod files and behaviors.

These reference fixtures establish only a known passing input for the portable
verifier. They are not real-engine or full Palworld Mod oracle evidence.

Docker/Harbor execution and a real Palworld server rerun were unavailable while
this export was authored. Container-image buildability is therefore checked only
statically here; do not promote these rows to container or engine evidence until
the corresponding controls have actually run.
