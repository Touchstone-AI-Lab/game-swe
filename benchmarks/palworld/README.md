# Palworld benchmark pack

This directory contains the Palworld catalog and evaluator-owned assets.

- `benchmark.json` selects the `palworld` plugin and catalog.
- `fixed-v1.json` is the machine-readable catalog (currently 2.0.0); its stable filename
  matches the pack layout used by the other Rhenium game packs.
- `exams/<task-id>.md` contains the public authored exam documents.
- `hidden/<task-id>.lua` contains sandboxed plain-Lua behavioral assertions.
- `server/<task-id>.lua` contains private headless dedicated-server assertions.
- `private/harbor/<task-id>/` contains the corresponding standalone Harbor 1.4
  package, including its agent environment, separate verifier, and portable
  reference fixture.
- `validation/` records the nop, reference and discriminating control runs
  measured on a real dedicated server.

Catalog 1.1.0 adds five advanced tasks without changing the original five task
entries or their authored assets. The new tasks cover a receipt-driven outbox,
exact workforce matching, revisioned event-time settlement, greatest consistent
checkpoints, and epoch/generation fencing. Their independent validation status
is recorded in [advanced controls](validation/advanced-controls.md); the original
real-server controls do not validate these additions.

Catalog 1.2.0 translates every public exam, and the Harbor instruction header,
from Chinese to English. Requirements, interfaces, error codes, hidden and server
assertions are unchanged; attempts recorded against 1.1.0 saw the Chinese exams.

The pack is read-only. Generated public manifests and starter workspaces live
under `.rhenium/hub/packs/palworld/core/`, outside this directory.

Rhenium attempts contain no solution implementation. This is a public benchmark
repository, so the Harbor `tests/` directories and `solution/reference/`
fixtures are open source assets rather than repository secrets. Harbor's runtime
boundary keeps both out of the agent container, then supplies the tests only to
the separate verifier phase. The `oracle` control copies the portable fixture
into `/app/mod`; an evaluated agent instead receives the empty
`environment/mod/` starter. Here, "hidden" and "private" describe the isolated
attempt boundary, not confidentiality from repository readers.

The Harbor export, regeneration workflow, portable validation boundary, and
version decision are documented in
[`private/harbor/README.md`](private/harbor/README.md).

Supported versions, platforms, languages, ownership, and runtime limitations
are documented in
[Palworld benchmark support](../../docs/games/palworld.md).

Catalog 2.0.0 replaces two construct tasks for native Linux evaluation:
`palbox-transfer-transaction` is retired in favor of `base-containment-mincut`,
and `damage-attribution-arbiter` is retired in favor of
`guild-draft-canonical-order`. Both replacements start from an empty workspace.
They require exact global optimization, stable history, deterministic ties,
atomic validation and certified recovery. The suggested 960 minutes per task
are author estimates; no model difficulty calibration is claimed.

The other eight catalog entries and their authored assets are unchanged.
Retired exams, assertions and reference fixtures remain as historical assets;
they are not registered or exported by the active catalog. New task identities
inherit no results from the retired tasks. The catalog change is intentionally
breaking for the two removed task identities. The stable pack ID and evaluator
weights do not change.

Native Linux runtime pins, positive and negative controls, and limitations are
recorded in [Linux controls](validation/linux-controls.md). Those historical
controls used manual preparation; evaluation does not download or build a server.

Plugin 0.7.0 registers a managed native Linux runtime for all ten tasks. The
existing Steam provider acquires the server from exact `steam-depots` manifests;
the game builder validates its required files and critical source hashes,
compiles native UE4SS and seals the local image. The
[Lab Steam-depot controls](validation/lab-steam-depot-controls.json) record
successful preparation/verification and all required control outcomes on the
final recipe. Two negative controls required one standard recheck each after
Docker timeouts; the original incomplete results are retained. The earlier
[managed-runtime controls](validation/managed-runtime-controls.md) describe the
historical SteamCMD prototype only.
The review fixes change no authored task, assertion, fixture or scoring weight.
The earlier manual controls remain a separate historical record.
