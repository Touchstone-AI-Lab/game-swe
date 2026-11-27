# Maintenance notes: data-patch-regressions

## Upstream

- Repository: https://github.com/Anuken/Mindustry (GPL-3.0, `LICENSE` kept).
- Base: release tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`.

| Report | Upstream fix | In v159.7? | Starter | Reference |
| --- | --- | --- | --- | --- |
| patches cannot use server-defined content | `e25b7280890aa50edcd0b53f7f4fea9ca4808fb0` (issue #12299), `DataPatcher` hunk only | yes | reverted | as released |
| patched build towers keep vanilla builder stats | `15c9ea4cc9e2964ac8e0cc6e3a1c8e6bc3b8aa17` | yes | reverted | as released |
| patches for another planet are still listed | `feab7aa908fa6135e32d8d31f0a74d42041f55e3` (PR #12389, first released in v160) | no | as released | fix applied |

`e25b72808` also fixed a directional-unloader sprite refresh and an Arc collection
issue; only its `DataPatcher.java` hunk (moving patch application after custom content)
is reverted. The reverted fixes first appeared in v159.1 (`e25b72808`) and v158
(`15c9ea4cc`), so both defects shipped in releases. No defect is injected. `solution/after` holds `DataPatcher.java` and
`BuildTurret.java`.

## Defects

- `DataPatcher.apply` assigns patch fields before it parses the content assets, so a
  patch naming a `dp-` item fails with `No item found with name`.
- `BuildTurret` copies `buildSpeed`, `range`, `rotateSpeed` and `buildBeamOffset` into its
  private builder `unitType` only in `init()`; patching the block does not reach the unit.
- `DataPatcher.apply` skips a patch whose `requiredPlanets` excludes the current planet
  but leaves it in the patch list that `DataManager` keeps, saves and sends to clients.

## Suite design

Seven cases: one sentinel, three targets, three preserved. They use the server's own
data-asset path: write JSON files into `config/assets/patches` and
`config/assets/content/items`, run `reloadassets`, `host Ancient_Caldera` and `stop`
through the console, and read block and unit-type fields, the `dp-rhenium-alloy` item
and `state.data.getPatches()`.
