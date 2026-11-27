#!/bin/bash
# note (luojiaxuan): one isolated model attempt; usage: run_attempt.sh <out-dir> <task> <variant> <model-id> <rep>
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
out=$1 task=$2 variant=$3 model=$4 rep=$5
short=$(echo "$model" | sed -E 's/claude-//; s/-[0-9]{8}$//')
run="${task#stardew-automate-}.${variant}.${short}.r${rep}"
ws="$out/attempts/$run"
pristine="$out/pristine/$run"
mkdir -p "$out/logs"
python3 "$HERE/materialize.py" "$task" "$variant" "$ws"
rm -rf "$pristine"; mkdir -p "$pristine"; cp -a "$ws/StardewMods" "$pristine/StardewMods"
SYS="You are the model under test in a Stardew Valley SMAPI mod repair benchmark. Work only in the supplied C# workspace and implement the authored task contract. Do not inspect or search for upstream fixes, benchmark internals, private tests, reference solutions, or prior results. The private evaluator will compile the submission and run assertions in the pinned real game without network access."
PROMPT="Complete the task below.

$(cat "$ws/EXAM.md")

Use your file tools to inspect and edit the current workspace. This workspace has no shell, build toolchain, or game install, so you cannot compile or run anything. When the implementation is complete, stop and list the files you changed."
start=$(date -u +%s)
( cd "$ws" && timeout 3600 claude -p --restricted --strict-mcp-config \
    --tools "Read,Glob,Grep,Edit,Write" --permission-mode acceptEdits \
    --model "$model" --append-system-prompt "$SYS" \
    --output-format stream-json --verbose "$PROMPT" ) > "$out/logs/$run.jsonl" 2> "$out/logs/$run.err"
code=$?
end=$(date -u +%s)
( cd "$out" && diff -ru "pristine/$run/StardewMods" "attempts/$run/StardewMods" ) > "$out/logs/$run.diff"
echo "$run exit=$code wall=$((end-start))s" | tee -a "$out/logs/_runs.txt"
