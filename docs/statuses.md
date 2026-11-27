# Benchmark status

Every Supported Games entry uses one of these states.

| Status | Meaning | Promotion requirement |
| --- | --- | --- |
| `Planned` | Ownership and scope are recorded, but no usable implementation exists. | A plugin skeleton and implementation plan are accepted. |
| `In Development` | The adapter, catalog, or evaluator is being built and its contract may change freely. | At least one end-to-end task works in a supported environment. |
| `Experimental` | End-to-end runs work and are test-covered, but compatibility or scoring may still change. | Version policy, runtime matrix, evaluator contract, and CI are verified. |
| `Stable` | The documented contract is supported and changes follow compatibility policy. | Maintainers explicitly approve promotion after all release gates pass. |

Status describes the benchmark integration, not the quality or release status
of the underlying game.
