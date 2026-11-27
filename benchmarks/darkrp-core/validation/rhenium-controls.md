# Rhenium integration controls

These controls were run on 2026-09-01 on the Lab Linux x86_64 host with Docker
29.7.2. They exercise the Rhenium plugin path, not Harbor's standalone task runner.
The reviewed code is commit `38a5ac3` on top of PR #3 head `4b12283`.

The prepared runtime recorded this immutable artifact identity:

```text
runtime:  garrys-mod/gmod-gluatest-darkrp
artifact: sha256:8de461b019b229e998860dd2115364bb2c087e028671e63809a19f5001b949fd
release:  sha256:fb3f49a4234e242d7d196a101b3cb456222c3e633ae6d7fbe627246ad7d2e9b8
live:     sha256:27c0e922ac5c94c02f4e5d1de28a340995b32ac4d0964a7834234233f4757494
door:     sha256:69de760523d3d5d81b0a7afb47bf70057fcc9344fa327c6fbb4965077de8da5a
```

## Base and reference

| Task | Submission | Run ID | Score | Complete | Passed |
| --- | --- | --- | ---: | --- | --- |
| release regressions | reference | `run-5e2af03b86264e46` | 100 | true | true |
| release regressions | base | `run-e025d2dac14d4946` | 10 | true | false |
| live-server regressions | reference | `run-81752c04438e439b` | 100 | true | true |
| live-server regressions | base | `run-bb5e05ed2ba34e7f` | 10 | true | false |
| door/economy regressions | reference | `run-49edbbe3232b447c` | 100 | true | true |
| door/economy regressions | base | `run-fbc470f8cbec462e` | 10 | true | false |

Every run completed the real headless server. References passed every private case;
the broken bases completed but failed their assertions.

## Adversarial and fairness controls

`run-3005c4bdcd294214` added an obfuscated `GLuaTest_LogTestResult` mutation hook
to the broken live-server tree. The static preflight deliberately did not match the
split hook name, so the real server and patched private runner executed. The public
hook could not mutate the authoritative snapshots: the result remained 2 pass / 9
fail, reward 0, complete true, and passed false.

`run-85f0b7a1437d4378` started from the door/economy reference and changed the
allow-list predicate to accept everyone. It completed with 10 pass / 1 fail; only
group R failed. This proves the negative authorization half of R is discriminating.

The full per-defect matrices in `per-defect-matrix.md` were produced before the
runner-collector replacement. The task assertions did not change in that replacement;
the controls above re-establish base/reference separation and directly re-run the two
paths affected by review findings.

## Superseded failure

Before the collector replacement, `run-251d75626548417a` produced a genuine 10/10
suite with reward 1 but Rhenium returned score 10 and `passed=false`, because the
plugin still expected the obsolete `occurrences` case schema. The current reference
runs above demonstrate that this integration bug is closed.
