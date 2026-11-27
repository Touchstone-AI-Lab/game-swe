# Validation record

Per-task records are in `../<task-id>/validation/runs.md` (starter and three reference
runs) and in `../../study-controls/<task-id>/NOTES.md` (E0 controls). Every task must pass
all of these gates on the real Mindustry v159.7 dedicated server, through
`rhenium run mindustry/mindustry-core/<task-id>` with the prepared
`mindustry/mindustry-159.7` runtime, before it enters `catalog.json`:

| Control | Expectation |
| --- | --- |
| starter | complete, not passed; exactly the target cases fail |
| reference (`solution/after`) | complete, passed, 100, three runs with identical case outcomes |
| alternative | an independently written repair also scores 100 |
| target-negative | a plausible partial repair fails only target case(s) |
| compat-negative | a repair that breaks a preserved behaviour fails exactly preserved case(s) and no target |

All five tasks met every gate on 2026-09-24 (Linux x86_64 host with Docker); the run IDs
are in the per-task records and in `docs/games/mindustry.md`.

## Official-download runtime control, 2026-10-31

The runtime moved from the `local-files` snapshot to the `official-download` provider. Runs used
the Lab Linux x86_64 host (Docker 29.8.1, containerd image store), from commit `ac5d446f` in an isolated Hub state, not the operator Hub.

- `rhenium auth login official-download` created the empty session.
- `rhenium runtime prepare mindustry/mindustry-159.7` requested
  `https://github.com/Anuken/Mindustry/releases/download/v159.7/server-release.jar`. It followed
  GitHub's redirect to the declared `release-assets.githubusercontent.com` and verified the jar
  (19,158,443 bytes, SHA-256 `e41289c3…2ab`).
- The first attempt was stopped deliberately during an image build. The retry reused the verified
  download cache without a request, then built and verified the base and all five verifier
  images. Artifact identity:
  `sha256:5cf2e2b60860f7d06a1dc82197a6f59211390b2ccea58762a55f07a968fc291c`.

Controls through `rhenium run mindustry/mindustry-core/<task> <submission> --profile full`:

| Task | Control | Run | Result |
| --- | --- | --- | --- |
| `server-console-regressions` | starter, unchanged `environment/mindustry` | `run-8368f148bb53422a` | complete, failed, 10/100; 6/10 server cases; fails exactly the four target cases (`pause on and pause off set the requested state`, `host without a map while shuffling is off keeps the console working`, `pardon lets a kicked player connect again`, `player records survive a server restart`) |
| `server-console-regressions` | reference, starter plus `solution/after` | `run-0679c6701ee14afc` | complete, passed, 100/100; 10/10 server cases |

The other four tasks' verifier images were built and label-verified, but no control was run on
them under this runtime.
