# Maintainer notes

## Current review correction: 0.2.1 / v14

The v14 verifier gives every Hypno creation phase the same documented allowance
from the actual post-spawn forward, including respawn and pre-unload setup.
It retains the 57-case contract and all ownership/cleanup assertions. A focused
seven-case control accepts a 0.5-second deferred creation and rejects a two-second
creation. These focused controls are not full-task passes. Full gold/NOP controls
and independent review are recorded in `validation/revision-controls.json` and
[`../../../review-revisions.md`](../../../review-revisions.md).

All older v13 control evidence below remains historical and does not certify
the v14 verifier.

This task freezes the GPL-3.0-or-later Mutant Tanks v9.3 source at upstream
commit `c7ef30eea49abce235ef9ff50587aed7cd3c4d5a`. The submitted artifact is
source-only: 90 files, including 65 `.sp` files and two `.inc` files, with no
Valve game data, compiled plugins, archives, credentials, or Git metadata.

## Regression scope

The nine operator reports cover independent observable behavior:

1. nested configuration callbacks lose `special` and `specsection` context;
2. plugin-level Special Infected health fallback loses precedence;
3. Warp relocates survivors already pinned by four supported attacker classes;
4. the terminal four-stage Boss timer reads beyond its arrays;
5. two differently configured Tank rewards stack incorrectly for Damage Boost
   and Ammo Regen, including survivor replacement and timed expiry;
6. Hypno shield creation, ownership, replacement, and cleanup diverge from the
   visual lifecycle;
7. `Panic Type = 0` fails to select its documented uncommon fallback;
8. a live Rainbow reward loses its SDK hook across both replacement directions;
9. Acid and Ammo omit their configured melee/claw cooldown eligibility guard.

Seven regressions are deliberately seeded into the frozen snapshot. Boss and
Reward preserve upstream regressions. The historical behavior is anchored by
the revisions listed in `task.toml`; Reward is specifically anchored by
`5cc02e8f0ef489c94f1d69ef10f20ecc7d55621a`. Meteor remains ordinary upstream
code and is not a task report, predicate, or solution change.

## Real-server contract

The private verifier runs 57 managed cases in ten fresh L4D2 dedicated-server
boots. `reward_stacking` is one external behavior group expanded into two
isolated order scenarios (`reward_ab` and `reward_ba`); the other eight groups
use one boot each. Tests compile submitted SourcePawn and observe public
forwards, real entities, engine properties, real weapon ammunition, and real
SDKHooks damage. They do not compare candidate source to the reference repair
or inspect candidate-private variables.

Reward uses valid documented positive configuration values. Type A supplies
Damage Boost 1.5 and Ammo Regen 10; Type B supplies 2.0 and 20. Two real Tank
deaths credit one survivor through the public reward forward. The A-to-B order
must expose 15 damage from a real baseline-ten bullet hit and a first SMG
regeneration increment of 10. The B-to-A order must expose 35 damage and 30
ammo. Both orders then verify ownership migration through `bot_player_replace`,
absence of stale effects on the old owner, one public `apply=false` expiry over
a complete observation window, restored ten damage, and stopped regeneration.

Every boot must emit its exact case set and exactly one nonce-bound FINAL.
Fatal signatures are scanned through FINAL inclusive. Duplicate cases,
duplicate or missing FINAL, load failures, unbound natives, crash signatures,
unknown cases, and unexecuted cases fail closed. The verifier timeout is 2100
seconds because ten boots run serially inside one evaluation.

## Package and public checks

`python3 tools/smoke.py` is the public source-only check. It compiles the core
and both production aggregates with SourceMod 1.12.0.7246. The private gate
repeats package validation, compiles the same production entry points, compiles
all ten frozen private fixtures, and separately compiles a public API consumer
against the submitted include.

Only regular UTF-8 source/data text from a strict suffix allowlist is accepted.
The scanner rejects symlinks, Git metadata, binary/archive magic, NUL bytes,
compiled assets, additional Python helpers, credential-like material,
executable network-client code, inconsistent SourcePawn line endings, missing
GPL attribution, and altered frozen provenance. Pure LF and pure CRLF are both
valid. Fifty package-probe rows cover 25 public/private pairs. All 50 outcomes
match their expected gate in `validation/package-probes.tsv`.

## Frozen local and Harbor evidence

The current contract was validated locally and offline. Harbor 0.20.0 then ran
current nop and oracle controls before these evidence rows were written. Both
used task checksum
`307b3e695ee3838a379a80d1b1a57ceec32da6a21eb1cd97848823cb40add4ea`:
the nop trial scored 32/57 with reward zero, and the oracle scored 57/57 with
reward one. Their downloaded 90-file artifact trees exactly match the frozen
base and oracle tree digests. Trial IDs and stdout/verifier hashes are recorded
in `validation/control-runs.tsv`. Raw server logs remain outside the task under
`work/v13-validation-matrix` and `work/harbor-jobs` and are intentionally not
shipped.

The 16-run full matrix contains broken base, byte-identical no-op, three oracle
controls, nine target-only predicates, and two non-oracle full alternatives:

| candidate | result |
|---|---:|
| broken base / no-op | 32/57 each |
| oracle runs 1-3 | 57/57 each |
| Config / Health | 33/57 each |
| Warp | 36/57 |
| Boss | 34/57 |
| Reward | 36/57 |
| Hypno | 37/57 |
| Panic / Rainbow | 34/57 each |
| Cooldown | 36/57 |
| alternatives A and B | 57/57 each |

Each run contains exactly 57 unique expected cases, ten unique nonces, ten
FINAL markers, zero duplicate cases, and zero unexecuted cases. Unrepaired Boss
runs contain seven expected pre-FINAL out-of-bounds lines and fail that group
closed; the Boss predicate, three oracle runs, and both alternatives have zero
pre-FINAL fatal lines. Each predicate gains only its target cases and regresses
no passing guard. Detailed hashes are in `validation/predicate-matrix.tsv`,
`validation/differential-matrix.tsv`, and `validation/control-runs.tsv`.

A synthetic parser regression independently confirms that valid output and
post-FINAL shutdown noise are accepted, while duplicate, missing, extra, or
post-FINAL CASE records, duplicate or missing FINAL records, wrong counts, and
pre-FINAL fatal signatures fail the complete selected group closed.

Alternative A uses field-local Reward accumulation, event-branch state
transfer, and separate cooldown early returns. Alternative B uses narrow
positive Reward merge helpers, event reconciliation, and module-local cooldown
eligibility helpers. Neither copies the Reward oracle structure, and neither
modifies passive WeaponHandling behavior.

`validation/candidates/rebuild.py` applies each frozen patch with
`git -c core.autocrlf=false apply`, then checks the exact manifest tree digest.
Fresh reconstruction, patch SHA-256, changed-file headers, public compilation,
and private compile-only preflight passed for all eleven candidates.

The frozen aggregate contract is
`f2b6eddbd8cbc80ea8bae50ad091c2c5eae5cdfc7d4e79b5354f57f7d7103b0d`.
The final verifier image is
`sha256:09ec196a7d38023922df2f55c5f5266d0fe668f26a94d5cbaaeda966e4f65fad`,
and the final agent image is
`sha256:7e96dcd438e14f3a7e91eaa55f24a20184fa0a0ab32b628b9e72a8256df4c902`.
No solved tree, raw verifier log, SourceMod cache, or compiled output is stored
inside the benchmark task.
