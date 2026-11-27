Validation policy: run every oracle and every single-defect ablation. An oracle must earn reward 1. An ablation must earn reward 0 without a Harbor exception, fail the case named in its manifest, and leave at least one unrelated case passing. Do not commit claimed results or logs until those executions have actually occurred.

## Hub validation record, 2026-11-12 (`blueprint-layout-reconciler`, catalog 1.2.0)

Catalog 1.2.0 adds `blueprint-layout-reconciler`. Runs used the Lab Linux x86_64 host from
this change in an isolated Hub state, not the operator Hub. `rhenium runtime prepare
mindustry/mindustry` built the base and all ten task images (artifact identity
`sha256:b92271763cedab187317c740c07a11fe2d6ca088f451cb64e2ee5349b9382f0f`).

| Task | Reference | Starter (empty scaffold) | Ablation `observe-origin-only` |
| --- | --- | --- | --- |
| `blueprint-layout-reconciler` | 100, complete, 9/9 cases (`run-b5a78722bb79481b`) | 0, incomplete at the shape gate by design (`run-5922eadff9ee4335`) | 10, complete, 1 of 9 cases failed (`run-959ee3fc6daa46c9`) |

The ablation was also run directly in a prepared image: it fails
`world observation of real buildings` and passes the other eight cases. Three more
single-defect variants are study target-negative controls; their runs are recorded in
`private/study-controls/blueprint-layout-reconciler/NOTES.md`. No other task was run under
this runtime.

## Hub validation record, 2026-10-31 (official-download runtime)

The runtime moved from the `local-files` snapshot to the `official-download` provider. Runs used
the Lab Linux x86_64 host (Docker 29.8.1, containerd image store), from commit `ac5d446f` in an isolated Hub state, not the operator Hub.

`rhenium runtime prepare mindustry/mindustry` downloaded the v159.7 `server-release.jar` from
the GitHub release into this runtime's own cache. It followed the redirect to the declared
`release-assets.githubusercontent.com` and verified the jar (19,158,443 bytes, SHA-256
`e41289c3…2ab`). It then built the base and all ten task images. Artifact identity:
`sha256:e47cbe24637e0a64fa92ffa9ec94dccf79e2cdb3441c433713e389763bf09f59`.

| Task | Reference | Starter (empty scaffold) |
| --- | --- | --- |
| `build-quota-auditor` | 100, complete, 8/8 cases (`run-a6fb4b0593c14884`) | 0, incomplete at the shape gate by design (`run-ffbf4f3791434830`) |

No ablation and no other task was run under this runtime.

## Hub validation record, 2026-09-24

This pack was restored from `9b038435^` as `mindustry/construct`. Five
`environment/Dockerfile`s were changed from `FROM mindustry:latest` to
`FROM mindustry:159.7`, because preparation never builds `latest`. The as-restored
runtime failed at `item-reservation-ledger` with `mindustry:latest: failed to resolve`.

`rhenium runtime prepare mindustry/mindustry` then succeeded with 10 task images
(artifact identity
`sha256:5c7f29646dd076f994851b2e7c4a769f847c715fbcb81fdf392cd31942671bec`).

All runs used `rhenium run mindustry/construct/<task>` on a Linux x86_64 Docker host.
The submissions were built as follows:

- **Reference**: the materialized scaffold with `solution/solve.sh` applied.
- **Starter**: the unchanged empty scaffold, which the shape gate rejects as incomplete
  by design.
- **Ablation**: the reference with the manifest patch applied.

| Task | Reference | Starter | Ablation |
| --- | --- | --- | --- |
| `transactional-core-router` | 100, complete, 13/13 cases (`run-56eae951f2154172`) | 0, incomplete (`run-22755d3fde1c4d53`) | 10, complete, 2 of 13 cases failed (`run-aece75e30f974118`) |
| `build-quota-auditor` | 100, complete, 8/8 cases (`run-7c51395da5ca4252`) | 0, incomplete (`run-4efaefd7e5d6459e`) | 10, complete, 1 of 8 cases failed (`run-40c111933e3d4324`) |
| `unit-lease-scheduler` | 100, complete, 7/7 cases (`run-c823d2f0499b41ae`) | 0, incomplete (`run-1bc2637f822b4bd9`) | 10, complete, 1 of 7 cases failed (`run-2d9a3a980c4f44f4`) |
| `power-grid-controller` | 100, complete, 8/8 cases (`run-5c8f2be076ba4aa6`) | 0, incomplete (`run-c0d52c6b37614707`) | 10, complete, 1 of 8 cases failed (`run-85f3f682a0634990`) |
| `wave-threat-arbiter` | 100, complete, 7/7 cases (`run-10fc450025024836`) | 0, incomplete (`run-bc5455c37fd640e3`) | 10, complete, 1 of 7 cases failed (`run-3688f26563c84d1d`) |
| `item-reservation-ledger` | 100, complete, 4/4 cases (`run-0e17042328c442e3`) | 0, incomplete (`run-261e8aab05c54bf0`) | 10, complete, 1 of 4 cases failed (`run-312a9065e62d4f20`) |
| `wave-budget-planner` | 100, complete, 4/4 cases (`run-f4485ad5add84563`) | 0, incomplete (`run-1ab67d8d3343448c`) | 10, complete, 1 of 4 cases failed (`run-0117c5e6fe9a448e`) |
| `command-rate-limiter` | 100, complete, 4/4 cases (`run-21ecdcb5cfa74ba7`) | 0, incomplete (`run-f0d3f3d65c3e4f15`) | 10, complete, 1 of 4 cases failed (`run-e6ee5eadef834c0a`) |
| `logic-link-registry` | 100, complete, 4/4 cases (`run-a86986893e9d465e`) | 0, incomplete (`run-a3e0f6e25dcc48c0`) | not run: `expiry-boundary.patch` does not apply |
| `core-failover-coordinator` | 100, complete, 4/4 cases (`run-2a511bc80e81462e`) | 0, incomplete (`run-b22125c17b5f4c9a`) | not run: `capacity-order.patch` does not apply |

The eight ablations were also rerun directly in the prepared images. Each failed the
case named in its manifest and left the other cases passing, except
`transactional-core-router`, which also failed
`compensation failure remains recoverable`.

Two ablation patches do not apply to the oracle (`patch`: 1 out of 1 hunk FAILED), so
those tasks have no complete failing control:

- `logic-link-registry/validation/ablations/expiry-boundary.patch`
- `core-failover-coordinator/validation/ablations/capacity-order.patch`

No Harbor run was made.
