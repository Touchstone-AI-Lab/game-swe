#!/usr/bin/env bash
# Evaluate every pending submission of this kit once, plus one retry after an
# incomplete run. Results already present are never overwritten.
set -uo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 /path/to/rhenium" >&2
  exit 2
fi
rhenium=$1
kit=$(cd "$(dirname "$0")" && pwd)

python3 - "$kit/manifest.json" <<'PY' |
import json, sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
for item in manifest["attempts"]:
    print("\t".join((item["attemptId"], item["task"], item["submission"], manifest["profile"])))
PY
while IFS=$'\t' read -r attempt task submission profile; do
  for index in 1 2; do
    output="$kit/attempts/$attempt/result-$index.json"
    if [ ! -e "$output" ]; then
      echo "[$attempt] run $index: $task"
      # Exit status 1 only means the submission did not pass; keep its output.
      "$rhenium" run "$task" "$kit/$submission" --profile "$profile" > "$output" < /dev/null || true
    fi
    if python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("result",{}).get("complete") is True else 1)' "$output" 2>/dev/null; then
      break
    fi
  done
done
echo "all attempts processed"
