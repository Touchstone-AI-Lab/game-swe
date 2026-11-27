# Decision requested: immutable Python snapshot check scope

Status: proposal only. Root lint/type-check configuration has not been changed.

The current full Ruff command reports 36 findings, all in six byte-frozen Python
copies: three original Session/RPC/check modules and three historical save-probe
modules. Their hashes are already bound by the existing native asset descriptor,
probe provenance and v2 execution capsule. Reformatting or annotating them would
break the requested unchanged-byte boundary. Mypy also discovers duplicate probe
module names and untyped/dynamically supplied original imports in these copies.

The repository rules require full applicable checks and prohibit weakening rules
or changing frozen assertions merely to make checks pass. Treating these copied
snapshots as a static-check exception changes the check boundary, so it requires
an explicit decision; it is not being silently counted as a full unchanged-scope
pass. No benchmark assertion, expected result or frozen byte would change.

## Proposed narrow scope

Ruff continues to inspect every maintained source and test. Only the already
present diagnostic codes below are exempted for these exact immutable paths:

| Path under `plugins/balatro/` | Existing Ruff codes |
| --- | --- |
| `runtime/linux/save_capability_v1/fixtures/tasks/durable_charge/load_diag_v1/probe.py` | F401, I001 |
| `runtime/linux/save_capability_v1/fixtures/tasks/durable_charge/probe.py` | E701, E702, I001 |
| `runtime/linux/save_capability_v1/fixtures/tasks/durable_charge/save_probe_v3/probe.py` | E701, E702, I001 |
| `src/rhenium_balatro/linux_assets/legacy/poc/checks.py` | E501, E701, E702, I001 |
| `src/rhenium_balatro/linux_assets/legacy/poc/evaluate.py` | B905, E501, E701, F401, I001, SIM102 |
| `src/rhenium_balatro/linux_assets/legacy/poc/rpc.py` | E501, E701, SIM102 |

Mypy would exclude discovery only under those two immutable copy roots and skip
following imports of `rhenium_balatro.linux_assets.legacy.poc.*`. Typed adapters,
transport/runtime implementation, maintenance drivers and all ordinary tests
remain checked. A new integrity test must enforce the exact six-file Python
closure, their existing provenance hashes and the exact exception scope. A new
file, changed byte, broadened rule or changed checksum must fail that gate.

The prepared literal configuration diff is retained in
`.test-state/repository-checks-v3/proposed-pyproject.patch`; the corresponding
baseline is `frozen-static-scope.json`. These are proposals, not modified pins.
Known ordinary typing defects are being fixed in their maintained code rather
than added to this exception list. Other collection/dependency failures must
still be resolved separately. No exception authorizes installing tools, changing
game/runtime components, skipping engine assertions, or marking absent checks
as passed.

## Validation if approved

1. Apply the exact scope and add the provenance/closure guard using existing hashes.
2. Prove that byte drift, added snapshot modules and broader exception rules are
   rejected, using isolated test fixtures rather than changing real frozen files.
3. Run full Ruff, Mypy and pytest with the complete workspace inputs. Report the
   approved immutable-snapshot exception explicitly with their actual results.
4. Recheck fixed dependencies, original protection baselines and old evidence;
   retain old v2 reports and fingerprints unchanged. No commit/push/PR.
