# Validation record

Per-task acceptance gates are recorded in `../<task-id>/validation/controls.md`.
Every task must pass all of them on the real Paper 1.21.11 build 132 server
before it enters `catalog.json`:

| Control | Expectation |
| --- | --- |
| starter (`nop`) | complete, not passed; only the mapped target cases fail |
| reference (`oracle`, `solution/after`) | complete, passed, 100, three consecutive runs |
| alternative | an independently written fix also scores 100 |
| target-negative | a plausible wrong fix fails only its mapped target case(s) |
| compat-negative | a fix that breaks a preserved behaviour fails exactly that contract case |
| tamper | editing a frozen build file or upstream test has no effect on the verdict |

Summary table for catalog 0.1.0 (filled by `scripts/validate-all.sh`; historical):

| Task | nop reward | oracle reward | Date |
| --- | --- | --- | --- |
| multiverse-core-case-insensitive-world-names | 0 (40/100, two target cases) | 1 (100/100 ×3) | 2026-09-22 |
| chatty-bad-channel-disables-plugin | 0 (two target cases) | 1 (100/100 ×3) | 2026-09-22 |
| betterteams-help-page-bounds | 0 (three target cases) | 1 (100/100 ×3) | 2026-09-22 |
| prometheus-exporter-players-total-main-thread | 0 (two target cases) | 1 (100/100 ×3) | 2026-09-22 |
| chatty-reload-ignores-chat-commands | 0 (two target cases) | 1 (100/100 ×3) | 2026-09-22 |
| multiverse-core-world-exists-by-key | 0 (four target cases) | 1 (100/100 ×3) | 2026-09-22 |
| betterteams-description-tag-injection | 0 (two target cases) | 1 (100/100 ×3) | 2026-09-22 |
| chatty-reload-leaks-threads | 0 (three target cases) | 1 (100/100 ×3) | 2026-09-22 |
| chatty-failed-migration-dead-plugin | 0 (three target cases) | 1 (100/100 ×3) | 2026-09-22 |
| chatty-v2-migration-null-spy-format | 0 (four target cases) | 1 (100/100 ×3) | 2026-09-22 |

## Official-download runtime control, 2026-10-31

The runtime moved from the `local-files` snapshot to the `official-download` provider. Runs used
the Lab Linux x86_64 host (Docker 29.8.1, containerd image store), from commit `ac5d446f` in an isolated Hub state, not the operator Hub.

- `rhenium auth login official-download` created the empty session.
- The first `rhenium runtime prepare minecraft/paper-1.21.11-132` downloaded
  `paper-1.21.11-132.jar` from `fill-data.papermc.io` and verified it (54,846,016 bytes, SHA-256
  `5ffef465…fba`). It then stopped with exit status 2, `action_required`, kind `accept-eula`, and
  named the acceptance record `packs/minecraft/core/eula.txt` in that Hub state. The builder built
  nothing.
- As the operator step, `eula=true` was written to that record. The second `prepare` reused the
  verified download cache without a request, built the base and all ten verifier images, and
  verified them. Artifact identity:
  `sha256:8eecb64b5c5d8313b9bb8fcf925fdcbd80dd4b790a075229d391052b09ba3690`.

Controls through `rhenium run minecraft/core/<task> <submission> --profile full`:

| Task | Control | Run | Result |
| --- | --- | --- | --- |
| `prometheus-exporter-players-total-main-thread` | starter (`nop`), unchanged `environment/plugin` | `run-00435484f47f44dc` | complete, failed, 40/100: build and 27/27 unit cases pass, 3/5 server cases; fails exactly the two target cases (`players_total is collected without the main thread`, `scrape completes while the main thread is busy`) |
| `prometheus-exporter-players-total-main-thread` | reference, starter plus `solution/after` | `run-8c3cfb42f3944092` | complete, passed, 100/100: 27/27 unit and 5/5 server cases |

The other nine tasks' verifier images were built and label-verified, but no control was run on
them under this runtime.

## Catalog 0.2.0, 2026-11-02

0.2.0 rewrote every exam, extended every server suite (90 cases instead of 64) and merged
a second upstream fix into `chatty-v2-migration-null-spy-format`, so none of the results
above applies to it. Offline, on Lab, the starter, the reference and every control in
`../../study-controls/<task>/manifest.tsv` of all ten tasks build with the frozen paths
restored and pass their frozen upstream unit cases (except the compat-negative of
`multiverse-core-case-insensitive-world-names`, which fails its two case-insensitivity tests
by design), and every suite compiles against GcbHarness, paper-api and the built jar.

The real-server gates of 0.2.0 have not been run: the operator's EULA acceptance record
was not present in Lab's Hub state, so no 0.2.0 verifier image exists. Each task's
`validation/controls.md` lists what remains.
