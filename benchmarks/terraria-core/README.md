# Terraria core benchmark pack

This pack is being authored one task at a time. Each task freezes a distinct,
license-compatible Terraria/tModLoader mod revision and evaluates repairs to its
real production source. Canonical task keys use `terraria/core/<task-id>`.

The current tasks exercise production files from Magic Storage, Fargo's
Mutant Mod, Terraria Overhaul, Quality of Terraria, Spirit Mod, ModLiquid
Library, Aequus, Starlight River, Fargo's Souls Mod, and Calamity Overhaul.
Evaluation is layered: exhaustive deterministic checks compile the submitted
production files in offline .NET 8 source projections, then three task-specific
integration sentinels compile the same submission into a real `.tmod` and load
it in tModLoader `2026.7.3.0` against Terraria `1.4.4.9` on a dedicated server.

| difficulty | task | defect groups | projection cases | projection starter / oracle | engine starter / oracle |
| --- | --- | ---: | ---: | --- | --- |
| hard | `terraria-magic-storage-compressed-io-regressions-hard` | 11 | 68 | 11/68; 68/68 | 0/3; 3/3 |
| hard | `terraria-fargos-enchanted-tree-transactions-hard` | 15 | 78 | 30/78; 78/78 | 0/3; 3/3 |
| hard | `terraria-overhaul-entity-chunk-lifetime-hard` | 16 | 78 | 25/78; 78/78 | 0/3; 3/3 |
| hard | `terraria-improvegame-space-wand-authority-hard` | 14 | 82 | 33/82; 82/82 | 0/3; 3/3 |
| hard | `terraria-spirit-branching-quest-replication-hard` | 16 | 97 | 16/97; 97/97 | 0/3; 3/3 |
| hard | `terraria-modliquid-map-persistence-hard` | 17 | 103 | 38/103; 103/103 | 0/3; 3/3 |
| hard | `terraria-aequus-carpentry-replication-hard` | 12 | 87 | 12/87; 87/87 | 0/3; 3/3 |
| hard | `terraria-starlight-ability-state-hard` | 11 | 84 | 14/84; 84/84 | 0/3; 3/3 |
| hard | `terraria-fargos-toggle-presets-hard` | 10 | 82 | 25/82; 82/82 | 0/3; 3/3 |
| hard | `terraria-calamity-overhaul-time-replication-hard` | 8 | 78 | 35/78; 78/78 | 0/3; 3/3 |

Prepare both pinned evaluator layers before a full run. The second command
requires `RHENIUM_TERRARIA_TML_DIR` to contain the reviewed official
`tModLoader.zip` and `krafs.publicizer.2.2.1.nupkg` inputs described in
`private/runtime/README.md`.

```sh
rhenium auth login container
rhenium runtime prepare terraria/dotnet-8.0.419-source-projection
rhenium runtime prepare terraria/tmodloader-2026.07.3.0-server
```

The public attempt receives the frozen mod source, the source-projection build,
and the authored symptom report. Private tests, reference repairs, predicate
controls, and validation receipts remain outside the attempt workspace. Full
verification runs with `--network=none`. A `full` result is incomplete and
cannot pass unless both layers finish and all three real-engine assertions are
reported. Client-only drawing, input, and IL paths that a dedicated server
cannot honestly execute remain in the source-projection layer and are disclosed
per task in `engine-rubric.json`.
