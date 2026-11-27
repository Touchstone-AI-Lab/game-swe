# Validation

Real-game two-way controls of every construct task, measured on 2026-09-26 (UTC) on
Ubuntu 24.04 x86_64 Azure D4s_v5 hosts with Docker whose runtime state was prepared
by the managed `rhenium runtime prepare` flow (the base `afterbirth-plus-1.06.t1`
client state and profile, cloned by disk snapshot to run tasks in parallel). Each
row is one networkless verifier container started with the evaluator's flags
(`--network none`, 4 CPUs, 8 GiB, AppArmor `gcb-isaac-steam`, seccomp unconfined),
running the task's `tests/test.sh` against the reference (`solution/reference.lua`
in the starter's `mod/`) and against the untouched empty starter. `process` is the
single game process; `summaries` counts `[GCB_SUMMARY]` lines.

| task | tree | pass / fail | reward | summaries | fatals | process |
| --- | --- | --- | --- | --- | --- | --- |
| `construct-room-rng` | reference | 35 / 0 | 1 | 1 | 0 | 1/1 |
| `construct-room-rng` | empty starter | 0 / 35 | 0 | 1 | 0 | 1/1 |
| `construct-config-persistence` | reference | 35 / 0 | 1 | 1 | 0 | 1/1 |
| `construct-config-persistence` | empty starter | 0 / 35 | 0 | 1 | 0 | 1/1 |
| `construct-callback-transaction` | reference | 35 / 0 | 1 | 1 | 0 | 1/1 |
| `construct-callback-transaction` | empty starter | 0 / 35 | 0 | 1 | 0 | 1/1 |
| `construct-option-rendering` | reference | 35 / 0 | 1 | 1 | 0 | 1/1 |
| `construct-option-rendering` | empty starter | 0 / 35 | 0 | 1 | 0 | 1/1 |
| `construct-legacy-hud-lifecycle` | reference | 35 / 0 | 1 | 1 | 0 | 1/1 |
| `construct-legacy-hud-lifecycle` | empty starter | 0 / 35 | 0 | 1 | 0 | 1/1 |
| `construct-hud-compositor` | reference | 35 / 0 | 1 | 1 | 0 | 1/1 |
| `construct-hud-compositor` | empty starter | 0 / 35 | 0 | 1 | 0 | 1/1 |
| `construct-config-navigation` | reference | 35 / 0 | 1 | 1 | 0 | 1/1 |
| `construct-config-navigation` | empty starter | 0 / 35 | 0 | 1 | 0 | 1/1 |
| `construct-entity-cleanup` | reference | 35 / 0 | 1 | 1 | 0 | 1/1 |
| `construct-entity-cleanup` | empty starter | 0 / 35 | 0 | 1 | 0 | 1/1 |

A reference row is the pass control (35 / 0, reward 1); an empty-starter row is the
fail control (0 / 35, reward 0). Both must be complete (exit 0, one summary, no
`[GCB_FATAL]`) for the task to be admitted.

Hub-level records (`rhenium run isaac-rebirth/synth/<task> <tree> --profile full`, an
isolated operator Hub on the same host whose runtime was prepared with
`rhenium runtime prepare isaac-rebirth/afterbirth-plus-1.06.t1-synth`):

| task | tree | score | complete | passed | run | verifier image |
| --- | --- | --- | --- | --- | --- | --- |
| `construct-room-rng` | empty starter | 10.0 | True | False | `run-7e50b863c4fe40aa` | `sha256:8165b6ebbbc1…` |
| `construct-room-rng` | reference | 100.0 | True | True | `run-703db83fb9c34c5e` | `sha256:8165b6ebbbc1…` |

`controls.tsv` holds the same rows. The `hard` labels are estimates.

## Second host: Lab, 2026-10-30/31 (CST)

Hub-level controls of all eight tasks through `rhenium run isaac-rebirth/synth/<task> <tree>
--profile full` on the operator Hub of the licensed NixOS x86_64 Docker host. The runtime was
prepared on that host with `rhenium runtime prepare isaac-rebirth/afterbirth-plus-1.06.t1-synth`
after the construct preparation drops the client update the online profile run stages (see
`docs/games/isaac-rebirth.md`); before that fix no control on this host launched the game. The
unrelated-change tree replaces the starter's `main.lua` with a mod that only counts game starts.
Every run completed on its first try; `hub-controls-lab.tsv` holds the same rows.

