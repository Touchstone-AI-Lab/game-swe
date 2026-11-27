# Deferred evaluation kit: study `{{STUDY_ID}}`

This kit holds model submissions that were generated on the study host but cannot be
graded there, because their game engine runs only on another host. For example,
Palworld's dedicated server under UE4SS needs Windows. Your job is to run the
repository's own evaluator once on each submission and send back what it prints. You
do not score or judge anything yourself: the study host classifies every result with
the same rules it uses for its own evaluations.

## What is in the kit

- `manifest.json`: the study id, its configuration digest, the repository snapshot
  (`{{SNAPSHOT}}`), and one entry per attempt (attempt id, task key, submission path).
  Do not edit it.
- `attempts/<attempt-id>/submission/`: the frozen submission. Do not edit it.
- `evaluate.ps1` (Windows PowerShell) and `evaluate.sh` (bash): these run the evaluator
  on every submission that has no result yet.

## Prepare the evaluation host

1. Check out the repository at exactly `{{SNAPSHOT}}`:
   `git clone <repository> && git checkout {{SNAPSHOT}}`. A different commit can
   change the evaluator, and its results cannot be combined with the study.
2. Install Rhenium with the plugin for the game, as the repository README describes.
   For example, `uv sync --locked --all-packages` puts `rhenium` into `.venv`.
3. Install and configure the game's engine exactly as `docs/games/<game>.md` in that
   checkout says. For Palworld, follow `docs/games/palworld.md`, "Runtime setup": a
   throwaway dedicated server from SteamCMD app 2394010, RE-UE4SS extracted into
   `Pal/Binaries/Win64/`, and `RHENIUM_PLUGIN_PALWORLD_ROOT` pointing at the server
   directory. Record the server build and the UE4SS version you used; you will report
   them.
4. Check that the evaluator reaches the engine. Pick one task from the manifest and
   run `rhenium run <task> <any submission directory> --profile full`. Its JSON output
   must contain a `headless-server` check that actually ran.

## Run the evaluations

From the kit directory, on Windows:

```powershell
.\evaluate.ps1 -Rhenium C:\path\to\repo\.venv\Scripts\rhenium.exe
```

or with bash:

```sh
./evaluate.sh /path/to/repo/.venv/bin/rhenium
```

For each attempt, the script runs:

```
rhenium run <task> attempts/<id>/submission --profile full
```

It saves the printed JSON as `attempts/<id>/result-1.json`. If that run is not complete
(`result.complete` is not `true`), the script runs the evaluator once more on the same
submission and saves `result-2.json`. It never runs a third time.

The scripts skip attempts that already have a result, so an interrupted batch can be
restarted safely. Evaluate one submission at a time: the evaluator uses a single server
installation.

## Rules

- Do not modify submissions, the manifest or the repository checkout.
- Do not rerun an attempt whose `result-1.json` is complete, and never delete a result
  file to try again. The study's protocol allows at most one retry, and only after an
  incomplete run.
- If the engine setup was wrong for a whole batch (for example, the server was missing),
  stop and report it instead of rerunning.

## Send back

Zip the whole kit directory, including all `result-*.json` files, and send it with:

- the evaluation host description (OS, CPU);
- the game server build and mod-loader version;
- the date of the runs;
- anything unusual you saw.

The study host imports the results with:

```
rhenium-study e1 import-evaluations --config <study.toml> --kit <kit> --host "<host description>"
```

The import checks that the kit belongs to this study configuration, and it scores only
attempts that are still pending.
