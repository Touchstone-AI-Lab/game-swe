# Left 4 Dead 2 core benchmark pack

This pack contains ten source-only repository-debugging tasks over five
independently licensed Left 4 Dead 2 mod codebases. Canonical task keys use
`left-4-dead-2/core/<task-id>`.

The private evaluator compiles SourcePawn submissions or packages Squirrel
VScripts, then runs the frozen case set in a real headless Left 4 Dead 2
dedicated server. No Valve game files are committed. The managed runtime builds
anonymous SteamCMD app `222860`, rejects any build other than `23990100`, and
pins MetaMod `1.12.0-git1225` plus SourceMod `1.12.0-git7246` by archive hash.

| difficulty | task | defect groups | private cases |
| --- | --- | ---: | ---: |
| easy | `l4d2-competitive-release-regressions-easy` | 3 | 20 |
| medium | `l4d2-left4dhooks-api-regressions-medium` | 12 | 71 |
| medium | `l4d2-infected-bots-release-regressions-medium` | 4 | 18 |
| hard | `l4d2-linge-release-regressions-hard-v3` | 9 | 42 |
| hard | `l4d2-mutant-tanks-release-regressions-hard` | 9 | 57 |
| hard | `l4d2-linge-director-state-hard` | 9 | 41 |
| hard | `l4d2-competitive-score-lifecycle-hard` | 7 | 57 |
| hard | `l4d2-vslib-scheduler-persistence-hard` | 8 | 52 |
| hard | `l4d2-confogl-cvar-transactions-hard` | 7 | 42 |
| hard | `l4d2-library-map-tank-state-hard` | 8 | 44 |

Pack 1.2.0 contains 444 cases across 76 defect groups; the five additions
contribute 236 cases across 39 groups. See [review revisions](review-revisions.md)
for reference/base controls, equivalent solutions, and targeted negative
controls on the revised contracts. Historical matrices remain labelled as such.
The five hard additions were validated through the Hub full profile on 2026-09-24,
after four verifier-harness fixes; see the
[Hub validation record](validation/hub-full-profile-hard-tasks.md).

All ten tasks repair different existing production modules. They reuse five
upstream repositories, and later starters intentionally contain earlier repairs.
The [task-identity review](task-independence.md) documents actual compile/load
paths and the required grouping of answer-bearing baselines across dataset
splits. Exact clone checks supplement semantic independent review; hashes alone
do not establish independence or realistic difficulty.

The revised tasks have not been model-calibrated. Hard labels are author
assessments, not solve-rate guarantees.

The [original authoring validation record](authoring-validation.md) retains the
initial reviews and checks. A fail-closed 0/N control means the verifier rejects
an invalid run; it does not mean every raw engine assertion failed.

Prepare the verifier images before a full run:

```sh
rhenium auth login container
rhenium runtime prepare left-4-dead-2/l4d2-23990100-sourcemod-1.12.7246
```

The public attempt receives only the broken source tree and authored symptom
report. Private tests, reference repairs, validation tables, and the dedicated
server remain outside the attempt workspace; full verification runs with
`--network=none`.