| task | tree | score | complete | passed / total | run |
| --- | --- | --- | --- | --- | --- |
| `construct-room-rng` | empty starter | 10 | True | 0 / 35 | `run-26efee268b5a491a` |
| `construct-room-rng` | reference | 100 | True | 35 / 35 | `run-bd7d1cc6d19542e0` |
| `construct-room-rng` | unrelated change | 10 | True | 0 / 35 | `run-c8f54f0a55934133` |
| `construct-config-persistence` | empty starter | 10 | True | 0 / 35 | `run-962e4d582a1e4077` |
| `construct-config-persistence` | reference | 100 | True | 35 / 35 | `run-bc46d096cbf1495a` |
| `construct-config-persistence` | unrelated change | 10 | True | 0 / 35 | `run-a1162211e47d42be` |
| `construct-callback-transaction` | empty starter | 10 | True | 0 / 35 | `run-43907f97ce46463c` |
| `construct-callback-transaction` | reference | 100 | True | 35 / 35 | `run-744dfe62bb73410a` |
| `construct-callback-transaction` | unrelated change | 10 | True | 0 / 35 | `run-c98baa79e38c4c35` |
| `construct-option-rendering` | empty starter | 10 | True | 0 / 35 | `run-c3027bf244254803` |
| `construct-option-rendering` | reference | 100 | True | 35 / 35 | `run-05b6476f4086467e` |
| `construct-option-rendering` | unrelated change | 10 | True | 0 / 35 | `run-28200f855b1b4b63` |
| `construct-legacy-hud-lifecycle` | empty starter | 10 | True | 0 / 35 | `run-b15570648f254066` |
| `construct-legacy-hud-lifecycle` | reference | 100 | True | 35 / 35 | `run-edab8956a78b4d40` |
| `construct-legacy-hud-lifecycle` | unrelated change | 10 | True | 0 / 35 | `run-25517639aab04687` |
| `construct-hud-compositor` | empty starter | 10 | True | 0 / 35 | `run-f0283cbfc5e24398` |
| `construct-hud-compositor` | reference | 100 | True | 35 / 35 | `run-a344c036e4fe4c9e` |
| `construct-hud-compositor` | unrelated change | 10 | True | 0 / 35 | `run-4d31af1a98064fd1` |
| `construct-config-navigation` | empty starter | 10 | True | 0 / 35 | `run-ac729e512246424f` |
| `construct-config-navigation` | reference | 100 | True | 35 / 35 | `run-ea5d46ff768d49c2` |
| `construct-config-navigation` | unrelated change | 10 | True | 0 / 35 | `run-499c9f46f8ba4bdf` |
| `construct-entity-cleanup` | empty starter | 10 | True | 0 / 35 | `run-262c9850928a4cc1` |
| `construct-entity-cleanup` | reference | 100 | True | 35 / 35 | `run-73ac21320f854869` |
| `construct-entity-cleanup` | unrelated change | 10 | True | 0 / 35 | `run-d9a552888d274e01` |

Each task has a measured empty-starter failure, a 100/complete reference and a failed
unrelated-change control on the licensed Afterbirth+ build.

## Catalog 0.1.1, Lab, 2026-11-02 (CST)

Catalog 0.1.1 changes only each starter's `metadata.xml` `<id>`, which named the task; it is now
the mod's `<directory>` value. On the same host and runtime, an anonymous attempt of every task
was prepared without the Hub's internal-identifier refusal. The starter and reference ran again
as the E0 baseline (`rhenium-study e0 baseline`, real game), and the unrelated-change control
through the Hub's `full` profile. Every run was complete; `hub-controls-lab-0.1.1.tsv` holds the
rows.

| task | empty starter | reference | unrelated change |
| --- | --- | --- | --- |
| `construct-room-rng` | 0 / 35 `run-fdd0f6816dbd4f1a` | 35 / 35 `run-6722a5382e474c2c` | 0 / 35 `run-8a0c92cf0e6c4dbc` |
| `construct-config-navigation` | 0 / 35 `run-edb4262d59c748df` | 35 / 35 `run-63619fde61884c63` | 0 / 35 `run-3e34757194084a7a` |
| `construct-config-persistence` | 0 / 35 `run-636987c1cb0e492e` | 35 / 35 `run-cc7b689b35794779` | 0 / 35 `run-695d82fd385b42c9` |
| `construct-hud-compositor` | 0 / 35 `run-a7be70f19f8543ae` | 35 / 35 `run-b76002396ead4558` | 0 / 35 `run-afa80349197648c7` |
| `construct-legacy-hud-lifecycle` | 0 / 35 `run-2199fd812d3a4bd4` | 35 / 35 `run-a5ae2e79d7764751` | 0 / 35 `run-b3666553074a4a8e` |
| `construct-option-rendering` | 0 / 35 `run-2405000dea744289` | 35 / 35 `run-a2e79ac2d93a484f` | 0 / 35 `run-318aca81cbf94281` |
| `construct-entity-cleanup` | 0 / 35 `run-6c4396a5673c4ea8` | 35 / 35 `run-64b10a316f2b42b3` | 0 / 35 `run-b0e2936c42a94c53` |
| `construct-callback-transaction` | 0 / 35 `run-63d22275a6fb4e47` | 35 / 35 `run-1d88e28a95a647b5` | 0 / 35 `run-f38ffc3e6c664215` |
