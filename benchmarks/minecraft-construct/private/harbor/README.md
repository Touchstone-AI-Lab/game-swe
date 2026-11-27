# Minecraft construct Harbor task suite

This directory exports the `rhenium-minecraft-construct-v1` construct tasks as independent
[Harbor 1.4 packages](https://www.harborframework.com/docs/tasks). Prompts, frozen case sets,
weights and pass criteria are the catalog's; the export changes none of them.

```text
task.toml                         # task_kind = "construct", from_scratch = true
instruction.md                    # construct header + exams/<task>.md
NOTES.md                          # maintenance: design, live-server notes, fairness review
environment/Dockerfile            # generated: JDK 21, pinned Maven 3.9.11, warmed paper-api cache
environment/plugin/               # the skeleton: frozen pom.xml, minimal plugin.yml, empty main class
tests/Dockerfile                  # generated: FROM the pinned Paper verifier base image
tests/test.sh, tests/verify.py    # copies of harness/{test.sh,verify.py}
tests/task.json                   # frozen build spec and case set (equal to the catalog)
tests/starter/                    # mirror of the skeleton; pom.xml is restored from it
tests/suite/*.java                # hidden GcbHarness grader suite
solution/solve.sh                 # oracle control: copies solution/after over /app/plugin
solution/after/                   # the complete reference plugin
validation/case-contracts.tsv     # case -> exam requirement
validation/controls.md            # acceptance record on the real server
```

The agent image has JDK 21, Maven 3.9.11 and the skeleton's dependency cache (the Paper API),
so an agent can run `mvn -o -q -DskipTests package` but has no Paper server, harness or suite.
The verifier (`tests/verify.py`, identical to the repair packs') restores `pom.xml`, removes any
`src/test`, builds offline, checks that the jar names the expected plugin, and runs the hidden
suite on the real server, requiring exactly one `MINECRAFT_RESULT` envelope with the run's
nonce and the frozen case set. The skeleton itself builds and enables, so an unchanged
workspace is a complete, failing run (score 10: the build layer), not an incomplete one.

`scripts/materialize.py` regenerates every generated file from `catalog.json`, `exams/` and
`harness/`; re-running it on a clean tree produces no diff. The pack-level record of the
acceptance runs is `validation/README.md`.
