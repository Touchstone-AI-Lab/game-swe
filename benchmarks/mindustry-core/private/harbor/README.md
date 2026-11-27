# Mindustry Harbor task suite

This directory exports the `rhenium-mindustry-v2` repair tasks as independent
[Harbor 1.4 packages](https://www.harborframework.com/docs/tasks). Prompts, frozen case
sets, weights and pass criteria are the catalog's; the export changes none of them.

Every task has the standard Harbor layout:

```text
task.toml
instruction.md
NOTES.md                          # maintenance: upstream fixes, defects, suite design
environment/Dockerfile            # generated: JDK 17, no server
environment/mindustry/            # vendored v159.7 game sources with the defects (starter)
tests/Dockerfile                  # generated: FROM the pinned Mindustry verifier base image
tests/test.sh, tests/verify.py    # copies of harness/{test.sh,verify.py}
tests/task.json                   # frozen build spec and case set (equal to the catalog)
tests/suite/rhenium/mindustry/grader/TaskSuite.java  # hidden grader suite
solution/solve.sh                 # oracle control: copies solution/after over /app/mindustry
solution/after/                   # the upstream fix, only the changed files
validation/case-contracts.tsv     # case -> role (sentinel/target/preserved) and public report
validation/runs.md                # acceptance record on the real server
```

The evaluated agent receives the starter in an image that has a JDK but no Mindustry
server, no harness and no suite. After the agent phase Harbor builds `tests/` into a
separate networkless verifier container; `environment_mode = "separate"` and the
`[verifier]` section of `task.toml` declare that boundary.

## Verification boundary

`tests/verify.py` is the only scorer. It:

1. validates the verifier environment (server jar, packaged grader plugin, tools) and the
   submission shape (no symlinks, VCS metadata or compiled artifacts, size limits);
2. copies `/submission/mindustry` to `/app/mindustry` and compiles every Java file below
   the frozen source roots, plus the annotation definitions, with `javac --release 17`
   against the pinned `server-release.jar`;
3. starts the real dedicated server with the compiled classes ahead of the jar and the
   trusted harness plugin (packaged with the hidden suite when the image was built) in
   `config/mods`, with stdin closed and no network;
4. accepts exactly one `MINDUSTRY_RESULT` line carrying the run's nonce, whose case set
   equals the frozen `serverCases`, and writes `result.json` and `reward.txt`.

Everything fails closed: a build failure, a server timeout, a missing or duplicated
result line or an unexpected case set make the run incomplete, never a pass.

## Regenerating

After changing `catalog.json`, an exam, a suite or the harness templates run

```sh
python benchmarks/mindustry-core/private/harbor/scripts/materialize.py
```

and re-prepare the runtime (`rhenium runtime prepare mindustry/mindustry-159.7`); the
runtime artifact records a fingerprint of every task's `tests/` directory and stops
verifying when one changes.
