# Minecraft Harbor task suite

This directory exports the `rhenium-minecraft-v1` repair tasks as independent
[Harbor 1.4 packages](https://www.harborframework.com/docs/tasks). Prompts,
frozen case sets, weights and pass criteria are the catalog's; the export
changes none of them.

Every task has the standard Harbor layout:

```text
task.toml
instruction.md
NOTES.md                          # maintenance: upstream bug, design, fairness review
environment/Dockerfile            # generated: JDK 21 + warmed Gradle/Maven cache, no server
environment/plugin/               # vendored upstream tree at base_commit (starter)
tests/Dockerfile                  # generated: FROM the pinned Paper verifier base image
tests/test.sh, tests/verify.py    # copies of harness/{test.sh,verify.py}
tests/task.json                   # frozen build spec and case sets (equal to the catalog)
tests/starter/                    # mirror of environment/plugin; frozen paths are restored from it
tests/suite/*.java                # hidden GcbHarness grader suite
solution/solve.sh                 # oracle control: copies solution/after over /app/plugin
solution/after/                   # upstream fix, only the changed files
validation/case-contracts.tsv     # case -> exam clause mapping (target/preserved/sentinel)
validation/controls.md            # acceptance-gate record on the real server
```

The evaluated agent receives the starter in an image that has a JDK and the
repository's dependency cache but no Paper server, no harness and no suite; it
can compile and run the upstream unit tests, nothing more. After the agent
phase Harbor builds `tests/` into a separate networkless verifier container.
`environment_mode = "separate"` and the `[verifier]` section of `task.toml`
declare that boundary.

## Verification boundary

`tests/verify.py` is the only scorer. It:

1. validates the verifier environment (server jar, `versions/`, `libraries/`,
   harness jar, frozen files) and the submission shape (no symlinks, no compiled
   artifacts outside build directories, required files present);
2. copies `/submission/plugin` to `/app/plugin` and restores every frozen path
   from `tests/starter`, so a submission cannot change the build files or the
   upstream tests;
3. builds offline with the repository's own Gradle or Maven (or the trusted
   `javac-build.sh` for synthetic tasks) and checks that the artifact's
   `plugin.yml` names the expected plugin;
4. runs the upstream JUnit suite offline and compares the observed test ids with
   the frozen `unitCases`;
5. compiles the hidden grader suite against the server classpath, the harness
   and the candidate jar, starts the real Paper server with the candidate,
   GcbHarness and the grader, and requires exactly one `MINECRAFT_RESULT`
   envelope whose nonce and case-name set match the frozen `serverCases`;
6. writes `/logs/verifier/{result.json,reward.txt}`; the reward is 1 only when
   every layer was observed and every case passed.

Missing layers, unexpected or duplicated case names, a forged or absent envelope
and a build that does not produce the named plugin all fail closed with reward 0
and `complete: false`.

## Materialization

`scripts/materialize.py` regenerates every generated file from `catalog.json`,
`exams/` and `harness/`; re-running it on a clean tree must produce no diff.
`scripts/validate-task.sh <task> <out>` runs the `nop` and `oracle` controls
through the Harbor packages; `scripts/validate-all.sh <out>` runs them for
every task and records the summary.
