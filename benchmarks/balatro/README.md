# Balatro-10 v0.2 candidate materials

Status: **candidate assets and historical PoC evidence only**. This directory is
not a registered Rhenium benchmark pack. It intentionally has no `benchmark.json`
and no corresponding plugin distribution in this change. `rhenium run-attempt`
cannot score these materials through this branch.

The ten tasks have authored 3 Easy / 4 Medium / 3 Hard labels, all uncalibrated.
Their original controlled Windows PoC completed gold/base and declared-control
validation. The [sanitized record](validation/poc-v02-controls.md) separates that
historical evidence from this asset-import check and from future integration.

## Contents

- `public/v02/`: exact participant files from the validated v0.2 release;
  `INDEX.json` lists ten packages. Each package includes its original contract,
  starter, manifest and any required public API documents.
- `candidate-release.json`: an explicit byte/size allowlist for these snapshots.
- `validation/`: aggregate historical controls, provenance, task differences
  and the limits of what this branch proves. This is maintainer context, not
  material to give to a model under test.

No gold solutions, private tests, observers, fixtures, raw logs, submissions,
saves, game/dependency content, credentials or local runtime are included.
The public snapshots are intentional authored benchmark source assets, not a
location for generated attempts. Keep every run and editable copy outside this
directory. Byte-preserving Git attributes prevent newline conversion from
invalidating the frozen manifests.

## Handoff to another agent

For an independent implementation, give the agent **only one selected package**
from `public/v02/`, copy its `starter/` outside the repository, and follow the
contract and `editable_files`/`immutable_files` declarations. Do not provide
the maintainer validation material or access to the original PoC's private data.
This change does not start an agent attempt or measure a model pass rate.

For a maintenance review, an agent may inspect these materials and the
integration discussion. Actual engine scoring currently requires an operator
with the separately preserved PoC tools, private assets, fixed dependencies and
licensed installation. The commands in each frozen package README refer to
that external PoC environment; the `poc` Python module is not installed by this
repository. Code must be reviewed before the operator seals its hash and runs
one visible serial evaluation. An arbitrary submitted Lua program is not safe
merely because its package hash is valid.

See [Balatro integration status](../../docs/games/balatro.md) for the next-stage
requirements and the comparison with Palworld. No formal integration or
untrusted-host support is claimed here.
