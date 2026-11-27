# Isaac Rebirth clean-room construct pack

`isaac-rebirth/synth` (pack id `synth`, catalog 0.1.1) is a registered construct pack
with eight tasks. Each one is written from an empty `mod/` starter (only `main.lua` and
`metadata.xml`) against the pinned Afterbirth+ build. It runs on its own runtime,
`isaac-rebirth/afterbirth-plus-1.06.t1-synth`, which pins the same Steam depots as the
Exodus runtime. Every task is `clean_room_synthetic: true`, so the plugin grades it
through its single verifier process with the construct branch (`fromScratch: true`,
`taskKind: "construct"`). The pack does not alter the frozen Exodus task or its checksum.

## Layout

```text
benchmarks/isaac-synth/
├── benchmark.json          # schema_version 2, pack_id "synth", catalog "catalog.json"
├── catalog.json            # 8 tasks, every one clean_room_synthetic: true
├── runtimes.json           # afterbirth-plus-1.06.t1-synth
├── exams/<task-id>.md      # public prompt
└── private/harbor/
    ├── <task-id>/
    │   ├── environment/mod/            # empty starter: main.lua + metadata.xml only
    │   ├── solution/reference.lua      # the reference main.lua
    │   ├── tests/                      # test.sh (expected=35), suite.lua, Dockerfile
    │   └── scripts/private-runtime.Dockerfile
    └── validation/                     # measured controls (README.md, *.tsv)
```

## Catalog 0.1.1

Catalog 0.1.0's starters set each mod's `metadata.xml` `<id>` to the task id, for example
`construct-room-rng`. The Hub refuses attempt material that names its task, so no anonymous
attempt of any construct task could be prepared. Catalog 0.1.1 sets `<id>` to the mod's own
`<directory>` value (`gcb_construct_room_rng`, ...). The game loads local mods by directory,
and no verifier reads the starter's `<id>`. No exam, case, reference, weight or pass rule
changed. The E0 baseline and the unrelated-change controls were run again on 0.1.1.

## Runtime

```sh
rhenium auth login steam
rhenium runtime prepare isaac-rebirth/afterbirth-plus-1.06.t1-synth
```

Preparation stages the acquired official client state and the pinned depots. It then
boots the game once, online, so the client caches the ownership ticket its offline
launches need. After that it builds one networkless verifier image per task. Without a
signed-in client it returns `RuntimeActionRequired`, as the Exodus runtime does.
`docs/games/isaac-rebirth.md` describes the preparation steps that keep a congested
host from failing it. A construct runtime prepared before those fixes must be pruned
(`rhenium runtime prune <key> --yes`) and prepared again: `prepare` returns a ready
artifact unchanged.

## Validation

`private/harbor/validation/README.md` holds the measured controls:

- **2026-09-26, Azure hosts.** Every reference passed 35/35, and every untouched empty
  starter failed 0/35, both complete.
- **2026-10-30/31, Lab host.** Hub-level controls of all eight tasks: empty starter 0/35,
  reference 35/35 and an unrelated-change mod 0/35, all complete on their first try.

So each task has a measured empty-starter failure, a 100/complete reference score and a
failed unrelated-change control on the licensed Afterbirth+ build.

The study inventory admits the eight tasks. Their clause maps and E0 notes are under
`private/study-controls/<task-id>/`. The `hard` labels are estimates.

## Provenance

The `rhenium-author` clean-room pipeline produced the candidates: behavior capsules, a
public-interface contract, a fixed implementation and an independently authored
verifier. `drafts/EXAM-DRAFTS.md` keeps the original public task contracts. The license
is in `LICENSE`.
